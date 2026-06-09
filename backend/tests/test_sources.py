import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.services.sources.github_source import GitHubSource
from app.services.sources.reddit_source import RedditSource
from app.services.sources.hackernews_source import HackerNewsSource
from app.services.sources.stackoverflow_source import StackOverflowSource
from app.services.sources.base import Signal


# --- GitHub Source ---


@pytest.mark.asyncio
async def test_github_search_repos():
    source = GitHubSource()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {
                "id": 1,
                "full_name": "test/repo",
                "description": "A test repo",
                "html_url": "https://github.com/test/repo",
                "owner": {"login": "testuser"},
                "stargazers_count": 100,
                "open_issues_count": 5,
            }
        ]
    }
    with patch("app.services.sources.github_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(return_value=mock_resp)
        signals = await source._search_repos("AI", limit=5)
    assert len(signals) == 1
    assert signals[0].source == "github"
    assert signals[0].score == 100


@pytest.mark.asyncio
async def test_github_search_repos_error():
    source = GitHubSource()
    with patch("app.services.sources.github_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(side_effect=httpx.RequestError("fail"))
        signals = await source._search_repos("AI", limit=5)
    assert signals == []


@pytest.mark.asyncio
async def test_github_search_issues():
    source = GitHubSource()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {
                "id": 100,
                "title": "Issue title",
                "body": "Issue body",
                "html_url": "https://github.com/test/repo/issues/1",
                "user": {"login": "user1"},
                "reactions": {"+1": 10},
                "comments": 3,
            }
        ]
    }
    with patch("app.services.sources.github_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(return_value=mock_resp)
        signals = await source._search_issues("AI", limit=5)
    assert len(signals) == 1
    assert signals[0].source == "github"
    assert signals[0].score == 10


@pytest.mark.asyncio
async def test_github_search_issues_error():
    source = GitHubSource()
    with patch("app.services.sources.github_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(side_effect=httpx.RequestError("fail"))
        signals = await source._search_issues("AI", limit=5)
    assert signals == []


# --- Reddit Source ---


@pytest.mark.asyncio
async def test_reddit_search():
    source = RedditSource()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc",
                        "title": "Reddit post",
                        "selftext": "Content here",
                        "permalink": "/r/test/abc",
                        "author": "user1",
                        "score": 42,
                        "num_comments": 7,
                    }
                }
            ]
        }
    }
    with patch("app.services.sources.reddit_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(return_value=mock_resp)
        signals = await source.search("AI", limit=5)
    assert len(signals) == 1
    assert signals[0].source == "reddit"
    assert signals[0].score == 42


@pytest.mark.asyncio
async def test_reddit_search_error():
    source = RedditSource()
    with patch("app.services.sources.reddit_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(side_effect=httpx.RequestError("fail"))
        signals = await source.search("AI", limit=5)
    assert signals == []


# --- HackerNews Source ---


@pytest.mark.asyncio
async def test_hn_search():
    source = HackerNewsSource()
    mock_list_resp = MagicMock()
    mock_list_resp.status_code = 200
    mock_list_resp.raise_for_status = MagicMock()
    mock_list_resp.json.return_value = [123]

    mock_item_resp = MagicMock()
    mock_item_resp.status_code = 200
    mock_item_resp.raise_for_status = MagicMock()
    mock_item_resp.json.return_value = {
        "type": "story",
        "title": "HN Story",
        "text": "Story text",
        "url": "https://example.com",
        "by": "hnuser",
        "score": 55,
        "descendants": 12,
    }
    with patch("app.services.sources.hackernews_source.httpx.AsyncClient") as MockClient:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get = AsyncMock(side_effect=[mock_list_resp, mock_item_resp])
        MockClient.return_value = instance
        signals = await source._get_stories("topstories", limit=1)
    assert len(signals) == 1
    assert signals[0].source == "hackernews"


@pytest.mark.asyncio
async def test_hn_search_error():
    source = HackerNewsSource()
    with patch("app.services.sources.hackernews_source.httpx.AsyncClient") as MockClient:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.get = AsyncMock(side_effect=httpx.RequestError("fail"))
        MockClient.return_value = instance
        signals = await source._get_stories("topstories", limit=1)
    assert signals == []


# --- StackOverflow Source ---


@pytest.mark.asyncio
async def test_so_search():
    source = StackOverflowSource()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {
                "question_id": 456,
                "title": "SO Question",
                "body": "Question body",
                "link": "https://stackoverflow.com/q/456",
                "owner": {"display_name": "souser"},
                "score": 25,
                "answer_count": 3,
            }
        ]
    }
    with patch("app.services.sources.stackoverflow_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(return_value=mock_resp)
        signals = await source.search("AI", limit=5)
    assert len(signals) == 1
    assert signals[0].source == "stackoverflow"


@pytest.mark.asyncio
async def test_so_search_error():
    source = StackOverflowSource()
    with patch("app.services.sources.stackoverflow_source.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        MockClient.get = AsyncMock(side_effect=httpx.RequestError("fail"))
        signals = await source.search("AI", limit=5)
    assert signals == []
