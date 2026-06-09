import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def mock_search_service():
    with patch("app.api.rag.VectorSearchService") as MockCls:
        instance = MockCls.return_value
        instance.similarity_search = AsyncMock(return_value=[])
        instance.get_document_context = AsyncMock(return_value=[])
        yield instance


def test_search_endpoint_empty(mock_search_service):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/rag/search",
        json={"query": "AI tutor", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["results"] == []


def test_search_endpoint_validation():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/rag/search",
        json={"query": ""},
    )
    assert response.status_code == 422


def test_context_endpoint_empty(mock_search_service):
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/rag/context",
        json={"query": "AI tutor personalization"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["context"] == []


def test_context_endpoint_validation():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/rag/context",
        json={"query": ""},
    )
    assert response.status_code == 422
