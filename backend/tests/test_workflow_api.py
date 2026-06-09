import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@patch("app.api.workflow.build_graph")
def test_workflow_run(mock_build, client):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "query": "AI tutor",
        "report": {"query": "AI tutor", "executive_summary": "Test report"},
    })
    mock_build.return_value = mock_graph

    resp = client.post("/api/v1/workflow/run", json={"query": "AI tutor"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["report"]["executive_summary"] == "Test report"


@patch("app.api.workflow.build_graph")
def test_workflow_run_error(mock_build, client):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(side_effect=Exception("Graph error"))
    mock_build.return_value = mock_graph

    resp = client.post("/api/v1/workflow/run", json={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert len(data["errors"]) == 1


def test_workflow_run_validation_error(client):
    resp = client.post("/api/v1/workflow/run", json={"query": ""})
    assert resp.status_code == 422


from unittest.mock import MagicMock
