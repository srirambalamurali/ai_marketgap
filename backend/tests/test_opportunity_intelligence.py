from types import SimpleNamespace
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.opportunity_intelligence import OpportunityIntelligenceService


def _signal(source="github", title="Need better onboarding", content="Teams need better onboarding for SaaS", score=10, days_ago=1):
    return SimpleNamespace(
        id="1",
        source=source,
        source_type="post",
        title=title,
        content=content,
        url="https://example.com",
        score=score,
        collected_at=datetime.utcnow() - timedelta(days=days_ago),
    )


@pytest.mark.asyncio
async def test_build_opportunity_produces_evidence_and_scores(monkeypatch):
    service = OpportunityIntelligenceService()
    signals = [
        _signal(source="github", title="Need better onboarding", content="We need onboarding automation"),
        _signal(source="hackernews", title="Onboarding pain", content="Users churn during onboarding"),
        _signal(source="rss", title="Onboarding article", content="New onboarding workflows for SaaS"),
        _signal(source="google_trends", title="onboarding automation", content="Interest rising"),
    ]

    opportunity = service._build_opportunity("onboarding automation", signals)

    assert opportunity["startup_name"]
    assert opportunity["market_score"] > 0
    assert opportunity["confidence_score"] > 0
    assert opportunity["evidence_count"] == 4
    assert opportunity["evidence"]["signals"][0]["source"] in {"github", "hackernews", "rss", "google_trends"}
    assert opportunity["competition_level"] in {"Low", "Medium", "High"}


@pytest.mark.asyncio
async def test_cluster_and_sort(monkeypatch):
    service = OpportunityIntelligenceService()

    class DummyResult:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return self

        def all(self):
            return self._items

    class DummySession:
        async def execute(self, *args, **kwargs):
            return DummyResult([
                _signal(title="Open source onboarding gap", content="onboarding automation for devtools", score=4),
                _signal(title="Onboarding workflow pain", content="onboarding automation for teams", score=7),
            ])

        def add_all(self, *args, **kwargs):
            return None

        async def flush(self):
            return None

    session = DummySession()
    opportunities = await service.build_opportunities(session, limit=5, query="onboarding automation")

    assert isinstance(opportunities, list)


@pytest.mark.asyncio
async def test_build_opportunities_filters_wrong_domain_and_repo_noise(monkeypatch):
    service = OpportunityIntelligenceService()

    fitness_signal = _signal(
        source="github",
        title="Workout tracker for gym members",
        content="Fitness members need exercise planning, wellness tracking, and nutrition coaching",
    )
    education_signal = _signal(
        source="rss",
        title="Teacher workload automation assistant",
        content="Automating classroom workflows and student planning",
    )
    repo_noise_signal = _signal(
        source="github",
        title="Reluctant2828 System-Fitness-Advisor-Skill",
        content="Repository metadata and project slug",
    )

    async def fake_load_signals(*args, **kwargs):
        return [fitness_signal, education_signal, repo_noise_signal]

    class DummyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class DummySession:
        async def execute(self, *args, **kwargs):
            return DummyResult()

        def add_all(self, *args, **kwargs):
            return None

        async def flush(self):
            return None

    monkeypatch.setattr(service, "_load_signals", fake_load_signals)

    opportunities = await service.build_opportunities(
        DummySession(),
        limit=5,
        query="Find opportunities in fitness technology",
        query_id="123e4567-e89b-12d3-a456-426614174000",
    )

    assert opportunities
    assert all(opp["query_domain"] == "fitness" for opp in opportunities)
    assert all(opp["query_relevance_score"] >= 80 for opp in opportunities)
    joined = " ".join(
        f"{opp.get('startup_name', '')} {opp.get('problem', '')} {opp.get('solution', '')}".lower()
        for opp in opportunities
    )
    assert "teacher workload" not in joined
    assert "course recommendation" not in joined
