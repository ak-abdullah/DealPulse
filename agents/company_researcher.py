"""Company researcher node: web context + Groq analysis per stalled deal."""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config.settings import settings
from graph.state import AgentState, DealInfo
from prompts.researcher_prompt import RESEARCHER_SYSTEM_PROMPT
from prompts.scorer_prompt import SCORER_SYSTEM_PROMPT
from tools.browser import fetch_company_page_text

LOGGER = logging.getLogger(__name__)

_VALID_SCORES = frozenset({"hot", "warm", "cold"})


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.2,
    )


def _deal_context(deal: DealInfo) -> str:
    return (
        f"Company: {deal.company_name or '(unknown)'}\n"
        f"Contact: {deal.contact_name or '(unknown)'} <{deal.contact_email or 'n/a'}>\n"
        f"Deal value: ${deal.deal_value:,.0f}\n"
        f"Stage: {deal.current_stage or '(unknown)'}\n"
        f"Days since activity: {deal.days_since_activity}\n"
        f"Last activity type: {deal.last_activity_type or '(unknown)'}\n"
        f"Website: {deal.company_website or '(none)'}\n"
    )


def _normalize_score(raw: str) -> str:
    token = raw.strip().lower()
    match = re.search(r"\b(hot|warm|cold)\b", token)
    if match:
        return match.group(1)
    return "warm"


def _research_deal(deal: DealInfo) -> tuple[str, str]:
    website_text = fetch_company_page_text(deal.company_website)
    llm = _llm()

    research_user = (
        f"{_deal_context(deal)}\n"
        "--- Website text ---\n"
        f"{website_text or '(no website content available)'}"
    )
    research_response = llm.invoke(
        [
            SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
            HumanMessage(content=research_user),
        ]
    )
    report = str(research_response.content).strip()

    score_response = llm.invoke(
        [
            SystemMessage(content=SCORER_SYSTEM_PROMPT),
            HumanMessage(
                content=f"{_deal_context(deal)}\n--- Research brief ---\n{report}"
            ),
        ]
    )
    score = _normalize_score(str(score_response.content))
    if score not in _VALID_SCORES:
        score = "warm"

    return report, score


def company_researcher_node(state: AgentState) -> dict[str, Any]:
    """
    Research one stalled deal (by ``current_deal_index``) and advance the index.

    Returns a partial state dict for LangGraph to merge.
    """
    idx = state.current_deal_index
    deals = state.stalled_deals

    if idx >= len(deals):
        LOGGER.info("Researcher: no remaining deals (index=%s)", idx)
        return {}

    deal = deals[idx]
    company = deal.company_name or deal.deal_id
    LOGGER.info("Researching deal %s (%s)", deal.deal_id, company)

    reports = dict(state.research_reports)
    scores = dict(state.deal_scores)
    update: dict[str, Any] = {
        "research_reports": reports,
        "deal_scores": scores,
        "current_deal_index": idx + 1,
    }

    try:
        report, score = _research_deal(deal)
        reports[deal.deal_id] = report
        scores[deal.deal_id] = score
        update["actions_taken"] = [f"researched:{deal.deal_id}:{score}"]
        LOGGER.info("Scored %s as %s", company, score)
    except Exception as exc:  # noqa: BLE001 — keep pipeline running on one bad deal
        LOGGER.exception("Research failed for deal %s", deal.deal_id)
        update["errors"] = [f"company_researcher:{deal.deal_id}: {exc}"]

    return update
