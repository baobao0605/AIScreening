"""Strict validation for Gemini screening output."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


EXPECTED_KEYS = {
    "Title",
    "DOI",
    "Decision",
    "Exclude reason",
    "Construct",
    "Note",
}


class ModelOutputValidationError(ValueError):
    """Raised when model output is not valid screening JSON."""


FENCED_JSON_RE = re.compile(
    r"^\s*```(?:json)?\s*(?P<body>[\s\S]*?)\s*```\s*$",
    re.IGNORECASE,
)


def _normalize_json_candidate(raw_response: str) -> str:
    """Strip common model wrappers while still requiring a JSON object payload."""

    candidate = raw_response.strip()
    fenced = FENCED_JSON_RE.match(candidate)
    if fenced:
        candidate = fenced.group("body").strip()
    return candidate


def _normalize_key(value: str) -> str:
    return " ".join(value.strip().casefold().replace("_", " ").split())


def _repair_payload_dict(payload: dict[str, object]) -> dict[str, object]:
    """Best-effort normalization for common LLM schema/value drift."""

    key_aliases = {
        "title": "Title",
        "doi": "DOI",
        "decision": "Decision",
        "exclude reason": "Exclude reason",
        "exclude_reason": "Exclude reason",
        "excludereason": "Exclude reason",
        "construct": "Construct",
        "note": "Note",
    }

    repaired: dict[str, object] = {}
    for raw_key, raw_value in payload.items():
        key = key_aliases.get(_normalize_key(str(raw_key)))
        if key is not None and key not in repaired:
            repaired[key] = raw_value

    for required in EXPECTED_KEYS:
        repaired.setdefault(required, "")

    decision_map = {
        "include": "INCLUDE",
        "exclude": "EXCLUDE",
        "maybe": "MAYBE",
    }
    reason_map = {
        "wrong topic": "Wrong topic",
        "qualitative only": "Qualitative only",
        "foreign language": "Foreign language",
        "exp is a predictor": "Exp is a predictor",
        "wrong exp timing": "Wrong EXP timing",
        "wrong publication type": "Wrong publication type",
        "wrong population": "Wrong population",
        "no effect size": "No effect size",
    }

    decision_raw = str(repaired.get("Decision", "")).strip()
    repaired["Decision"] = decision_map.get(decision_raw.casefold(), decision_raw)

    reason_raw = str(repaired.get("Exclude reason", "")).strip()
    repaired["Exclude reason"] = reason_map.get(reason_raw.casefold(), reason_raw)

    repaired["Title"] = str(repaired.get("Title", "")).strip()
    repaired["DOI"] = str(repaired.get("DOI", "")).strip()
    repaired["Construct"] = str(repaired.get("Construct", "")).strip()
    repaired["Note"] = str(repaired.get("Note", "")).strip()
    return repaired


class ScreeningResult(BaseModel):
    """Validated screening payload returned by the model."""

    model_config = ConfigDict(extra="forbid", populate_by_name=False, str_strip_whitespace=True)

    Title: str
    DOI: str = ""
    Decision: Literal["INCLUDE", "EXCLUDE", "MAYBE"]
    Exclude_reason: str = Field(alias="Exclude reason")
    Construct: str
    Note: str

    @field_validator("Construct", mode="before")
    @classmethod
    def normalize_construct(cls, value: object) -> str:
        raw = str(value).strip().lower()
        alias_to_canonical = {
            "": "unclear",
            "none": "unclear",
            "null": "unclear",
            "n/a": "unclear",
            "na": "unclear",
            "target construct": "target construct",
            "educational expectation": "target construct",
            "educational expectations": "target construct",
            "educational aspirations": "target construct",
            "educational aspiration": "target construct",
            "both": "target construct",
            "unclear": "unclear",
        }
        return alias_to_canonical.get(raw, raw)

    @field_validator("Construct")
    @classmethod
    def validate_construct_value(cls, value: str) -> str:
        if value not in {"target construct", "unclear"}:
            raise ValueError("Invalid construct.")
        return value

    @field_validator("Title", "Note")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("Field must not be empty.")
        return value

    @field_validator("Exclude_reason")
    @classmethod
    def validate_reason_value(cls, value: str) -> str:
        allowed = {
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
        if value not in allowed:
            raise ValueError("Invalid exclusion reason.")
        return value

    @model_validator(mode="after")
    def validate_cross_field_rules(self) -> "ScreeningResult":
        if self.Decision == "EXCLUDE" and not self.Exclude_reason:
            raise ValueError("Exclude reason must be present when Decision is EXCLUDE.")
        if self.Decision in {"INCLUDE", "MAYBE"} and self.Exclude_reason:
            raise ValueError("Exclude reason must be empty unless Decision is EXCLUDE.")
        return self

    def to_db_payload(self) -> dict[str, str]:
        """Return a simple payload for repository persistence/export."""

        return {
            "Title": self.Title,
            "DOI": self.DOI,
            "Decision": self.Decision,
            "Exclude reason": self.Exclude_reason,
            "Construct": self.Construct,
            "Note": self.Note,
        }


def validate_model_output(raw_response: str) -> ScreeningResult:
    """Parse and strictly validate the model's JSON response."""

    normalized = _normalize_json_candidate(raw_response)

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ModelOutputValidationError(f"Model response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ModelOutputValidationError("Model response must be a JSON object.")
    repaired = _repair_payload_dict(parsed)

    try:
        return ScreeningResult.model_validate(repaired)
    except ValidationError as exc:
        raise ModelOutputValidationError(str(exc)) from exc
