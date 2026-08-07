from __future__ import annotations

from typing import Any


_PROCESS_HANDLERS: dict[str, Any] = {}
_BUILTINS_REGISTERED = False


def register_process_handler(handler) -> None:
    instance = handler() if isinstance(handler, type) else handler
    process_type = getattr(instance, "process_type", "")
    if not process_type:
        raise ValueError("Process handler must define process_type.")
    _PROCESS_HANDLERS[process_type] = instance


def get_process_handler(process_type: str):
    return _PROCESS_HANDLERS.get(process_type)


def list_process_types() -> list[dict]:
    ensure_builtin_handlers()
    items = []
    for process_type, handler in sorted(_PROCESS_HANDLERS.items()):
        definition = handler.get_definition()
        items.append(
            {
                "process_type": process_type,
                "display_name": definition.display_name,
                "description": definition.description,
                "supports_preview": definition.supports_preview,
                "supports_incremental": definition.supports_incremental,
                "supports_rebuild": definition.supports_rebuild,
                "default_configuration": definition.default_configuration,
            }
        )
    return items


def ensure_builtin_handlers() -> None:
    global _BUILTINS_REGISTERED
    if _BUILTINS_REGISTERED:
        return
    from logger.logger_json_import_handler import LoggerJsonImportHandler

    register_process_handler(LoggerJsonImportHandler())
    _BUILTINS_REGISTERED = True
