import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    from app.database.postgres import get_db
    from unittest.mock import AsyncMock

    async def override_get_db():
        db = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_get_latest_signals(client):
    with patch("app.api.signal_stats.list_recent", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [
            MagicMock(
                id="test-id",
                source="github",
                source_type="issue",
                title="Test Signal",
                content="Content here",
                url="https://example.com",
                author="user1",
                score=10,
                credibility_score=0.7,
                collected_at=MagicMock(isoformat=lambda: "2025-01-06T12:00:00"),
            )
        ]
        resp = client.get("/api/v1/signals/latest?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["signals"][0]["source"] == "github"


def test_get_latest_signals_empty(client):
    with patch("app.api.signal_stats.list_recent", new_callable=AsyncMock, return_value=[]):
        resp = client.get("/api/v1/signals/latest")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_get_signal_stats(client):
    with patch("app.api.signal_stats.get_dashboard_metrics", new_callable=AsyncMock) as mock_dash:
        mock_dash.return_value = {
            "total_signals": 42,
            "by_source": {"github": 20, "hackernews": 15, "rss": 7},
            "by_type": {"issue": 10, "story": 15},
            "recent_signals": [],
            "avg_credibility_score": 0.65,
            "generated_at": "2025-01-06T12:00:00",
        }
        resp = client.get("/api/v1/signals/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_signals"] == 42
    assert data["by_source"]["github"] == 20
