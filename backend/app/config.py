from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    redis_url: str
    session_encryption_key: str
    linkedin_session_id: str = "primary"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env.local", env_file_encoding="utf-8", extra="ignore")

    @field_validator("linkedin_session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in cleaned):
            raise ValueError("LINKEDIN_SESSION_ID may only contain letters, numbers, hyphens, and underscores.")
        return cleaned

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
