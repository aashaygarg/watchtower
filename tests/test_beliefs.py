"""Tests for the belief engine: model, store, relevance, and evolution."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from typer.testing import CliRunner
from watchtower.adapters.persistence import JsonBeliefStore
from watchtower.domain.beliefs import (
    Belief,
    BeliefAction,
    BeliefCategory,
    BeliefConfidence,
    BeliefStatus,
    BeliefUpdate,
)
from watchtower.domain.messages import Message
from watchtower.interface import app
from watchtower.kernel.worldview import (
    apply_updates,
    format_for_prompt,
    select_relevant,
    update_beliefs,
)
from watchtower.kernel.worldview.consolidation import ConsolidationAction, consolidate

runner = CliRunner()


class FakeLLM:
    """Returns a canned worldview-update response."""

    def __init__(self, updates: list[dict[str, Any]]) -> None:
        self._updates = updates

    def complete(self, messages: Sequence[Message]) -> str:
        return "ok"

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return {"updates": self._updates}


def _belief(**kwargs: Any) -> Belief:
    defaults: dict[str, Any] = {
        "id": "b1",
        "title": "Memory is the next bottleneck",
        "category": BeliefCategory.PRODUCT,
        "confidence": BeliefConfidence.MEDIUM,
        "created_at": datetime(2026, 7, 28, 9, 0, 0),
        "updated_at": datetime(2026, 7, 28, 9, 0, 0),
    }
    defaults.update(kwargs)
    return Belief(**defaults)


def test_json_store_roundtrip(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    belief = _belief(
        supporting_evidence=("we keep re-explaining context",),
        assumptions=("users want continuity",),
    )
    store.upsert(belief)

    reloaded = JsonBeliefStore(tmp_path / "beliefs.json")
    loaded = reloaded.get("b1")

    assert loaded is not None
    assert loaded.title == belief.title
    assert loaded.category is BeliefCategory.PRODUCT
    assert loaded.confidence is BeliefConfidence.MEDIUM
    assert loaded.supporting_evidence == ("we keep re-explaining context",)
    assert loaded.created_at == belief.created_at


def test_select_relevant_uses_lexical_overlap() -> None:
    memory = _belief(
        id="b1", title="Memory is the next bottleneck", category=BeliefCategory.PRODUCT
    )
    pricing = _belief(id="b2", title="Founders will pay for pricing insights")
    dead = _belief(id="b3", title="Memory matters", status=BeliefStatus.DISPROVEN)

    relevant = select_relevant([memory, pricing, dead], "should we build memory next?")

    assert memory in relevant
    assert pricing not in relevant  # unrelated
    assert dead not in relevant  # disproven beliefs are never injected


def test_weaken_matches_the_spec_example(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1", confidence=BeliefConfidence.MEDIUM))

    llm = FakeLLM(
        [
            {
                "action": "weaken",
                "belief_id": "b1",
                "confidence": "low",
                "evidence": ["Interviewed ten users; none requested memory."],
                "rationale": "Recent evidence contradicts the previous hypothesis.",
            }
        ]
    )
    conversation = ["You: I interviewed ten users.", "You: None requested memory."]
    applied = apply_updates(store, update_beliefs(conversation, store.all(), llm))

    belief = store.get("b1")
    assert belief is not None
    assert belief.confidence is BeliefConfidence.LOW
    assert belief.status is BeliefStatus.WEAKENING
    assert belief.revision == 2
    assert any("none requested memory" in e.lower() for e in belief.contradicting_evidence)
    # The change is traceable in the log.
    assert applied and applied[0].action is BeliefAction.WEAKEN
    assert store.history()[-1].rationale.startswith("Recent evidence")


def test_supersede_preserves_history(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1", title="Growth comes from virality"))

    llm = FakeLLM(
        [
            {
                "action": "supersede",
                "belief_id": "b1",
                "title": "Growth comes from paid acquisition",
                "category": "strategy",
                "confidence": "medium",
                "rationale": "Virality never materialized; paid channels convert.",
            }
        ]
    )
    apply_updates(store, update_beliefs(["You: paid ads convert"], store.all(), llm))

    old = store.get("b1")
    assert old is not None
    assert old.status is BeliefStatus.SUPERSEDED  # not deleted
    assert old.superseded_by is not None
    replacement = store.get(old.superseded_by)
    assert replacement is not None
    assert replacement.title == "Growth comes from paid acquisition"
    assert replacement.status is BeliefStatus.ACTIVE


def test_create_and_disprove(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    create = FakeLLM(
        [
            {
                "action": "create",
                "title": "Founders return without prompting",
                "category": "customer",
                "confidence": "low",
                "evidence": ["Two founders came back unprompted."],
                "rationale": "New signal worth tracking.",
            }
        ]
    )
    apply_updates(store, update_beliefs(["You: they came back"], store.all(), create))
    created = store.all()[0]
    assert created.title == "Founders return without prompting"
    assert created.confidence is BeliefConfidence.LOW

    disprove = FakeLLM(
        [{"action": "disprove", "belief_id": created.id, "rationale": "It was a fluke."}]
    )
    apply_updates(store, update_beliefs(["You: it was a fluke"], store.all(), disprove))
    assert store.get(created.id).status is BeliefStatus.DISPROVEN


def test_no_change_is_recorded_but_changes_nothing(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1"))
    llm = FakeLLM([{"action": "no_change", "rationale": "Nothing new."}])

    apply_updates(store, update_beliefs(["You: hi"], store.all(), llm))

    assert store.get("b1").revision == 1  # unchanged
    assert store.history()[-1].action is BeliefAction.NO_CHANGE  # still traceable


def test_format_for_prompt() -> None:
    belief = _belief(confidence=BeliefConfidence.HIGH, description="we re-explain context daily")
    lines = format_for_prompt([belief])
    assert lines == ("[high] Memory is the next bottleneck - we re-explain context daily",)


def test_beliefs_command_lists_current_beliefs(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / ".watchtower" / "beliefs.json")
    store.upsert(_belief(id="b1", title="Retention is the real risk"))

    result = runner.invoke(app, ["beliefs", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "Retention is the real risk" in result.stdout


def test_disprove_of_high_belief_by_low_evidence_is_downgraded_to_weaken(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1", confidence=BeliefConfidence.HIGH, status=BeliefStatus.ACTIVE))

    applied = apply_updates(
        store,
        [
            BeliefUpdate(
                action=BeliefAction.DISPROVE,
                belief_id="b1",
                confidence=BeliefConfidence.LOW,
                evidence=("one weak counter-signal",),
            )
        ],
    )

    assert store.get("b1").status is BeliefStatus.WEAKENING  # never destroyed outright
    assert applied[0].action is BeliefAction.WEAKEN  # the logged change reflects the downgrade


def test_supersede_of_high_belief_by_low_evidence_creates_no_replacement(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1", confidence=BeliefConfidence.HIGH))
    before = len(store.all())

    apply_updates(
        store,
        [
            BeliefUpdate(
                action=BeliefAction.SUPERSEDE,
                belief_id="b1",
                title="A shinier replacement",
                description="...",
                confidence=BeliefConfidence.LOW,
                evidence=("weak hunch",),
            )
        ],
    )

    assert len(store.all()) == before  # no replacement belief was spawned
    weakened = store.get("b1")
    assert weakened.status is BeliefStatus.WEAKENING
    assert weakened.superseded_by is None


def test_disprove_of_high_belief_by_high_evidence_still_disproves(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1", confidence=BeliefConfidence.HIGH))

    apply_updates(
        store,
        [
            BeliefUpdate(
                action=BeliefAction.DISPROVE,
                belief_id="b1",
                confidence=BeliefConfidence.HIGH,
                evidence=("a strong, direct contradiction",),
            )
        ],
    )

    assert store.get("b1").status is BeliefStatus.DISPROVEN  # strong evidence still lands


def test_disprove_of_medium_belief_by_low_evidence_still_disproves(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1", confidence=BeliefConfidence.MEDIUM))

    apply_updates(
        store,
        [
            BeliefUpdate(
                action=BeliefAction.DISPROVE,
                belief_id="b1",
                confidence=BeliefConfidence.LOW,
                evidence=("weak",),
            )
        ],
    )

    assert store.get("b1").status is BeliefStatus.DISPROVEN  # only HIGH beliefs are protected


def test_consolidate_skips_an_empty_candidate() -> None:
    assert consolidate("", "", []).action is ConsolidationAction.SKIP


def test_consolidate_creates_when_nothing_is_similar() -> None:
    memory = _belief(id="b1", title="Memory is the next bottleneck")
    decision = consolidate("Founders will pay for pricing", "", [memory])
    assert decision.action is ConsolidationAction.CREATE
    assert decision.target_id is None


def test_consolidate_merges_a_near_duplicate() -> None:
    memory = _belief(id="b1", title="Memory is the next bottleneck")
    decision = consolidate("Memory is the next bottleneck", "", [memory])
    assert decision.action is ConsolidationAction.MERGE
    assert decision.target_id == "b1"


def test_create_of_a_duplicate_merges_instead_of_duplicating(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(
        _belief(id="b1", title="Memory is the next bottleneck", confidence=BeliefConfidence.MEDIUM)
    )

    applied = apply_updates(
        store,
        [
            BeliefUpdate(
                action=BeliefAction.CREATE,
                title="Memory is the next bottleneck",
                confidence=BeliefConfidence.HIGH,
                evidence=("users keep asking for memory",),
            )
        ],
    )

    assert len(store.all()) == 1  # merged, not duplicated
    merged = store.get("b1")
    assert merged.confidence is BeliefConfidence.HIGH
    assert "users keep asking for memory" in merged.supporting_evidence
    assert merged.revision == 2
    assert applied[0].action is BeliefAction.STRENGTHEN


def test_create_of_something_new_still_creates(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    store.upsert(_belief(id="b1", title="Memory is the next bottleneck"))

    apply_updates(
        store,
        [
            BeliefUpdate(
                action=BeliefAction.CREATE,
                title="Founders will pay for pricing insights",
                confidence=BeliefConfidence.MEDIUM,
                evidence=("three asked about pricing",),
            )
        ],
    )

    assert len(store.all()) == 2  # genuinely new belief created


def test_create_with_no_content_is_skipped(tmp_path: Path) -> None:
    store = JsonBeliefStore(tmp_path / "beliefs.json")
    applied = apply_updates(
        store, [BeliefUpdate(action=BeliefAction.CREATE, title="", description="")]
    )
    assert applied == ()
    assert store.all() == ()
