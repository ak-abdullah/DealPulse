"""Shared pipeline runner for manual CLI and scheduled worker."""

from __future__ import annotations

import logging
import os
from typing import Any

from graph.pipeline import pipeline
from graph.state import AgentState, DealInfo
from observability.langsmith_config import invoke_config, tracing_enabled

LOGGER = logging.getLogger(__name__)


def _coerce_state(final: Any) -> AgentState:
    if isinstance(final, AgentState):
        return final
    return AgentState.model_validate(final)


def _format_deal(deal: DealInfo) -> str:
    company = deal.company_name or "(no company)"
    return (
        f"  - {company} | ${deal.deal_value:,.0f} | "
        f"{deal.days_since_activity}d idle | deal={deal.deal_id}"
    )


def run_pipeline(*, trigger: str = "manual") -> int:
    """
    Execute the LangGraph pipeline once.

    Returns process exit code (0 = success, 1 = errors recorded on state).
    """
    LOGGER.info("Starting Sentinel pipeline (trigger=%s)", trigger)
    if tracing_enabled():
        project = os.getenv("LANGCHAIN_PROJECT", "default")
        LOGGER.info("LangSmith tracing is on (project=%s)", project)

    final = _coerce_state(
        pipeline.invoke(AgentState(), config=invoke_config(trigger=trigger))
    )
    stalled = final.stalled_deals

    print(f"Stalled deals: {len(stalled)}")
    for deal in stalled:
        print(_format_deal(deal))

    if final.research_reports:
        print("\nResearch reports:")
        for deal in stalled:
            report = final.research_reports.get(deal.deal_id)
            score = final.deal_scores.get(deal.deal_id, "n/a")
            company = deal.company_name or deal.deal_id
            print(f"\n--- {company} [{score}] ---")
            if report:
                print(report)
            else:
                print("  (no report)")

    if final.drafted_emails:
        print("\nDrafted emails:")
        for deal in stalled:
            email = final.drafted_emails.get(deal.deal_id)
            company = deal.company_name or deal.deal_id
            if not email:
                print(f"\n--- {company} ---\n  (no draft)")
                continue
            print(f"\n--- {company} ---")
            print(f"To: {deal.contact_email or '(no email)'}")
            print(f"Subject: {email.get('subject', '')}")
            print(email.get("body", ""))

    if final.actions_taken:
        print("\nActions taken:")
        for action in final.actions_taken:
            print(f"  - {action}")

    if final.errors:
        print("\nErrors:")
        for message in final.errors:
            print(f"  ! {message}")
        LOGGER.warning("Pipeline finished with %s error(s)", len(final.errors))
        return 1

    LOGGER.info("Pipeline finished successfully")
    return 0
