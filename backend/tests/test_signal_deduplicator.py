import pytest
from app.services.signal_deduplicator import SignalDeduplicator
from app.schemas.signals import Signal


@pytest.fixture
def dedup():
    d = SignalDeduplicator(similarity_threshold=0.85)
    yield d
    d.reset()


def _make_signal(source="github", source_id="1", title="Test Signal", content="Content"):
    return Signal(source=source, source_id=source_id, title=title, content=content)


def test_deduplicate_removes_exact_duplicates(dedup):
    signals = [
        _make_signal(source_id="1", title="Same Title"),
        _make_signal(source_id="1", title="Same Title"),
    ]
    result = dedup.deduplicate(signals)
    assert len(result) == 1


def test_deduplicate_keeps_unique_signals(dedup):
    signals = [
        _make_signal(source_id="1", title="First Signal"),
        _make_signal(source_id="2", title="Second Signal"),
        _make_signal(source_id="3", title="Third Signal"),
    ]
    result = dedup.deduplicate(signals)
    assert len(result) == 3


def test_deduplicate_removes_title_similar(dedup):
    signals = [
        _make_signal(source_id="1", title="How to build an AI chatbot"),
        _make_signal(source_id="2", title="How to build an AI chatbot for beginners"),
    ]
    result = dedup.deduplicate(signals)
    assert len(result) == 1


def test_deduplicate_keeps_different_titles(dedup):
    signals = [
        _make_signal(source_id="1", title="Python web frameworks comparison"),
        _make_signal(source_id="2", title="JavaScript testing best practices"),
    ]
    result = dedup.deduplicate(signals)
    assert len(result) == 2


def test_deduplicate_removes_same_source_id(dedup):
    signals = [
        _make_signal(source="github", source_id="abc", title="Title A"),
        _make_signal(source="github", source_id="abc", title="Title B"),
    ]
    result = dedup.deduplicate(signals)
    assert len(result) == 1


def test_deduplicate_allows_same_id_different_source(dedup):
    signals = [
        _make_signal(source="github", source_id="1", title="Title A"),
        _make_signal(source="hackernews", source_id="1", title="Title B"),
    ]
    result = dedup.deduplicate(signals)
    assert len(result) == 2


def test_deduplicate_with_existing_signals(dedup):
    existing = [_make_signal(source_id="1", title="Existing Signal")]
    new = [
        _make_signal(source_id="1", title="Existing Signal"),
        _make_signal(source_id="2", title="New Signal"),
    ]
    result = dedup.deduplicate(new, existing=existing)
    assert len(result) == 1
    assert result[0].source_id == "2"


def test_deduplicate_empty_list(dedup):
    result = dedup.deduplicate([])
    assert result == []


def test_deduplicate_single_signal(dedup):
    signals = [_make_signal()]
    result = dedup.deduplicate(signals)
    assert len(result) == 1


def test_deduplicate_reset(dedup):
    dedup.deduplicate([_make_signal(source_id="1", title="Test")])
    assert len(dedup._seen_hashes) == 1
    dedup.reset()
    assert len(dedup._seen_hashes) == 0
    assert len(dedup._seen_titles) == 0


def test_deduplicate_many_duplicates(dedup):
    signals = [_make_signal(source_id=str(i), title=f"Signal {i % 3}") for i in range(9)]
    result = dedup.deduplicate(signals)
    assert len(result) == 3


def test_content_hash_is_deterministic(dedup):
    s1 = _make_signal(source_id="1", title="Test")
    s2 = _make_signal(source_id="1", title="Test")
    assert dedup._content_hash(s1) == dedup._content_hash(s2)


def test_title_hash_normalizes_case(dedup):
    h1 = dedup._title_hash("Hello World")
    h2 = dedup._title_hash("hello world")
    assert h1 == h2


def test_deduplicate_preserves_order(dedup):
    signals = [_make_signal(source_id=str(i), title=f"Unique Title {i}") for i in range(5)]
    result = dedup.deduplicate(signals)
    assert [s.source_id for s in result] == ["0", "1", "2", "3", "4"]
