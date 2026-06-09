import pytest
from unittest.mock import AsyncMock, patch
from app.agents.pain_point.agent import PainPointAgent


@pytest.fixture
def agent():
    return PainPointAgent()


@pytest.mark.asyncio
async def test_empty_documents(agent):
    result = await agent.run({"documents": []})
    assert result == {"pain_points": []}


@pytest.mark.asyncio
async def test_extracts_pain_points(agent):
    docs = [
        {"title": "AI tutor issues", "content": "Too expensive and no personalization", "source": "reddit"},
        {"title": "Homework help app", "content": "Slow response times frustrate users", "source": "github"},
    ]

    mock_result = [
        {
            "title": "High cost of AI tutoring",
            "description": "Users complain AI tutors are too expensive",
            "frequency": 15,
            "severity_score": 8.5,
            "evidence": ["Too expensive", "Pricing is unreasonable"],
        },
        {
            "title": "Lack of personalization",
            "description": "AI tutors give generic responses",
            "frequency": 10,
            "severity_score": 7.0,
            "evidence": ["No personalization", "Same answers for everyone"],
        },
    ]

    with patch("app.agents.pain_point.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_result):
        result = await agent.run({"documents": docs})

    assert len(result["pain_points"]) == 2
    assert result["pain_points"][0]["title"] == "High cost of AI tutoring"
    assert result["pain_points"][0]["severity_score"] == 8.5
    assert result["pain_points"][0]["id"]  # UUID generated
    assert "evidence" in result["pain_points"][0]


@pytest.mark.asyncio
async def test_handles_llm_failure(agent):
    docs = [{"title": "test", "content": "test"}]

    with patch("app.agents.pain_point.agent.invoke_llm_json", new_callable=AsyncMock, return_value=None):
        result = await agent.run({"documents": docs})

    assert result["pain_points"] == []


@pytest.mark.asyncio
async def test_handles_malformed_llm_response(agent):
    docs = [{"title": "test", "content": "test"}]

    with patch("app.agents.pain_point.agent.invoke_llm_json", new_callable=AsyncMock, return_value="not json"):
        result = await agent.run({"documents": docs})

    assert result["pain_points"] == []


@pytest.mark.asyncio
async def test_includes_rag_context(agent):
    docs = [{"title": "test", "content": "test"}]
    rag_ctx = ["retrieved chunk 1", "retrieved chunk 2"]

    mock_result = [
        {"title": "PP1", "description": "desc", "frequency": 5, "severity_score": 6.0, "evidence": ["e1"]},
    ]

    with patch("app.agents.pain_point.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_result) as mock_invoke:
        await agent.run({"documents": docs, "rag_context": rag_ctx})

    call_args = mock_invoke.call_args
    assert "retrieved chunk 1" in call_args[0][1]


@pytest.mark.asyncio
async def test_skips_invalid_items(agent):
    docs = [{"title": "test", "content": "test"}]

    mock_result = [
        "invalid string",
        {"title": "Valid PP", "description": "desc", "frequency": 3, "severity_score": 5.0, "evidence": []},
        123,
    ]

    with patch("app.agents.pain_point.agent.invoke_llm_json", new_callable=AsyncMock, return_value=mock_result):
        result = await agent.run({"documents": docs})

    assert len(result["pain_points"]) == 1
    assert result["pain_points"][0]["title"] == "Valid PP"
