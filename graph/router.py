"""Conditional routing for LangGraph edges."""

from __future__ import annotations

from typing import Literal

from graph.state import AgentState


def route_after_monitor(state: AgentState) -> Literal["continue", "end"]:
    """
    Decide what happens after the monitor node.

    Week 1: both branches point to END in ``pipeline.py``.
    Week 2+: ``continue`` will route to the researcher node.
    """
    stalled = state.stalled_deals if isinstance(state, AgentState) else state.get("stalled_deals", [])
    return "continue" if stalled else "end"
