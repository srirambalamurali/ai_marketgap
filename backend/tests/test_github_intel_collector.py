import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.collectors.github_collector import GitHubIntelligenceCollector


@pytest.fixture
def collector():
    return GitHubIntelligenceCollector(token="test-token")


@pytest.mark.asyncio
async def test_collect_trending_repos(collector):
    mock_data = {
        "items": [
            {
                "id": 1,
                "full_name": "test/repo",
                "description": "A test repo",
                "html_url": "https://github.com/test/repo",
                "owner": {"login": "testuser"},
                "stargazers_count": 100,
                "forks_count": 10,
                "language": "Python",
                "topics": ["ai", "ml"],
                "open_issues_count": 5,
            }
        ]
    }
    with patch.object(collector, "_get", new_callable=AsyncMock, return_value=mock_data):
        batch = await collector.collect_trending_repos("AI", limit=10)
    assert batch.source == "github"
    assert len(batch.signals) == 1
    assert batch.signals[0].source_type == "repository"
    assert batch.signals[0].score == 100
    assert batch.signals[0].metadata["stars"] == 100


@pytest.mark.asyncio
async def test_collect_issues(collector):
    mock_data = {
        "items": [
            {
                "id": 100,
                "title": "Bug in auth",
                "body": "Login fails sometimes",
                "html_url": "https://github.com/test/repo/issues/1",
                "user": {"login": "dev1"},
                "reactions": {"+1": 15},
                "comments": 8,
                "labels": [{"name": "bug"}],
                "state": "open",
                "repository_url": "https://api.github.com/repos/test/repo",
            }
        ]
    }
    with patch.object(collector, "_get", new_callable=AsyncMock, return_value=mock_data):
        batch = await collector.collect_issues("AI", limit=10)
    assert len(batch.signals) == 1
    assert batch.signals[0].source_type == "issue"
    assert batch.signals[0].metadata["labels"] == ["bug"]


@pytest.mark.asyncio
async def test_collect_feature_requests(collector):
    mock_data = {
        "items": [
            {
                "id": 200,
                "title": "Add dark mode",
                "body": "Please add dark mode support",
                "html_url": "https://github.com/test/repo/issues/2",
                "user": {"login": "user1"},
                "reactions": {"+1": 30},
                "comments": 12,
                "labels": [{"name": "feature request"}],
            }
        ]
    }
    with patch.object(collector, "_get", new_callable=AsyncMock, return_value=mock_data):
        batch = await collector.collect_feature_requests("AI", limit=10)
    assert len(batch.signals) == 1
    assert batch.signals[0].source_type == "feature_request"


@pytest.mark.asyncio
async def test_collect_all(collector):
    from app.schemas.signals import Signal
    real_signal = Signal(source="github", source_id="1", title="Test", content="C")
    with patch.object(collector, "collect_trending_repos", new_callable=AsyncMock) as mock_repos:
        mock_repos.return_value = MagicMock(signals=[real_signal])
        with patch.object(collector, "collect_issues", new_callable=AsyncMock) as mock_issues:
            mock_issues.return_value = MagicMock(signals=[])
            with patch.object(collector, "collect_feature_requests", new_callable=AsyncMock) as mock_fr:
                mock_fr.return_value = MagicMock(signals=[])
                batch = await collector.collect_all("AI")
    assert batch.source == "github"


@pytest.mark.asyncio
async def test_collect_handles_api_error(collector):
    with patch.object(collector, "_get", new_callable=AsyncMock, return_value=None):
        batch = await collector.collect_trending_repos("AI")
    assert len(batch.signals) == 0


@pytest.mark.asyncio
async def test_collect_handles_empty_response(collector):
    with patch.object(collector, "_get", new_callable=AsyncMock, return_value={"items": []}):
        batch = await collector.collect_trending_repos("AI")
    assert len(batch.signals) == 0


def test_days_ago():
    result = GitHubIntelligenceCollector._days_ago(30)
    assert len(result) == 10
    assert "-" in result
