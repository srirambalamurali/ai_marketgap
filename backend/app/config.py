from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus


class Settings(BaseSettings):
    app_name: str = "AI Market Gap Discovery Engine"
    debug: bool = False
    demo_mode: bool = False
    api_v1_prefix: str = "/api/v1"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "marketgap"
    postgres_ssl: bool = False

    @property
    def database_url(self) -> str:
        password = quote_plus(self.postgres_password or "")
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ChromaDB
    chroma_url: str | None = None
    chroma_host: str = "127.0.0.1"
    chroma_port: int = 8001
    chroma_collection: str = "market_gap_documents"
    chroma_knowledge_collection: str = "market_gap_knowledge"

    # GitHub
    github_token: str = ""

    # Reddit OAuth2 (free for read-only)
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "MarketGapResearch/1.0"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Monitoring
    enable_monitoring: bool = True
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Timeouts
    request_timeout_seconds: int = 60
    source_timeout_seconds: int = 60
    generation_timeout_seconds: int = 120

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7

    model_config = {
        "env_file": (".env", ".env.local"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
