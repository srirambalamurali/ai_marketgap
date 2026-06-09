import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.reports import store_report, _report_store


@pytest.fixture(autouse=True)
def clean_store():
    _report_store.clear()
    yield
    _report_store.clear()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_get_report_not_found(client):
    resp = client.get("/api/v1/report/nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not found" in data["error"].lower()


def test_get_report_found(client):
    store_report("test-123", {"query": "AI tutor", "summary": "test"})
    resp = client.get("/api/v1/report/test-123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["report"]["query"] == "AI tutor"
