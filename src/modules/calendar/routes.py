import calendar as cal
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for

from common import data
from common.utils import get_tabs, get_side_tabs


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

    events = data.get_calendar_events(data.conn, year=year, month=month, project=project)
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
    if request.method == "POST":
        title = request.form["title"].strip()
        date_str = request.form.get("date", "").strip()
        time_str = request.form.get("time", "").strip()
        detail = request.form.get("detail", "").strip()
        project = request.form.get("project", "General").strip() or "General"

        event = data.add_calendar_event(data.conn, title, date_str, time_str, detail, project)
        year_month = _date_to_year_month(event.get("date", ""))
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
    event = data.get_calendar_event_by_id(data.conn, event_id)
    if not event:
        return redirect(url_for("calendar.month_view_route"))

    if request.method == "POST":
        data.update_calendar_event(
            data.conn,
            event_id,
            request.form["title"].strip(),
            request.form.get("date", "").strip(),
            request.form.get("time", "").strip(),
            request.form.get("detail", "").strip(),
            request.form.get("project", "General").strip() or "General",
        )
        year_month = _date_to_year_month(request.form.get("date", ""))
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
    event = data.get_calendar_event_by_id(data.conn, event_id)
    data.delete_calendar_event(data.conn, event_id)
    if event:
        year_month = _date_to_year_month(event.get("date", ""))
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
    return redirect(url_for("calendar.month_view_route"))
