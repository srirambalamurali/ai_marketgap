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


def test_collect_run(client):
    with patch("app.api.collect_signals.GitHubIntelligenceCollector") as MockGH:
        mock_gh = MockGH.return_value
        mock_gh.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
        with patch("app.api.collect_signals.HackerNewsCollector") as MockHN:
            mock_hn = MockHN.return_value
            mock_hn.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
            with patch("app.api.collect_signals.RSSCollector") as MockRSS:
                mock_rss = MockRSS.return_value
                mock_rss.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
                with patch("app.api.collect_signals.pipeline") as mock_pipe:
                    mock_pipe.process_batch = AsyncMock(return_value={"signals_collected": 0})
                    resp = client.post("/api/v1/collect/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data


def test_collect_github(client):
    with patch("app.api.collect_signals.GitHubIntelligenceCollector") as MockGH:
        mock_gh = MockGH.return_value
        mock_gh.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
        with patch("app.api.collect_signals.pipeline") as mock_pipe:
            mock_pipe.process_batch = AsyncMock(return_value={"signals_collected": 0})
            resp = client.post("/api/v1/collect/signals/github?query=AI")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_collect_hackernews(client):
    with patch("app.api.collect_signals.HackerNewsCollector") as MockHN:
        mock_hn = MockHN.return_value
        mock_hn.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
        with patch("app.api.collect_signals.pipeline") as mock_pipe:
            mock_pipe.process_batch = AsyncMock(return_value={"signals_collected": 0})
            resp = client.post("/api/v1/collect/hackernews")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_collect_rss(client):
    with patch("app.api.collect_signals.RSSCollector") as MockRSS:
        mock_rss = MockRSS.return_value
        mock_rss.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
        with patch("app.api.collect_signals.pipeline") as mock_pipe:
            mock_pipe.process_batch = AsyncMock(return_value={"signals_collected": 0})
            resp = client.post("/api/v1/collect/rss")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_collect_github_error(client):
    with patch("app.api.collect_signals.GitHubIntelligenceCollector") as MockGH:
        mock_gh = MockGH.return_value
        mock_gh.collect_all = AsyncMock(side_effect=Exception("API fail"))
        resp = client.post("/api/v1/collect/signals/github")
    assert resp.status_code == 200
    assert resp.json()["success"] is False
    assert "error" in resp.json()


def test_collect_status(client):
    with patch("app.api.collect_signals.get_job_status", return_value={"github_collection": {"id": "github_collection"}}):
        resp = client.get("/api/v1/collect/status")
    assert resp.status_code == 200
    assert "scheduler_jobs" in resp.json()


def test_collect_reddit(client):
    with patch("app.api.collect_signals.RedditCollector") as MockReddit:
        mock_r = MockReddit.return_value
        mock_r.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
        with patch("app.api.collect_signals.pipeline") as mock_pipe:
            mock_pipe.process_batch = AsyncMock(return_value={"signals_collected": 0})
            resp = client.post("/api/v1/collect/reddit")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_collect_reddit_error(client):
    with patch("app.api.collect_signals.RedditCollector") as MockReddit:
        mock_r = MockReddit.return_value
        mock_r.collect_all = AsyncMock(side_effect=Exception("API fail"))
        resp = client.post("/api/v1/collect/reddit")
    assert resp.status_code == 200
    assert resp.json()["success"] is False


def test_collect_google_trends(client):
    with patch("app.api.collect_signals.GoogleTrendsCollector") as MockGT:
        mock_gt = MockGT.return_value
        mock_gt.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
        with patch("app.api.collect_signals.pipeline") as mock_pipe:
            mock_pipe.process_batch = AsyncMock(return_value={"signals_collected": 0})
            resp = client.post("/api/v1/collect/google-trends")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_collect_google_trends_error(client):
    with patch("app.api.collect_signals.GoogleTrendsCollector") as MockGT:
        mock_gt = MockGT.return_value
        mock_gt.collect_all = AsyncMock(side_effect=Exception("API fail"))
        resp = client.post("/api/v1/collect/google-trends")
    assert resp.status_code == 200
    assert resp.json()["success"] is False


def test_collect_run_all(client):
    with patch("app.api.collect_signals.GitHubIntelligenceCollector") as MockGH:
        MockGH.return_value.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
        with patch("app.api.collect_signals.HackerNewsCollector") as MockHN:
            MockHN.return_value.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
            with patch("app.api.collect_signals.RSSCollector") as MockRSS:
                MockRSS.return_value.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
                with patch("app.api.collect_signals.RedditCollector") as MockReddit:
                    MockReddit.return_value.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
                    with patch("app.api.collect_signals.GoogleTrendsCollector") as MockGT:
                        MockGT.return_value.collect_all = AsyncMock(return_value=MagicMock(count=0, signals=[]))
                        with patch("app.api.collect_signals.pipeline") as mock_pipe:
                            mock_pipe.process_batch = AsyncMock(return_value={"signals_collected": 0})
                            resp = client.post("/api/v1/collect/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "reddit" in data["results"]
    assert "google_trends" in data["results"]
