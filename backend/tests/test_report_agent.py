import pytest
from unittest.mock import AsyncMock, patch
from app.agents.report.agent import ReportAgent


@pytest.fixture
def agent():
    return ReportAgent()


@pytest.mark.asyncio
async def test_generates_report(agent):
    state = {
        "query": "AI tutor",
        "documents": [{"title": "d1"}, {"title": "d2"}],
        "rag_context": ["ctx1"],
        "trends": [{"title": "T1", "description": "AI growing", "trend_score": 80, "confidence": 0.8}],
        "pain_points": [{"title": "PP1", "description": "Too expensive", "frequency": 10, "severity_score": 8, "evidence": ["e1"]}],
        "gaps": [{"title": "G1", "description": "No affordable tutor", "opportunity_score": 85, "pain_points": [], "supporting_trends": []}],
        "opportunities": [],
            "validation": [{"opportunity": {"title": "Affordable AI tutor for students", "description": "Adaptive tutoring for learners", "confidence_score": 70}, "overall_score": 75, "checks": [], "validated": True}],
    }

    mock_llm = {
        "executive_summary": "The AI tutoring market shows strong demand but lacks affordable solutions.",
        "recommendation": "Launch an affordable AI tutor focused on personalization.",
    }

    with patch("app.agents.report.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_llm):
        result = await agent.run(state)

    report = result["report"]
    assert report["query"] == "AI tutor"
    assert report["executive_summary"] == mock_llm["executive_summary"]
    assert report["recommendation"] == mock_llm["recommendation"]
    assert len(report["top_pain_points"]) == 1
    assert len(report["top_trends"]) == 1
    assert len(report["top_market_gaps"]) == 1
    assert len(report["top_opportunities"]) == 1
    assert report["metadata"]["total_signals"] == 2


@pytest.mark.asyncio
async def test_fallback_summary(agent):
    state = {
        "query": "test",
        "documents": [{} for _ in range(10)],
        "rag_context": [],
        "trends": [{} for _ in range(3)],
        "pain_points": [{} for _ in range(5)],
        "gaps": [{} for _ in range(2)],
        "opportunities": [{} for _ in range(4)],
        "validation": [{"validated": True}, {"validated": False}],
    }

    with patch("app.agents.report.agent.invoke_llm_json", new_callable=AsyncMock, return_value=None):
        result = await agent.run(state)

    report = result["report"]
    assert "10 signals" in report["executive_summary"]
    assert "3 trends" in report["executive_summary"]
    assert "5 pain points" in report["executive_summary"]


@pytest.mark.asyncio
async def test_handles_llm_failure_gracefully(agent):
    state = {
        "query": "q",
        "documents": [],
        "rag_context": [],
        "trends": [],
        "pain_points": [],
        "gaps": [],
        "opportunities": [],
        "validation": [],
    }

    with patch("app.agents.report.agent.invoke_llm_json", new_callable=AsyncMock, side_effect=Exception("LLM error")):
        result = await agent.run(state)

    assert result["report"]["query"] == "q"
    assert result["report"]["executive_summary"]  # fallback generated
