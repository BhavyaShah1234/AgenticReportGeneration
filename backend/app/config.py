"""Application settings, read from environment / backend/.env."""

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SECRET = "dev-insecure-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_secret_key: str = DEFAULT_SECRET  # JWT signing + Fernet key derivation
    database_url: str = f"sqlite:///{BACKEND_DIR / 'storage' / 'app.db'}"
    storage_dir: Path = BACKEND_DIR / "storage"
    frontend_url: str = "http://localhost:3000"
    jwt_ttl_hours: int = 24
    # Public demo: new companies created at signup get the server's demo Snowflake
    # connection and the demo report formats, so judges can use the app immediately.
    demo_mode: bool = False

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
    # LLM_PROVIDER=cortex: run on Snowflake Cortex open-weight models through the company's own
    # Snowflake connection; LLM_FALLBACK keeps the OpenAI-compatible endpoint above as a backup.
    llm_provider: Literal["openai", "cortex"] = "openai"
    cortex_model: str = "llama3.1-70b"
    llm_fallback: bool = True


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    (s.storage_dir / "reports").mkdir(parents=True, exist_ok=True)
    if s.app_secret_key == DEFAULT_SECRET:
        # No APP_SECRET_KEY given: use a persistent per-install secret so the server, the seed
        # and restarts all agree (it encrypts stored Snowflake tokens and signs sessions).
        secret_file = s.storage_dir / ".app_secret"
        if not secret_file.exists():
            secret_file.write_text(secrets.token_urlsafe(48))
            secret_file.chmod(0o600)
        s.app_secret_key = secret_file.read_text().strip()
    return s
