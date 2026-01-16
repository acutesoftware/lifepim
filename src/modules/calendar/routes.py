import calendar as cal
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for

from common import data
from common.utils import get_tabs, get_side_tabs, get_table_def


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


def _date_to_year_month(date_str):
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.year, parsed.month
    except (ValueError, TypeError):
        return None


@calendar_bp.route("/")
def month_view_route():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    project = request.args.get("proj")

    tbl = get_table_def("calendar")
    if not tbl:
        events = []
    else:
        cols = ["id"] + tbl["col_list"]
        condition_parts = ["1=1"]
        params = []
        if project and project not in ("any", "spacer"):
            condition_parts.append("project = ?")
            params.append(project)
        condition_parts.append("event_date LIKE ?")
        params.append(f"{year:04d}-{month:02d}%")
        condition = " AND ".join(condition_parts)
        rows = data.get_data(data.conn, tbl["name"], cols, condition, params)
        events = [_event_from_row(row) for row in rows]
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
        month_weeks=month_weeks,
        month=month,
        year=year,
        month_name=cal.month_name[month],
        events_by_day=events_by_day,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        project=project,
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
