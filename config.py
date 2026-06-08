"""Application configuration via pydantic-settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env early so GCP clients can find credentials at import time
load_dotenv()

_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if _creds_path and not os.path.isabs(_creds_path):
    resolved = Path(_creds_path).resolve()
    if resolved.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved)

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "local"

    # Gemini via Vertex AI
    gcp_project_id: str = Field(default="")
    google_vertex_location: str = Field(default="us-central1")

    # Local DB (used when env=local)
    db_host: str = "localhost"
    db_port: int = 5432
    db_database: str = "insafdaar_db"
    db_user: str = "postgres"
    db_password: str = ""

    # Production (used when env=production)
    express_internal_url: str = ""
    internal_api_key: str = ""

    # RAG
    rag_api_url: str = ""

    # Service
    port: int = 8001
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
