import pytest
from unittest.mock import AsyncMock, patch
from app.workflows.market_gap_graph import build_graph, get_graph, print_graph_mermaid, AGENT_ORDER
from app.models.state import MarketGapState


@pytest.fixture
def initial_state() -> MarketGapState:
    return {
        "query": "test",
        "documents": [],
        "rag_context": [],
        "recent_signals": [],
        "signal_summary": "",
        "trends": [],
        "pain_points": [],
        "gaps": [],
        "opportunities": [],
        "validation": [],
        "report": None,
        "opportunity_scores": [],
        "market_gaps": [],
        "trend_analysis": [],
    }


@pytest.mark.asyncio
async def test_all_nodes_execute_in_sequence(initial_state: MarketGapState):
    execution_order: list[str] = []
    node_names = [name for name, _ in AGENT_ORDER]

    original_runs = {}
    for name, agent in AGENT_ORDER:
        original_runs[name] = agent.run

        def make_wrapper(n, orig):
            async def wrapper(state):
                execution_order.append(n)
                return await orig(state)
            return wrapper

        agent.run = make_wrapper(name, original_runs[name])

    try:
        compiled = build_graph()
        result = await compiled.ainvoke(initial_state)
    finally:
        for name, agent in AGENT_ORDER:
            agent.run = original_runs[name]

    assert execution_order == node_names, (
        f"Expected sequential execution, got: {execution_order}"
    )
    assert result["query"] == "test"


@pytest.mark.asyncio
async def test_graph_returns_updated_state(initial_state: MarketGapState):
    compiled = build_graph()
    result = await compiled.ainvoke(initial_state)

    assert result["query"] == "test"
    assert isinstance(result["documents"], list)
    assert isinstance(result["trends"], list)
    assert isinstance(result["pain_points"], list)
    assert isinstance(result["gaps"], list)
    assert isinstance(result["opportunities"], list)
    assert isinstance(result["validation"], list)


def test_get_graph_returns_singleton():
    g1 = get_graph()
    g2 = get_graph()
    assert g1 is g2


def test_build_graph_returns_fresh_compiled():
    g1 = build_graph()
    g2 = build_graph()
    assert g1 is not g2


def test_mermaid_output():
    mermaid = print_graph_mermaid()
    assert "data_collector" in mermaid
    assert "trend_detector" in mermaid
    assert "report" in mermaid
    assert "-->" in mermaid
