"""CLI entry point: monitor stalled deals and research each with Groq."""

from __future__ import annotations

import logging
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from graph.pipeline import pipeline
from graph.state import AgentState, DealInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)

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


def run() -> int:
    LOGGER.info("Starting Sentinel pipeline (Week 2: monitor + research + write)")
    final = _coerce_state(pipeline.invoke(AgentState()))
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
            print(f"Subject: {email.get('subject', '')}")
            print(email.get("body", ""))

    if final.errors:
        print("\nErrors:")
        for message in final.errors:
            print(f"  ! {message}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run())
