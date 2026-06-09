import pytest
from unittest.mock import AsyncMock, patch
from app.agents.gap_analysis.agent import GapAnalysisAgent


@pytest.fixture
def agent():
    return GapAnalysisAgent()


@pytest.mark.asyncio
async def test_empty_inputs(agent):
    result = await agent.run({"trends": [], "pain_points": []})
    assert result == {"gaps": []}


@pytest.mark.asyncio
async def test_identifies_gaps(agent):
    pain_points = [
        {"title": "High cost", "description": "AI tutors too expensive", "severity_score": 8, "frequency": 15},
    ]
    trends = [
        {"title": "AI learning", "description": "AI tutoring growing", "trend_score": 85, "confidence": 0.8},
    ]

    mock_result = [
        {
            "title": "Affordable AI Tutoring Gap",
            "description": "No affordable AI tutoring solution exists",
            "opportunity_score": 80,
            "pain_points": ["High cost"],
            "supporting_trends": ["AI learning"],
        },
    ]

    with patch("app.agents.gap_analysis.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_result):
        result = await agent.run({"trends": trends, "pain_points": pain_points})

    assert len(result["gaps"]) == 1
    assert result["gaps"][0]["opportunity_score"] > 0
    assert result["gaps"][0]["id"]


@pytest.mark.asyncio
async def test_handles_llm_failure(agent):
    pp = [{"title": "P1", "description": "d", "severity_score": 5, "frequency": 3}]
    trends = [{"title": "T1", "description": "d", "trend_score": 50, "confidence": 0.5}]

    with patch("app.agents.gap_analysis.agent.invoke_llm_json", new_callable=AsyncMock, return_value=None):
        result = await agent.run({"trends": trends, "pain_points": pp})

    assert result["gaps"] == []


@pytest.mark.asyncio
async def test_scoring_uses_linked_references(agent):
    pp = [
        {"title": "Expensive", "description": "Too pricey", "severity_score": 9, "frequency": 20},
        {"title": "Slow", "description": "Slow responses", "severity_score": 5, "frequency": 8},
    ]
    trends = [
        {"title": "AI Growth", "description": "Growing", "trend_score": 90, "confidence": 0.9},
        {"title": "Mobile First", "description": "Mobile", "trend_score": 40, "confidence": 0.4},
    ]

    mock_result = [
        {
            "title": "Gap 1",
            "description": "Gap description",
            "opportunity_score": 0,
            "pain_points": ["Expensive"],
            "supporting_trends": ["AI Growth"],
        },
    ]

    with patch("app.agents.gap_analysis.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_result):
        result = await agent.run({"trends": trends, "pain_points": pp})

    assert result["gaps"][0]["opportunity_score"] > 0
