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


settings = Settings()