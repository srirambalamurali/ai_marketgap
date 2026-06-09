import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.source_document import SourceDocument, SourceType


SAMPLE_REPOS = [
    SourceDocument(
        source="github",
        source_type=SourceType.REPOSITORY,
        title="test/repo1",
        content="test/repo1: Description 1",
        url="https://github.com/test/repo1",
        metadata={"stars": 100, "forks": 10, "language": "Python", "topics": ["ai"]},
    ),
]

SAMPLE_ISSUES = [
    SourceDocument(
        source="github",
        source_type=SourceType.ISSUE,
        title="Issue title",
        content="Issue body",
        url="https://github.com/test/repo1/issues/1",
        metadata={"labels": ["bug"], "comments": 3, "state": "open"},
    ),
]


@pytest.fixture
def mock_collector():
    with patch("app.api.github.GitHubCollector") as MockClass:
        instance = MockClass.return_value
        instance.search_repositories = AsyncMock(return_value=SAMPLE_REPOS)
        instance.search_issues = AsyncMock(return_value=SAMPLE_ISSUES)
        yield instance


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session


def test_collect_github_success(mock_collector, mock_db):
    with patch("app.api.github.bulk_insert_documents", new_callable=AsyncMock, return_value=2):
        with patch("app.api.github.get_db", return_value=iter([mock_db])):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/collect/github",
                json={"query": "AI education"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["repositories_found"] == 1
    assert data["issues_found"] == 1
    assert data["documents_saved"] == 2
    assert data["errors"] == []


def test_collect_github_with_custom_limits(mock_collector, mock_db):
    with patch("app.api.github.bulk_insert_documents", new_callable=AsyncMock, return_value=5):
        with patch("app.api.github.get_db", return_value=iter([mock_db])):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/collect/github",
                json={"query": "AI", "repo_limit": 5, "issue_limit": 10},
            )

    assert response.status_code == 200
    mock_collector.search_repositories.assert_called_once_with("AI", limit=5)
    mock_collector.search_issues.assert_called_once_with("AI", limit=10)


def test_collect_github_empty_query():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/collect/github",
        json={"query": ""},
    )
    assert response.status_code == 422


def test_collect_github_repo_failure(mock_collector, mock_db):
    mock_collector.search_repositories = AsyncMock(side_effect=Exception("API error"))

    with patch("app.api.github.bulk_insert_documents", new_callable=AsyncMock, return_value=1):
        with patch("app.api.github.get_db", return_value=iter([mock_db])):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/collect/github",
                json={"query": "test"},
            )

    data = response.json()
    assert data["success"] is False
    assert data["repositories_found"] == 0
    assert data["issues_found"] == 1
    assert len(data["errors"]) == 1


def test_collect_github_db_failure(mock_collector, mock_db):
    with patch(
        "app.api.github.bulk_insert_documents",
        new_callable=AsyncMock,
        side_effect=Exception("DB error"),
    ):
        with patch("app.api.github.get_db", return_value=iter([mock_db])):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/api/v1/collect/github",
                json={"query": "test"},
            )

    data = response.json()
    assert data["success"] is False
    assert data["repositories_found"] == 1
    assert data["documents_saved"] == 0
    assert any("Database" in e for e in data["errors"])
