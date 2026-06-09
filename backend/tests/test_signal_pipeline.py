import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.signal_pipeline import SignalIngestionPipeline, PipelineMetrics
from app.schemas.signals import Signal, SignalBatch


@pytest.fixture
def pipeline():
    return SignalIngestionPipeline()


def test_pipeline_metrics_default():
    m = PipelineMetrics()
    assert m.signals_collected == 0
    assert m.signals_ingested == 0
    assert m.duplicates_removed == 0
    assert m.vectors_created == 0
    assert m.collection_latency_ms == 0
    assert m.ingestion_latency_ms == 0


def test_pipeline_metrics_to_dict():
    m = PipelineMetrics()
    m.signals_collected = 10
    m.signals_ingested = 8
    m.duplicates_removed = 2
    d = m.to_dict()
    assert d["signals_collected"] == 10
    assert d["signals_ingested"] == 8
    assert d["duplicates_removed"] == 2


@pytest.mark.asyncio
async def test_process_batch(pipeline):
    batch = SignalBatch(
        source="github",
        signals=[
            Signal(source="github", source_id="1", title="Test1", content="Content1"),
            Signal(source="github", source_id="2", title="Test2", content="Content2"),
        ],
    )
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("app.services.signal_pipeline.get_by_source_id", new_callable=AsyncMock, return_value=None):
        with patch("app.services.signal_pipeline.db_create_signal", new_callable=AsyncMock):
            with patch.object(pipeline.vector_service, "ingest_documents", new_callable=AsyncMock, return_value=2):
                result = await pipeline.process_batch(batch, mock_session)

    assert result["signals_collected"] == 2
    assert result["signals_ingested"] == 2


@pytest.mark.asyncio
async def test_process_batch_deduplicates(pipeline):
    batch = SignalBatch(
        source="github",
        signals=[
            Signal(source="github", source_id="1", title="Same Title", content="C1"),
            Signal(source="github", source_id="2", title="Same Title", content="C2"),
        ],
    )
    mock_session = AsyncMock()

    with patch("app.services.signal_pipeline.get_by_source_id", new_callable=AsyncMock, return_value=None):
        with patch("app.services.signal_pipeline.db_create_signal", new_callable=AsyncMock):
            with patch.object(pipeline.vector_service, "ingest_documents", new_callable=AsyncMock, return_value=1):
                result = await pipeline.process_batch(batch, mock_session)

    assert result["signals_collected"] == 2
    assert result["duplicates_removed"] >= 1


@pytest.mark.asyncio
async def test_process_batch_empty(pipeline):
    batch = SignalBatch(source="github", signals=[])
    mock_session = AsyncMock()
    result = await pipeline.process_batch(batch, mock_session)
    assert result["signals_collected"] == 0
    assert result["signals_ingested"] == 0


@pytest.mark.asyncio
async def test_process_batch_skips_existing(pipeline):
    batch = SignalBatch(
        source="github",
        signals=[Signal(source="github", source_id="1", title="Existing", content="C")],
    )
    mock_session = AsyncMock()

    mock_existing = MagicMock()
    with patch("app.services.signal_pipeline.get_by_source_id", new_callable=AsyncMock, return_value=mock_existing):
        with patch("app.services.signal_pipeline.db_create_signal", new_callable=AsyncMock):
            with patch.object(pipeline.vector_service, "ingest_documents", new_callable=AsyncMock, return_value=0):
                result = await pipeline.process_batch(batch, mock_session)

    assert result["signals_ingested"] == 0
