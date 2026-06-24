# =============================================================
# FILE: backend/tests/test_ai_parser.py
# PURPOSE: Unit tests for services/ai_parser.py
#
# Tests focus on the _parse_response helper (pure function, no API call)
# and the _coerce_years helper so the Gemini API is NOT called in CI.
#
# For integration testing against real Gemini, set GEMINI_API_KEY
# and run:  pytest tests/test_ai_parser.py -v -m integration
#
# Run (unit only): pytest tests/test_ai_parser.py -v
# =============================================================

import pytest
from services.ai_parser import _parse_response, _coerce_years, ParsedResume


# ---- _parse_response tests ----------------------------------

def test_parses_valid_json():
    raw = '{"skills": ["Python", "FastAPI"], "years_experience": 4.5, "current_title": "Backend Engineer", "location": "Hyderabad, India"}'
    result = _parse_response(raw)
    assert isinstance(result, ParsedResume)
    assert "Python" in result.skills
    assert result.years_experience == 4.5
    assert result.current_title == "Backend Engineer"
    assert result.location == "Hyderabad, India"


def test_parses_json_with_markdown_fences():
    raw = '```json\n{"skills": ["React"], "years_experience": 2, "current_title": "Frontend Dev", "location": "Berlin"}\n```'
    result = _parse_response(raw)
    assert "React" in result.skills
    assert result.years_experience == 2.0


def test_null_fields_become_none():
    raw = '{"skills": [], "years_experience": null, "current_title": null, "location": null}'
    result = _parse_response(raw)
    assert result.years_experience is None
    assert result.current_title is None
    assert result.location is None


def test_empty_skills_list():
    raw = '{"skills": [], "years_experience": 3, "current_title": "PM", "location": "NYC"}'
    result = _parse_response(raw)
    assert result.skills == []


def test_raises_on_invalid_json():
    with pytest.raises(ValueError, match="non-JSON"):
        _parse_response("This is not JSON at all.")


def test_skills_stripped_of_whitespace():
    raw = '{"skills": ["  Python  ", " Django "], "years_experience": 2, "current_title": "Dev", "location": "London"}'
    result = _parse_response(raw)
    assert "Python" in result.skills
    assert "Django" in result.skills


# ---- _coerce_years tests ------------------------------------

def test_coerce_int():
    assert _coerce_years(4) == 4.0

def test_coerce_float():
    assert _coerce_years(3.5) == 3.5

def test_coerce_string_number():
    assert _coerce_years("4.5") == 4.5

def test_coerce_string_with_word():
    assert _coerce_years("4 years") == 4.0

def test_coerce_none():
    assert _coerce_years(None) is None

def test_coerce_invalid_string():
    assert _coerce_years("unknown") is None
