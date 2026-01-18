import calendar as cal
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for

from common import data
from common.utils import get_tabs, get_side_tabs, get_table_def, paginate_items, build_pagination
import common.config as cfg
from utils import importer


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


def _get_calendar_table():
    return get_table_def("calendar")


def _fetch_events(project=None, start_date=None, end_date=None):
    tbl = _get_calendar_table()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    condition_parts = ["1=1"]
    params = []
    if project and project not in ("any", "All", "all", "ALL", "spacer"):
        condition_parts.append("lower(project) = lower(?)")
        params.append(project)
    if start_date and end_date:
        condition_parts.append("event_date >= ? AND event_date < ?")
        params.append(start_date.strftime("%Y-%m-%d"))
        params.append(end_date.strftime("%Y-%m-%d"))
    condition = " AND ".join(condition_parts)
    rows = data.get_data(data.conn, tbl["name"], cols, condition, params)
    return [_event_from_row(row) for row in rows]


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


@calendar_bp.route("/")
def month_view_route():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None

    first_day = date(year, month, 1)
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    end_day = date(next_year, next_month, 1)
    events = _fetch_events(project=project, start_date=first_day, end_date=end_day)
    events_by_day = {}
    for event in events:
        try:
            day = int(event["date"].split("-")[2])
        except (IndexError, ValueError, AttributeError):
            continue
        events_by_day.setdefault(day, []).append(event)

    month_weeks = cal.monthcalendar(year, month)
    prev_year, prev_month, next_year, next_month = _month_nav(year, month)

    return render_template(
        "calendar_month.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"{cal.month_name[month]} {year}",
        content_html="",
        view_date=first_day,
        month_weeks=month_weeks,
        month=month,
        year=year,
        month_name=cal.month_name[month],
        events_by_day=events_by_day,
        days_with_events=set(events_by_day.keys()),
        today=date.today(),
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        project=project,
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
    anchor = _parse_date_param(date_param) or today
    week_start = anchor - timedelta(days=anchor.weekday())
    week_end = week_start + timedelta(days=7)
    events = _fetch_events(project=project, start_date=week_start, end_date=week_end)
    events_by_day = {}
    for event in events:
        try:
            day = datetime.strptime(event.get("date", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        events_by_day.setdefault(day, []).append(event)
    week_days = [week_start + timedelta(days=offset) for offset in range(7)]
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
        content_title=f"Week of {week_start.strftime('%Y-%m-%d')}",
        content_html="",
        view_date=anchor,
        week_days=week_days,
        events_by_day=events_by_day,
        timeslots=timeslots,
        timed_events=timed_events,
        all_day_events=all_day_events,
        prev_week=prev_week,
        next_week=next_week,
        project=project,
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
    anchor = _parse_date_param(date_param) or today
    next_day = anchor + timedelta(days=1)
    events = _fetch_events(project=project, start_date=anchor, end_date=next_day)
    events = sorted(events, key=lambda e: (e.get("time", ""), e.get("title", "")))
    month_weeks = cal.monthcalendar(anchor.year, anchor.month)
    month_start = date(anchor.year, anchor.month, 1)
    next_month = anchor.month + 1
    next_year = anchor.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    month_end = date(next_year, next_month, 1)
    month_events = _fetch_events(project=project, start_date=month_start, end_date=month_end)
    events_by_day = {}
    for event in month_events:
        try:
            day = int(event["date"].split("-")[2])
        except (IndexError, ValueError, AttributeError):
            continue
        events_by_day.setdefault(day, []).append(event)
    prev_day = anchor - timedelta(days=1)
    return render_template(
        "calendar_day.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=anchor.strftime("%Y-%m-%d"),
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
        days_with_events=set(events_by_day.keys()),
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
    months = []
    for month in range(1, 13):
        month_weeks = cal.monthcalendar(year, month)
        month_start = date(year, month, 1)
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        month_end = date(next_year, next_month, 1)
        month_events = _fetch_events(project=project, start_date=month_start, end_date=month_end)
        events_by_day = {}
        for event in month_events:
            try:
                day = int(event["date"].split("-")[2])
            except (IndexError, ValueError, AttributeError):
                continue
            events_by_day.setdefault(day, []).append(event)
        months.append(
            {
                "month": month,
                "month_name": cal.month_name[month],
                "month_weeks": month_weeks,
                "days_with_events": set(events_by_day.keys()),
            }
        )
    return render_template(
        "calendar_year.html",
        active_tab="calendar",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=str(year),
        content_html="",
        year=year,
        months=months,
        today=today,
        project=project,
        highlight_day_data=cfg.CAL_HIGHLIGHT_DAY_DATA,
        highlight_day_today=cfg.CAL_HIGHLIGHT_DAY_TODAY,
        col_bg_day=cfg.CAL_COL_BG_DAY,
        col_bg_weekend=cfg.CAL_COL_BG_WEEKEND,
        col_bg_today=cfg.CAL_COL_BG_TODAY,
    )


@calendar_bp.route("/list")
def list_view_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "date"
    sort_dir = request.args.get("dir") or "asc"
    events = _fetch_events(project=project)
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
        content_title=f"Events ({project or 'All'})",
        content_html="",
        events=events,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        now=date.today(),
    )


@calendar_bp.route("/view/<int:event_id>")
def view_event_route(event_id):
    tbl = get_table_def("calendar")
    event = None
    if tbl:
        rows = data.get_data(data.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [event_id])
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
    tbl = get_table_def("calendar")
    if request.method == "POST" and tbl:
        title = request.form["title"].strip()
        date_str = request.form.get("date", "").strip()
        time_str = request.form.get("time", "").strip()
        detail = request.form.get("detail", "").strip()
        project = request.form.get("project", "General").strip() or "General"

        event_date = _combine_event_date(date_str, time_str)
        values = [title, detail, event_date, "", project]
        data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
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
    )


@calendar_bp.route("/edit/<int:event_id>", methods=["GET", "POST"])
def edit_event_route(event_id):
    tbl = get_table_def("calendar")
    event = None
    if tbl:
        rows = data.get_data(data.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [event_id])
        if rows:
            event = _event_from_row(rows[0])
    if not event:
        return redirect(url_for("calendar.month_view_route"))

    if request.method == "POST" and tbl:
        title = request.form["title"].strip()
        date_str = request.form.get("date", "").strip()
        time_str = request.form.get("time", "").strip()
        detail = request.form.get("detail", "").strip()
        project = request.form.get("project", "General").strip() or "General"
        event_date = _combine_event_date(date_str, time_str)
        values = [title, detail, event_date, "", project]
        data.update_record(data.conn, tbl["name"], event_id, tbl["col_list"], values)
        year_month = _date_to_year_month(date_str)
        if year_month:
            return redirect(
                url_for(
                    "calendar.month_view_route",
                    year=year_month[0],
                    month=year_month[1],
                    proj=event.get("project"),
                )
            )
        return redirect(url_for("calendar.month_view_route", proj=event.get("project")))

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
    )


@calendar_bp.route("/delete/<int:event_id>")
def delete_event_route(event_id):
    tbl = get_table_def("calendar")
    event = None
    if tbl:
        rows = data.get_data(data.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [event_id])
        if rows:
            event = _event_from_row(rows[0])
        data.delete_record(data.conn, tbl["name"], event_id)
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
    date_str, time_str = _parse_event_datetime(event.get("event_date"))
    event["date"] = date_str
    event["time"] = time_str
    event["detail"] = event.get("content", "")
    return event


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
