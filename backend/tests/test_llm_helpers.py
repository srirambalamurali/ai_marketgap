import pytest
from app.llm.helpers import _parse_json_response


def test_parse_json_array():
    result = _parse_json_response('[{"key": "value"}]')
    assert result == [{"key": "value"}]


def test_parse_json_object():
    result = _parse_json_response('{"key": "value"}')
    assert result == {"key": "value"}


def test_parse_json_embedded_array():
    result = _parse_json_response('Here is the result:\n[{"key": "value"}]\nDone.')
    assert result == [{"key": "value"}]


def test_parse_json_embedded_object():
    result = _parse_json_response('Response:\n{"key": "value"}\nEnd.')
    assert result == {"key": "value"}


def test_parse_json_invalid():
    result = _parse_json_response("not json at all")
    assert result is None


def test_parse_json_empty():
    result = _parse_json_response("")
    assert result is None


def test_parse_json_none():
    result = _parse_json_response(None)
    assert result is None
