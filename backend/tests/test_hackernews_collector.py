import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.collectors.hackernews_collector import HackerNewsCollector


@pytest.fixture
def collector():
    return HackerNewsCollector()


@pytest.mark.asyncio
async def test_fetch_story_ids(collector):
    with patch.object(collector, "_fetch_item", new_callable=AsyncMock, return_value=None):
        with patch("httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock()
            mock_resp.json.return_value = [123, 456]
            mock_resp.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            ids = await collector._fetch_story_ids("topstories")
    assert ids == [123, 456]


@pytest.mark.asyncio
async def test_collect_top_stories(collector):
    mock_item = {
        "id": 123,
        "type": "story",
        "title": "Test Story",
        "text": "Some text",
        "url": "https://example.com",
        "by": "user1",
        "score": 50,
        "descendants": 10,
        "kids": [1, 2, 3],
    }
    with patch.object(collector, "_fetch_story_ids", new_callable=AsyncMock, return_value=[123]):
        with patch.object(collector, "_fetch_item", new_callable=AsyncMock, return_value=mock_item):
            batch = await collector.collect_top_stories(limit=5)
    assert len(batch.signals) == 1
    assert batch.signals[0].source_type == "story"
    assert batch.signals[0].score == 50


@pytest.mark.asyncio
async def test_collect_ask_hn(collector):
    mock_item = {"id": 456, "type": "story", "title": "Ask HN: How to?", "text": "Question", "by": "asker", "score": 20}
    with patch.object(collector, "_fetch_story_ids", new_callable=AsyncMock, return_value=[456]):
        with patch.object(collector, "_fetch_item", new_callable=AsyncMock, return_value=mock_item):
            batch = await collector.collect_ask_hn(limit=5)
    assert len(batch.signals) == 1
    assert batch.signals[0].source_type == "ask_hn"


@pytest.mark.asyncio
async def test_collect_show_hn(collector):
    mock_item = {"id": 789, "type": "story", "title": "Show HN: My Project", "text": "Check it out", "by": "maker", "score": 30}
    with patch.object(collector, "_fetch_story_ids", new_callable=AsyncMock, return_value=[789]):
        with patch.object(collector, "_fetch_item", new_callable=AsyncMock, return_value=mock_item):
            batch = await collector.collect_show_hn(limit=5)
    assert len(batch.signals) == 1
    assert batch.signals[0].source_type == "show_hn"


@pytest.mark.asyncio
async def test_collect_new_stories(collector):
    mock_item = {"id": 999, "type": "story", "title": "New Story", "text": "", "by": "newuser", "score": 5}
    with patch.object(collector, "_fetch_story_ids", new_callable=AsyncMock, return_value=[999]):
        with patch.object(collector, "_fetch_item", new_callable=AsyncMock, return_value=mock_item):
            batch = await collector.collect_new_stories(limit=5)
    assert len(batch.signals) == 1
    assert batch.signals[0].source_type == "new_story"


@pytest.mark.asyncio
async def test_collect_all(collector):
    mock_item = {"id": 1, "type": "story", "title": "Test", "text": "", "by": "u", "score": 1}
    with patch.object(collector, "_fetch_story_ids", new_callable=AsyncMock, return_value=[1]):
        with patch.object(collector, "_fetch_item", new_callable=AsyncMock, return_value=mock_item):
            batch = await collector.collect_all(limit_per_type=1)
    assert len(batch.signals) >= 1


@pytest.mark.asyncio
async def test_fetch_item_failure(collector):
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=Exception("timeout"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await collector._fetch_item(123)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_story_ids_failure(collector):
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=Exception("network error"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        ids = await collector._fetch_story_ids("topstories")
    assert ids == []


@pytest.mark.asyncio
async def test_item_to_signal(collector):
    item = {"id": 42, "type": "story", "title": "Hello", "text": "Body", "url": "https://x.com", "by": "author", "score": 10, "descendants": 5, "kids": [1, 2]}
    signal = collector._item_to_signal(item)
    assert signal.source == "hackernews"
    assert signal.title == "Hello"
    assert signal.score == 10
    assert signal.metadata["hn_id"] == 42


@pytest.mark.asyncio
async def test_collect_handles_non_story_items(collector):
    mock_item = {"id": 1, "type": "comment", "title": "", "text": "A comment"}
    with patch.object(collector, "_fetch_story_ids", new_callable=AsyncMock, return_value=[1]):
        with patch.object(collector, "_fetch_item", new_callable=AsyncMock, return_value=mock_item):
            batch = await collector.collect_top_stories(limit=5)
    assert len(batch.signals) == 0
