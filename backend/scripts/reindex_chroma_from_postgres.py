from __future__ import annotations

import asyncio

from app.scripts.backfill_rag_documents import backfill_documents, ingest_documents
from app.utils.logging import setup_logging, get_logger

logger = get_logger("scripts.reindex_chroma_from_postgres")


async def main() -> None:
    setup_logging()
    created = await backfill_documents()
    ingested = await ingest_documents()
    logger.info(
        "Reindex complete. documents_created=%d chunks_ingested=%d",
        created,
        ingested,
    )


if __name__ == "__main__":
    asyncio.run(main())
