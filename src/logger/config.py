from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common import data as main_data
from common import config as app_config
from common import settings as settings_mod


DEFAULT_SESSION_GAP_SECONDS = 60
DEFAULT_MINIMUM_SESSION_SECONDS = 3


@dataclass(frozen=True)
class LoggerConfig:
    database_path: Path
    mobile_source_path: Path | None
    aggie_source_path: Path | None
    session_gap_seconds: int = DEFAULT_SESSION_GAP_SECONDS
    minimum_session_seconds: int = DEFAULT_MINIMUM_SESSION_SECONDS
    main_database_path: Path | None = None


def load_logger_config(conn=None, user_id=None, username=None) -> LoggerConfig:
    settings_mod.ensure_settings_schema(conn)
    logger_settings = settings_mod.get_logger_settings(conn, user_id=user_id, username=username)
    db_path = settings_mod.get_setting("logger_database_path", "", conn).strip()
    mobile_path = settings_mod.get_setting("logger_mobile_source_path", "", conn).strip()
    aggie_path = settings_mod.get_setting("logger_aggie_source_path", "", conn).strip()
    gap = _int_setting(settings_mod.get_setting("logger_session_gap_seconds", str(DEFAULT_SESSION_GAP_SECONDS), conn), DEFAULT_SESSION_GAP_SECONDS)
    minimum = _int_setting(
        settings_mod.get_setting("logger_minimum_session_seconds", str(DEFAULT_MINIMUM_SESSION_SECONDS), conn),
        DEFAULT_MINIMUM_SESSION_SECONDS,
    )

    main_db_path = _main_database_path(conn)
    if not _looks_like_sqlite_path(db_path):
        db_path = str(_default_logger_database_path(main_db_path))
    if not mobile_path:
        mobile_path = logger_settings.get("raw_data_root") or ""
    return LoggerConfig(
        database_path=_expand_path(db_path),
        mobile_source_path=_optional_path(mobile_path),
        aggie_source_path=_optional_path(aggie_path),
        session_gap_seconds=max(1, gap),
        minimum_session_seconds=max(0, minimum),
        main_database_path=main_db_path,
    )


def _optional_path(value: str | None) -> Path | None:
    value = (value or "").strip()
    if not value:
        return None
    return _expand_path(value)


def _expand_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (Path(getattr(app_config, "user_folder", ".")).expanduser() / path).resolve()


def _default_logger_database_path(main_db_path: Path | None = None) -> Path:
    db_dir = main_db_path.parent if main_db_path else Path(getattr(app_config, "DB_FILE", ".")).expanduser().parent
    return db_dir / "logger.sqlite"


def _looks_like_sqlite_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return Path(text).suffix.lower() in {".db", ".sqlite", ".sqlite3"}


def _main_database_path(conn=None) -> Path | None:
    db_path = ""
    if conn is not None:
        try:
            row = conn.execute("PRAGMA database_list").fetchone()
            if row:
                db_path = row["file"] if hasattr(row, "keys") else row[2]
        except Exception:
            db_path = ""
    if not db_path:
        db_path = getattr(main_data, "DB_FILE", "") or getattr(app_config, "DB_FILE", "")
    if db_path:
        return Path(db_path).expanduser().resolve()
    return None


def _int_setting(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
