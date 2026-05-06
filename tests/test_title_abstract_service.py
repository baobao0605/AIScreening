from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.title_abstract.service import TitleAbstractService


class FakeProvider:
    provider_name = "gemini"
    model_name = "gemini-2.5-flash"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    def screen(self, prompt: str) -> str:
        return self.responses.pop(0)


def _settings(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "criteria_prompt.txt").write_text("criteria", encoding="utf-8")
    (tmp_path / "config" / "settings.yaml").write_text(
        "\n".join(
            [
                "app:",
                "  name: aiscreening",
                "paths:",
                "  input_dir: \"input/local_papers\"",
                "  output_dir: \"output\"",
                "  database_path: \"data/app.db\"",
                "  full_excel_path: \"output/screening_log.xlsx\"",
                "  full_csv_path: \"output/screening_log.csv\"",
                "  criteria_prompt_path: \"config/criteria_prompt.txt\"",
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path / "config" / "settings.yaml"


def test_title_abstract_service_run_and_retry(monkeypatch, tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    excel = tmp_path / "input.xlsx"
    pd.DataFrame({"Title": ["A"], "Abstract": ["AA"]}).to_excel(excel, index=False)
    provider = FakeProvider(
        ['{"Decision":"INCLUDE","Exclude reason":"","Construct":"target construct","Note":"ok"}']
    )
    monkeypatch.setattr("src.title_abstract.service.create_provider", lambda **kwargs: provider)
    service = TitleAbstractService(tmp_path, settings_path)
    summary = service.run(
        excel_path=excel,
        provider_name="gemini",
        api_key="k",
        model="m",
        base_url="",
        prompt_text="criteria",
        run_mode="start",
    )
    assert summary.done == 1
    assert summary.failed == 0


def test_title_abstract_service_retry_failed_only(monkeypatch, tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    excel = tmp_path / "input.xlsx"
    pd.DataFrame({"Title": ["A"], "Abstract": ["AA"]}).to_excel(excel, index=False)
    provider = FakeProvider(
        [
            '{"Decision":"INCLUDE","Exclude reason":"","Construct":"target construct","Note":"ok"}',
            '{"Decision":"INCLUDE","Exclude reason":"","Construct":"target construct","Note":"ok"}',
        ]
    )
    monkeypatch.setattr("src.title_abstract.service.create_provider", lambda **kwargs: provider)
    service = TitleAbstractService(tmp_path, settings_path)
    start_summary = service.run(
        excel_path=excel,
        provider_name="gemini",
        api_key="k",
        model="m",
        base_url="",
        prompt_text="criteria",
        run_mode="start",
    )
    assert start_summary.done == 1
    retry_summary = service.run(
        excel_path=excel,
        provider_name="gemini",
        api_key="k",
        model="m",
        base_url="",
        prompt_text="criteria",
        run_mode="retry_failed",
    )
    assert retry_summary.queued == 0
    assert retry_summary.done == 0


def test_title_abstract_service_new_only_skips_retryable(monkeypatch, tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    excel = tmp_path / "input.xlsx"
    pd.DataFrame({"Title": ["A", "B"], "Abstract": ["AA", "BB"]}).to_excel(excel, index=False)
    provider = FakeProvider(
        [
            '{"Decision":"INCLUDE","Exclude reason":"","Construct":"target construct","Note":"ok"}',
            "invalid-json",
            '{"Decision":"EXCLUDE","Exclude reason":"Wrong topic","Construct":"unclear","Note":"ok"}',
        ]
    )
    monkeypatch.setattr("src.title_abstract.service.create_provider", lambda **kwargs: provider)
    service = TitleAbstractService(tmp_path, settings_path)
    first_summary = service.run(
        excel_path=excel,
        provider_name="gemini",
        api_key="k",
        model="m",
        base_url="",
        prompt_text="criteria",
        run_mode="start",
    )
    assert first_summary.queued == 2
    assert first_summary.done == 1
    assert first_summary.failed == 1
    # No NEW rows left, only retryable failure exists. new_only should not consume it.
    new_only_summary = service.run(
        excel_path=excel,
        provider_name="gemini",
        api_key="k",
        model="m",
        base_url="",
        prompt_text="criteria",
        run_mode="new_only",
    )
    assert new_only_summary.queued == 0
    assert new_only_summary.done == 0
    # Retry mode should process the previously failed row.
    retry_summary = service.run(
        excel_path=excel,
        provider_name="gemini",
        api_key="k",
        model="m",
        base_url="",
        prompt_text="criteria",
        run_mode="retry_failed",
    )
    assert retry_summary.queued == 1
    assert retry_summary.done == 1
