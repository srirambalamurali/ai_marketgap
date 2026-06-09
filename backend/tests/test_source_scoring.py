import pytest
from app.services.source_scoring import score_source, score_signal, SOURCE_WEIGHTS


def test_score_source_github_issue():
    assert score_source("github", "issue") == 0.70


def test_score_source_github_feature_request():
    assert score_source("github", "feature_request") == 0.80


def test_score_source_github_discussion():
    assert score_source("github", "discussion") == 0.80


def test_score_source_github_repository():
    assert score_source("github", "repository") == 0.65


def test_score_source_github_unknown():
    assert score_source("github", "unknown") == 0.50


def test_score_source_hackernews_story():
    assert score_source("hackernews", "story") == 0.85


def test_score_source_hackernews_ask_hn():
    assert score_source("hackernews", "ask_hn") == 0.80


def test_score_source_hackernews_show_hn():
    assert score_source("hackernews", "show_hn") == 0.75


def test_score_source_hackernews_new_story():
    assert score_source("hackernews", "new_story") == 0.70


def test_score_source_rss_techcrunch():
    assert score_source("rss", "techcrunch") == 0.65


def test_score_source_rss_venturebeat():
    assert score_source("rss", "venturebeat") == 0.65


def test_score_source_unknown_source():
    assert score_source("unknown", "unknown") == 0.50


def test_score_signal_low_engagement():
    signal = {"source": "github", "source_type": "issue", "score": 5, "comments_count": 2}
    score = score_signal(signal)
    assert score == 0.70


def test_score_signal_high_engagement():
    signal = {"source": "github", "source_type": "issue", "score": 200, "comments_count": 150}
    score = score_signal(signal)
    assert score > 0.70
    assert score <= 1.0


def test_score_signal_very_high_engagement():
    signal = {"source": "hackernews", "source_type": "story", "score": 600, "comments_count": 200}
    score = score_signal(signal)
    assert score <= 1.0
    assert score > 0.85


def test_score_signal_capped_at_one():
    signal = {"source": "hackernews", "source_type": "story", "score": 9999, "comments_count": 9999}
    score = score_signal(signal)
    assert score <= 1.0


def test_score_signal_unknown_source():
    signal = {"source": "unknown", "source_type": "unknown", "score": 0, "comments_count": 0}
    score = score_signal(signal)
    assert score == 0.50


def test_source_weights_completeness():
    assert "github" in SOURCE_WEIGHTS
    assert "hackernews" in SOURCE_WEIGHTS
    assert "rss" in SOURCE_WEIGHTS
    assert "reddit" in SOURCE_WEIGHTS
    assert "google_trends" in SOURCE_WEIGHTS


def test_score_source_reddit_post():
    assert score_source("reddit", "post") == 0.75


def test_score_source_reddit_comment():
    assert score_source("reddit", "comment") == 0.60


def test_score_source_google_trends_trending():
    assert score_source("google_trends", "trending_search") == 0.70


def test_score_source_google_trends_rising():
    assert score_source("google_trends", "rising_query") == 0.80


def test_score_source_google_trends_interest():
    assert score_source("google_trends", "interest_trend") == 0.75


def test_score_signal_reddit_high_engagement():
    signal = {"source": "reddit", "source_type": "post", "score": 200, "comments_count": 50}
    score = score_signal(signal)
    assert score > 0.75
    assert score <= 1.0


def test_score_signal_google_trends():
    signal = {"source": "google_trends", "source_type": "rising_query", "score": 300, "comments_count": 0}
    score = score_signal(signal)
    assert score > 0.80
    assert score <= 1.0
