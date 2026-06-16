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
        ge=0,
        description="Deals idle at least this many days are stalled (0 = all open deals, for testing)",
    )

    groq_api_key: str = Field(
        ...,
        description="Groq API key for LLM research and writing",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat model id",
    )

    gmail_credentials_path: str = Field(
        default="credentials.json",
        description="Path to Gmail OAuth client secrets JSON",
    )
    gmail_token_path: str = Field(
        default="token.json",
        description="Path to saved Gmail OAuth token JSON",
    )
    sender_email: str = Field(
        default="",
        description="Gmail address emails are sent from",
    )
    sender_name: str = Field(
        default="",
        description="Display name on outbound emails",
    )


settings = Settings()
