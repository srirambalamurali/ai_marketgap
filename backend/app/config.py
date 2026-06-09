from pydantic_settings import BaseSettings
from functools import lru_cache


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

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ChromaDB
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
