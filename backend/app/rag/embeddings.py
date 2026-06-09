import logging

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    before_sleep_log,
)
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger("rag.embeddings")

EMBEDDING_MODEL = "models/gemini-embedding-001"
BATCH_SIZE = 20


def _is_retryable_embedding_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "resource_exhausted" in message or "quota" in message or "429" in message:
        return False
    return True


class EmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=settings.gemini_api_key,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable_embedding_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def embed_text(self, text: str) -> list[float]:
        result = await self._embeddings.aembed_query(text)
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable_embedding_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            logger.info(
                "Embedding batch %d/%d (size=%d)",
                i // BATCH_SIZE + 1,
                (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE,
                len(batch),
            )
            batch_embeddings = await self._embeddings.aembed_documents(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings
