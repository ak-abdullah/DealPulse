"""Conditional routing for LangGraph edges."""

from __future__ import annotations

from typing import Literal

from graph.state import AgentState


def route_after_monitor(state: AgentState) -> Literal["continue", "end"]:
    """Route to researcher when stalled deals exist, otherwise stop."""
    stalled = (
        state.stalled_deals
        if isinstance(state, AgentState)
        else state.get("stalled_deals", [])
    )
    return "continue" if stalled else "end"


def route_after_researcher(state: AgentState) -> Literal["continue", "write"]:
    """Research one deal per visit; loop until all deals are researched."""
    if isinstance(state, AgentState):
        idx = state.current_deal_index
        total = len(state.stalled_deals)
    else:
        idx = state.get("current_deal_index", 0)
        total = len(state.get("stalled_deals", []))
    return "continue" if idx < total else "write"


def route_after_writer(state: AgentState) -> Literal["continue", "execute"]:
    """Draft one email per visit; loop until all deals have drafts."""
    if isinstance(state, AgentState):
        drafted = len(state.drafted_emails)
        total = len(state.stalled_deals)
    else:
        drafted = len(state.get("drafted_emails", {}))
        total = len(state.get("stalled_deals", []))
    return "continue" if drafted < total else "execute"


def executor_progress(state: AgentState | dict) -> int:
    """How many deals have completed an executor pass (send, skip, or fail)."""
    if isinstance(state, AgentState):
        actions = state.actions_taken
    else:
        actions = state.get("actions_taken", [])
    prefixes = (
        "sent_email:",
        "skipped_send:",
        "skipped_duplicate:",
        "failed_send:",
    )
    return sum(1 for action in actions if action.startswith(prefixes))


def _executor_progress(state: AgentState | dict) -> int:
    return executor_progress(state)


def route_after_executor(state: AgentState) -> Literal["continue", "end"]:
    """Execute one deal per visit; loop until all deals are handled."""
    if isinstance(state, AgentState):
        total = len(state.stalled_deals)
    else:
        total = len(state.get("stalled_deals", []))
    return "continue" if executor_progress(state) < total else "end"


def route_after_error_handler(state: AgentState) -> Literal["continue", "end"]:
    """After central error review, loop executor or finish the run."""
    return route_after_executor(state)