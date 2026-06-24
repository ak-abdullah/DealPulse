"""Compiled LangGraph workflow for the sales pipeline agent."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.action_executor import action_executor_node
from agents.company_researcher import company_researcher_node
from agents.email_writer import email_writer_node
from agents.error_handler import error_handler_node
from agents.pipeline_monitor import pipeline_monitor_node
from graph.router import (
    route_after_error_handler,
    route_after_monitor,
    route_after_researcher,
    route_after_writer,
)
from graph.state import AgentState


def build_graph():
    """Week 3 graph: monitor → research → write → send → error handler."""
    graph = StateGraph(AgentState)

    graph.add_node("monitor", pipeline_monitor_node)
    graph.add_node("researcher", company_researcher_node)
    graph.add_node("writer", email_writer_node)
    graph.add_node("executor", action_executor_node)
    graph.add_node("error_handler", error_handler_node)

    graph.add_edge(START, "monitor")
    graph.add_conditional_edges(
        "monitor",
        route_after_monitor,
        {
            "continue": "researcher",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "researcher",
        route_after_researcher,
        {
            "continue": "researcher",
            "write": "writer",
        },
    )
    graph.add_conditional_edges(
        "writer",
        route_after_writer,
        {
            "continue": "writer",
            "execute": "executor",
        },
    )
    graph.add_edge("executor", "error_handler")
    graph.add_conditional_edges(
        "error_handler",
        route_after_error_handler,
        {
            "continue": "executor",
            "end": END,
        },
    )

    return graph.compile()


pipeline = build_graph()
