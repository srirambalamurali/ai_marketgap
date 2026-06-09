SOURCE_WEIGHTS: dict[str, dict[str, float]] = {
    "github": {
        "issue": 0.70,
        "feature_request": 0.80,
        "repository": 0.65,
        "discussion": 0.80,
        "unknown": 0.50,
    },
    "hackernews": {
        "story": 0.85,
        "ask_hn": 0.80,
        "show_hn": 0.75,
        "new_story": 0.70,
        "comment": 0.60,
        "unknown": 0.50,
    },
    "rss": {
        "techcrunch": 0.65,
        "venturebeat": 0.65,
        "ycombinator": 0.60,
        "hackernews": 0.60,
        "unknown": 0.50,
    },
    "reddit": {
        "post": 0.75,
        "comment": 0.60,
        "unknown": 0.50,
    },
    "google_trends": {
        "trending_search": 0.70,
        "rising_query": 0.80,
        "interest_trend": 0.75,
        "unknown": 0.50,
    },
}

DEFAULT_SCORE = 0.50


def score_source(source: str, source_type: str = "unknown") -> float:
    source_weights = SOURCE_WEIGHTS.get(source, {})
    return source_weights.get(source_type, DEFAULT_SCORE)


def score_signal(signal_dict: dict) -> float:
    source = signal_dict.get("source", "")
    source_type = signal_dict.get("source_type", "unknown")
    base_score = score_source(source, source_type)

    engagement_bonus = 0.0
    score_val = signal_dict.get("score", 0)
    comments = signal_dict.get("comments_count", 0)

    if score_val > 100:
        engagement_bonus += 0.05
    if score_val > 500:
        engagement_bonus += 0.05
    if comments > 20:
        engagement_bonus += 0.03
    if comments > 100:
        engagement_bonus += 0.03

    return min(1.0, base_score + engagement_bonus)
