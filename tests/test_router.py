"""Tests for graph routing helpers."""

from __future__ import annotations

from graph.router import (
    executor_progress,
    route_after_error_handler,
    route_after_monitor,
    route_after_researcher,
    route_after_writer,
)
from graph.state import AgentState, DealInfo


def _deal(deal_id: str) -> DealInfo:
    return DealInfo(
        deal_id=deal_id,
        company_name="Acme",
        contact_email="buyer@example.com",
    )


def test_route_after_monitor_stops_when_no_deals() -> None:
    assert route_after_monitor(AgentState()) == "end"


def test_route_after_monitor_continues_with_deals() -> None:
    state = AgentState(stalled_deals=[_deal("d1")])
    assert route_after_monitor(state) == "continue"


def test_route_after_researcher_loops_until_index_catches_up() -> None:
    state = AgentState(stalled_deals=[_deal("d1"), _deal("d2")], current_deal_index=1)
    assert route_after_researcher(state) == "continue"

    state = AgentState(stalled_deals=[_deal("d1"), _deal("d2")], current_deal_index=2)
    assert route_after_researcher(state) == "write"


def test_route_after_writer_loops_until_all_drafts_exist() -> None:
    state = AgentState(
        stalled_deals=[_deal("d1"), _deal("d2")],
        drafted_emails={"d1": {"subject": "Hi", "body": "Body"}},
    )
    assert route_after_writer(state) == "continue"

    state = AgentState(
        stalled_deals=[_deal("d1"), _deal("d2")],
        drafted_emails={
            "d1": {"subject": "Hi", "body": "Body"},
            "d2": {"subject": "Hi", "body": "Body"},
        },
    )
    assert route_after_writer(state) == "execute"


def test_executor_progress_counts_skip_and_send_outcomes() -> None:
    state = AgentState(
        stalled_deals=[_deal("d1"), _deal("d2")],
        actions_taken=["sent_email:d1", "skipped_duplicate:d2"],
    )
    assert executor_progress(state) == 2
    assert route_after_error_handler(state) == "end"
