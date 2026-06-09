from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.opportunity_intelligence import (
    OpportunityIntelligenceService,
    _competition_level,
    _customer_for,
    _gtm,
    _mvp_features,
    _pitch_for,
    _revenue_model,
    _startup_name_from_topic,
)


def test_competition_level_low():
    assert _competition_level(80) == "High"


def test_competition_level_medium():
    assert _competition_level(55) == "Medium"


def test_competition_level_high():
    assert _competition_level(20) == "Low"


def test_startup_name_from_topic_basic():
    assert _startup_name_from_topic("onboarding automation") == "OnboardingAutomation"


def test_startup_name_from_topic_empty():
    assert _startup_name_from_topic("") == "SignalForge"


def test_pitch_for_topic():
    assert "onboarding automation" in _pitch_for("onboarding automation")


def test_customer_for_topic():
    assert "onboarding automation" in _customer_for("onboarding automation")


def test_revenue_model():
    assert "Subscription SaaS" in _revenue_model("anything")


def test_mvp_features_count():
    assert len(_mvp_features("topic")) == 4


def test_gtm_text():
    assert "founder communities" in _gtm("topic")


def test_tokenize_and_cluster_build():
    service = OpportunityIntelligenceService()
    signal = SimpleNamespace(
        id="1",
        source="github",
        source_type="issue",
        title="Need onboarding automation",
        content="Teams need onboarding automation now",
        url="https://example.com",
        score=5,
        collected_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    cluster = service._cluster_signals([signal])
    assert list(cluster.keys())


def test_evidence_shape():
    service = OpportunityIntelligenceService()
    signal = SimpleNamespace(
        id="1",
        source="github",
        source_type="issue",
        title="Need onboarding automation",
        content="Teams need onboarding automation now",
        url="https://example.com",
        score=5,
        collected_at=datetime.now(timezone.utc),
    )
    evidence = service._evidence([signal])
    assert evidence["signals"][0]["source"] == "github"


def test_build_opportunity_has_metrics():
    service = OpportunityIntelligenceService()
    signal = SimpleNamespace(
        id="1",
        source="github",
        source_type="issue",
        title="Need onboarding automation",
        content="Teams need onboarding automation now",
        url="https://example.com",
        score=5,
        collected_at=datetime.now(timezone.utc),
    )
    opp = service._build_opportunity("onboarding automation", [signal], query="onboarding automation", query_terms=["onboarding", "automation"])
    assert opp["market_score"] >= 0


def test_build_opportunity_has_explanation():
    service = OpportunityIntelligenceService()
    signal = SimpleNamespace(
        id="1",
        source="rss",
        source_type="article",
        title="Need onboarding automation",
        content="Teams need onboarding automation now",
        url="https://example.com",
        score=5,
        collected_at=datetime.now(timezone.utc),
    )
    opp = service._build_opportunity("onboarding automation", [signal], query="onboarding automation", query_terms=["onboarding", "automation"])
    assert "why_this_opportunity_exists" in opp["explanation"]


def test_build_opportunity_confidence_present():
    service = OpportunityIntelligenceService()
    signal = SimpleNamespace(
        id="1",
        source="google_trends",
        source_type="trend",
        title="onboarding automation",
        content="Interest rising",
        url="https://example.com",
        score=5,
        collected_at=datetime.now(timezone.utc),
    )
    opp = service._build_opportunity("onboarding automation", [signal], query="onboarding automation", query_terms=["onboarding", "automation"])
    assert opp["confidence_score"] >= 0
