import pytest
from unittest.mock import AsyncMock, patch
from app.agents.trend_detector.agent import TrendDetectionAgent


@pytest.fixture
def agent():
    return TrendDetectionAgent()


@pytest.mark.asyncio
async def test_empty_documents(agent):
    result = await agent.run({"documents": []})
    assert result == {"trends": []}


@pytest.mark.asyncio
async def test_detects_trends(agent):
    docs = [
        {"title": "AI tutoring boom", "content": "AI tutors gaining popularity", "source": "github", "score": 100},
        {"title": "Personalized learning", "content": "EdTech growing fast", "source": "reddit", "score": 50},
    ]

    mock_result = [
        {
            "title": "AI-Powered Personalized Learning",
            "description": "Growing demand for AI tutors with personalization",
            "trend_score": 85.0,
            "confidence": 0.85,
        },
        {
            "title": "EdTech Market Expansion",
            "description": "EdTech adoption accelerating post-pandemic",
            "trend_score": 72.0,
            "confidence": 0.7,
        },
    ]

    with patch("app.agents.trend_detector.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_result):
        result = await agent.run({"documents": docs})

    assert len(result["trends"]) == 2
    assert result["trends"][0]["trend_score"] == 85.0
    assert result["trends"][0]["confidence"] == 0.85
    assert result["trends"][0]["id"]


@pytest.mark.asyncio
async def test_handles_llm_failure(agent):
    docs = [{"title": "test", "content": "test"}]

    with patch("app.agents.trend_detector.agent.invoke_llm_json", new_callable=AsyncMock, return_value=None):
        result = await agent.run({"documents": docs})

    assert result["trends"] == []


@pytest.mark.asyncio
async def test_includes_rag_context(agent):
    docs = [{"title": "test", "content": "test"}]
    rag_ctx = ["context chunk"]

    mock_result = [{"title": "T1", "description": "d", "trend_score": 50, "confidence": 0.5}]

    with patch("app.agents.trend_detector.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_result) as mock_invoke:
        await agent.run({"documents": docs, "rag_context": rag_ctx})

    call_args = mock_invoke.call_args
    assert "context chunk" in call_args[0][1]


@pytest.mark.asyncio
async def test_handles_malformed_response(agent):
    docs = [{"title": "test", "content": "test"}]

    with patch("app.agents.trend_detector.agent.invoke_llm_json", new_callable=AsyncMock, return_value="bad"):
        result = await agent.run({"documents": docs})

    assert result["trends"] == []
