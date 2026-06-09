import os
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8001")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "test-token")

from app.config import get_settings, Settings

get_settings.cache_clear()

_test_settings = Settings(
    postgres_user="test",
    postgres_password="test",
    postgres_db="test_db",
    gemini_api_key="test-key",
    github_token="test-token",
)

import app.config as config_module
config_module.get_settings = lambda: _test_settings

_patches = [
    patch("app.database.validation.validate_postgres", new_callable=AsyncMock),
    patch("app.database.validation.validate_chroma"),
    patch("app.database.validation.validate_gemini_key"),
    patch("app.database.validation.validate_github_token"),
    patch("app.scheduler.jobs.start_scheduler"),
    patch("app.scheduler.jobs.shutdown_scheduler"),
    patch("app.main.validate_postgres", new_callable=AsyncMock),
    patch("app.main.validate_chroma"),
    patch("app.main.validate_gemini_key"),
    patch("app.main.validate_github_token"),
    patch("app.main.start_scheduler"),
    patch("app.main.shutdown_scheduler"),
    patch("app.main._create_tables", new_callable=AsyncMock),
]
for p in _patches:
    p.start()
