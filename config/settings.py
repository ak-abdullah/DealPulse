"""Application settings loaded from environment (.env) and defaults."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hubspot_api_key: str = Field(
        ...,
        description="HubSpot private app access token",
    )
    stale_deal_days: int = Field(
        default=7,
        ge=1,
        description="Deals with no activity longer than this are treated as stalled",
    )

    groq_api_key: str = Field(
        ...,
        description="Groq API key for LLM research and writing",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat model id",
    )


settings = Settings()
