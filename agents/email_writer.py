"""Email writer node: Groq drafts a follow-up from research."""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config.settings import settings
from graph.state import AgentState, DealInfo
from prompts.writer_prompt import WRITER_SYSTEM_PROMPT

LOGGER = logging.getLogger(__name__)


def _llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.4,
    )


def _deal_context(deal: DealInfo) -> str:
    return (
        f"Company: {deal.company_name or '(unknown)'}\n"
        f"Contact: {deal.contact_name or '(unknown)'} <{deal.contact_email or 'n/a'}>\n"
        f"Deal value: ${deal.deal_value:,.0f}\n"
        f"Stage: {deal.current_stage or '(unknown)'}\n"
        f"Days since activity: {deal.days_since_activity}\n"
    )


def _parse_email(raw: str) -> dict[str, str]:
    text = raw.strip()
    subject = "Following up"
    body = text

    subject_match = re.search(r"^SUBJECT:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    body_match = re.search(r"^BODY:\s*\n?", text, re.MULTILINE | re.IGNORECASE)

    if subject_match:
        subject = subject_match.group(1).strip()
    if body_match:
        body = text[body_match.end() :].strip()
    elif subject_match:
        body = re.sub(
            r"^SUBJECT:\s*.+$",
            "",
            text,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        ).strip()

    return {"subject": subject, "body": body}


def _draft_email(deal: DealInfo, report: str, score: str) -> dict[str, str]:
    llm = _llm()
    user_content = (
        f"{_deal_context(deal)}\n"
        f"Deal score: {score}\n"
        f"--- Research brief ---\n"
        f"{report or '(no research available)'}"
    )
    response = llm.invoke(
        [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    return _parse_email(str(response.content))


def email_writer_node(state: AgentState) -> dict[str, Any]:
    """Draft one email (next deal without a draft yet)."""
    idx = len(state.drafted_emails)
    deals = state.stalled_deals

    if idx >= len(deals):
        LOGGER.info("Writer: no remaining deals (index=%s)", idx)
        return {}

    deal = deals[idx]
    company = deal.company_name or deal.deal_id
    report = state.research_reports.get(deal.deal_id, "")
    score = state.deal_scores.get(deal.deal_id, "warm")

    LOGGER.info("Drafting email for deal %s (%s)", deal.deal_id, company)

    drafts = dict(state.drafted_emails)
    update: dict[str, Any] = {"drafted_emails": drafts}

    try:
        email = _draft_email(deal, report, score)
        drafts[deal.deal_id] = email
        update["actions_taken"] = [f"drafted_email:{deal.deal_id}"]
        LOGGER.info("Drafted email for %s: %s", company, email["subject"])
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Email draft failed for deal %s", deal.deal_id)
        drafts[deal.deal_id] = {"subject": "", "body": ""}
        update["errors"] = [f"email_writer:{deal.deal_id}: {exc}"]

    return update
