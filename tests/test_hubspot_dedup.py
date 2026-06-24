"""Tests for HubSpot follow-up note deduplication."""

from __future__ import annotations

from tools.hubspot import (
    FOLLOWUP_NOTE_MARKER,
    add_deal_note,
    deal_has_followup_note,
)


def test_deal_has_no_followup_note_initially() -> None:
    assert deal_has_followup_note("deal-100") is False


def test_add_deal_note_registers_followup_in_mock_mode() -> None:
    note = (
        f"{FOLLOWUP_NOTE_MARKER} to buyer@example.com (Acme).\n"
        "Subject: Checking in\n"
        "Gmail message id: mock-1"
    )
    add_deal_note("deal-100", note)
    assert deal_has_followup_note("deal-100") is True


def test_unrelated_note_does_not_count_as_followup() -> None:
    add_deal_note("deal-200", "Rep called the contact manually.")
    assert deal_has_followup_note("deal-200") is False
