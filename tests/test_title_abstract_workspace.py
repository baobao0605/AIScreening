from __future__ import annotations

from pathlib import Path

from src.title_abstract.service import TitleAbstractService


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


def test_title_abstract_workspace_id_stable(tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    service = TitleAbstractService(tmp_path, settings_path)
    excel = tmp_path / "my data" / "rayyan_export.xlsx"
    excel.parent.mkdir(parents=True, exist_ok=True)
    ws1 = service._workspace_from_excel(excel)
    ws2 = service._workspace_from_excel(excel)
    assert ws1.project_id == ws2.project_id
    assert ws1.project_id.startswith("ta_")


def test_title_abstract_workspace_id_diff_for_diff_excel(tmp_path: Path) -> None:
    settings_path = _settings(tmp_path)
    service = TitleAbstractService(tmp_path, settings_path)
    excel_a = tmp_path / "A.xlsx"
    excel_b = tmp_path / "B.xlsx"
    ws_a = service._workspace_from_excel(excel_a)
    ws_b = service._workspace_from_excel(excel_b)
    assert ws_a.project_id != ws_b.project_id
    assert "projects" in str(ws_a.root_dir)
    assert "projects" in str(ws_b.root_dir)
