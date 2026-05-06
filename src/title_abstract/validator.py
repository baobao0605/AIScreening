"""Validation for title-abstract model JSON output."""

from __future__ import annotations

import json


class TitleAbstractValidationError(ValueError):
    """Raised when model output is invalid for title-abstract schema."""


ALLOWED_DECISIONS = {"INCLUDE", "EXCLUDE", "MAYBE"}
ALLOWED_CONSTRUCT = {"target construct", "unclear"}
ALLOWED_EXCLUDE_REASONS = {
    "",
    "Wrong topic",
    "Qualitative only",
    "Foreign language",
    "Exp is a predictor",
    "Wrong EXP timing",
    "Wrong publication type",
    "Wrong population",
    "No effect size",
}


def get_allowed_exclude_reasons_text() -> str:
    values = [reason for reason in sorted(ALLOWED_EXCLUDE_REASONS) if reason]
    return ", ".join(values)


def normalize_construct(value: str) -> str:
    raw = value.strip().lower()
    alias_to_canonical = {
        "": "unclear",
        "none": "unclear",
        "null": "unclear",
        "n/a": "unclear",
        "na": "unclear",
        "target construct": "target construct",
        "educational expectation": "target construct",
        "educational expectations": "target construct",
        "educational aspiration": "target construct",
        "educational aspirations": "target construct",
        "both": "target construct",
        "unclear": "unclear",
    }
    return alias_to_canonical.get(raw, raw)


def validate_title_abstract_output(raw_response: str) -> dict[str, str]:
    try:
        payload = json.loads(raw_response.strip())
    except json.JSONDecodeError as exc:
        raise TitleAbstractValidationError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TitleAbstractValidationError("Response must be a JSON object.")
    required = {"Decision", "Exclude reason", "Construct", "Note"}
    if set(payload.keys()) != required:
        raise TitleAbstractValidationError("Response must contain exactly Decision/Exclude reason/Construct/Note.")
    decision = str(payload["Decision"]).strip()
    reason = str(payload["Exclude reason"]).strip()
    construct = normalize_construct(str(payload["Construct"]))
    note = str(payload["Note"]).strip()
    if decision not in ALLOWED_DECISIONS:
        raise TitleAbstractValidationError(
            f'Invalid Decision: "{decision}". Allowed values are: {", ".join(sorted(ALLOWED_DECISIONS))}.'
        )
    if reason not in ALLOWED_EXCLUDE_REASONS:
        raise TitleAbstractValidationError(
            f'Invalid Exclude reason: "{reason}". Allowed values are: {get_allowed_exclude_reasons_text()}.'
        )
    if construct not in ALLOWED_CONSTRUCT:
        raise TitleAbstractValidationError("Invalid Construct.")
    if not note:
        raise TitleAbstractValidationError("Note must not be empty.")
    if decision == "EXCLUDE" and not reason:
        raise TitleAbstractValidationError("Exclude reason is required when Decision is EXCLUDE.")
    if decision in {"INCLUDE", "MAYBE"} and reason:
        raise TitleAbstractValidationError("Exclude reason must be empty unless Decision is EXCLUDE.")
    return {
        "Decision": decision,
        "Exclude reason": reason,
        "Construct": construct,
        "Note": note,
    }
