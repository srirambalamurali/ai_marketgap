import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.data_collector.agent import DataCollectorAgent


def _make_mock_signal(source="github", idx=0):
    s = MagicMock()
    s.id = f"sig-{source}-{idx}"
    s.source = source
    s.source_type = "post"
    s.title = f"Signal {source} {idx}"
    s.content = f"Content from {source}"
    s.url = f"https://{source}.com/{idx}"
    s.author = f"user_{idx}"
    s.score = 10 + idx
    s.credibility_score = 0.7
    s.collected_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
    return s


@pytest.mark.asyncio
async def test_data_collector_returns_documents():
    agent = DataCollectorAgent()
    signals = [_make_mock_signal("github", 0)]

    with patch("app.database.postgres.async_session") as mock_ctx:
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.agents.data_collector.agent.list_recent", new_callable=AsyncMock, return_value=signals):
            with patch("app.agents.data_collector.agent.list_by_source", new_callable=AsyncMock, return_value=signals):
                result = await agent.run({"query": "AI tutor", "documents": []})

    assert "documents" in result
    assert len(result["documents"]) == 1
    assert result["documents"][0]["source"] == "github"
    assert "recent_signals" in result
    assert "signal_summary" in result


@pytest.mark.asyncio
async def test_data_collector_empty_database():
    agent = DataCollectorAgent()

    with patch("app.database.postgres.async_session") as mock_ctx:
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.agents.data_collector.agent.list_recent", new_callable=AsyncMock, return_value=[]):
            with patch("app.agents.data_collector.agent.list_by_source", new_callable=AsyncMock, return_value=[]):
                result = await agent.run({"query": "test", "documents": []})

    assert result["documents"] == []
    assert result["recent_signals"] == []


@pytest.mark.asyncio
async def test_data_collector_handles_db_error():
    agent = DataCollectorAgent()

    with patch("app.database.postgres.async_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB error"))
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await agent.run({"query": "test", "documents": []})

    assert result["documents"] == []
    assert result["recent_signals"] == []
    assert result["signal_summary"] == ""


@pytest.mark.asyncio
async def test_data_collector_populates_signal_summary():
    agent = DataCollectorAgent()

    signals = []
    for i in range(5):
        src = ["github", "reddit", "hackernews", "rss", "google_trends"][i % 5]
        signals.append(_make_mock_signal(src, i))

    with patch("app.database.postgres.async_session") as mock_ctx:
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.agents.data_collector.agent.list_recent", new_callable=AsyncMock, return_value=signals):
            with patch("app.agents.data_collector.agent.list_by_source", new_callable=AsyncMock, return_value=signals[:1]):
                result = await agent.run({"query": "test", "documents": []})

    assert "recent_signals" in result
    assert len(result["recent_signals"]) == 5
    assert "Total recent signals" in result["signal_summary"]
