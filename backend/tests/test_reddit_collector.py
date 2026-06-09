import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.collectors.reddit_collector import RedditCollector, SUBREDDITS


@pytest.fixture
def collector():
    return RedditCollector()


@pytest.mark.asyncio
async def test_fetch_subreddit_success(collector):
    mock_data = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc123",
                        "title": "Building an AI SaaS startup",
                        "selftext": "Looking for co-founders",
                        "permalink": "/r/startups/comments/abc123/",
                        "author": "founder1",
                        "score": 150,
                        "num_comments": 25,
                        "created_utc": 1700000000,
                        "upvote_ratio": 0.92,
                        "over_18": False,
                        "is_self": True,
                        "url": "https://reddit.com/r/startups/comments/abc123/",
                    }
                }
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = mock_data

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        batch = await collector._fetch_subreddit("startups", limit=5)

    assert batch.source == "reddit"
    assert len(batch.signals) == 1
    s = batch.signals[0]
    assert s.source_type == "post"
    assert s.source_id == "abc123"
    assert s.title == "Building an AI SaaS startup"
    assert s.author == "founder1"
    assert s.score == 150
    assert s.metadata["subreddit"] == "startups"
    assert s.metadata["upvote_ratio"] == 0.92


@pytest.mark.asyncio
async def test_fetch_subreddit_empty(collector):
    mock_data = {"data": {"children": []}}
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = mock_data

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        batch = await collector._fetch_subreddit("startups")

    assert len(batch.signals) == 0


@pytest.mark.asyncio
async def test_fetch_subreddit_rate_limit(collector):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status = MagicMock(side_effect=Exception("429"))

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("rate limited"))
        batch = await collector._fetch_subreddit("startups")

    assert len(batch.signals) == 0


@pytest.mark.asyncio
async def test_fetch_subreddit_network_error(collector):
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=Exception("timeout"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        batch = await collector._fetch_subreddit("startups")

    assert len(batch.signals) == 0


@pytest.mark.asyncio
async def test_collect_all(collector):
    from app.schemas.signals import Signal, SignalBatch
    signals = [Signal(source="reddit", source_id=f"post_{i}", title=f"Post {i}") for i in range(3)]
    mock_batch = SignalBatch(source="reddit", signals=signals)

    with patch.object(collector, "_fetch_subreddit", new_callable=AsyncMock, return_value=mock_batch):
        batch = await collector.collect_all(limit_per_sub=3)

    assert len(batch.signals) == len(SUBREDDITS) * 3
    assert batch.source == "reddit"


@pytest.mark.asyncio
async def test_collect_all_handles_partial_failures(collector):
    from app.schemas.signals import Signal, SignalBatch
    call_count = 0

    async def side_effect(sub, sort="hot", limit=15):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return SignalBatch(source="reddit", signals=[])
        return SignalBatch(source="reddit", signals=[
            Signal(source="reddit", source_id=f"p{call_count}", title=f"Post {call_count}")
        ])

    with patch.object(collector, "_fetch_subreddit", side_effect=side_effect):
        batch = await collector.collect_all(limit_per_sub=1)

    assert len(batch.signals) >= 1


def test_subreddits_configured():
    assert "startups" in SUBREDDITS
    assert "entrepreneur" in SUBREDDITS
    assert "SaaS" in SUBREDDITS
    assert "artificial" in SUBREDDITS
    assert "SideProject" in SUBREDDITS
    assert "smallbusiness" in SUBREDDITS
    assert len(SUBREDDITS) == 6


def test_subreddit_post_metadata():
    from datetime import datetime
    from app.schemas.signals import Signal
    s = Signal(
        source="reddit", source_id="1", source_type="post",
        title="Test", content="Body",
        metadata={"subreddit": "startups", "upvote_ratio": 0.9, "credibility_score": 0.75},
    )
    assert s.metadata["subreddit"] == "startups"
    assert s.metadata["credibility_score"] == 0.75
