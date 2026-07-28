"""Inquiry helpers: the small state machine that keeps a dialogue converging.

These functions find the currently open inquiry, apply an update to the inquiry
list in place, and render the prompt fragments that tell the model what has
already been asked or answered. They are the mechanics behind Watchtower's rule
that a question is asked at most twice and never re-asked once resolved.
"""

from __future__ import annotations

from collections.abc import Sequence

from watchtower.domain.inquiry import Inquiry, InquiryStatus


def _first_open(inquiries: Sequence[Inquiry]) -> Inquiry | None:
    for inquiry in inquiries:
        if inquiry.status is InquiryStatus.OPEN:
            return inquiry
    return None


def _replace_inquiry(items: list[Inquiry], inquiry: Inquiry) -> None:
    for index, existing in enumerate(items):
        if existing.id == inquiry.id:
            items[index] = inquiry
            return


def _open_inquiry_block(open_inquiry: Inquiry | None, *, can_reask: bool) -> str:
    if open_inquiry is None:
        return ""
    text = (
        f'You are waiting on an earlier question you asked: "{open_inquiry.original_question}" '
        f'(to resolve: "{open_inquiry.uncertainty_being_resolved}"). First decide whether the '
        "founder's latest message answers it.\n"
    )
    if not can_reask:
        text += (
            "You have already pressed this question. Do not ask it again - reason with what you "
            "have and give your best recommendation.\n"
        )
    return text + "\n"


def _answered_block(answered: Sequence[Inquiry]) -> str:
    if not answered:
        return ""
    body = "\n".join(
        f'- "{inquiry.uncertainty_being_resolved}": {inquiry.founder_answer}'
        for inquiry in answered
    )
    return "Already resolved (never ask about these again; use the answers):\n" + body + "\n\n"
