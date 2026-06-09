import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.collectors.rss_collector import RSSCollector, RSS_FEEDS


@pytest.fixture
def collector():
    return RSSCollector()


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Test Feed</title>
    <item>
        <title>Article One</title>
        <link>https://example.com/1</link>
        <description>First article about AI</description>
        <pubDate>Mon, 06 Jan 2025 12:00:00 +0000</pubDate>
        <author>Author One</author>
    </item>
    <item>
        <title>Article Two</title>
        <link>https://example.com/2</link>
        <description>Second article about ML</description>
        <pubDate>Tue, 07 Jan 2025 12:00:00 +0000</pubDate>
        <author>Author Two</author>
    </item>
</channel>
</rss>"""


@pytest.mark.asyncio
async def test_fetch_feed(collector):
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_RSS
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        result = await collector._fetch_feed("https://example.com/feed.xml")
    assert result is not None
    assert "Article One" in result


@pytest.mark.asyncio
async def test_fetch_feed_failure(collector):
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=Exception("timeout"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await collector._fetch_feed("https://example.com/feed.xml")
    assert result is None


def test_parse_feed(collector):
    signals = collector._parse_feed(SAMPLE_RSS, "test_feed")
    assert len(signals) == 2
    assert signals[0].title == "Article One"
    assert signals[0].url == "https://example.com/1"
    assert signals[0].source == "rss"
    assert signals[0].source_type == "test_feed"
    assert "First article about AI" in signals[0].content


def test_parse_feed_empty(collector):
    signals = collector._parse_feed("<rss></rss>", "empty")
    assert len(signals) == 0


def test_parse_feed_invalid_xml(collector):
    signals = collector._parse_feed("not xml at all", "bad")
    assert len(signals) == 0


def test_parse_feed_strips_html(collector):
    html_rss = """<?xml version="1.0"?>
<rss><channel><item>
    <title>Test</title>
    <description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description>
</item></channel></rss>"""
    signals = collector._parse_feed(html_rss, "test")
    assert len(signals) == 1
    assert "<p>" not in signals[0].content
    assert "Hello" in signals[0].content


@pytest.mark.asyncio
async def test_collect_feed(collector):
    with patch.object(collector, "_fetch_feed", new_callable=AsyncMock, return_value=SAMPLE_RSS):
        batch = await collector.collect_feed("test", "https://example.com/feed")
    assert len(batch.signals) == 2
    assert batch.source == "rss"


@pytest.mark.asyncio
async def test_collect_feed_returns_empty_on_failure(collector):
    with patch.object(collector, "_fetch_feed", new_callable=AsyncMock, return_value=None):
        batch = await collector.collect_feed("test", "https://example.com/feed")
    assert len(batch.signals) == 0


@pytest.mark.asyncio
async def test_collect_all(collector):
    from app.schemas.signals import Signal
    from app.schemas.signals import SignalBatch
    batches = [
        SignalBatch(source="rss", signals=[
            Signal(source="rss", source_id=f"feed{i}_1", title=f"Art{i}_1", content=f"C{i}_1"),
            Signal(source="rss", source_id=f"feed{i}_2", title=f"Art{i}_2", content=f"C{i}_2"),
        ])
        for i in range(4)
    ]
    with patch.object(collector, "collect_feed", new_callable=AsyncMock) as mock_collect:
        mock_collect.side_effect = batches
        batch = await collector.collect_all()
    assert len(batch.signals) == 8


def test_rss_feeds_configured():
    assert "techcrunch" in RSS_FEEDS
    assert "venturebeat" in RSS_FEEDS
    assert "ycombinator" in RSS_FEEDS
    assert "hackernews" in RSS_FEEDS


def test_parse_feed_pubdate_handling(collector):
    rss = """<?xml version="1.0"?>
<rss><channel><item>
    <title>Test</title>
    <pubDate>2025-01-15T10:30:00Z</pubDate>
</item></channel></rss>"""
    signals = collector._parse_feed(rss, "test")
    assert len(signals) == 1


def test_parse_feed_no_pubdate(collector):
    rss = """<?xml version="1.0"?>
<rss><channel><item>
    <title>No Date</title>
</item></channel></rss>"""
    signals = collector._parse_feed(rss, "test")
    assert len(signals) == 1


def test_parse_feed_preserves_metadata(collector):
    signals = collector._parse_feed(SAMPLE_RSS, "techcrunch")
    assert signals[0].metadata["feed"] == "techcrunch"
    assert signals[0].metadata["credibility_score"] == 0.65


def test_parse_feed_author_default(collector):
    rss = """<?xml version="1.0"?>
<rss><channel><item>
    <title>No Author</title>
</item></channel></rss>"""
    signals = collector._parse_feed(rss, "myfeed")
    assert signals[0].author == "myfeed"
