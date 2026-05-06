from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.db import get_connection
from src.title_abstract.exporter import TA_OUTPUT_COLUMNS, TitleAbstractExporter
from src.title_abstract.repository import TARepository, TA_NEW


def test_ta_exporter_column_order(tmp_path: Path) -> None:
    repo = TARepository(get_connection(tmp_path / "ta.sqlite"))
    repo.initialize()
    repo.upsert_rows(tmp_path / "in.xlsx", "Sheet1", [(2, "A", "AA")])
    rec = repo.queue((TA_NEW,))[0]
    repo.mark_done(
        rec.id,
        decision="INCLUDE",
        exclude_reason="",
        construct="target construct",
        note="ok",
        screening_model="gemini / gemini-2.5-flash",
        raw_response="{}",
    )
    excel = tmp_path / "out.xlsx"
    csv = tmp_path / "out.csv"
    TitleAbstractExporter(repo, excel_path=excel, csv_path=csv).export()
    frame = pd.read_excel(excel)
    assert list(frame.columns) == TA_OUTPUT_COLUMNS

