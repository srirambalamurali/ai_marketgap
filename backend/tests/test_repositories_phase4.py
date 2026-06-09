import pytest
from unittest.mock import AsyncMock, MagicMock
import app.repositories.market_signal_repository as msr
import app.repositories.trend_repository as tr
import app.repositories.pain_point_repository as ppr
import app.repositories.gap_repository as gr
import app.repositories.opportunity_repository as opr
import app.repositories.validation_repository as vr


def _mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


# --- MarketSignal ---


@pytest.mark.asyncio
async def test_signal_create():
    session = _mock_session()
    result = await msr.create(session, source="github", source_id="1", title="T", content="C")
    assert result.source == "github"
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_signal_bulk_create():
    session = _mock_session()
    signals = [{"source": "github", "source_id": "1", "title": "T1", "content": "C1"},
               {"source": "reddit", "source_id": "2", "title": "T2", "content": "C2"}]
    result = await msr.bulk_create(session, signals)
    assert len(result) == 2
    session.add_all.assert_called_once()


@pytest.mark.asyncio
async def test_signal_count():
    session = _mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    session.execute = AsyncMock(return_value=mock_result)
    count = await msr.count(session)
    assert count == 42


# --- DetectedTrend ---


@pytest.mark.asyncio
async def test_trend_create():
    session = _mock_session()
    result = await tr.create(session, topic="AI", growth_score=80.0, mention_count=10)
    assert result.topic == "AI"
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_trend_bulk_create():
    session = _mock_session()
    result = await tr.bulk_create(session, [{"topic": "A"}, {"topic": "B"}])
    assert len(result) == 2


@pytest.mark.asyncio
async def test_trend_count():
    session = _mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    session.execute = AsyncMock(return_value=mock_result)
    assert await tr.count(session) == 5


# --- PainPoint ---


@pytest.mark.asyncio
async def test_pain_point_create():
    session = _mock_session()
    result = await ppr.create(session, description="Too expensive", severity=8, mentions=15)
    assert result.severity == 8
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_pain_point_bulk_create():
    session = _mock_session()
    result = await ppr.bulk_create(session, [{"description": "P1"}, {"description": "P2"}])
    assert len(result) == 2


@pytest.mark.asyncio
async def test_pain_point_count():
    session = _mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 3
    session.execute = AsyncMock(return_value=mock_result)
    assert await ppr.count(session) == 3


# --- MarketGap ---


@pytest.mark.asyncio
async def test_gap_create():
    session = _mock_session()
    result = await gr.create(session, gap_description="No solution", opportunity_score=85.0)
    assert result.opportunity_score == 85.0


@pytest.mark.asyncio
async def test_gap_bulk_create():
    session = _mock_session()
    result = await gr.bulk_create(session, [{"gap_description": "G1"}])
    assert len(result) == 1


@pytest.mark.asyncio
async def test_gap_count():
    session = _mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 7
    session.execute = AsyncMock(return_value=mock_result)
    assert await gr.count(session) == 7


# --- StartupOpportunity ---


@pytest.mark.asyncio
async def test_opportunity_create():
    session = _mock_session()
    result = await opr.create(session, startup_name="TutorAI", problem="P", solution="S", market_score=90.0)
    assert result.startup_name == "TutorAI"


@pytest.mark.asyncio
async def test_opportunity_bulk_create():
    session = _mock_session()
    result = await opr.bulk_create(session, [{"startup_name": "A"}, {"startup_name": "B"}])
    assert len(result) == 2


@pytest.mark.asyncio
async def test_opportunity_count():
    session = _mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 4
    session.execute = AsyncMock(return_value=mock_result)
    assert await opr.count(session) == 4


# --- ValidationResult ---


@pytest.mark.asyncio
async def test_validation_create():
    session = _mock_session()
    result = await vr.create(session, demand_score=80.0, competition_score=30.0, confidence_score=75.0)
    assert result.confidence_score == 75.0


@pytest.mark.asyncio
async def test_validation_bulk_create():
    session = _mock_session()
    result = await vr.bulk_create(session, [{"demand_score": 50.0}])
    assert len(result) == 1


@pytest.mark.asyncio
async def test_validation_count():
    session = _mock_session()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 2
    session.execute = AsyncMock(return_value=mock_result)
    assert await vr.count(session) == 2
