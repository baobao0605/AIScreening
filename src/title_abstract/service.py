"""Title-abstract screening workflow service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Callable

from src.config import load_settings
from src.db import get_connection
from src.logger import configure_logging
from src.project_workspace import ProjectWorkspace
from src.providers.factory import create_provider
from src.title_abstract.excel_loader import TitleAbstractRow, load_title_abstract_rows
from src.title_abstract.exporter import TitleAbstractExporter
from src.title_abstract.prompt_builder import build_title_abstract_prompt
from src.title_abstract.repository import (
    TA_NEW,
    TA_SCREEN_FAILED_RETRY,
    TA_FAILED,
    TARepository,
)
from src.title_abstract.validator import TitleAbstractValidationError, validate_title_abstract_output


@dataclass(slots=True)
class TARunSummary:
    queued: int
    done: int
    failed: int
    exported_rows: int


class TitleAbstractService:
    def __init__(self, base_dir: Path, config_path: Path | None = None) -> None:
        self.base_dir = base_dir
        self.config_path = config_path
        self.settings = load_settings(base_dir, config_path=config_path)

    def _workspace_from_excel(self, excel_path: Path) -> ProjectWorkspace:
        from src.project_workspace import make_project_id

        pid = f"ta_{make_project_id(excel_path)}"
        root = self.settings.output_dir / "projects" / pid
        return ProjectWorkspace(
            input_dir=excel_path.resolve(),
            project_id=pid,
            root_dir=root,
            database_path=root / "title_abstract.sqlite",
            excel_path=root / "title_abstract_screening_log.xlsx",
            csv_path=root / "title_abstract_screening_log.csv",
            run_log_path=root / "run.log",
            error_log_path=root / "error.log",
            prompt_snapshot_path=root / "title_abstract_prompt_snapshot.txt",
            settings_snapshot_path=root / "settings_snapshot.json",
        )

    def _prepare_runtime(
        self,
        *,
        excel_path: Path,
        provider_name: str,
        api_key: str,
        model: str,
        base_url: str,
        prompt_text: str,
        run_mode: str,
    ) -> tuple[ProjectWorkspace, TARepository, object]:
        workspace = self._workspace_from_excel(excel_path)
        workspace.root_dir.mkdir(parents=True, exist_ok=True)
        connection = get_connection(workspace.database_path)
        repository = TARepository(connection)
        repository.initialize()
        provider = create_provider(
            settings=self.settings,
            provider_name=provider_name,
            api_key=api_key or None,
            model=model or None,
            base_url=base_url or None,
        )
        logger = configure_logging(workspace.root_dir, self.settings.app.log_level)
        logger.info("Title-Abstract run started. project=%s mode=%s", workspace.project_id, run_mode)
        workspace.prompt_snapshot_path.write_text(prompt_text, encoding="utf-8")
        snapshot = {
            "mode": "title_abstract",
            "input_excel": str(excel_path.resolve()),
            "project_id": workspace.project_id,
            "provider": provider_name,
            "model": model,
            "base_url": base_url,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "run_mode": run_mode,
        }
        workspace.settings_snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            shutil.copy2(excel_path, workspace.root_dir / "original_input_snapshot.xlsx")
        except Exception:
            pass
        return workspace, repository, provider

    def run(
        self,
        *,
        excel_path: Path,
        provider_name: str,
        api_key: str,
        model: str,
        base_url: str,
        prompt_text: str,
        run_mode: str,
        should_cancel: Callable[[], bool] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_started: Callable[[dict[str, int]], None] | None = None,
        on_record_started: Callable[[dict[str, str]], None] | None = None,
        on_record_finished: Callable[[dict[str, str]], None] | None = None,
        on_record_error: Callable[[dict[str, str]], None] | None = None,
        on_finished: Callable[[TARunSummary], None] | None = None,
        on_cancelled: Callable[[TARunSummary], None] | None = None,
    ) -> TARunSummary:
        workspace, repository, provider = self._prepare_runtime(
            excel_path=excel_path,
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            base_url=base_url,
            prompt_text=prompt_text,
            run_mode=run_mode,
        )
        rows = load_title_abstract_rows(excel_path)
        repository.upsert_rows(excel_path, "Sheet1", [(r.row_index, r.title, r.abstract) for r in rows])

        if run_mode == "retry_failed":
            queue = repository.queue((TA_SCREEN_FAILED_RETRY, TA_FAILED))
        elif run_mode == "new_only":
            queue = repository.queue((TA_NEW,))
        else:
            queue = repository.queue((TA_NEW, TA_SCREEN_FAILED_RETRY))
        done = 0
        failed = 0
        queued = len(queue)
        if on_started is not None:
            on_started({"total_count": queued})
        provider_display = f"{provider.provider_name} / {provider.model_name}"
        for item in queue:
            if should_cancel is not None and should_cancel():
                break
            repository.set_screening(item.id)
            if on_record_started is not None:
                on_record_started(
                    {
                        "row_index": str(item.row_index),
                        "title": item.title,
                        "status": "Running",
                    }
                )
            prompt = build_title_abstract_prompt(
                criteria_prompt=prompt_text,
                title=item.title,
                abstract=item.abstract,
            )
            raw_response: str | None = None
            try:
                raw_response = provider.screen(prompt)
                validated = validate_title_abstract_output(raw_response)
                repository.mark_done(
                    item.id,
                    decision=validated["Decision"],
                    exclude_reason=validated["Exclude reason"],
                    construct=validated["Construct"],
                    note=validated["Note"],
                    screening_model=provider_display,
                    raw_response=raw_response,
                )
                done += 1
                if on_record_finished is not None:
                    on_record_finished(
                        {
                            "row_index": str(item.row_index),
                            "title": item.title,
                            "status": "Done",
                            "decision": validated["Decision"],
                            "model": provider_display,
                        }
                    )
            except (TitleAbstractValidationError, Exception) as exc:
                error_message = str(exc)
                lowered = error_message.casefold()
                if "503" in lowered or "unavailable" in lowered or "high demand" in lowered:
                    error_message = (
                        f"{error_message} | Gemini is temporarily unavailable or under high demand. "
                        "You can click Retry Failed later."
                    )
                repository.mark_failed(item.id, error_message, raw_response)
                failed += 1
                if on_record_error is not None:
                    on_record_error(
                        {
                            "row_index": str(item.row_index),
                            "title": item.title,
                            "status": "Error",
                            "error": error_message,
                        }
                    )
                if on_log is not None:
                    on_log(f"Row {item.row_index} failed: {error_message}")
        exported_rows = TitleAbstractExporter(
            repository,
            excel_path=workspace.excel_path,
            csv_path=workspace.csv_path,
        ).export()
        summary = TARunSummary(queued=queued, done=done, failed=failed, exported_rows=exported_rows)
        if should_cancel is not None and should_cancel():
            if on_cancelled is not None:
                on_cancelled(summary)
        else:
            if on_finished is not None:
                on_finished(summary)
        return summary
