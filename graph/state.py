"""LangGraph shared state: validated domain models for each deal and the full run."""

from __future__ import annotations

import operator
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class DealInfo(BaseModel):
    """One opportunity the pipeline treats as stalled or actionable."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )

    deal_id: str = Field(..., min_length=1, description="HubSpot deal id")
    company_name: str = Field(default="", max_length=500)
    contact_name: str = Field(default="", max_length=500)
    contact_email: str = Field(default="", max_length=320)
    deal_value: float = Field(default=0.0, ge=0)
    current_stage: str = Field(default="", max_length=200)
    days_since_activity: int = Field(default=0, ge=0)
    last_activity_type: str = Field(default="", max_length=200)
    company_website: str | None = Field(default=None, max_length=2000)

    @classmethod
    def from_hubspot_dict(cls, row: dict[str, Any]) -> DealInfo:
        """Build from a normalized dict produced by tools.hubspot (strict boundary)."""
        return cls.model_validate(row)


class AgentState(BaseModel):
    """State passed between LangGraph nodes; partial updates merge into this model."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    run_id: str = Field(default="", max_length=64)
    triggered_at: str = Field(default="", max_length=64)

    stalled_deals: list[DealInfo] = Field(default_factory=list)
    current_deal_index: int = Field(default=0, ge=0)

    research_reports: dict[str, str] = Field(
        default_factory=dict,
        description="deal_id -> research markdown/text",
    )
    deal_scores: dict[str, str] = Field(
        default_factory=dict,
        description="deal_id -> hot | warm | cold",
    )
    drafted_emails: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="deal_id -> {subject, body}",
    )

    actions_taken: Annotated[list[str], operator.add] = Field(default_factory=list)
    errors: Annotated[list[str], operator.add] = Field(default_factory=list)

    should_continue: bool = Field(default=True)