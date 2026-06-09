from app.utils.logging import get_logger

logger = get_logger("services.scoring")

LEGACY_WEIGHTS = {
    "pain_severity": 0.4,
    "trend_strength": 0.3,
    "market_demand": 0.2,
    "competition_gap": 0.1,
}

SCORING_DIMENSIONS = {
    "demand": "How strong is the market demand? Based on signal frequency and engagement.",
    "competition": "How underserved is the market? Higher = less competition = better opportunity.",
    "growth": "What is the growth potential? Based on trend momentum and direction.",
    "pain_intensity": "How painful is the problem for users? Based on pain point severity.",
    "technical_feasibility": "How feasible is building a solution? Based on existing tooling and complexity.",
}

DIMENSION_WEIGHTS = {
    "demand": 0.25,
    "competition": 0.20,
    "growth": 0.25,
    "pain_intensity": 0.20,
    "technical_feasibility": 0.10,
}

MAX_DIMENSION_SCORE = 25


def compute_opportunity_score(
    pain_severity: float = 0.0,
    trend_strength: float = 0.0,
    market_demand: float = 0.0,
    competition_gap: float = 0.0,
) -> float:
    """Legacy scoring using 4 dimensions. Returns 0-100."""
    score = (
        pain_severity * LEGACY_WEIGHTS["pain_severity"]
        + trend_strength * LEGACY_WEIGHTS["trend_strength"]
        + market_demand * LEGACY_WEIGHTS["market_demand"]
        + competition_gap * LEGACY_WEIGHTS["competition_gap"]
    )
    return round(min(100.0, max(0.0, score)), 1)


def compute_5d_score(
    demand: float = 0.0,
    competition: float = 0.0,
    growth: float = 0.0,
    pain_intensity: float = 0.0,
    technical_feasibility: float = 0.0,
) -> float:
    """Score an opportunity on 5 dimensions (0-25 each). Returns 0-100 total."""
    dims = {
        "demand": max(0.0, min(MAX_DIMENSION_SCORE, demand)),
        "competition": max(0.0, min(MAX_DIMENSION_SCORE, competition)),
        "growth": max(0.0, min(MAX_DIMENSION_SCORE, growth)),
        "pain_intensity": max(0.0, min(MAX_DIMENSION_SCORE, pain_intensity)),
        "technical_feasibility": max(0.0, min(MAX_DIMENSION_SCORE, technical_feasibility)),
    }
    total = sum(dims.values())
    return round(min(100.0, max(0.0, total)), 1)


def score_opportunity(
    opportunity: dict,
    trends: list[dict] | None = None,
    pain_points: list[dict] | None = None,
    documents: list[dict] | None = None,
) -> dict:
    """Compute 5-dimension scores for an opportunity from available data."""
    trends = trends or []
    pain_points = pain_points or []
    documents = documents or []

    demand_score = _compute_demand(opportunity, documents)
    competition_score = _compute_competition(opportunity, trends)
    growth_score = _compute_growth(opportunity, trends)
    pain_score = _compute_pain_intensity(opportunity, pain_points)
    feasibility_score = _compute_feasibility(opportunity)

    total = compute_5d_score(demand_score, competition_score, growth_score, pain_score, feasibility_score)

    result = {
        "demand_score": round(demand_score, 1),
        "competition_score": round(competition_score, 1),
        "growth_score": round(growth_score, 1),
        "pain_intensity_score": round(pain_score, 1),
        "technical_feasibility_score": round(feasibility_score, 1),
        "total_score": total,
        "recommendation": _recommendation(total),
    }
    opportunity.update(result)
    return opportunity


def _compute_demand(opportunity: dict, documents: list[dict]) -> float:
    base = 5.0
    opp_text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}".lower()
    signal_count = len(documents)
    base += min(10.0, signal_count * 0.5)
    mention_count = sum(
        1 for d in documents
        if any(word in d.get("title", "").lower() for word in opp_text.split() if len(word) > 3)
    )
    base += min(10.0, mention_count * 2.0)
    return min(MAX_DIMENSION_SCORE, base)


