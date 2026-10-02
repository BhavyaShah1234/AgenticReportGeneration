"""Application settings, read from environment / backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_secret_key: str = "dev-insecure-change-me"  # JWT signing + Fernet key derivation
    database_url: str = f"sqlite:///{BACKEND_DIR / 'storage' / 'app.db'}"
    storage_dir: Path = BACKEND_DIR / "storage"
    frontend_url: str = "http://localhost:3000"
    jwt_ttl_hours: int = 24

    # Optional server-side Snowflake connection, used by tests and seeding only.
    # End users connect their own account through the UI.
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_api: str | None = None  # Programmatic Access Token
    snowflake_warehouse: str | None = None
    snowflake_role: str | None = None
    snowflake_default_table: str = "DEMO_CORP.SALES.V_SALES"
    query_timeout_s: int = 60
    max_rows: int = 5000

    # Open-source LLM behind an OpenAI-compatible endpoint (Ollama by default, Voyager via config).
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen3:8b"
    llm_api_key: str = "ollama"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    (s.storage_dir / "reports").mkdir(parents=True, exist_ok=True)
    return s
