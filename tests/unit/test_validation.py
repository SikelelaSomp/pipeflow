"""
Unit tests for the validation layer.
These test validation rules in isolation — no database required.
"""

import pytest
from app.validators.event_validator import _luhn_check, validate_rsa_id
from app.models.models import ValidationOutcome


def test_luhn_check_valid():
    # Real SA ID number structure (this is a constructed valid example)
    assert _luhn_check("9001015009087") is True


def test_luhn_check_invalid():
    assert _luhn_check("9001015009088") is False


def test_validate_rsa_id_wrong_length():
    results = validate_rsa_id("123")
    failures = [r for r in results if r.outcome == ValidationOutcome.FAIL]
    assert any(r.rule == "format" for r in failures)


def test_validate_rsa_id_non_numeric():
    results = validate_rsa_id("900101500908A")
    failures = [r for r in results if r.outcome == ValidationOutcome.FAIL]
    assert any(r.rule == "format" for r in failures)


def test_validate_rsa_id_fails_luhn():
    # 13 digits but bad checksum
    results = validate_rsa_id("9001015009088")
    failures = [r for r in results if r.outcome == ValidationOutcome.FAIL]
    assert any(r.rule == "luhn_check" for r in failures)


def test_validate_rsa_id_passes():
    results = validate_rsa_id("9001015009087")
    assert all(r.outcome == ValidationOutcome.PASS for r in results)