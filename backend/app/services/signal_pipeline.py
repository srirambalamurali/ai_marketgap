import time
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.signals import Signal, SignalBatch
from app.models.collected_document import CollectedDocument
from app.services.signal_deduplicator import SignalDeduplicator
from app.services.source_scoring import score_signal
from app.services.signal_quality_service import quality_service
from app.services.monitoring import pipeline_monitor
from app.rag.chunking import DocumentChunker
from app.repositories.market_signal_repository import (
    create as db_create_signal,
    get_by_source_id,
    count as db_count_signals,
)
from app.utils.logging import get_logger

logger = get_logger("services.signal_pipeline")


class PipelineMetrics:
    def __init__(self) -> None:
        self.signals_collected: int = 0
        self.signals_ingested: int = 0
        self.duplicates_removed: int = 0
        self.quality_filtered: int = 0
        self.vectors_created: int = 0
        self.collection_latency_ms: float = 0
        self.ingestion_latency_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "signals_collected": self.signals_collected,
            "signals_ingested": self.signals_ingested,
            "duplicates_removed": self.duplicates_removed,
            "quality_filtered": self.quality_filtered,
            "vectors_created": self.vectors_created,
            "collection_latency_ms": round(self.collection_latency_ms, 2),
            "ingestion_latency_ms": round(self.ingestion_latency_ms, 2),
        }


class SignalIngestionPipeline:
    def __init__(self) -> None:
        self.deduplicator = SignalDeduplicator()
        self.chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
        self.vector_service = _LazyVectorService()
        self.metrics = PipelineMetrics()

    async def process_batch(
        self, batch: SignalBatch, session: AsyncSession
    ) -> dict:
        start = time.time()
        self.metrics = PipelineMetrics()
        self.metrics.signals_collected = batch.count

        existing_signals = []
        for signal in batch.signals:
            existing = await get_by_source_id(session, signal.source, signal.source_id)
            if existing:
                existing_signals.append(signal)

        unique_signals = self.deduplicator.deduplicate(batch.signals, existing_signals)
        self.metrics.duplicates_removed = batch.count - len(unique_signals)

        quality_signals = quality_service.filter_signals(unique_signals)
        self.metrics.quality_filtered = len(unique_signals) - len(quality_signals)

        ingested = 0
        for signal in quality_signals:
            document = CollectedDocument(
                source=signal.source,
                source_type=signal.source_type,
                title=signal.title,
                content=signal.content or signal.title,
                url=signal.url,
                created_at=signal.created_at or signal.collected_at,
                metadata_json={
                    **signal.metadata,
                    "source_id": signal.source_id,
                    "source": signal.source,
                    "source_type": signal.source_type,
                },
            )
            session.add(document)
            score = score_signal(signal.model_dump())
            quality = signal.metadata.get("quality_score", 0.5)
            final_score = (score + quality) / 2
            await db_create_signal(session, **{
                "source": signal.source,
                "source_type": signal.source_type,
                "source_id": signal.source_id,
                "title": signal.title,
                "content": signal.content,
                "url": signal.url,
                "author": signal.author,
                "score": signal.score,
                "comments_count": signal.comments_count,
                "credibility_score": round(final_score, 3),
                "created_at": signal.created_at or signal.collected_at,
                "collected_at": signal.collected_at,
                "extra_metadata": signal.metadata,
            })
            ingested += 1

        await session.flush()

        self.metrics.signals_ingested = ingested
        self.metrics.collection_latency_ms = (time.time() - start) * 1000

        ingest_start = time.time()
        vectors = 0
        for signal in quality_signals:
            text = f"{signal.title}\n{signal.content}"
            chunks = self.chunker.chunk_document(
                doc_id=str(signal.id),
                content=text,
                metadata={
                    "source": signal.source,
                    "source_type": signal.source_type,
                    "url": signal.url,
                    "collected_at": signal.collected_at.isoformat() if signal.collected_at else None,
                    "source_id": signal.source_id,
                },
            )
            if chunks:
                try:
                    await self.vector_service.ingest_documents(chunks)
                    vectors += len(chunks)
                except Exception as exc:
                    logger.warning("Vector ingestion skipped for %s: %s", signal.source_id, exc)

        self.metrics.vectors_created = vectors
        self.metrics.ingestion_latency_ms = (time.time() - ingest_start) * 1000

        logger.info(
            "Pipeline: collected=%d, deduped=%d, quality_filtered=%d, ingested=%d, vectors=%d",
            self.metrics.signals_collected,
            self.metrics.duplicates_removed,
            self.metrics.quality_filtered,
            self.metrics.signals_ingested,
            self.metrics.vectors_created,
        )

        pipeline_monitor.record_pipeline_run(batch.source, self.metrics.to_dict(), success=True)

        return self.metrics.to_dict()


class _LazyVectorService:
    def __init__(self) -> None:
        self._service = None

    def _get(self):
        if self._service is None:
            from app.rag.ingestion import VectorIngestionService

            self._service = VectorIngestionService()
        return self._service

    async def ingest_documents(self, chunks):
        return await self._get().ingest_documents(chunks)
