"""
Application settings — loaded from environment variables / .env file.
"""
import json
import logging
from typing import List
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────────────────────
    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "rootlensai"

    # ── Groq AI ───────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""

    # ── File upload ───────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["*"]

    # ── Feature flags ─────────────────────────────────────────────────────────
    ENABLE_MOCK_TELEMETRY: bool = True
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Normalise ALLOWED_ORIGINS: handle JSON-encoded list in env var
if len(settings.ALLOWED_ORIGINS) == 1:
    val = settings.ALLOWED_ORIGINS[0]
    if val.startswith("["):
        try:
            settings.ALLOWED_ORIGINS = json.loads(val)
        except Exception:
            pass

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
