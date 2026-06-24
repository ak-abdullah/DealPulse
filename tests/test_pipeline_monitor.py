"""Tests for monitor node with HubSpot mock fixtures."""

from __future__ import annotations

from agents.pipeline_monitor import pipeline_monitor_node
from graph.state import AgentState


def test_monitor_returns_mock_deals() -> None:
    update = pipeline_monitor_node(AgentState())

    assert update["should_continue"] is True
    assert len(update["stalled_deals"]) == 1
    assert update["stalled_deals"][0].deal_id == "mock-deal-1"
    assert update["current_deal_index"] == 0
    assert update["drafted_emails"] == {}
