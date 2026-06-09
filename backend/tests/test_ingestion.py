import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.rag.schemas import DocumentChunk
from app.rag.ingestion import VectorIngestionService


@pytest.fixture
def mock_chroma():
    with patch("app.rag.ingestion.chromadb") as mock_chromadb:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.HttpClient.return_value = mock_client
        yield mock_collection


@pytest.fixture
def mock_embed():
    with patch("app.rag.ingestion.EmbeddingService") as MockCls:
        instance = MockCls.return_value
        instance.embed_batch = AsyncMock(
            return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        )
        yield instance


def _make_chunks():
    return [
        DocumentChunk(
            chunk_id="doc1_chunk_0",
            content="First chunk content",
            metadata={"source": "github", "document_id": "doc1"},
        ),
        DocumentChunk(
            chunk_id="doc1_chunk_1",
            content="Second chunk content",
            metadata={"source": "github", "document_id": "doc1"},
        ),
    ]


@pytest.mark.asyncio
async def test_ingest_document(mock_chroma, mock_embed):
    service = VectorIngestionService()
    count = await service.ingest_document(_make_chunks())
    assert count == 2
    mock_chroma.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_empty(mock_chroma, mock_embed):
    service = VectorIngestionService()
    count = await service.ingest_document([])
    assert count == 0
    mock_chroma.upsert.assert_not_called()


def test_delete_document(mock_chroma, mock_embed):
    mock_chroma.get.return_value = {"ids": ["chunk1", "chunk2"]}
    service = VectorIngestionService()
    count = service.delete_document("doc1")
    assert count == 2
    mock_chroma.delete.assert_called_once_with(ids=["chunk1", "chunk2"])


def test_delete_document_not_found(mock_chroma, mock_embed):
    mock_chroma.get.return_value = {"ids": []}
    service = VectorIngestionService()
    count = service.delete_document("nonexistent")
    assert count == 0


def test_get_vector_count(mock_chroma, mock_embed):
    mock_chroma.count.return_value = 42
    service = VectorIngestionService()
    assert service.get_vector_count() == 42
