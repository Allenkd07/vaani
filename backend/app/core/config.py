from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Loaded from environment variables, then backend/.env. Fields without a default are required."""

    # Absolute path, so .env is found from any working directory.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str

    stt_provider: str
    gemini_api_key: str
    gemini_model: str
    stt_mode: str
    # Comma-separated BCP-47 codes; empty = automatic detection.
    stt_languages: str = ""

    # Comma-separated; empty = same origin only (FastAPI serves the frontend, Vite proxies in dev).
    cors_origins: str = ""

    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"

    @field_validator("database_url")
    @classmethod
    def normalize_db_url(cls, value: str) -> str:
        # Render provides "postgres://"; SQLAlchemy needs the psycopg driver in the scheme.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @property
    def language_codes(self) -> list[str]:
        return [code.strip() for code in self.stt_languages.split(",") if code.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # populated from the environment
