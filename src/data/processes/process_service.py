from __future__ import annotations

import logging
from pathlib import Path

from common import config as app_config
from common import settings as settings_mod

from .process_context import ProcessRunContext
from .process_models import ProcessRunResult, ValidationResult
from .process_registry import ensure_builtin_handlers, get_process_handler, list_process_types
from .process_repository import ProcessRepository, default_logger_config

log = logging.getLogger(__name__)


class ProcessService:
    def __init__(self, connection=None):
        ensure_builtin_handlers()
        self.repository = ProcessRepository(connection)

    def list_process_types(self) -> list[dict]:
        return list_process_types()

    def list_processes(self) -> list[dict]:
        return self._decorate_processes(self.repository.list_processes())

    def get_process(self, process_id: int) -> dict | None:
        process = self.repository.get_process(process_id)
        return self._decorate_process(process) if process else None

    def get_default_logger_process(self) -> dict | None:
        process = self.repository.first_process_by_type("logger_json_import")
        if process:
            process = self._apply_default_logger_paths(process)
        return self._decorate_process(process) if process else None

    def create_process(self, values: dict) -> int:
        values = dict(values)
        values.setdefault("process_type", "logger_json_import")
        values.setdefault("configuration", default_logger_config())
        return self.repository.save_process(None, values)

    def update_process(self, process_id: int, values: dict) -> int:
        existing = self.repository.get_process(process_id)
        if not existing:
            raise ValueError("Process not found.")
        merged_config = dict(existing.get("configuration") or {})
        merged_config.update(values.get("configuration") or {})
        values = dict(values)
        values["configuration"] = merged_config
        values["process_type"] = existing["process_type"]
        return self.repository.save_process(process_id, values)

    def validate_process(self, process_id: int) -> ValidationResult:
        process = self.repository.get_process(process_id)
        if not process:
            result = ValidationResult(False)
            result.add("error", "process", "Process not found.", "PROCESS_NOT_FOUND")
            return result
        handler = get_process_handler(process["process_type"])
        if not handler:
            result = ValidationResult(False)
            result.add("error", "process_type", "Handler unavailable for this process type.", "HANDLER_UNAVAILABLE")
            return result
        config = self._handler_config(handler, process.get("configuration") or {})
        return handler.validate_config(config)

    def preview_process(self, process_id: int, trigger_type: str = "manual") -> ProcessRunResult:
        return self._execute(process_id, "preview", trigger_type)

    def run_process(self, process_id: int, trigger_type: str = "manual") -> ProcessRunResult:
        return self._execute(process_id, "incremental", trigger_type)

    def rebuild_process(self, process_id: int, trigger_type: str = "manual") -> ProcessRunResult:
        return self._execute(process_id, "rebuild", trigger_type)

    def list_runs(self, process_id: int | None = None, filters: dict | None = None, limit: int = 100) -> list[dict]:
        return self.repository.list_runs(process_id=process_id, filters=filters, limit=limit)

    def get_run_details(self, run_id: int) -> dict:
        run = self.repository.get_run(run_id)
        if not run:
            raise ValueError("Process run not found.")
        return {
            "run": run,
            "files": self.repository.list_run_files(run_id),
            "messages": self.repository.list_run_messages(run_id),
        }

    def _execute(self, process_id: int, run_mode: str, trigger_type: str) -> ProcessRunResult:
        self.repository.recover_stale_running_runs()
        process = self.repository.get_process(process_id)
        if not process:
            raise ValueError("Process not found.")
        handler = get_process_handler(process["process_type"])
        if not handler:
            raise ValueError("Handler unavailable for this process type.")
        if run_mode != "preview" and not process.get("is_enabled"):
            raise ValueError("This process is disabled.")
        if self.repository.has_running_process(process_id):
            raise ValueError("This process is already running.")
        config = self._handler_config(handler, process.get("configuration") or {})
        validation = handler.validate_config(config)
        if not validation.valid:
            raise ValueError("; ".join(msg.message for msg in validation.messages if msg.level == "error") or "Configuration is invalid.")

        run_id = self.repository.create_run(process_id, trigger_type, run_mode)
        context = ProcessRunContext(self.repository, process_id, run_id, run_mode, trigger_type)
        self.repository.mark_run_running(run_id)
        try:
            if run_mode == "preview":
                result = handler.preview(config, context)
            elif run_mode == "rebuild":
                result = handler.rebuild(config, context)
            else:
                result = handler.run(config, context)
        except Exception as exc:
            log.exception("Process run failed unexpectedly", extra={"process_id": process_id, "run_mode": run_mode})
            context.error("UNEXPECTED_ERROR", "The process failed unexpectedly. See the application log for details.")
            result = ProcessRunResult(status="failed", summary="Process failed.", error_message=str(exc))
        self.repository.finalise_run(run_id, result)
        result.process_run_id = run_id
        return result

    def _handler_config(self, handler, config: dict) -> dict:
        definition = handler.get_definition()
        merged = dict(definition.default_configuration or {})
        merged.update(config or {})
        return merged

    def _decorate_processes(self, processes: list[dict]) -> list[dict]:
        return [self._decorate_process(process) for process in processes]

    def _decorate_process(self, process: dict) -> dict:
        process = dict(process)
        handler = get_process_handler(process["process_type"])
        process["handler_available"] = bool(handler)
        if handler:
            definition = handler.get_definition()
            process["process_type_name"] = definition.display_name
            process["type_definition"] = definition
        else:
            process["process_type_name"] = process["process_type"]
            process["type_definition"] = None
        config = process.get("configuration") or {}
        resolved_source = _resolve_process_path(config.get("source_folder") or "")
        resolved_database = _resolve_process_path(config.get("database_path") or "")
        process["resolved_configuration"] = {
            **config,
            "source_folder": resolved_source,
            "database_path": resolved_database,
        }
        process["input_summary"] = resolved_source or "Not configured"
        process["output_summary"] = resolved_database or ""
        return process

    def _apply_default_logger_paths(self, process: dict) -> dict:
        config = dict(process.get("configuration") or {})
        updated = False
        if not str(config.get("source_folder") or "").strip():
            logger_settings = settings_mod.get_logger_settings(self.repository.conn)
            source_folder = logger_settings.get("mobile_source_path") or logger_settings.get("raw_data_root") or ""
            if source_folder:
                config["source_folder"] = source_folder
                updated = True
        if str(config.get("file_pattern") or "").strip() in {"", "*.json"}:
            config["file_pattern"] = "*.json;*.jsonl"
            updated = True
        if updated:
            self.repository.save_process(
                process["process_id"],
                {
                    "process_name": process["process_name"],
                    "description": process.get("description") or "",
                    "is_enabled": bool(process.get("is_enabled")),
                    "configuration": config,
                },
            )
            process = self.repository.get_process(process["process_id"]) or process
        return process


def _resolve_process_path(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    data_folder = getattr(app_config, "data_folder", "") or getattr(app_config, "user_folder", ".")
    return str(Path(text.replace("<LIFEPIM_DATA>", data_folder)).expanduser())
