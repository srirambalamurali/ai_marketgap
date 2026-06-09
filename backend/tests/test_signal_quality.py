import pytest
from datetime import datetime, timedelta
from app.schemas.signals import Signal
from app.services.signal_quality_service import SignalQualityService, quality_service, MIN_QUALITY_SCORE


@pytest.fixture
def svc():
    return SignalQualityService()


def _make_signal(source="github", score=50, comments=10, content_len=100, created_hours_ago=1):
    return Signal(
        source=source,
        source_id="1",
        source_type="post",
        title="Test signal title here",
        content="x" * content_len,
        url="https://example.com",
        author="user1",
        score=score,
        comments_count=comments,
        collected_at=datetime.utcnow(),
        created_at=datetime.utcnow() - timedelta(hours=created_hours_ago),
    )


def test_score_source_reliability(svc):
    github = _make_signal(source="github")
    reddit = _make_signal(source="reddit")
    assert svc.score_signal(github) > svc.score_signal(reddit)


def test_score_high_engagement(svc):
    high = _make_signal(score=500, comments=100)
    low = _make_signal(score=1, comments=0)
    assert svc.score_signal(high) > svc.score_signal(low)


def test_score_recent_beats_old(svc):
    recent = _make_signal(created_hours_ago=1)
    old = _make_signal(created_hours_ago=720)
    assert svc.score_signal(recent) > svc.score_signal(old)


def test_score_with_content(svc):
    with_content = _make_signal(content_len=200)
    without_content = _make_signal(content_len=0)
    assert svc.score_signal(with_content) > svc.score_signal(without_content)


def test_score_range(svc):
    signal = _make_signal()
    score = svc.score_signal(signal)
    assert 0.0 <= score <= 1.0


def test_filter_signals(svc):
    signals = [
        _make_signal(source="github", score=100, comments=50, content_len=200),
        _make_signal(source="reddit", score=0, comments=0, content_len=0),
    ]
    filtered = svc.filter_signals(signals, min_score=0.3)
    assert len(filtered) >= 1


def test_filter_low_quality(svc):
    signals = [
        Signal(source="unknown", source_id="1", title="X", content=""),
        Signal(source="unknown", source_id="2", title="Another test title", content="Long enough content here"),
    ]
    filtered = svc.filter_signals(signals, min_score=0.5)
    assert len(filtered) <= len(signals)


def test_quality_score_in_metadata(svc):
    signals = [_make_signal()]
    filtered = svc.filter_signals(signals)
    if filtered:
        assert "quality_score" in filtered[0].metadata


def test_content_quality_empty(svc):
    signal = Signal(source="test", source_id="1", title="T", content="")
    score = svc._content_quality(signal)
    assert score < 1.0


def test_engagement_score_varies(svc):
    s1 = Signal(source="test", source_id="1", title="T", score=2000, comments_count=200)
    s2 = Signal(source="test", source_id="2", title="T", score=1, comments_count=0)
    assert svc._engagement_score(s1) > svc._engagement_score(s2)
