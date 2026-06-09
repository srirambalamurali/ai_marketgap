import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.rag.embeddings import EmbeddingService


@pytest.fixture
def mock_embeddings():
    with patch("app.rag.embeddings.GoogleGenerativeAIEmbeddings") as MockCls:
        instance = MockCls.return_value
        instance.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        instance.aembed_documents = AsyncMock(
            return_value=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        )
        yield instance


@pytest.mark.asyncio
async def test_embed_text(mock_embeddings):
    service = EmbeddingService()
    result = await service.embed_text("test query")
    assert result == [0.1, 0.2, 0.3]
    mock_embeddings.aembed_query.assert_awaited_once_with("test query")


@pytest.mark.asyncio
async def test_embed_batch(mock_embeddings):
    service = EmbeddingService()
    texts = ["text1", "text2", "text3"]
    result = await service.embed_batch(texts)
    assert len(result) == 3
    mock_embeddings.aembed_documents.assert_awaited_once_with(texts)


@pytest.mark.asyncio
async def test_embed_batch_empty(mock_embeddings):
    service = EmbeddingService()
    result = await service.embed_batch([])
    assert result == []
    mock_embeddings.aembed_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_batch_large(mock_embeddings):
    service = EmbeddingService()
    texts = [f"text_{i}" for i in range(25)]

    async def fake_embed(texts_batch):
        return [[0.1] for _ in texts_batch]

    mock_embeddings.aembed_documents = AsyncMock(side_effect=fake_embed)
    result = await service.embed_batch(texts)
    assert len(result) == 25
    assert mock_embeddings.aembed_documents.call_count == 2
