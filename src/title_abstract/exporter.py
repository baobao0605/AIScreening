"""Exporter for title-abstract screening outputs."""

from __future__ import annotations

from pathlib import Path

from src.title_abstract.repository import TARepository
from src.utils import ensure_parent_dir


TA_OUTPUT_COLUMNS = [
    "Title",
    "Abstract",
    "Decision",
    "Exclude reason",
    "Construct",
    "Note",
    "Model",
    "Status",
    "Error",
]


class TitleAbstractExporter:
    def __init__(self, repository: TARepository, *, excel_path: Path, csv_path: Path | None) -> None:
        self.repository = repository
        self.excel_path = excel_path
        self.csv_path = csv_path

    def export(self) -> int:
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pandas/openpyxl is required for export.") from exc
        rows = self.repository.export_rows()
        frame = pd.DataFrame(rows, columns=TA_OUTPUT_COLUMNS)
        ensure_parent_dir(self.excel_path)
        with pd.ExcelWriter(self.excel_path, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name="title_abstract_screening_log", index=False)
        if self.csv_path is not None:
            ensure_parent_dir(self.csv_path)
            frame.to_csv(self.csv_path, index=False)
        return len(frame.index)

