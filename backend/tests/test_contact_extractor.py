# =============================================================
# FILE: backend/tests/test_contact_extractor.py
# PURPOSE: Unit tests for services/contact_extractor.py
#
# Tests verify that email, phone, LinkedIn URL, GitHub URL,
# and name are correctly extracted from realistic resume text.
#
# Run: pytest tests/test_contact_extractor.py -v
# =============================================================

import pytest
from services.contact_extractor import extract_contacts


SAMPLE_RESUME = """
Alice Johnson
Senior Product Designer | UX/UI Specialist

alice.johnson@designstudio.com
+44 7911 123456
linkedin.com/in/alicejohnson
github.com/alicejohnson-design

EXPERIENCE
Lead Designer at Figma (2020–2024)
UX Researcher at Google (2017–2020)

SKILLS
Figma, Sketch, User Research, Prototyping, HTML, CSS
"""


def test_extracts_email():
    result = extract_contacts(SAMPLE_RESUME)
    assert result["email"] == "alice.johnson@designstudio.com"


def test_extracts_phone():
    result = extract_contacts(SAMPLE_RESUME)
    assert result["phone"] is not None
    # Should contain the main digits
    assert "7911" in result["phone"] or "123456" in result["phone"]


def test_extracts_linkedin():
    result = extract_contacts(SAMPLE_RESUME)
    assert result["linkedin_url"] is not None
    assert "linkedin.com/in/alicejohnson" in result["linkedin_url"]


def test_extracts_github():
    result = extract_contacts(SAMPLE_RESUME)
    assert result["github_url"] is not None
    assert "github.com/alicejohnson-design" in result["github_url"]


def test_extracts_name():
    result = extract_contacts(SAMPLE_RESUME)
    # Name extraction is a best-effort heuristic; we check it's not None
    # and contains "Alice" or "Johnson"
    assert result["name"] is not None
    assert "Alice" in result["name"] or "Johnson" in result["name"]


def test_missing_fields_return_none():
    sparse = "Python Developer with 5 years of experience."
    result = extract_contacts(sparse)
    assert result["email"] is None
    assert result["phone"] is None
    assert result["linkedin_url"] is None


def test_email_with_plus_sign():
    text = "Contact: user+tag@company.io\nSoftware Engineer"
    result = extract_contacts(text)
    assert result["email"] == "user+tag@company.io"


def test_linkedin_with_https():
    text = "Jane Doe\nhttps://www.linkedin.com/in/janedoe123"
    result = extract_contacts(text)
    assert result["linkedin_url"] is not None
    assert "janedoe123" in result["linkedin_url"]


def test_returns_all_keys():
    """extract_contacts must always return all four keys."""
    result = extract_contacts("Some random text")
    assert "name" in result
    assert "email" in result
    assert "phone" in result
    assert "linkedin_url" in result
    assert "github_url" in result
