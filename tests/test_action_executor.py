"""Tests for the action executor send step."""

from __future__ import annotations

from unittest.mock import patch

from agents.action_executor import action_executor_node
from graph.state import AgentState, DealInfo


def _state_with_draft() -> AgentState:
    deal = DealInfo(
        deal_id="deal-1",
        company_name="Acme",
        contact_email="buyer@example.com",
    )
    return AgentState(
        stalled_deals=[deal],
        drafted_emails={
            "deal-1": {
                "subject": "Quick follow-up",
                "body": "Hi Alex,\n\nChecking in.\n\nBest,\nRep",
            }
        },
    )


def test_executor_skips_when_followup_note_exists() -> None:
    state = _state_with_draft()
    with patch("agents.action_executor.deal_has_followup_note", return_value=True):
        update = action_executor_node(state)

    assert update["actions_taken"] == ["skipped_duplicate:deal-1"]
    assert "errors" not in update


def test_executor_sends_when_no_prior_note() -> None:
    state = _state_with_draft()
    with (
        patch("agents.action_executor.deal_has_followup_note", return_value=False),
        patch("agents.action_executor.send_email", return_value="gmail-abc") as send,
        patch("agents.action_executor.add_deal_note", return_value="note-xyz") as note,
    ):
        update = action_executor_node(state)

    send.assert_called_once()
    note.assert_called_once()
    assert update["actions_taken"] == [
        "sent_email:deal-1",
        "crm_note:deal-1:note-xyz",
    ]
