"""Excel loader for title-abstract screening."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class TitleAbstractExcelError(ValueError):
    """Raised when title-abstract Excel input is invalid."""


@dataclass(slots=True)
class TitleAbstractRow:
    row_index: int
    title: str
    abstract: str


def load_title_abstract_rows(excel_path: Path) -> list[TitleAbstractRow]:
    if not excel_path.exists():
        raise TitleAbstractExcelError(f"Excel file does not exist: {excel_path}")
    if excel_path.suffix.lower() != ".xlsx":
        raise TitleAbstractExcelError("Only .xlsx files are supported.")
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise TitleAbstractExcelError("pandas/openpyxl is required to read Excel files.") from exc

    frame = pd.read_excel(excel_path, sheet_name=0)
    if frame.shape[1] < 2:
        raise TitleAbstractExcelError(
            "Excel must have at least two columns. Column A is Title and Column B is Abstract."
        )

    rows: list[TitleAbstractRow] = []
    for idx, series in frame.iterrows():
        title = "" if series.iloc[0] is None else str(series.iloc[0]).strip()
        abstract = "" if series.iloc[1] is None else str(series.iloc[1]).strip()
        if not title and not abstract:
            continue
        rows.append(TitleAbstractRow(row_index=int(idx) + 2, title=title, abstract=abstract))
    return rows