def _compute_competition(opportunity: dict, trends: list[dict]) -> float:
    base = 12.0
    opp_text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}".lower()
    competition_indicators = ["competitor", "established", "saturated", "many solutions", "existing"]
    has_competition = any(ind in opp_text for ind in competition_indicators)
    if has_competition:
        base -= 5.0
    unique_angle = sum(
        1 for t in trends
        if any(word in t.get("description", "").lower() for word in ["emerging", "new", "novel", "first"])
    )
    base += min(8.0, unique_angle * 4.0)
    return min(MAX_DIMENSION_SCORE, max(0.0, base))


def _compute_growth(opportunity: dict, trends: list[dict]) -> float:
    base = 5.0
    opp_text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}".lower()
    for trend in trends:
        trend_text = f"{trend.get('title', '')} {trend.get('description', '')}".lower()
        overlap = len(set(opp_text.split()) & set(trend_text.split()))
        if overlap > 2:
            strength = trend.get("strength", trend.get("trend_score", 50))
            if isinstance(strength, (int, float)):
                base += min(10.0, strength / 10.0)
            direction = trend.get("growth_direction", "")
            if direction == "rising":
                base += 5.0
    return min(MAX_DIMENSION_SCORE, base)


def _compute_pain_intensity(opportunity: dict, pain_points: list[dict]) -> float:
    base = 5.0
    opp_text = f"{opportunity.get('title', '')} {_opp_description(opportunity)}".lower()
    for pp in pain_points:
        pp_text = f"{pp.get('title', '')} {pp.get('description', '')}".lower()
        overlap = len(set(opp_text.split()) & set(pp_text.split()))
        if overlap > 2:
            severity = pp.get("severity_score", 5.0)
            base += min(10.0, severity * 1.5)
            frequency = pp.get("frequency", 1)
            base += min(5.0, frequency * 0.5)
    return min(MAX_DIMENSION_SCORE, base)


def _compute_feasibility(opportunity: dict) -> float:
    base = 15.0
    opp_text = f"{opportunity.get('title', '')} {_opp_description(opportunity)}".lower()
    high_complexity = ["blockchain", "hardware", "biotech", "regulated", "compliance"]
    low_complexity = ["api", "saas", "web", "mobile", "no-code", "automation", "integration"]
    if any(kw in opp_text for kw in high_complexity):
        base -= 8.0
    if any(kw in opp_text for kw in low_complexity):
        base += 5.0
    difficulty = opportunity.get("implementation_difficulty", "medium")
    if difficulty == "easy":
        base += 5.0
    elif difficulty == "hard":
        base -= 5.0
    return min(MAX_DIMENSION_SCORE, max(0.0, base))


def _opp_description(opportunity: dict) -> str:
    return opportunity.get("description", "")


def _recommendation(total_score: float) -> str:
    if total_score >= 75:
        return "strong_opportunity"
    if total_score >= 50:
        return "moderate_opportunity"
    return "weak_opportunity"


def rank_opportunities(opportunities: list[dict]) -> list[dict]:
    """Sort opportunities by total_score or confidence_score descending."""
    return sorted(
        opportunities,
        key=lambda o: o.get("total_score", o.get("confidence_score", o.get("overall_score", 0))),
        reverse=True,
    )


def score_gap(
    pain_points: list[dict],
    trends: list[dict],
    gap_pain_titles: list[str],
    gap_trend_titles: list[str],
) -> float:
    """Compute opportunity score for a market gap based on linked pain points and trends."""
    relevant_pp = [
        p for p in pain_points
        if p.get("title") in gap_pain_titles
    ]
    relevant_trends = [
        t for t in trends
        if t.get("title") in gap_trend_titles
    ]

    if not relevant_pp and not relevant_trends:
        return 0.0

    avg_severity = (
        sum(p.get("severity_score", 0) for p in relevant_pp) / max(len(relevant_pp), 1)
    )
    avg_trend = (
        sum(t.get("trend_score", 0) for t in relevant_trends) / max(len(relevant_trends), 1)
    )
    avg_freq = (
        sum(p.get("frequency", 0) for p in relevant_pp) / max(len(relevant_pp), 1)
    )

    pain_severity = min(100, avg_severity * 10)
    trend_strength = min(100, avg_trend)
    market_demand = min(100, avg_freq * 5)
    competition_gap = max(0, 100 - avg_trend) if relevant_trends else 50.0

    return compute_opportunity_score(pain_severity, trend_strength, market_demand, competition_gap)
