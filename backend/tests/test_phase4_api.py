import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


# --- /collect/signals ---


@patch("app.api.signals.DataCollectorAgent")
def test_collect_signals_success(MockAgent):
    instance = MockAgent.return_value
    instance.run = AsyncMock(return_value={
        "documents": [{"source": "github"}, {"source": "reddit"}]
    })
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/collect/signals", json={"query": "AI tutor"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["documents_collected"] == 2


@patch("app.api.signals.DataCollectorAgent")
def test_collect_signals_error(MockAgent):
    instance = MockAgent.return_value
    instance.run = AsyncMock(side_effect=Exception("API fail"))
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/collect/signals", json={"query": "AI"}
    )
    data = resp.json()
    assert data["success"] is False


def test_collect_signals_validation():
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/collect/signals", json={"query": ""}
    )
    assert resp.status_code == 422


# --- /trends/run ---


@patch("app.api.trends.TrendDetectionAgent")
def test_trends_run(MockAgent):
    instance = MockAgent.return_value
    instance.run = AsyncMock(return_value={"trends": [{"topic": "AI"}]})
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/trends/run",
        json={"query": "AI", "documents": [{"title": "d1"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["trends"]) == 1


# --- /opportunities/run ---


@patch("app.api.opportunities.OpportunityAgent")
def test_opportunities_run(MockAgent):
    instance = MockAgent.return_value
    instance.run = AsyncMock(return_value={"opportunities": [{"startup_name": "X"}]})
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/opportunities/run",
        json={"gaps": [], "pain_points": [], "trends": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["opportunities"]) == 1


# --- /workflow/run ---


@patch("app.api.workflow.build_graph")
def test_workflow_run(mock_build):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "query": "AI",
        "report": {"summary": "test report"},
    })
    mock_build.return_value = mock_graph
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/workflow/run", json={"query": "AI tutor"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["report"]["summary"] == "test report"


@patch("app.api.workflow.build_graph")
def test_workflow_run_error(mock_build):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=Exception("Graph fail"))
    mock_build.return_value = mock_graph
    resp = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/workflow/run", json={"query": "AI tutor"}
    )
    data = resp.json()
    assert data["success"] is False
    assert len(data["errors"]) == 1
