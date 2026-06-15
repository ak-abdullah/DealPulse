"""Compiled LangGraph workflow for the sales pipeline agent."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.pipeline_monitor import pipeline_monitor_node
from graph.router import route_after_monitor
from graph.state import AgentState


def build_graph():
    """
    Week 1 graph: monitor stalled deals, then stop.

    Week 2+ will route ``continue`` to researcher instead of END.
    """
    graph = StateGraph(AgentState)

    graph.add_node("monitor", pipeline_monitor_node)
    graph.add_edge(START, "monitor")
    graph.add_conditional_edges(
        "monitor",
        route_after_monitor,
        {
            "continue": END,
            "end": END,
        },
    )

    return graph.compile()


pipeline = build_graph()
