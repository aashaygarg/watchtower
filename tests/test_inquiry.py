"""Regression tests for Inquiry: clarification conversations must converge.

Conversation Engine V3 asked a clarification, got an answer, and then asked the
same conceptual question again. These tests pin the fix: once an inquiry is
answered it is never re-asked, and an unanswered one is rephrased at most once
before the engine converges.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from watchtower.cognition import think
from watchtower.domain.inquiry import InquiryStatus
from watchtower.domain.messages import Message
from watchtower.startup.models import Startup, StartupId
from watchtower.startup.workspace import StartupWorkspace


def _workspace() -> StartupWorkspace:
    return StartupWorkspace(
        root=Path("."),
        startup=Startup(id=StartupId("healthos"), name="HealthOS", mission="Make health simple."),
        vision="",
    )


class ScriptedLLM:
    """Replays a queue of canned turns and records each prompt it received."""

    def __init__(self, responses: Sequence[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.messages: list[Message] = []
        self.prompts: list[str] = []

    def complete(self, messages: Sequence[Message]) -> str:
        return "ok"

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        self.messages = list(messages)
        self.prompts.append(messages[-1].content)
        return self._responses.pop(0)


_ASK_TURN = {
    "understanding": "You want to decide whether to build memory next.",
    "challenged_assumption": "You may be assuming memory is the bottleneck.",
    "current_thinking": "Validation likely matters more than memory.",
    "biggest_uncertainty": "Whether any user has actually asked for memory.",
    "question": "Have users actually requested memory?",
    "recommendation": "",
}

_RESOLVE_TURN = {
    "understanding": "No user has asked for memory.",
    "challenged_assumption": "You assumed users want memory.",
    "current_thinking": "With no demand, validation comes first.",
    "biggest_uncertainty": "",
    "question": "",
    "resolves_open_inquiry": True,
    "founder_answer": "None.",
    "resolution_summary": "No users have requested memory.",
    "recommendation": "Do not build memory yet; validate demand first.",
    "confidence_level": "High",
    "confidence_reasons": [{"supports": False, "text": "No user has asked for memory."}],
}


def test_answered_inquiry_is_not_reasked() -> None:
    """Regression 1: answer the inquiry, and it must never be asked again."""
    llm = ScriptedLLM([_ASK_TURN, _RESOLVE_TURN])
    ws = _workspace()

    first = think("Should I build memory?", workspace=ws, llm=llm)
    assert first.question == "Have users actually requested memory?"
    assert len(first.inquiries) == 1
    assert first.inquiries[0].status is InquiryStatus.OPEN

    second = think(
        "None.",
        workspace=ws,
        llm=llm,
        history=["You: Should I build memory?", "Watchtower: (asked...)"],
        inquiries=first.inquiries,
    )

    # The inquiry is resolved and carries the founder's answer.
    assert second.resolved_inquiry_id == first.inquiries[0].id
    assert len(second.inquiries) == 1
    resolved = second.inquiries[0]
    assert resolved.status is InquiryStatus.ANSWERED
    assert resolved.founder_answer == "None."

    # The engine converged to a recommendation and asked nothing further.
    assert second.recommendation
    assert second.question == ""


def test_answered_inquiries_are_shown_as_do_not_reask() -> None:
    """The resolved uncertainty is surfaced to the model as off-limits."""
    llm = ScriptedLLM([_ASK_TURN, _RESOLVE_TURN, _RESOLVE_TURN])
    ws = _workspace()

    first = think("Should I build memory?", workspace=ws, llm=llm)
    second = think("None.", workspace=ws, llm=llm, inquiries=first.inquiries)
    # The resolved inquiry only appears as "already resolved" on the next turn,
    # since resolution happens during the turn it is answered.
    think("What about onboarding?", workspace=ws, llm=llm, inquiries=second.inquiries)

    prompt = llm.prompts[-1]
    assert "Already resolved" in prompt
    assert "None." in prompt


_REPHRASE_TURN = {
    "understanding": "Your answer was ambiguous.",
    "challenged_assumption": "",
    "current_thinking": "I still need a clearer signal.",
    "biggest_uncertainty": "Whether users have asked for memory.",
    "question": "To be clear, has any specific user asked for memory?",
    "resolves_open_inquiry": False,
    "recommendation": "",
}

_STILL_UNCLEAR_TURN = {
    "understanding": "Still ambiguous.",
    "challenged_assumption": "",
    "current_thinking": "I will reason with what I have.",
    "biggest_uncertainty": "Whether users have asked for memory.",
    "question": "Has any specific user asked for memory?",
    "resolves_open_inquiry": False,
    "recommendation": "Validate demand before building memory.",
    "confidence_level": "Low",
    "confidence_reasons": [{"supports": False, "text": "Demand is still unclear."}],
}


def test_ambiguous_answer_allows_one_followup_then_converges() -> None:
    """Regression 2: at most one rephrase, then the loop must end."""
    llm = ScriptedLLM([_ASK_TURN, _REPHRASE_TURN, _STILL_UNCLEAR_TURN])
    ws = _workspace()

    first = think("Should I build memory?", workspace=ws, llm=llm)
    original = first.inquiries[0]
    assert original.times_asked == 1

    # Ambiguous answer -> one allowed rephrase, same inquiry, times_asked bumps.
    second = think("Maybe, not sure.", workspace=ws, llm=llm, inquiries=first.inquiries)
    assert len(second.inquiries) == 1
    rephrased = second.inquiries[0]
    assert rephrased.id == original.id
    assert rephrased.status is InquiryStatus.OPEN
    assert rephrased.times_asked == 2
    assert second.question

    # Still ambiguous -> rephrase budget spent: abandon and stop asking.
    third = think("Still unclear.", workspace=ws, llm=llm, inquiries=second.inquiries)
    assert third.question == ""
    assert len(third.inquiries) == 1
    assert third.inquiries[0].status is InquiryStatus.ABANDONED
    assert third.recommendation
