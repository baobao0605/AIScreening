from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.title_abstract.excel_loader import TitleAbstractExcelError, load_title_abstract_rows


def test_excel_loader_reads_first_two_columns(tmp_path: Path) -> None:
    path = tmp_path / "ta.xlsx"
    pd.DataFrame(
        {
            "Title": ["Paper A", "Paper B"],
            "Abstract": ["A abstract", "B abstract"],
            "Other": [1, 2],
        }
    ).to_excel(path, index=False)
    rows = load_title_abstract_rows(path)
    assert len(rows) == 2
    assert rows[0].title == "Paper A"
    assert rows[0].abstract == "A abstract"


def test_excel_loader_skips_empty_rows(tmp_path: Path) -> None:
    path = tmp_path / "ta.xlsx"
    pd.DataFrame({"Title": ["Paper A", ""], "Abstract": ["A abstract", ""]}).to_excel(path, index=False)
    rows = load_title_abstract_rows(path)
    assert len(rows) == 1


def test_excel_loader_raises_when_columns_insufficient(tmp_path: Path) -> None:
    path = tmp_path / "ta.xlsx"
    pd.DataFrame({"Title": ["Paper A"]}).to_excel(path, index=False)
    with pytest.raises(TitleAbstractExcelError):
        load_title_abstract_rows(path)

