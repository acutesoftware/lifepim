import calendar as cal
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for

from common import data
from common import projects as projects_mod
from common import settings as settings_mod
from common.utils import get_tabs, get_side_tabs, get_table_def, paginate_items, build_pagination
import common.config as cfg
from utils import importer
from modules.calendar.services import calendar_index


calendar_bp = Blueprint(
    "calendar",
    __name__,
    url_prefix="/calendar",
    template_folder="templates",
    static_folder="static",
)


def _month_nav(year, month):
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    return prev_year, prev_month, next_year, next_month


def _week_nav(anchor_date):
    prev_week = anchor_date - timedelta(days=7)
    next_week = anchor_date + timedelta(days=7)
    return prev_week, next_week


def _date_to_year_month(date_str):
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.year, parsed.month
    except (ValueError, TypeError):
        return None


def _parse_date_param(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _calendar_jump_context(current_view, selected_date, project=None, day_source_params=None):
    current_year = date.today().year
    return {
        "jump_current_view": current_view,
        "jump_selected_date": selected_date,
        "jump_years": list(range(current_year - 20, current_year + 6)),
        "jump_months": [(month, cal.month_name[month]) for month in range(1, 13)],
        "jump_project": project,
        "jump_day_source_params": day_source_params or {},
    }


def _get_calendar_table():
    return get_table_def("calendar")


def _ensure_calendar_index():
    calendar_index.ensure_calendar_schema(data.conn)


def _fetch_events(project=None, start_date=None, end_date=None, source_keys=None):
    _ensure_calendar_index()
    if start_date and end_date:
        return calendar_index.fetch_calendar_items_for_days(
            start_date,
            end_date,
            sources=source_keys,
            project=project,
            conn=data.conn,
        )
    return _fetch_agenda_items(project=project, source_keys=source_keys)


def _append_project_filter(where, params, column, project):
    if not project or project in ("any", "All", "all", "ALL", "spacer"):
        return
    if project.lower() == "unmapped":
        where.append(f"(COALESCE({column}, '') = '' OR lower({column}) = lower(?))")
        params.append(project)
        return
    where.append(f"(lower(COALESCE({column}, '')) = lower(?) OR lower(COALESCE({column}, '')) LIKE lower(?) || '/%')")
    params.extend([project, project])


def _fetch_agenda_items(
    project=None,
    source_keys=None,
    start_date=None,
    end_date=None,
    event_type=None,
    category=None,
    status=None,
    search=None,
    recurring_only=False,
):
    _ensure_calendar_index()
    params = []
    where = ["ci.is_visible = 1", "cs.enabled = 1"]
    _append_project_filter(where, params, "ci.project", project)
    source_list = [s for s in (source_keys or []) if s]
    if source_list:
        where.append("ci.source_key IN (" + ",".join(["?"] * len(source_list)) + ")")
        params.extend(source_list)
    if start_date:
        where.append("ci.end_date >= ?")
        params.append(start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else start_date)
    if end_date:
        where.append("ci.start_date < ?")
        params.append(end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else end_date)
    if event_type:
        where.append("ci.event_type = ?")
        params.append(event_type)
    if category:
        where.append("ci.category = ?")
        params.append(category)
    if status:
        where.append("ci.status = ?")
        params.append(status)
    else:
        where.append("ci.status != 'cancelled'")
    if recurring_only:
        where.append("ci.recurrence_parent_id IS NOT NULL")
    if search:
        where.append("(lower(ci.title) LIKE lower(?) OR lower(COALESCE(ci.content, '')) LIKE lower(?))")
        params.extend([f"%{search}%", f"%{search}%"])
    rows = data.conn.execute(
        """
        SELECT ci.*, ci.start_date AS item_date, 1 AS day_number, 1 AS total_days,
               1 AS is_first_day, 1 AS is_last_day, cs.source_name,
               cs.default_color, cs.default_text_color, cs.default_icon
        FROM lp_calendar_items ci
        JOIN lp_calendar_sources cs ON cs.source_key = ci.source_key
        WHERE """ + " AND ".join(where) + """
        ORDER BY ci.start_date, ci.start_time, ci.sort_priority, ci.title
        """,
        params,
    ).fetchall()
    return [_event_from_index_row(row) for row in rows]


def _table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return set()
    columns = set()
    for row in rows:
        try:
            columns.add(row["name"])
        except (KeyError, TypeError):
            columns.add(row[1])
    return columns


def _parse_day_sources(args):
    _ensure_calendar_index()
    source_rows = calendar_index.fetch_calendar_sources(data.conn)
    source_defaults = {row["source_key"]: bool(row["visible_by_default"]) for row in source_rows}

    defaults = settings_mod.get_calendar_view_settings(data.conn)

    def checked(name, default=False):
        values = args.getlist(name) if hasattr(args, "getlist") else []
        value = values[-1] if values else args.get(name)
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    legacy_sources = {
        "events": checked("show_events", defaults["events"]),
        "files": checked("show_files", defaults["files"]),
        "usage": checked("show_usage", defaults["usage"]),
    }
    selected = set()
    if "sources" in args:
        raw_sources = args.get("sources", "")
        selected = {part.strip() for part in raw_sources.split(",") if part.strip()}
        if any(key in args for key in ("show_events", "show_files", "show_usage")):
            for key in ("manual", "recurring", "birthdays", "holidays_au", "holidays_sa", "tasks"):
                if legacy_sources["events"]:
                    selected.add(key)
                else:
                    selected.discard(key)
            for key in ("files", "media", "audio"):
                if legacy_sources["files"]:
                    selected.add(key)
                else:
                    selected.discard(key)
            if legacy_sources["usage"]:
                selected.add("usage")
            else:
                selected.discard("usage")
    elif hasattr(args, "getlist") and args.getlist("source"):
        selected = {part.strip() for part in args.getlist("source") if part.strip()}
    else:
        selected = {key for key, enabled in source_defaults.items() if enabled}
        for key in ("manual", "recurring", "birthdays", "holidays_au", "holidays_sa", "tasks"):
            if legacy_sources["events"]:
                selected.add(key)
            else:
                selected.discard(key)
        for key in ("files", "media", "audio"):
            if legacy_sources["files"]:
                selected.add(key)
            else:
                selected.discard(key)
        if legacy_sources["usage"]:
            selected.add("usage")
        else:
            selected.discard("usage")
        if "show_events" in args:
            for key in ("manual", "recurring", "birthdays", "holidays_au", "holidays_sa", "tasks"):
                if legacy_sources["events"]:
                    selected.add(key)
                else:
                    selected.discard(key)
        if "show_files" in args:
            for key in ("files", "media", "audio"):
                if legacy_sources["files"]:
                    selected.add(key)
                else:
                    selected.discard(key)
        if "show_usage" in args:
            if legacy_sources["usage"]:
                selected.add("usage")
            else:
                selected.discard("usage")
    valid_keys = {row["source_key"] for row in source_rows}
    selected = selected & valid_keys
    media_selected = bool({"files", "media", "audio"} & selected)
    event_selected = bool({"manual", "recurring", "birthdays", "holidays_au", "holidays_sa", "tasks"} & selected)
    sources = {
        **legacy_sources,
        "events": event_selected,
        "files": media_selected,
        "usage": "usage" in selected,
        "selected": selected,
        "rows": source_rows,
    }
    if any(key in args for key in ("show_events", "show_files", "show_usage")):
        settings_mod.save_calendar_view_settings(legacy_sources, data.conn)
    params = {
        "show_events": "1" if legacy_sources["events"] else "0",
        "show_files": "1" if legacy_sources["files"] else "0",
        "show_usage": "1" if legacy_sources["usage"] else "0",
        "sources": ",".join(sorted(selected)),
    }
    return sources, params


def _source_hidden_fields(**values):
    return [{"name": key, "value": value} for key, value in values.items() if value not in (None, "")]


def _project_options(conn):
    options = [{"value": "", "label": "No project / Unmapped"}]
    seen = {""}
    try:
        for row in projects_mod.projects_list_sidebar(conn=conn):
            value = (row.get("project_id") or "").strip()
            label = (row.get("project_name") or value).strip()
            if value and value not in seen:
                options.append({"value": value, "label": label})
                seen.add(value)
    except Exception:
        pass
    for side_tab in get_side_tabs():
        value = (side_tab.get("id") if isinstance(side_tab, dict) else str(side_tab)).strip()
        label = (side_tab.get("label") if isinstance(side_tab, dict) else value).strip()
        if not value or value in ("spacer", "any", "All", "all", "ALL") or value in seen:
            continue
        options.append({"value": value, "label": label or value})
        seen.add(value)
    try:
        rows = conn.execute(
            "SELECT DISTINCT project FROM lp_calendar_events WHERE COALESCE(project, '') != '' ORDER BY lower(project)"
        ).fetchall()
    except Exception:
        rows = []
    for row in rows:
        value = (row["project"] or "").strip()
        if value and value not in seen:
            options.append({"value": value, "label": value})
            seen.add(value)
    if "General" not in seen:
        options.insert(1, {"value": "General", "label": "General"})
    return options


def _default_list_dates():
    today = date.today()
    start = date(today.year, today.month, 1)
    next_month = today.month + 1
    next_year = today.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    end = date(next_year, next_month, 1) - timedelta(days=1)
    return start, end


def _project_label(project, conn):
    if not project:
        return ""
    project_lower = project.lower()
    for option in _project_options(conn):
        if option["value"].lower() == project_lower:
            return option["label"]
    return project


def _calendar_title(base, project):
    label = _project_label(project, data.conn)
    return f"{base} - {label}" if label else base


def _calendar_media_settings(conn):
    settings = settings_mod.get_calendar_view_settings(conn)
    return {
        "thumbnail_size": settings["thumbnail_size"],
        "thumbnail_limit": settings["thumbnail_limit"],
        "thumbnail_class": f"calendar-thumb-{settings['thumbnail_size']}",
    }


def _fetch_calendar_media(conn, start_day, end_day, include_media=True, include_audio=True):
    items = []
    if include_media:
        items.extend(_fetch_media_rows(conn, start_day, end_day))
    if include_audio:
        items.extend(_fetch_audio_rows(conn, start_day, end_day))
    return sorted(items, key=lambda item: ((item.get("display_date") or ""), (item.get("filename") or "").lower()))


def _fetch_image_media(conn, start_day, end_day, source_keys=None):
    source_keys = set(source_keys or [])
    include_media = not source_keys or "media" in source_keys or "files" in source_keys
    include_audio = "audio" in source_keys
    return _fetch_calendar_media(conn, start_day, end_day, include_media=include_media, include_audio=include_audio)


def _fetch_media_rows(conn, start_day, end_day):
    cols = _table_columns(conn, "lp_media")
    if not {"media_id", "path", "filename", "media_type", "mtime_utc"}.issubset(cols):
        return []
    start_str = start_day.strftime("%Y-%m-%d")
    end_str = end_day.strftime("%Y-%m-%d")
    meta_cols = _table_columns(conn, "lp_media_meta")
    if {"media_id", "taken_utc"}.issubset(meta_cols):
        rows = conn.execute(
            "SELECT m.media_id, m.path, m.filename, m.ext, m.media_type, "
            "m.size_bytes, m.mtime_utc, meta.taken_utc, "
            "m.mtime_utc AS display_date "
            "FROM lp_media m "
            "LEFT JOIN lp_media_meta meta ON meta.media_id = m.media_id "
            "WHERE lower(m.media_type) IN ('image', 'video') "
            "AND m.mtime_utc >= ? "
            "AND m.mtime_utc < ? "
            "ORDER BY display_date, lower(m.filename)",
            (start_str, end_str),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT media_id, path, filename, ext, media_type, size_bytes, "
            "mtime_utc, NULL AS taken_utc, mtime_utc AS display_date "
            "FROM lp_media "
            "WHERE lower(media_type) IN ('image', 'video') "
            "AND mtime_utc >= ? "
            "AND mtime_utc < ? "
            "ORDER BY display_date, lower(filename)",
            (start_str, end_str),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["source_type"] = "media"
        item["folder_key"] = _folder_key(item.get("path"))
        item["folder_path"] = _folder_path(item.get("path"))
        items.append(item)
    return items


def _fetch_audio_rows(conn, start_day, end_day):
    cols = _table_columns(conn, "lp_audio")
    if not {"id", "file_name", "path", "date_modified"}.issubset(cols):
        return []
    start_str = start_day.strftime("%Y-%m-%d")
    end_str = end_day.strftime("%Y-%m-%d")
    select_cols = [
        "id AS audio_id",
        "file_name AS filename",
        "path",
        "file_type AS ext" if "file_type" in cols else "NULL AS ext",
        "size AS size_bytes" if "size" in cols else "NULL AS size_bytes",
        "date_modified AS mtime_utc",
        "date_modified AS display_date",
    ]
    rows = conn.execute(
        "SELECT "
        + ", ".join(select_cols)
        + " FROM lp_audio "
        + "WHERE date_modified IS NOT NULL "
        + "AND date_modified >= ? "
        + "AND date_modified < ? "
        + "ORDER BY display_date, lower(file_name)",
        (start_str, end_str),
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["media_type"] = "audio"
        item["source_type"] = "audio"
        item["folder_key"] = _folder_key(item.get("path"))
        item["folder_path"] = _folder_path(item.get("path"))
        items.append(item)
    return items


def _folder_path(path):
    path = (path or "").strip()
    if not path:
        return ""
    normalized = os.path.normpath(path)
    if os.path.splitext(normalized)[1]:
        normalized = os.path.dirname(normalized)
    return normalized


def _folder_key(path):
    path = (path or "").strip()
    if not path:
        return ""
    normalized = os.path.normpath(path)
    if os.path.splitext(normalized)[1]:
        normalized = os.path.dirname(normalized)
    return normalized.lower()


def _order_calendar_media_previews(items):
    seen_folders = set()
    first_by_folder = []
    remaining = []
    for item in items:
        folder = item.get("folder_key") or _folder_key(item.get("path"))
        if folder and folder not in seen_folders:
            first_by_folder.append(item)
            seen_folders.add(folder)
        else:
            remaining.append(item)
    return first_by_folder + remaining


def _order_grouped_calendar_media(grouped):
    return {media_day: _order_calendar_media_previews(items) for media_day, items in grouped.items()}


def _fetch_day_media(conn, day):
    return _order_calendar_media_previews(_fetch_calendar_media(conn, day, day + timedelta(days=1)))


def _fetch_video_media_by_event_date(conn, events):
    event_dates = set()
    for event in events:
        parsed = _parse_date_param(event.get("date"))
        if parsed:
            event_dates.add(parsed)
    if not event_dates:
        return {}
    start_day = min(event_dates)
    end_day = max(event_dates) + timedelta(days=1)
    videos = [
        item
        for item in _fetch_media_rows(conn, start_day, end_day)
        if (item.get("media_type") or "").lower() == "video"
    ]
    grouped = {}
    for item in videos:
        display_date = (item.get("display_date") or item.get("mtime_utc") or "")[:10]
        try:
            media_day = datetime.strptime(display_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if media_day in event_dates:
            grouped.setdefault(media_day.strftime("%Y-%m-%d"), []).append(item)
    return grouped


def _group_media_by_date(items):
    grouped = {}
    for item in items:
        display_date = (item.get("display_date") or item.get("mtime_utc") or "")[:10]
        try:
            day = datetime.strptime(display_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        grouped.setdefault(day, []).append(item)
    return grouped


def _group_media_by_month_day(items):
    grouped = {}
    for item in items:
        display_date = (item.get("display_date") or item.get("mtime_utc") or "")[:10]
        try:
            parsed = datetime.strptime(display_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        grouped.setdefault(parsed.month, set()).add(parsed.day)
    return grouped


def _fetch_day_files(conn, day):
    cols = _table_columns(conn, "lp_files")
    if not {"path", "mtime_utc"}.issubset(cols):
        return []
    select_cols = ["id" if "id" in cols else "rowid AS id", "path", "mtime_utc"]
    if "filelist_name" in cols:
        select_cols.append("filelist_name")
    if "file_type" in cols:
        select_cols.append("file_type")
    if "size" in cols:
        select_cols.append("size")
    day_str = day.strftime("%Y-%m-%d")
    where = ["substr(mtime_utc, 1, 10) = ?"]
    if "is_deleted" in cols:
        where.append("COALESCE(is_deleted, 0) = 0")
    rows = conn.execute(
        "SELECT "
        + ", ".join(select_cols)
        + " FROM lp_files "
        + "WHERE "
        + " AND ".join(where)
        + " ORDER BY mtime_utc, lower(path)",
        (day_str,),
    ).fetchall()
    files = []
    media_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".mp4", ".mov", ".avi", ".mkv", ".webm"}
    for row in rows:
        item = dict(row)
        path = item.get("path") or ""
        ext = os.path.splitext(path)[1].lower()
        file_type = (item.get("file_type") or "").strip().lower()
        if ext in media_exts or file_type in {"image", "images", "media", "photo", "video"}:
            continue
        item["filename"] = item.get("filelist_name") or os.path.basename(path) or path
        files.append(item)
    return files


def _parse_time_to_minutes(time_str):
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours * 60 + minutes
    except (ValueError, TypeError, IndexError):
        return None


def _build_timeslots():
    start_val = int(cfg.CAL_TIMESLOT_START_TIME)
    end_val = int(cfg.CAL_TIMESLOT_END_TIME)
    slot_minutes = int(cfg.CAL_TIMESLOT_MINUTES)
    start_hour = start_val // 100
    start_min = start_val % 100
    end_hour = end_val // 100
    end_min = end_val % 100
    start_total = start_hour * 60 + start_min
    end_total = end_hour * 60 + end_min
    slots = []
    current = start_total
    while current <= end_total:
        hour = current // 60
        minute = current % 60
        slots.append({"label": f"{hour:02d}:{minute:02d}", "minutes": current})
        current += slot_minutes
    return slots


def _time_val_to_minutes(value):
    value_int = int(value)
    hours = value_int // 100
    minutes = value_int % 100
    return hours * 60 + minutes


def _read_csv_headers(csv_file_name):
    return importer.read_csv_headers(csv_file_name)


@calendar_bp.route("/jump", methods=["POST"])
def jump_route():
    current_view = request.form.get("view") or "day"
    project = request.form.get("proj") or None
    try:
        target = date(
            int(request.form.get("year", "")),
            int(request.form.get("month", "")),
            int(request.form.get("day", "")),
        )
    except (TypeError, ValueError):
        target = date.today()

    params = {"proj": project}
    for key in ("show_events", "show_files", "show_usage", "sources"):
        value = request.form.get(key)
        if key == "sources" and value:
            params[key] = value
        elif value in ("0", "1"):
            params[key] = value

    if current_view == "month":
        return redirect(
            url_for(
                "calendar.month_view_route",
                year=target.year,
                month=target.month,
                **params,
            )
        )
    if current_view == "week":
        return redirect(url_for("calendar.week_view_route", date=target.strftime("%Y-%m-%d"), **params))
    if current_view == "year":
        return redirect(url_for("calendar.year_view_route", year=target.year, **params))
    return redirect(url_for("calendar.day_view_route", date=target.strftime("%Y-%m-%d"), **params))


@calendar_bp.route("/")
def month_view_route():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    day_sources, day_source_params = _parse_day_sources(request.args)
    source_keys = day_sources["selected"]
    media_settings = _calendar_media_settings(data.conn)

    first_day = date(year, month, 1)
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    end_day = date(next_year, next_month, 1)
    events = _fetch_events(project=project, start_date=first_day, end_date=end_day, source_keys=source_keys)
    events_by_day = {}
    for event in events:
        try:
            day = int(event["date"].split("-")[2])
        except (IndexError, ValueError, AttributeError):
            continue
        events_by_day.setdefault(day, []).append(event)
    stats = calendar_index.fetch_calendar_day_stats(first_day, end_day, sources=source_keys, conn=data.conn)
    stat_days = {int(item["stat_date"].split("-")[2]) for item in stats if item.get("stat_date")}
    month_media = _fetch_image_media(data.conn, first_day, end_day, source_keys=source_keys) if day_sources["files"] else []
    media_by_date = _order_grouped_calendar_media(_group_media_by_date(month_media))
    media_by_day = {}
    for media_day, items in media_by_date.items():
        media_by_day[media_day.day] = items

    month_weeks = cal.monthcalendar(year, month)
    prev_year, prev_month, next_year, next_month = _month_nav(year, month)

    return render_template(
        "calendar_month.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=_calendar_title(f"{cal.month_name[month]} {year}", project),
        content_html="",
        view_date=first_day,
        month_weeks=month_weeks,
        month=month,
        year=year,
        month_name=cal.month_name[month],
        events_by_day=events_by_day,
        media_by_day=media_by_day,
        days_with_events=set(events_by_day.keys()) | stat_days,
        days_with_images=stat_days,
        today=date.today(),
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        project=project,
        day_sources=day_sources,
        day_source_params=day_source_params,
        calendar_thumbnail_limit=media_settings["thumbnail_limit"],
        calendar_thumbnail_class=media_settings["thumbnail_class"],
        source_action_url=url_for("calendar.month_view_route"),
        source_hidden_fields=_source_hidden_fields(year=year, month=month, proj=project),
        list_from=first_day,
        list_to=end_day - timedelta(days=1),
        **_calendar_jump_context("month", first_day, project, day_source_params),
        highlight_day_data=cfg.CAL_HIGHLIGHT_DAY_DATA,
        highlight_day_today=cfg.CAL_HIGHLIGHT_DAY_TODAY,
        col_bg_day=cfg.CAL_COL_BG_DAY,
        col_bg_weekend=cfg.CAL_COL_BG_WEEKEND,
        col_bg_today=cfg.CAL_COL_BG_TODAY,
    )


@calendar_bp.route("/week")
def week_view_route():
    today = date.today()
    date_param = request.args.get("date")
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    day_sources, day_source_params = _parse_day_sources(request.args)
    source_keys = day_sources["selected"]
    media_settings = _calendar_media_settings(data.conn)
    anchor = _parse_date_param(date_param) or today
    week_start = anchor - timedelta(days=anchor.weekday())
    week_end = week_start + timedelta(days=7)
    events = _fetch_events(project=project, start_date=week_start, end_date=week_end, source_keys=source_keys)
    events_by_day = {}
    for event in events:
        try:
            day = datetime.strptime(event.get("date", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        events_by_day.setdefault(day, []).append(event)
    week_days = [week_start + timedelta(days=offset) for offset in range(7)]
    media_by_day = (
        _order_grouped_calendar_media(_group_media_by_date(_fetch_image_media(data.conn, week_start, week_end, source_keys=source_keys)))
        if day_sources["files"]
        else {}
    )
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)
    timeslots = _build_timeslots()
    work_start = _time_val_to_minutes(cfg.CAL_TIME_START_WORK)
    work_end = _time_val_to_minutes(cfg.CAL_TIME_END_WORK)
    lunch_start = _time_val_to_minutes(cfg.CAL_TIME_LUNCH_START)
    lunch_end = _time_val_to_minutes(cfg.CAL_TIME_LUNCH_END)
    timed_events = {day: {} for day in week_days}
    all_day_events = {day: [] for day in week_days}
    for day in week_days:
        for event in events_by_day.get(day, []):
            mins = _parse_time_to_minutes(event.get("time"))
            if mins is None:
                all_day_events[day].append(event)
            else:
                timed_events[day].setdefault(mins, []).append(event)
    return render_template(
        "calendar_week.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=_calendar_title(f"Week of {week_start.strftime('%Y-%m-%d')}", project),
        content_html="",
        view_date=anchor,
        week_days=week_days,
        events_by_day=events_by_day,
        timeslots=timeslots,
        timed_events=timed_events,
        all_day_events=all_day_events,
        media_by_day=media_by_day,
        prev_week=prev_week,
        next_week=next_week,
        project=project,
        day_sources=day_sources,
        day_source_params=day_source_params,
        calendar_thumbnail_limit=media_settings["thumbnail_limit"],
        calendar_thumbnail_class=media_settings["thumbnail_class"],
        source_action_url=url_for("calendar.week_view_route"),
        source_hidden_fields=_source_hidden_fields(date=anchor.strftime("%Y-%m-%d"), proj=project),
        list_from=week_start,
        list_to=week_end - timedelta(days=1),
        **_calendar_jump_context("week", anchor, project, day_source_params),
        today=date.today(),
        highlight_day_data=cfg.CAL_HIGHLIGHT_DAY_DATA,
        highlight_day_today=cfg.CAL_HIGHLIGHT_DAY_TODAY,
        col_bg_day=cfg.CAL_COL_BG_DAY,
        col_bg_weekend=cfg.CAL_COL_BG_WEEKEND,
        col_bg_today=cfg.CAL_COL_BG_TODAY,
        work_start=work_start,
        work_end=work_end,
        lunch_start=lunch_start,
        lunch_end=lunch_end,
    )


@calendar_bp.route("/day")
def day_view_route():
    today = date.today()
    date_param = request.args.get("date")
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    day_sources, day_source_params = _parse_day_sources(request.args)
    source_keys = day_sources["selected"]
    media_settings = _calendar_media_settings(data.conn)
    anchor = _parse_date_param(date_param) or today
    next_day = anchor + timedelta(days=1)
    events = _fetch_events(project=project, start_date=anchor, end_date=next_day, source_keys=source_keys)
    events = sorted(events, key=lambda e: (e.get("time", ""), e.get("title", "")))
    detail_files_enabled = bool({"files", "media", "audio"} & source_keys)
    day_files = _fetch_day_files(data.conn, anchor) if detail_files_enabled else []
    day_media = _fetch_day_media(data.conn, anchor) if detail_files_enabled else []
    usage_items = []
    month_weeks = cal.monthcalendar(anchor.year, anchor.month)
    month_start = date(anchor.year, anchor.month, 1)
    next_month = anchor.month + 1
    next_year = anchor.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    month_end = date(next_year, next_month, 1)
    month_events = _fetch_events(project=project, start_date=month_start, end_date=month_end, source_keys=source_keys)
    events_by_day = {}
    for event in month_events:
        try:
            day = int(event["date"].split("-")[2])
        except (IndexError, ValueError, AttributeError):
            continue
        events_by_day.setdefault(day, []).append(event)
    month_stats = calendar_index.fetch_calendar_day_stats(month_start, month_end, sources=source_keys, conn=data.conn)
    days_with_images = {int(item["stat_date"].split("-")[2]) for item in month_stats if item.get("stat_date")}
    prev_day = anchor - timedelta(days=1)
    return render_template(
        "calendar_day.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=_calendar_title(anchor.strftime("%Y-%m-%d"), project),
        content_html="",
        view_date=anchor,
        day_date=anchor,
        prev_day=prev_day,
        next_day=next_day,
        month_weeks=month_weeks,
        month=anchor.month,
        year=anchor.year,
        month_name=cal.month_name[anchor.month],
        events=events,
        day_files=day_files,
        day_media=day_media,
        usage_items=usage_items,
        day_sources=day_sources,
        day_source_params=day_source_params,
        calendar_thumbnail_limit=media_settings["thumbnail_limit"],
        calendar_thumbnail_class=media_settings["thumbnail_class"],
        source_action_url=url_for("calendar.day_view_route"),
        source_hidden_fields=_source_hidden_fields(date=anchor.strftime("%Y-%m-%d"), proj=project),
        list_from=anchor,
        list_to=anchor,
        **_calendar_jump_context("day", anchor, project, day_source_params),
        days_with_events=set(events_by_day.keys()) | days_with_images,
        days_with_images=days_with_images,
        today=date.today(),
        project=project,
        highlight_day_data=cfg.CAL_HIGHLIGHT_DAY_DATA,
        highlight_day_today=cfg.CAL_HIGHLIGHT_DAY_TODAY,
        col_bg_day=cfg.CAL_COL_BG_DAY,
        col_bg_weekend=cfg.CAL_COL_BG_WEEKEND,
        col_bg_today=cfg.CAL_COL_BG_TODAY,
    )


@calendar_bp.route("/year")
def year_view_route():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    day_sources, day_source_params = _parse_day_sources(request.args)
    source_keys = day_sources["selected"]
    year_start = date(year, 1, 1)
    year_end = date(year + 1, 1, 1)
    year_stats = calendar_index.fetch_calendar_day_stats(year_start, year_end, sources=source_keys, conn=data.conn)
    year_events = _fetch_events(project=project, start_date=year_start, end_date=year_end, source_keys=source_keys)
    event_days_by_month = {}
    for event in year_events:
        try:
            event_day = datetime.strptime(event.get("date", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        event_days_by_month.setdefault(event_day.month, set()).add(event_day.day)
    media_days_by_month = {}
    for item in year_stats:
        try:
            stat_day = datetime.strptime(item["stat_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        media_days_by_month.setdefault(stat_day.month, set()).add(stat_day.day)
    months = []
    for month in range(1, 13):
        month_weeks = cal.monthcalendar(year, month)
        event_days = event_days_by_month.get(month, set())
        days_with_images = media_days_by_month.get(month, set())
        months.append(
            {
                "month": month,
                "month_name": cal.month_name[month],
                "month_weeks": month_weeks,
                "days_with_events": event_days | days_with_images,
                "days_with_images": days_with_images,
            }
        )
    return render_template(
        "calendar_year.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=_calendar_title(str(year), project),
        content_html="",
        year=year,
        months=months,
        today=today,
        project=project,
        day_sources=day_sources,
        day_source_params=day_source_params,
        source_action_url=url_for("calendar.year_view_route"),
        source_hidden_fields=_source_hidden_fields(year=year, proj=project),
        list_from=year_start,
        list_to=year_end - timedelta(days=1),
        **_calendar_jump_context("year", year_start, project, day_source_params),
        highlight_day_data=cfg.CAL_HIGHLIGHT_DAY_DATA,
        highlight_day_today=cfg.CAL_HIGHLIGHT_DAY_TODAY,
        col_bg_day=cfg.CAL_COL_BG_DAY,
        col_bg_weekend=cfg.CAL_COL_BG_WEEKEND,
        col_bg_today=cfg.CAL_COL_BG_TODAY,
    )


@calendar_bp.route("/summary")
def summary_view_route():
    _ensure_calendar_index()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    next_7 = today + timedelta(days=7)
    next_30 = today + timedelta(days=30)
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    day_sources, day_source_params = _parse_day_sources(request.args)
    source_keys = day_sources["selected"]
    today_items = _fetch_events(project=project, start_date=today, end_date=tomorrow, source_keys=source_keys)
    tomorrow_items = _fetch_events(project=project, start_date=tomorrow, end_date=tomorrow + timedelta(days=1), source_keys=source_keys)
    next_7_items = _fetch_events(project=project, start_date=today, end_date=next_7, source_keys=source_keys)
    next_30_items = _fetch_events(project=project, start_date=today, end_date=next_30, source_keys=source_keys)
    grouped = {}
    for group_key, col in {
        "event_type": "event_type",
        "category": "category",
        "project": "project",
        "source": "source_key",
    }.items():
        rows = data.conn.execute(
            f"""
            SELECT COALESCE({col}, '') AS label, COUNT(1) AS cnt
            FROM lp_calendar_items
            WHERE is_visible = 1 AND status != 'cancelled' AND start_date >= ? AND start_date < ?
            GROUP BY COALESCE({col}, '')
            ORDER BY cnt DESC, label
            """,
            [today.strftime("%Y-%m-%d"), next_30.strftime("%Y-%m-%d")],
        ).fetchall()
        grouped[group_key] = [dict(row) for row in rows]
    source_status = calendar_index.fetch_calendar_sources(data.conn)
    stats = calendar_index.fetch_calendar_day_stats(today, next_30, sources=source_keys, conn=data.conn)
    return render_template(
        "calendar_summary.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=_calendar_title("Calendar Summary", project),
        content_html="",
        today=today,
        project=project,
        day_sources=day_sources,
        day_source_params=day_source_params,
        today_items=today_items,
        tomorrow_items=tomorrow_items,
        next_7_items=next_7_items,
        next_30_items=next_30_items,
        grouped=grouped,
        source_status=source_status,
        stats=stats,
        source_action_url=url_for("calendar.summary_view_route"),
        source_hidden_fields=_source_hidden_fields(proj=project),
        **_calendar_jump_context("summary", today, project, day_source_params),
    )


@calendar_bp.route("/list")
def list_view_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "date"
    sort_dir = request.args.get("dir") or "asc"
    source_param = request.args.get("source") or ""
    source_keys = [source_param] if source_param else None
    start_date = _parse_date_param(request.args.get("from"))
    end_date = _parse_date_param(request.args.get("to"))
    if end_date:
        end_date = end_date + timedelta(days=1)
    events = _fetch_agenda_items(
        project=project,
        source_keys=source_keys,
        start_date=start_date,
        end_date=end_date,
        event_type=request.args.get("event_type") or None,
        category=request.args.get("category") or None,
        status=request.args.get("status") or None,
        search=request.args.get("q") or None,
        recurring_only=request.args.get("recurring") == "1",
    )
    if sort_col == "time":
        key_fn = lambda e: (e.get("time") or "", e.get("date") or "", e.get("title") or "")
    elif sort_col == "title":
        key_fn = lambda e: (e.get("title") or "", e.get("date") or "", e.get("time") or "")
    elif sort_col == "project":
        key_fn = lambda e: (e.get("project") or "", e.get("date") or "", e.get("time") or "")
    else:
        sort_col = "date"
        key_fn = lambda e: (e.get("date") or "", e.get("time") or "", e.get("title") or "")
    events.sort(key=key_fn, reverse=(sort_dir == "desc"))
    page = request.args.get("page", type=int) or 1
    page_data = paginate_items(events, page, cfg.RECS_PER_PAGE)
    events = page_data["items"]
    videos_by_date = {}
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "calendar.list_view_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    return render_template(
        "calendar_list.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=_calendar_title("Agenda", project),
        content_html="",
        events=events,
        videos_by_date=videos_by_date,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        now=date.today(),
        **_calendar_jump_context("list", date.today(), project),
    )


@calendar_bp.route("/event-list")
def event_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    day_sources, day_source_params = _parse_day_sources(request.args)
    source_keys = day_sources["selected"]
    default_from, default_to = _default_list_dates()
    start_date = _parse_date_param(request.args.get("from")) or default_from
    end_date_inclusive = _parse_date_param(request.args.get("to")) or default_to
    end_date = end_date_inclusive + timedelta(days=1)
    events = _fetch_agenda_items(
        project=project,
        source_keys=source_keys,
        start_date=start_date,
        end_date=end_date,
        event_type=request.args.get("event_type") or None,
        category=request.args.get("category") or None,
        status=request.args.get("status") or None,
        search=request.args.get("q") or None,
        recurring_only=request.args.get("recurring") == "1",
    )
    events.sort(key=lambda e: (e.get("date") or "", e.get("time") or "", e.get("title") or "", e.get("project") or ""))
    page = request.args.get("page", type=int) or 1
    page_data = paginate_items(events, page, cfg.RECS_PER_PAGE)
    events = page_data["items"]
    total_pages = page_data["total_pages"]
    page = page_data["page"]
    pagination_args = {
        "proj": project,
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date_inclusive.strftime("%Y-%m-%d"),
        "show_events": day_source_params["show_events"],
        "show_files": day_source_params["show_files"],
        "show_usage": day_source_params["show_usage"],
        "sources": day_source_params["sources"],
        "event_type": request.args.get("event_type", ""),
        "category": request.args.get("category", ""),
        "status": request.args.get("status", ""),
        "q": request.args.get("q", ""),
        "recurring": request.args.get("recurring", ""),
    }
    pagination = build_pagination(url_for, "calendar.event_list_route", pagination_args, page, total_pages)
    return render_template(
        "calendar_event_list.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=_calendar_title("List", project),
        content_html="",
        events=events,
        project=project,
        day_sources=day_sources,
        day_source_params=day_source_params,
        from_date=start_date,
        to_date=end_date_inclusive,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        source_action_url=url_for("calendar.event_list_route"),
        source_hidden_fields=_source_hidden_fields(
            proj=project,
            **{
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date_inclusive.strftime("%Y-%m-%d"),
                "event_type": request.args.get("event_type", ""),
                "category": request.args.get("category", ""),
                "status": request.args.get("status", ""),
                "q": request.args.get("q", ""),
                "recurring": request.args.get("recurring", ""),
            },
        ),
        now=date.today(),
        **_calendar_jump_context("list", date.today(), project, day_source_params),
    )


@calendar_bp.route("/view/<int:event_id>")
def view_event_route(event_id):
    _ensure_calendar_index()
    event = None
    rows = data.conn.execute("SELECT * FROM lp_calendar_events WHERE id = ?", [event_id]).fetchall()
    if rows:
        event = _event_from_row(rows[0])
    if not event:
        return redirect(url_for("calendar.month_view_route"))
    view_date = _parse_date_param(event.get("date")) or date.today()
    return render_template(
        "calendar_view.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=event.get("title") or "Event",
        content_html="",
        event=event,
        project=event.get("project"),
        view_date=view_date,
    )


@calendar_bp.route("/add", methods=["GET", "POST"])
def add_event_route():
    _ensure_calendar_index()
    if request.method == "POST":
        values = _form_event_values(request.form)
        event_id = calendar_index.create_calendar_event(values, data.conn)
        date_str = values["start_date"]
        project = values["project"]
        year_month = _date_to_year_month(date_str)
        if year_month:
            return redirect(
                url_for(
                    "calendar.month_view_route",
                    year=year_month[0],
                    month=year_month[1],
                    proj=project,
                )
            )
        return redirect(url_for("calendar.month_view_route", proj=project))

    default_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")
    default_project = request.args.get("proj") or "General"
    return render_template(
        "calendar_edit.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Event",
        content_html="",
        event=None,
        default_date=default_date,
        default_project=default_project,
        project_options=_project_options(data.conn),
    )


@calendar_bp.route("/edit/<int:event_id>", methods=["GET", "POST"])
def edit_event_route(event_id):
    _ensure_calendar_index()
    event = None
    rows = data.conn.execute("SELECT * FROM lp_calendar_events WHERE id = ?", [event_id]).fetchall()
    if rows:
        event = _event_from_row(rows[0])
    if not event:
        return redirect(url_for("calendar.month_view_route"))

    if request.method == "POST":
        values = _form_event_values(request.form)
        calendar_index.update_calendar_event(event_id, values, data.conn)
        date_str = values["start_date"]
        year_month = _date_to_year_month(date_str)
        if year_month:
            return redirect(
                url_for(
                    "calendar.month_view_route",
                    year=year_month[0],
                    month=year_month[1],
                    proj=values["project"],
                )
            )
        return redirect(url_for("calendar.month_view_route", proj=values["project"]))

    return render_template(
        "calendar_edit.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Edit: {event['title']}",
        content_html="",
        event=event,
        default_date=event.get("date"),
        default_project=event.get("project"),
        project_options=_project_options(data.conn),
    )


@calendar_bp.route("/delete/<int:event_id>", methods=["GET", "POST"])
def delete_event_route(event_id):
    _ensure_calendar_index()
    event = None
    rows = data.conn.execute("SELECT * FROM lp_calendar_events WHERE id = ?", [event_id]).fetchall()
    if rows:
        event = _event_from_row(rows[0])
    if request.method == "POST":
        calendar_index.delete_projected_event(event_id, data.conn)
        data.delete_record(data.conn, "lp_calendar_events", event_id)
    elif event:
        return redirect(url_for("calendar.view_event_route", event_id=event_id))
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    project = request.args.get("proj")
    if year and month:
        return redirect(url_for("calendar.month_view_route", year=year, month=month, proj=project))
    if event:
        year_month = _date_to_year_month(event.get("date", ""))
        if year_month:
            return redirect(
                url_for(
                    "calendar.month_view_route",
                    year=year_month[0],
                    month=year_month[1],
                    proj=project or event.get("project"),
                )
            )
        return redirect(url_for("calendar.month_view_route", proj=project or event.get("project")))
    return redirect(url_for("calendar.month_view_route", proj=project))


@calendar_bp.route("/import", methods=["GET", "POST"])
def import_events_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = get_table_def("calendar")
    csv_path = ""
    headers = []
    mappings = {}
    imported = None
    error = ""
    if request.method == "POST":
        csv_path = request.form.get("csv_path", "").strip()
        upload = request.files.get("csv_file")
        if upload and upload.filename:
            csv_path = importer.save_upload(upload)
        action = request.form.get("action", "load")
        headers = _read_csv_headers(csv_path)
        if action == "import" and tbl:
            mappings = {col: request.form.get(f"map_{col}", "") for col in tbl["col_list"]}
            map_list = []
            for col in tbl["col_list"]:
                choice = mappings.get(col, "")
                if choice == "{curr_project_selected}":
                    choice = project
                map_list.append(choice)
            try:
                importer.set_token("curr_project_selected", project)
                imported = importer.import_to_table(tbl["name"], csv_path, map_list)
                calendar_index.run_calendar_migration(data.conn)
            except Exception as exc:
                error = str(exc)
        else:
            mappings = {col: "" for col in (tbl["col_list"] if tbl else [])}
    return render_template(
        "calendar_import.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Events",
        content_html="",
        project=project,
        table_def=tbl,
        csv_path=csv_path,
        csv_headers=headers,
        mappings=mappings,
        imported=imported,
        error=error,
        today=date.today(),
    )


def _event_from_row(row):
    event = dict(row)
    date_str = event.get("start_date")
    time_str = event.get("start_time") or ""
    if not date_str:
        date_str, time_str = _parse_event_datetime(event.get("event_date"))
    event["date"] = date_str
    event["time"] = time_str
    event["detail"] = event.get("content", "")
    return event


def _event_from_index_row(row):
    event = dict(row)
    event["date"] = event.get("item_date") or event.get("start_date")
    event["time"] = event.get("start_time") or ""
    event["detail"] = event.get("content", "")
    event["can_edit"] = bool(event.get("target_id"))
    event["id"] = event.get("target_id") or event.get("id")
    return event


def _form_event_values(form):
    values = {
        "title": form.get("title", "").strip(),
        "content": form.get("detail", "").strip(),
        "start_date": form.get("start_date") or form.get("date", ""),
        "start_time": form.get("start_time") or form.get("time", ""),
        "end_date": form.get("end_date") or form.get("start_date") or form.get("date", ""),
        "end_time": form.get("end_time") or form.get("start_time") or form.get("time", ""),
        "all_day": form.get("all_day") == "1",
        "blocks_time": form.get("blocks_time") == "1",
        "event_type": form.get("event_type") or "event",
        "category": form.get("category") or "",
        "project": form.get("project", "").strip(),
        "status": form.get("status") or "active",
        "color": form.get("color") or "",
        "icon": form.get("icon") or "",
        "location": form.get("location") or "",
        "recurrence_rule": form.get("recurrence_rule") or "",
        "recurrence_end_date": form.get("recurrence_end_date") or "",
        "recurrence_count": form.get("recurrence_count") or "",
        "remind_date": form.get("remind_date") or "",
    }
    recurrence_type = form.get("recurrence_type") or "single"
    recurrence_rule = _recurrence_rule_from_form(form, recurrence_type)
    if recurrence_rule is not None:
        values["recurrence_rule"] = recurrence_rule
    if recurrence_type == "weekly":
        values["start_date"] = _next_weekday_date(form.get("weekly_day")).isoformat()
        values["end_date"] = values["start_date"]
    elif recurrence_type == "monthly":
        values["start_date"] = _monthly_start_date(form).isoformat()
        values["end_date"] = values["start_date"]
    if recurrence_type == "yearly_anniversary":
        month = _safe_int(form.get("anniversary_month"))
        day = _safe_int(form.get("anniversary_day"))
        if month and day:
            year = date.today().year
            values["start_date"] = f"{year:04d}-{month:02d}-{day:02d}"
            values["end_date"] = values["start_date"]
            values["event_type"] = form.get("event_type") or "birthday"
            values["all_day"] = True
    return values


def _recurrence_rule_from_form(form, recurrence_type):
    if recurrence_type == "single":
        return ""
    if recurrence_type == "weekly":
        day_code = form.get("weekly_day") or ""
        return f"FREQ=WEEKLY;BYDAY={day_code}" if day_code else "FREQ=WEEKLY"
    if recurrence_type == "fortnightly":
        return "FREQ=WEEKLY;INTERVAL=2"
    if recurrence_type == "monthly":
        mode = form.get("monthly_mode") or "day"
        if mode == "first_weekday":
            day_code = form.get("monthly_weekday") or ""
            return f"FREQ=MONTHLY;BYDAY=1{day_code}" if day_code else "FREQ=MONTHLY"
        day_of_month = _safe_int(form.get("monthly_day"))
        return f"FREQ=MONTHLY;BYMONTHDAY={day_of_month}" if day_of_month else "FREQ=MONTHLY"
    if recurrence_type == "yearly_anniversary":
        month = _safe_int(form.get("anniversary_month"))
        day = _safe_int(form.get("anniversary_day"))
        if month and day:
            return f"FREQ=YEARLY;BYMONTH={month};BYMONTHDAY={day}"
        return "FREQ=YEARLY"
    return form.get("recurrence_rule") or ""


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _next_weekday_date(day_code):
    target = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}.get(day_code, date.today().weekday())
    today = date.today()
    return today + timedelta(days=(target - today.weekday()) % 7)


def _monthly_start_date(form):
    today = date.today()
    if (form.get("monthly_mode") or "day") == "first_weekday":
        target = _next_weekday_date(form.get("monthly_weekday")).weekday()
        first = date(today.year, today.month, 1)
        candidate = first + timedelta(days=(target - first.weekday()) % 7)
        if candidate < today:
            next_month = today.month + 1
            next_year = today.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            first = date(next_year, next_month, 1)
            candidate = first + timedelta(days=(target - first.weekday()) % 7)
        return candidate
    day = max(1, min(31, _safe_int(form.get("monthly_day")) or today.day))
    year = today.year
    month = today.month
    while True:
        try:
            candidate = date(year, month, day)
        except ValueError:
            candidate = date(year, month, cal.monthrange(year, month)[1])
        if candidate >= today:
            return candidate
        month += 1
        if month > 12:
            month = 1
            year += 1


def _combine_event_date(date_str, time_str):
    if time_str:
        return f"{date_str} {time_str}"
    return date_str


def _parse_event_datetime(value):
    if not value:
        return "", ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M")
        except (ValueError, TypeError):
            continue
    return value[:10], ""
