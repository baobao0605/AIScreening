"""Prompt builder for title-abstract screening."""

from __future__ import annotations

from src.title_abstract.validator import get_allowed_exclude_reasons_text


def build_title_abstract_prompt(*, criteria_prompt: str, title: str, abstract: str) -> str:
    allowed_reasons = get_allowed_exclude_reasons_text()
    return (
        "You are screening based on TITLE and ABSTRACT only.\n"
        "Do not use assumptions beyond the provided text.\n"
        "If information is insufficient, choose MAYBE.\n\n"
        f"Criteria:\n{criteria_prompt.strip()}\n\n"
        "Output rules:\n"
        "- Return strict JSON only. Do not output markdown fences.\n"
        "- Do not output any explanation text outside JSON.\n"
        "- Decision must be one of: INCLUDE, EXCLUDE, MAYBE.\n"
        f"- Exclude reason must be one of: {allowed_reasons}.\n"
        '- If Decision is INCLUDE or MAYBE, Exclude reason must be "".\n'
        "- If Decision is EXCLUDE, Exclude reason must be a non-empty allowed value.\n"
        '- Construct must be "target construct" or "unclear".\n'
        "- Note must be one short sentence.\n\n"
        "Return JSON with exactly these keys:\n"
        "{\n"
        '  "Decision": "INCLUDE|EXCLUDE|MAYBE",\n'
        '  "Exclude reason": "",\n'
        '  "Construct": "target construct|unclear",\n'
        '  "Note": "short reason"\n'
        "}\n\n"
        f"Title:\n{title}\n\n"
        f"Abstract:\n{abstract}\n"
    )
