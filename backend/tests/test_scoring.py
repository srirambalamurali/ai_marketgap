import pytest
from app.services.opportunity_scoring import compute_opportunity_score, rank_opportunities, score_gap


def test_compute_opportunity_score_basic():
    score = compute_opportunity_score(
        pain_severity=80, trend_strength=70, market_demand=60, competition_gap=50
    )
    expected = 80 * 0.4 + 70 * 0.3 + 60 * 0.2 + 50 * 0.1
    assert score == round(expected, 1)


def test_compute_opportunity_score_zeros():
    score = compute_opportunity_score(0, 0, 0, 0)
    assert score == 0.0


def test_compute_opportunity_score_max():
    score = compute_opportunity_score(100, 100, 100, 100)
    assert score == 100.0


def test_compute_opportunity_score_clamped():
    score = compute_opportunity_score(200, 200, 200, 200)
    assert score == 100.0


def test_compute_opportunity_score_negative_clamped():
    score = compute_opportunity_score(-10, -10, -10, -10)
    assert score == 0.0


def test_rank_opportunities():
    opps = [
        {"title": "A", "confidence_score": 30},
        {"title": "B", "confidence_score": 80},
        {"title": "C", "confidence_score": 60},
    ]
    ranked = rank_opportunities(opps)
    assert ranked[0]["title"] == "B"
    assert ranked[1]["title"] == "C"
    assert ranked[2]["title"] == "A"


def test_rank_opportunities_with_overall_score():
    opps = [
        {"title": "A", "overall_score": 40},
        {"title": "B", "overall_score": 90},
    ]
    ranked = rank_opportunities(opps)
    assert ranked[0]["title"] == "B"


def test_score_gap():
    pp = [
        {"title": "Expensive", "severity_score": 8, "frequency": 15},
        {"title": "Slow", "severity_score": 5, "frequency": 8},
    ]
    trends = [
        {"title": "AI Growth", "trend_score": 90},
        {"title": "Mobile", "trend_score": 40},
    ]
    score = score_gap(pp, trends, ["Expensive"], ["AI Growth"])
    assert 0 <= score <= 100


def test_score_gap_no_matches():
    pp = [{"title": "X", "severity_score": 5, "frequency": 5}]
    trends = [{"title": "Y", "trend_score": 50}]
    score = score_gap(pp, trends, ["Nonexistent"], ["Nonexistent"])
    assert score == 0.0


def test_score_gap_empty():
    score = score_gap([], [], [], [])
    assert score == 0.0
