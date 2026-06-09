import pytest
from unittest.mock import AsyncMock, patch
from app.agents.validation.agent import ValidationAgent


@pytest.fixture
def agent():
    return ValidationAgent()


@pytest.mark.asyncio
async def test_empty_opportunities(agent):
    result = await agent.run({"opportunities": []})
    assert result == {"validation": []}


@pytest.mark.asyncio
async def test_validates_with_llm(agent):
    opps = [{"title": "TutorAI", "description": "AI tutor app", "confidence_score": 70}]
    trends = [{"title": "AI learning", "description": "Growing", "trend_score": 80, "confidence": 0.8}]
    pp = [{"title": "Cost", "description": "Expensive", "severity_score": 8, "frequency": 15}]
    docs = [{"title": "d1"}, {"title": "d2"}, {"title": "d3"}, {"title": "d4"}, {"title": "d5"}, {"title": "d6"}]

    mock_llm = [
        {
            "title": "TutorAI",
            "overall_score": 75,
            "checks": [
                {"check_name": "evidence_count", "passed": True, "score": 0.8, "details": "6 signals"},
                {"check_name": "trend_confirmation", "passed": True, "score": 1.0, "details": "Trend match"},
                {"check_name": "duplicate_detection", "passed": True, "score": 1.0, "details": "No duplicates"},
                {"check_name": "confidence_threshold", "passed": True, "score": 0.7, "details": "Score 70"},
            ],
            "validated": True,
        }
    ]

    with patch("app.agents.validation.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_llm):
        result = await agent.run({
            "opportunities": opps, "trends": trends, "pain_points": pp, "documents": docs
        })

    assert len(result["validation"]) == 1
    v = result["validation"][0]
    assert v["validated"] is True
    assert v["overall_score"] > 0
    assert len(v["checks"]) == 4


@pytest.mark.asyncio
async def test_falls_back_to_algorithmic(agent):
    opps = [{"title": "Opp1", "description": "desc", "confidence_score": 60}]
    docs = [{"title": "d1"} for _ in range(10)]

    with patch("app.agents.validation.agent.invoke_llm_json", new_callable=AsyncMock, return_value=None):
        result = await agent.run({
            "opportunities": opps, "trends": [], "pain_points": [], "documents": docs
        })

    assert len(result["validation"]) == 1
    assert len(result["validation"][0]["checks"]) == 4


@pytest.mark.asyncio
async def test_validated_flag_respects_threshold(agent):
    opps = [{"title": "Weak", "description": "d", "confidence_score": 10}]
    docs = [{"title": "d1"}]

    with patch("app.agents.validation.agent.invoke_llm_json", new_callable=AsyncMock, return_value=None):
        result = await agent.run({
            "opportunities": opps, "trends": [], "pain_points": [], "documents": docs
        })

    assert result["validation"][0]["validated"] is False
