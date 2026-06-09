import pytest
from app.schemas.analysis import (
    PainPoint, TrendSignal, MarketGap, Opportunity,
    ValidationCheck, ValidatedOpportunity, Report,
)


def test_pain_point_schema():
    pp = PainPoint(
        id="1", title="Test", description="Desc",
        frequency=10, severity_score=8.0, evidence=["e1"]
    )
    assert pp.frequency == 10
    assert pp.severity_score == 8.0


def test_trend_signal_schema():
    t = TrendSignal(
        id="1", title="Test", description="Desc",
        trend_score=85.0, confidence=0.85
    )
    assert t.trend_score == 85.0
    assert t.confidence == 0.85


def test_market_gap_schema():
    g = MarketGap(
        id="1", title="Test", description="Desc",
        opportunity_score=80.0, pain_points=["pp1"],
        supporting_trends=["t1"]
    )
    assert g.opportunity_score == 80.0


def test_opportunity_schema():
    o = Opportunity(
        id="1", title="Test", description="Desc",
        market_size_estimate="large",
        confidence_score=75.0,
        implementation_difficulty="medium"
    )
    assert o.confidence_score == 75.0


def test_validation_check():
    vc = ValidationCheck(
        check_name="test", passed=True, score=0.9, details="ok"
    )
    assert vc.passed is True


def test_validated_opportunity():
    opp = Opportunity(id="1", title="T", description="D")
    va = ValidatedOpportunity(
        opportunity=opp, overall_score=75.0,
        checks=[], validated=True
    )
    assert va.validated is True
    assert va.overall_score == 75.0


def test_report_schema():
    r = Report(query="test", executive_summary="summary", recommendation="rec")
    assert r.query == "test"
    assert r.top_pain_points == []
    assert r.metadata == {}


def test_schema_defaults():
    pp = PainPoint(title="T", description="D")
    assert pp.id == ""
    assert pp.frequency == 0
    assert pp.evidence == []
