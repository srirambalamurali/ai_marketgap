import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.collectors.google_trends_collector import GoogleTrendsCollector, FOCUS_KEYWORDS


@pytest.fixture
def collector():
    return GoogleTrendsCollector()


@pytest.mark.asyncio
async def test_fetch_related_queries(collector):
    from app.schemas.signals import Signal
    mock_rising = MagicMock()
    mock_rising.empty = False
    mock_rising.__iter__ = lambda self: iter([(0, ("ai agent framework", 500)), (1, ("saas template", 200))])
    mock_rising.head.return_value = mock_rising
    mock_rising.iloc = [0]

    mock_related = {"artificial intelligence": {"rising": mock_rising}}
    mock_client = MagicMock()
    mock_client.related_queries.return_value = mock_related
    mock_client.build_payload = MagicMock()

    with patch.object(collector, "_get_client", return_value=mock_client):
        with patch("app.collectors.google_trends_collector.time.sleep"):
            with patch("app.collectors.google_trends_collector._get_cached", return_value=None):
                with patch("app.collectors.google_trends_collector._set_cached"):
                    signals = await collector._fetch_related_queries("artificial intelligence")

    assert isinstance(signals, list)


@pytest.mark.asyncio
async def test_fetch_interest_over_time(collector):
    import pandas as pd
    dates = pd.date_range("2026-05-01", periods=30)
    mock_iot = pd.DataFrame(
        {"artificial intelligence": [50] * 29 + [80]},
        index=dates,
    )
    mock_client = MagicMock()
    mock_client.interest_over_time.return_value = mock_iot
    mock_client.build_payload = MagicMock()

    with patch.object(collector, "_get_client", return_value=mock_client):
        with patch("app.collectors.google_trends_collector.time.sleep"):
            with patch("app.collectors.google_trends_collector._get_cached", return_value=None):
                with patch("app.collectors.google_trends_collector._set_cached"):
                    signals = await collector._fetch_interest_over_time("artificial intelligence")

    assert len(signals) == 1
    assert signals[0].source_type == "interest_trend"


@pytest.mark.asyncio
async def test_fetch_interest_by_region(collector):
    import pandas as pd
    mock_ibr = pd.DataFrame(
        {"artificial intelligence": {"US": 100, "GB": 75, "DE": 50}},
    )
    mock_client = MagicMock()
    mock_client.interest_by_region.return_value = mock_ibr
    mock_client.build_payload = MagicMock()

    with patch.object(collector, "_get_client", return_value=mock_client):
        with patch("app.collectors.google_trends_collector.time.sleep"):
            with patch("app.collectors.google_trends_collector._get_cached", return_value=None):
                with patch("app.collectors.google_trends_collector._set_cached"):
                    signals = await collector._fetch_interest_by_region("artificial intelligence")

    assert len(signals) == 3
    assert signals[0].source_type == "regional_interest"


@pytest.mark.asyncio
async def test_fetch_related_queries_rate_limited(collector):
    mock_client = MagicMock()
    mock_client.build_payload.side_effect = Exception("429 Too Many Requests")

    with patch.object(collector, "_get_client", return_value=mock_client):
        with patch("app.collectors.google_trends_collector._get_cached", return_value=None):
            signals = await collector._fetch_related_queries("keyword")

    assert signals == []


@pytest.mark.asyncio
async def test_cache_hit(collector):
    from app.collectors.google_trends_collector import _cache, _set_cached
    from app.schemas.signals import Signal

    cached = [Signal(source="google_trends", source_id="cached", source_type="rising_query", title="Cached")]
    _set_cached("test_key", cached)

    with patch("app.collectors.google_trends_collector._cache_key", return_value="test_key"):
        result = await collector._fetch_related_queries("keyword")

    assert result == cached


@pytest.mark.asyncio
async def test_collect_all(collector):
    from app.schemas.signals import Signal
    related = [Signal(source="google_trends", source_id="r1", source_type="rising_query", title="R1")]
    interest = [Signal(source="google_trends", source_id="i1", source_type="interest_trend", title="I1")]
    region = [Signal(source="google_trends", source_id="rg1", source_type="regional_interest", title="RG1")]

    with patch.object(collector, "_fetch_related_queries", new_callable=AsyncMock, return_value=related):
        with patch.object(collector, "_fetch_interest_over_time", new_callable=AsyncMock, return_value=interest):
            with patch.object(collector, "_fetch_interest_by_region", new_callable=AsyncMock, return_value=region):
                batch = await collector.collect_all()

    assert batch.source == "google_trends"
    expected = len(FOCUS_KEYWORDS) * 3
    assert len(batch.signals) == expected


def test_focus_keywords():
    assert len(FOCUS_KEYWORDS) == 5
    assert "artificial intelligence" in FOCUS_KEYWORDS
