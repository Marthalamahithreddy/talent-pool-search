# =============================================================
# FILE: backend/tests/test_pii_scrubber.py
# PURPOSE: Unit tests for services/pii_scrubber.py
#
# Tests verify that:
#   - Email addresses are replaced with [EMAIL]
#   - Phone numbers are replaced with [PHONE]
#   - LinkedIn URLs are replaced with [LINKEDIN]
#   - GitHub URLs are replaced with [GITHUB]
#   - Non-PII content (years, regular numbers) is preserved
#
# Run: pytest tests/test_pii_scrubber.py -v
# =============================================================

import pytest
from services.pii_scrubber import scrub_pii


def test_scrubs_email():
    text = "Contact me at john.doe@example.com for more info."
    result = scrub_pii(text)
    assert "[EMAIL]" in result
    assert "john.doe@example.com" not in result


def test_scrubs_multiple_emails():
    text = "Primary: alice@company.com, backup: bob@gmail.com"
    result = scrub_pii(text)
    assert result.count("[EMAIL]") == 2
    assert "alice@company.com" not in result
    assert "bob@gmail.com" not in result


def test_scrubs_phone_international():
    text = "Call me at +91 9876543210 anytime."
    result = scrub_pii(text)
    assert "[PHONE]" in result
    assert "9876543210" not in result


def test_scrubs_phone_us_format():
    text = "My phone: (123) 456-7890"
    result = scrub_pii(text)
    assert "[PHONE]" in result


def test_preserves_years_not_phone():
    """Short number strings like years should NOT be replaced."""
    text = "Worked at Acme from 2018 to 2022."
    result = scrub_pii(text)
    assert "2018" in result
    assert "2022" in result


def test_scrubs_linkedin_with_https():
    text = "Profile: https://www.linkedin.com/in/johndoe"
    result = scrub_pii(text)
    assert "[LINKEDIN]" in result
    assert "linkedin.com/in/johndoe" not in result


def test_scrubs_linkedin_without_protocol():
    text = "See my profile at linkedin.com/in/jane-smith"
    result = scrub_pii(text)
    assert "[LINKEDIN]" in result


def test_scrubs_github():
    text = "Code at https://github.com/johndoe123"
    result = scrub_pii(text)
    assert "[GITHUB]" in result
    assert "github.com/johndoe123" not in result


def test_preserves_non_pii_content():
    """Skills, job titles, and regular text must survive scrubbing."""
    text = "Senior Python Developer with expertise in FastAPI and PostgreSQL."
    result = scrub_pii(text)
    assert "Senior Python Developer" in result
    assert "FastAPI" in result
    assert "PostgreSQL" in result


def test_all_pii_in_one_resume():
    """Full realistic resume snippet with all PII types."""
    resume = """
    John Smith
    john.smith@gmail.com | +1 (415) 555-0182
    linkedin.com/in/johnsmith | github.com/jsmith

    Senior Backend Engineer with 7 years of experience in Python.
    """
    result = scrub_pii(resume)
    assert "[EMAIL]" in result
    assert "[PHONE]" in result
    assert "[LINKEDIN]" in result
    assert "[GITHUB]" in result
    assert "john.smith@gmail.com" not in result
    assert "415" not in result          # phone digits gone
    assert "Python" in result           # skill preserved
    assert "7" in result                # experience preserved
