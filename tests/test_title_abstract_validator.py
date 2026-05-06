from __future__ import annotations

import json

import pytest

from src.title_abstract.prompt_builder import build_title_abstract_prompt
from src.title_abstract.validator import (
    TitleAbstractValidationError,
    get_allowed_exclude_reasons_text,
    normalize_construct,
    validate_title_abstract_output,
)


def test_prompt_contains_allowed_decision_and_exclude_reason_values() -> None:
    prompt = build_title_abstract_prompt(criteria_prompt="criteria", title="t", abstract="a")
    assert "Decision must be one of: INCLUDE, EXCLUDE, MAYBE." in prompt
    assert get_allowed_exclude_reasons_text() in prompt


def test_validator_accepts_valid_exclude_payload() -> None:
    payload = {
        "Decision": "EXCLUDE",
        "Exclude reason": "Wrong topic",
        "Construct": "unclear",
        "Note": "not relevant",
    }
    parsed = validate_title_abstract_output(json.dumps(payload))
    assert parsed["Decision"] == "EXCLUDE"


def test_validator_rejects_invalid_exclude_with_clear_message() -> None:
    payload = {
        "Decision": "EXCLUDE",
        "Exclude reason": "bad reason",
        "Construct": "unclear",
        "Note": "not relevant",
    }
    with pytest.raises(TitleAbstractValidationError) as exc:
        validate_title_abstract_output(json.dumps(payload))
    message = str(exc.value)
    assert 'Invalid Exclude reason: "bad reason"' in message
    assert "Allowed values are:" in message


def test_validator_normalizes_construct_alias() -> None:
    payload = {
        "Decision": "INCLUDE",
        "Exclude reason": "",
        "Construct": "educational expectation",
        "Note": "relevant",
    }
    parsed = validate_title_abstract_output(json.dumps(payload))
    assert parsed["Construct"] == "target construct"
    assert normalize_construct("both") == "target construct"


def test_validator_falls_back_empty_construct_to_unclear() -> None:
    payload = {
        "Decision": "INCLUDE",
        "Exclude reason": "",
        "Construct": "",
        "Note": "relevant",
    }
    parsed = validate_title_abstract_output(json.dumps(payload))
    assert parsed["Construct"] == "unclear"
