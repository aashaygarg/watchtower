"""Tests for the sectioned system-prompt assembly.

These pin the invariant that the prompt is a single system string composed from
named sections - so a section can be edited deliberately, but the composition
itself never silently reshapes the prompt.
"""

from __future__ import annotations

from watchtower.kernel.prompt import _DIALOGUE_SYSTEM, _SECTIONS, _assemble


def test_prompt_is_the_sections_joined_by_blank_lines() -> None:
    assert "\n\n".join(text for _, text in _SECTIONS) == _DIALOGUE_SYSTEM
    assert _assemble(_SECTIONS) == _DIALOGUE_SYSTEM


def test_prompt_has_the_expected_named_sections() -> None:
    assert [name for name, _ in _SECTIONS] == [
        "persona",
        "grounding",
        "convergence",
        "turn_structure",
        "response_contract",
    ]


def test_prompt_boundaries_and_shape_are_preserved() -> None:
    # Single system prompt, one pass: opens in persona, closes with the JSON contract.
    assert _DIALOGUE_SYSTEM.startswith("You are Watchtower,")
    assert _DIALOGUE_SYSTEM.endswith("'goal', 'duration', 'success', 'failure').")
    assert "Every turn:\n1. State" in _DIALOGUE_SYSTEM
    # No section carries leading/trailing blank padding that would shift the prompt.
    for _, text in _SECTIONS:
        assert text == text.strip()
