import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from app.rag.retrieval import VectorSearchService


@pytest.fixture
def mock_chroma():
    with patch("app.rag.retrieval.async_session") as mock_async_session, patch("app.rag.retrieval.get_chroma_service") as mock_get_chroma_service:
        mock_collection = MagicMock()
        mock_service = MagicMock()
        mock_service.health = AsyncMock(return_value={"chromadb_connected": True})

        async def _query_documents(**kwargs):
            return mock_collection.query(**kwargs)

        mock_service.query_documents = AsyncMock(side_effect=_query_documents)
        mock_get_chroma_service.return_value = mock_service

        @asynccontextmanager
        async def _session_cm():
            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute = AsyncMock(return_value=result)
            yield session

        mock_async_session.side_effect = lambda: _session_cm()
        yield mock_collection


@pytest.fixture
def mock_embed():
    with patch("app.rag.retrieval.EmbeddingService") as MockCls:
        instance = MockCls.return_value
        instance.embed_text = AsyncMock(return_value=[0.1] * 3072)
        yield instance


@pytest.mark.asyncio
async def test_similarity_search(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [["chunk1", "chunk2"]],
        "documents": [["Content A", "Content B"]],
        "metadatas": [[{"source": "github"}, {"source": "github"}]],
        "distances": [[0.1, 0.3]],
    }

    service = VectorSearchService()
    results = await service.similarity_search("content", top_k=2)

    assert len(results) == 2
    assert results[0].content == "Content A"
    assert results[0].score == 0.9
    assert results[1].content == "Content B"
    assert results[1].score == 0.7


@pytest.mark.asyncio
async def test_similarity_search_empty(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }

    service = VectorSearchService()
    results = await service.similarity_search("no results")
    assert results == []


@pytest.mark.asyncio
async def test_similarity_search_filters_cross_domain_results(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [["chunk1", "chunk2"]],
        "documents": [[
            "Workout tracker for gym members and wellness coaching",
            "Enterprise AI Governance for policy teams",
        ]],
        "metadatas": [[
            {"source": "github", "query_domain": "fitness"},
            {"source": "rss", "query_domain": "fitness"},
        ]],
        "distances": [[0.1, 0.1]],
    }

    service = VectorSearchService()
    results = await service.similarity_search("Find opportunities in fitness technology", top_k=5)

    assert len(results) == 1
    assert "workout tracker" in results[0].content.lower()
    assert results[0].query_domain == "fitness"
    assert results[0].query_relevance_score >= 70


@pytest.mark.asyncio
async def test_hybrid_search(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [["chunk1"]],
        "documents": [["Filtered content"]],
        "metadatas": [[{"source": "github"}]],
        "distances": [[0.2]],
    }

    service = VectorSearchService()
    results = await service.hybrid_search(
        "test", top_k=5, where={"source": "github"}
    )
    assert len(results) == 1
    mock_chroma.query.assert_called_once()


@pytest.mark.asyncio
async def test_get_document_context(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [["ctx1"]],
        "documents": [["Context chunk"]],
        "metadatas": [[{"source": "issue"}]],
        "distances": [[0.15]],
    }

    service = VectorSearchService()
    results = await service.get_document_context("query", top_k=5)
    assert len(results) == 1
    assert results[0].content == "Context chunk"


@pytest.mark.asyncio
async def test_filtered_search_by_source(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [["chunk1"]],
        "documents": [["Reddit post about AI"]],
        "metadatas": [[{"source": "reddit"}]],
        "distances": [[0.1]],
    }

    service = VectorSearchService()
    results = await service.filtered_search(
        "AI trends", top_k=5, source="reddit"
    )
    assert len(results) == 1
    assert results[0].metadata["source"] == "reddit"
    call_kwargs = mock_chroma.query.call_args[1]
    assert call_kwargs["where"] == {"source": "reddit"}


@pytest.mark.asyncio
async def test_filtered_search_by_source_and_type(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [["chunk1"]],
        "documents": [["HN story"]],
        "metadatas": [[{"source": "hackernews", "source_type": "story"}]],
        "distances": [[0.15]],
    }

    service = VectorSearchService()
    results = await service.filtered_search(
        "query", top_k=5, source="hackernews", source_type="story"
    )
    assert len(results) == 1
    call_kwargs = mock_chroma.query.call_args[1]
    assert "$and" in call_kwargs["where"]


@pytest.mark.asyncio
async def test_filtered_search_no_filters(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [["chunk1"]],
        "documents": [["Content"]],
        "metadatas": [[{"source": "github"}]],
        "distances": [[0.2]],
    }

    service = VectorSearchService()
    results = await service.filtered_search("query", top_k=5)
    assert len(results) == 1
    call_kwargs = mock_chroma.query.call_args[1]
    assert "where" not in call_kwargs


@pytest.mark.asyncio
async def test_filtered_search_empty_results(mock_chroma, mock_embed):
    mock_chroma.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }

    service = VectorSearchService()
    results = await service.filtered_search("query", source="reddit")
    assert results == []
