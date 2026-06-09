import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.github_collector import GitHubCollector, GitHubRateLimitError
from app.models.source_document import SourceType


SAMPLE_REPO = {
    "full_name": "test/repo",
    "name": "repo",
    "description": "A test repository",
    "html_url": "https://github.com/test/repo",
    "created_at": "2024-01-01T00:00:00Z",
    "stargazers_count": 150,
    "forks_count": 30,
    "language": "Python",
    "topics": ["ai", "ml"],
    "open_issues_count": 5,
}

SAMPLE_ISSUE = {
    "title": "Need better AI tutor",
    "body": "The current AI tutor lacks personalization features.",
    "html_url": "https://github.com/test/repo/issues/1",
    "created_at": "2024-06-01T12:00:00Z",
    "labels": [{"name": "enhancement"}, {"name": "ai"}],
    "comments": 12,
    "state": "open",
}


def test_normalize_repository():
    doc = GitHubCollector.normalize_repository(SAMPLE_REPO)

    assert doc.source == "github"
    assert doc.source_type == SourceType.REPOSITORY
    assert doc.title == "test/repo"
    assert doc.content == "test/repo: A test repository"
    assert doc.url == "https://github.com/test/repo"
    assert doc.metadata["stars"] == 150
    assert doc.metadata["forks"] == 30
    assert doc.metadata["language"] == "Python"
    assert doc.metadata["topics"] == ["ai", "ml"]
    assert doc.metadata["open_issues"] == 5


def test_normalize_repository_no_description():
    repo = {**SAMPLE_REPO, "description": None}
    doc = GitHubCollector.normalize_repository(repo)
    assert doc.content == "test/repo"


def test_normalize_issue():
    doc = GitHubCollector.normalize_issue(SAMPLE_ISSUE)

    assert doc.source == "github"
    assert doc.source_type == SourceType.ISSUE
    assert doc.title == "Need better AI tutor"
    assert doc.content == "The current AI tutor lacks personalization features."
    assert doc.url == "https://github.com/test/repo/issues/1"
    assert doc.metadata["labels"] == ["enhancement", "ai"]
    assert doc.metadata["comments"] == 12
    assert doc.metadata["state"] == "open"


def test_normalize_issue_no_body():
    issue = {**SAMPLE_ISSUE, "body": None}
    doc = GitHubCollector.normalize_issue(issue)
    assert doc.content == ""


@pytest.mark.asyncio
async def test_search_repositories_success():
    collector = GitHubCollector(token="test-token")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {
        "x-ratelimit-remaining": "4999",
        "x-ratelimit-reset": "9999999999",
    }
    mock_response.json.return_value = {"items": [SAMPLE_REPO, SAMPLE_REPO]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(collector, "_request", new_callable=AsyncMock, return_value=mock_response):
        docs = await collector.search_repositories("AI education", limit=2)

    assert len(docs) == 2
    assert all(d.source_type == SourceType.REPOSITORY for d in docs)


@pytest.mark.asyncio
async def test_search_repositories_rate_limit():
    collector = GitHubCollector(token="test-token")
    with patch.object(
        collector,
        "_request",
        side_effect=GitHubRateLimitError(reset_at=0, remaining=0),
    ):
        docs = await collector.search_repositories("AI", limit=10)

    assert docs == []


@pytest.mark.asyncio
async def test_search_repositories_http_error():
    collector = GitHubCollector(token="test-token")
    response = MagicMock()
    response.status_code = 422
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unprocessable", request=MagicMock(), response=response
    )

    with patch.object(collector, "_request", new_callable=AsyncMock, side_effect=httpx.HTTPStatusError(
        "Unprocessable", request=MagicMock(), response=response
    )):
        docs = await collector.search_repositories("bad query")

    assert docs == []


@pytest.mark.asyncio
async def test_search_issues_success():
    collector = GitHubCollector(token="test-token")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {
        "x-ratelimit-remaining": "4999",
        "x-ratelimit-reset": "9999999999",
    }
    mock_response.json.return_value = {"items": [SAMPLE_ISSUE]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(collector, "_request", new_callable=AsyncMock, return_value=mock_response):
        docs = await collector.search_issues("AI tutor", limit=10)

    assert len(docs) == 1
    assert docs[0].source_type == SourceType.ISSUE


@pytest.mark.asyncio
async def test_get_repository_success():
    collector = GitHubCollector(token="test-token")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {
        "x-ratelimit-remaining": "4999",
        "x-ratelimit-reset": "9999999999",
    }
    mock_response.json.return_value = SAMPLE_REPO
    mock_response.raise_for_status = MagicMock()

    with patch.object(collector, "_request", new_callable=AsyncMock, return_value=mock_response):
        doc = await collector.get_repository("test", "repo")

    assert doc is not None
    assert doc.title == "test/repo"


@pytest.mark.asyncio
async def test_get_repository_not_found():
    collector = GitHubCollector(token="test-token")
    response = MagicMock()
    response.status_code = 404

    with patch.object(
        collector, "_request",
        side_effect=httpx.HTTPStatusError("Not Found", request=MagicMock(), response=response),
    ):
        doc = await collector.get_repository("nonexistent", "repo")

    assert doc is None
