"""CLI entry point: run the Week 1 pipeline (monitor stalled deals)."""

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
    LOGGER.info("Starting DealPulse pipeline (Week 1: monitor only)")

    final = _coerce_state(pipeline.invoke(AgentState()))
    stalled = final.stalled_deals

    print(f"Stalled deals: {len(stalled)}")
    for deal in stalled:
        print(_format_deal(deal))

    if final.errors:
        print("Errors:")
        for message in final.errors:
            print(f"  ! {message}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run())
