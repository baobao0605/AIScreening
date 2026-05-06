from __future__ import annotations

from pathlib import Path

from src.db import get_connection
from src.title_abstract.repository import TARepository, TA_DONE, TA_NEW, TA_SCREEN_FAILED_RETRY


def test_ta_repository_upsert_and_queue(tmp_path: Path) -> None:
    db_path = tmp_path / "ta.sqlite"
    repo = TARepository(get_connection(db_path))
    repo.initialize()
    inserted = repo.upsert_rows(tmp_path / "in.xlsx", "Sheet1", [(2, "A", "AA"), (3, "B", "BB")])
    assert inserted == 2
    inserted_again = repo.upsert_rows(tmp_path / "in.xlsx", "Sheet1", [(2, "A", "AA")])
    assert inserted_again == 0
    queue = repo.queue((TA_NEW,))
    assert len(queue) == 2


def test_ta_repository_retry_queue(tmp_path: Path) -> None:
    db_path = tmp_path / "ta.sqlite"
    repo = TARepository(get_connection(db_path))
    repo.initialize()
    repo.upsert_rows(tmp_path / "in.xlsx", "Sheet1", [(2, "A", "AA")])
    record = repo.queue((TA_NEW,))[0]
    repo.mark_done(record.id, decision="INCLUDE", exclude_reason="", construct="unclear", note="n", screening_model="m", raw_response="{}")
    done_queue = repo.queue((TA_DONE,))
    assert len(done_queue) == 1
    repo.mark_failed(record.id, "oops")
    retry_queue = repo.queue((TA_SCREEN_FAILED_RETRY,))
    assert len(retry_queue) == 1

