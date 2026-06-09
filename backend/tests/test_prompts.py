import pytest
from app.llm.prompts.pain_point_prompt import build_pain_point_prompt, PAIN_POINT_SYSTEM
from app.llm.prompts.trend_prompt import build_trend_prompt, TREND_SYSTEM
from app.llm.prompts.gap_prompt import build_gap_prompt, GAP_SYSTEM
from app.llm.prompts.validation_prompt import build_validation_prompt, VALIDATION_SYSTEM
from app.llm.prompts.report_prompt import build_report_prompt, REPORT_SYSTEM


def test_pain_point_prompt():
    docs = [{"title": "T1", "content": "C1", "source": "github"}]
    prompt = build_pain_point_prompt(docs)
    assert "T1" in prompt
    assert "C1" in prompt
    assert "JSON" in PAIN_POINT_SYSTEM


def test_pain_point_prompt_with_rag():
    docs = [{"title": "T1", "content": "C1", "source": "github"}]
    prompt = build_pain_point_prompt(docs, ["rag chunk 1", "rag chunk 2"])
    assert "rag chunk 1" in prompt


def test_trend_prompt():
    docs = [{"title": "T1", "content": "C1", "source": "reddit", "score": 50}]
    prompt = build_trend_prompt(docs)
    assert "T1" in prompt
    assert "50" in prompt


def test_trend_prompt_with_rag():
    docs = [{"title": "T1", "content": "C1", "source": "reddit", "score": 50}]
    prompt = build_trend_prompt(docs, ["rag ctx"])
    assert "rag ctx" in prompt


def test_gap_prompt():
    pp = [{"title": "PP1", "description": "desc", "severity_score": 8, "frequency": 10}]
    trends = [{"title": "T1", "description": "trend desc", "trend_score": 80, "confidence": 0.8}]
    prompt = build_gap_prompt(pp, trends)
    assert "PP1" in prompt
    assert "T1" in prompt


def test_gap_prompt_with_rag():
    prompt = build_gap_prompt([], [], ["rag chunk"])
    assert "rag chunk" in prompt


def test_validation_prompt():
    opps = [{"title": "O1", "description": "d", "confidence_score": 70}]
    prompt = build_validation_prompt(opps, [], [], [])
    assert "O1" in prompt


def test_report_prompt():
    prompt = build_report_prompt("AI tutor", [], [], [], [])
    assert "AI tutor" in prompt
    assert "JSON" in REPORT_SYSTEM
