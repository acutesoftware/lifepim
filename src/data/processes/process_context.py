from __future__ import annotations

from dataclasses import dataclass

from .process_repository import ProcessRepository, utc_now


@dataclass
class ProcessRunContext:
    repository: ProcessRepository
    process_id: int
    process_run_id: int
    run_mode: str
    trigger_type: str = "manual"
    cancelled: bool = False

    def debug(self, code: str, text: str, context: dict | None = None) -> None:
        self.message("debug", code, text, context)

    def info(self, code: str, text: str, context: dict | None = None) -> None:
        self.message("info", code, text, context)

    def warning(self, code: str, text: str, context: dict | None = None) -> None:
        self.message("warning", code, text, context)

    def error(self, code: str, text: str, context: dict | None = None) -> None:
        self.message("error", code, text, context)

    def message(self, level: str, code: str, text: str, context: dict | None = None) -> None:
        self.repository.add_message(self.process_run_id, level, code, text, context)

    def register_file(self, file_info: dict) -> int:
        return self.repository.upsert_process_file(self.process_id, file_info)

    def update_file_result(self, process_file_id: int, status: str, counts: dict, message: str = "", detected_types: str = "") -> None:
        self.repository.update_file_result(process_file_id, self.process_run_id, status, counts, message, detected_types)
        self.repository.add_run_file(
            self.process_run_id,
            process_file_id,
            counts.get("source_path") or "",
            status,
            counts,
            message,
            started_at=counts.get("started_at_utc") or utc_now(),
        )

    def add_run_file(self, process_file_id: int | None, source_path: str, status: str, counts: dict, message: str = "") -> None:
        self.repository.add_run_file(self.process_run_id, process_file_id, source_path, status, counts, message)

    def check_cancelled(self) -> bool:
        return bool(self.cancelled)
