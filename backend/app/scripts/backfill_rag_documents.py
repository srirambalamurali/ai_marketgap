from __future__ import annotations

import asyncio
from collections.abc import Iterable

from sqlalchemy import select

from app.database.postgres import async_session
from app.models.collected_document import CollectedDocument
from app.models.embedding_status import DocumentEmbeddingStatus, EmbeddingStatus
from app.models.market_signal import MarketSignal
from app.rag.chunking import DocumentChunker
from app.rag.ingestion import VectorIngestionService
from app.utils.logging import get_logger

logger = get_logger("scripts.backfill_rag_documents")


async def backfill_documents() -> int:
    async with async_session() as session:
        signals_result = await session.execute(
            select(MarketSignal).order_by(MarketSignal.collected_at.asc())
        )
        signals = signals_result.scalars().all()

        existing_docs_result = await session.execute(select(CollectedDocument.url))
        existing_urls = {url for url in existing_docs_result.scalars().all() if url}

        created = 0
        for signal in signals:
            if signal.url and signal.url in existing_urls:
                continue

            doc = CollectedDocument(
                source=signal.source,
                source_type=signal.source_type,
                title=signal.title,
                content=signal.content or signal.title,
                url=signal.url or f"{signal.source}://{signal.source_id}",
                created_at=signal.created_at or signal.collected_at,
                metadata_json={
                    **(signal.extra_metadata or {}),
                    "source_id": signal.source_id,
                    "source": signal.source,
                    "source_type": signal.source_type,
                    "signal_id": str(signal.id),
                },
            )
            session.add(doc)
            created += 1
            if signal.url:
                existing_urls.add(signal.url)

        await session.commit()
        logger.info("Backfilled %d collected_documents rows from market_signals", created)
        return created


async def ingest_documents() -> int:
    async with async_session() as session:
        doc_result = await session.execute(
            select(CollectedDocument).where(
                ~CollectedDocument.id.in_(
                    select(DocumentEmbeddingStatus.document_id).where(
                        DocumentEmbeddingStatus.embedding_status == EmbeddingStatus.COMPLETED
                    )
                )
            )
        )
        documents = doc_result.scalars().all()

        if not documents:
            logger.info("No documents require ingestion")
            return 0

        chunker = DocumentChunker()
        ingestion = VectorIngestionService()
        total_chunks = 0

        for doc in documents:
            chunks = chunker.chunk_document(
                doc_id=str(doc.id),
                content=doc.content,
                metadata={
                    "source": doc.source,
                    "source_type": doc.source_type,
                    "url": doc.url,
                    "collected_at": doc.created_at.isoformat() if doc.created_at else None,
                },
            )
            if not chunks:
                continue

            status = DocumentEmbeddingStatus(
                document_id=doc.id,
                embedding_status=EmbeddingStatus.PROCESSING,
            )
            session.add(status)
            total_chunks += len(chunks)

            try:
                await ingestion.ingest_documents(chunks)
                status.embedding_status = EmbeddingStatus.COMPLETED
            except Exception as exc:
                logger.warning("Vector ingestion skipped for %s: %s", doc.id, exc)
                status.embedding_status = EmbeddingStatus.FAILED

        await session.commit()
        logger.info("Ingested %d chunks from %d documents into ChromaDB", total_chunks, len(documents))
        return total_chunks


async def main() -> None:
    created = await backfill_documents()
    ingested = await ingest_documents()
    logger.info("Backfill complete. documents_created=%d chunks_ingested=%d", created, ingested)


if __name__ == "__main__":
    asyncio.run(main())
