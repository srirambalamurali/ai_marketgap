from sqlalchemy import text
from app.config import get_settings
from app.utils.logging import get_logger
from app.database.postgres import engine
from app.database.repair import ensure_market_signals_schema
from app.services.chromadb_service import get_chroma_service

logger = get_logger("startup.validation")


async def validate_postgres() -> None:
    settings = get_settings()
    logger.info("Validating PostgreSQL connection to %s:%s/%s ...",
                settings.postgres_host, settings.postgres_port, settings.postgres_db)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        schema = await ensure_market_signals_schema()
        if schema["missing_after_repair"]:
            raise RuntimeError(
                f"market_signals schema still missing columns: {schema['missing_after_repair']}"
            )
        logger.info("PostgreSQL connection OK")
    except Exception as exc:
        raise RuntimeError(
            f"Cannot connect to PostgreSQL at {settings.postgres_host}:{settings.postgres_port}"
            f"/{settings.postgres_db}: {exc}"
        ) from exc


async def validate_chroma() -> dict:
    settings = get_settings()
    logger.info(
        "Validating ChromaDB connection at %s:%s ...",
        settings.chroma_host,
        settings.chroma_port,
    )
    service = get_chroma_service()
    health = await service.health()
    if health["chromadb_connected"]:
        logger.info("ChromaDB connection OK")
    else:
        logger.warning(
            "ChromaDB unavailable at %s:%s (%s)",
            settings.chroma_host,
            settings.chroma_port,
            health.get("error") or "unknown error",
        )
    return health


def validate_gemini_key() -> None:
    settings = get_settings()
    logger.info("Validating Gemini API key ...")
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )
    logger.info("Gemini API key present (length=%d)", len(settings.gemini_api_key))


def validate_github_token() -> None:
    settings = get_settings()
    logger.info("Validating GitHub token ...")
    if not settings.github_token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Add it to your .env file."
        )
    logger.info("GitHub token present (length=%d)", len(settings.github_token))


def validate_reddit_credentials() -> None:
    settings = get_settings()
    missing = []
    if not settings.reddit_client_id:
        missing.append("REDDIT_CLIENT_ID")
    if not settings.reddit_client_secret:
        missing.append("REDDIT_CLIENT_SECRET")
    if not settings.reddit_user_agent:
        missing.append("REDDIT_USER_AGENT")
    if missing:
        raise RuntimeError(
            "Missing Reddit OAuth configuration: " + ", ".join(missing)
            + ". Set them in backend/.env or export them before starting the app."
        )
    logger.info("Reddit OAuth configuration present (user_agent=%s)", settings.reddit_user_agent)
