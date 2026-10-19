"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite:///./app.db"

    # Security
    webhook_secret: str = "change-me"

    # Assessment
    assessment_base_url: str = "http://localhost:8000/assessment"

    # Email
    email_provider: str = "mock"
    email_from: str = "noreply@example.com"

    # Optional external email providers (not required for MVP)
    brevo_api_key: str = ""
    sendgrid_api_key: str = ""


settings = Settings()
