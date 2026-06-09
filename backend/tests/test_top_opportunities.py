import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_top_opportunities_empty(client):
    resp = client.post("/api/v1/opportunities/top", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["opportunities"] == []


def test_top_opportunities_with_validation(client):
    resp = client.post("/api/v1/opportunities/top", json={
        "validation": [
            {
                "opportunity": {"title": "A", "confidence_score": 90},
                "overall_score": 85,
                "validated": True,
            },
            {
                "opportunity": {"title": "B", "confidence_score": 50},
                "overall_score": 45,
                "validated": False,
            },
        ],
        "top_n": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["opportunities"]) == 1
    assert data["opportunities"][0]["title"] == "A"


def test_top_opportunities_fallback_to_opps(client):
    resp = client.post("/api/v1/opportunities/top", json={
        "opportunities": [
            {"title": "X", "confidence_score": 30},
            {"title": "Y", "confidence_score": 80},
        ],
        "validation": [],
        "top_n": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["opportunities"]) == 1
    assert data["opportunities"][0]["title"] == "Y"
