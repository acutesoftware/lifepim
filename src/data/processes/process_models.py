from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ProcessTypeDefinition:
    process_type: str
    display_name: str
    description: str
    supports_preview: bool = True
    supports_incremental: bool = True
    supports_rebuild: bool = False
    default_configuration: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationMessage:
    level: str
    field: str
    message: str
    code: str = ""


@dataclass
class ValidationResult:
    valid: bool = True
    messages: list[ValidationMessage] = field(default_factory=list)

    def add(self, level: str, field: str, message: str, code: str = "") -> None:
        self.messages.append(ValidationMessage(level, field, message, code))
        if level == "error":
            self.valid = False


@dataclass
class ProcessRunResult:
    status: str = "success"
    summary: str = ""
    files_found: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    records_read: int = 0
    records_written: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    error_message: str = ""


class ProcessHandler(Protocol):
    process_type: str

    def get_definition(self) -> ProcessTypeDefinition:
        ...

    def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        ...

    def preview(self, config: dict[str, Any], context) -> ProcessRunResult:
        ...

    def run(self, config: dict[str, Any], context) -> ProcessRunResult:
        ...

    def rebuild(self, config: dict[str, Any], context) -> ProcessRunResult:
        ...
