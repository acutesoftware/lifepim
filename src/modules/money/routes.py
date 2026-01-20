from flask import Blueprint, jsonify, render_template, request

from common.utils import get_tabs, get_side_tabs
from modules.money import dao


money_bp = Blueprint(
    "money",
    __name__,
    url_prefix="/money",
    template_folder="templates",
    static_folder="static",
)


STATUS_OPTIONS = [
    ("active", "Idea + Planned"),
    ("idea", "Idea"),
    ("planned", "Planned"),
    ("bought", "Bought"),
    ("cancelled", "Cancelled"),
    ("all", "All"),
]

DATE_OPTIONS = [
    ("all", "All"),
    ("next30", "Next 30"),
    ("next90", "Next 90"),
    ("next365", "Next 365"),
    ("unscheduled", "Unscheduled"),
]

SORT_OPTIONS = [
    ("target_date", "Target date"),
    ("priority", "Priority"),
    ("cost", "Cost"),
]


@money_bp.route("/")
def list_money_route():
    project = (request.args.get("proj") or "").strip()
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    domain = (request.args.get("domain") or "all").strip()
    if domain == "all" and project:
        domain = project
    status_filter = (request.args.get("status") or "active").strip()
    date_filter = (request.args.get("date") or "all").strip()
    sort_key = (request.args.get("sort") or "target_date").strip()
    statuses = _status_list(status_filter)
    plans = dao.list_plans(
        domain=None if domain.lower() == "all" else domain,
        statuses=statuses,
        date_preset=None if date_filter == "all" else date_filter,
        sort_key=sort_key,
    )
    domains = dao.list_domains()
    summary = dao.summary_totals(domain=None if domain.lower() == "all" else domain)
    return render_template(
        "money_list.html",
        active_tab="money",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Money",
        content_html="",
        plans=plans,
        domains=domains,
        domain_filter=domain,
        status_filter=status_filter,
        date_filter=date_filter,
        sort_key=sort_key,
        status_options=STATUS_OPTIONS,
        date_options=DATE_OPTIONS,
        sort_options=SORT_OPTIONS,
        summary=summary,
    )


@money_bp.route("/api/plans", methods=["GET", "POST"])
def plans_api_route():
    if request.method == "GET":
        project = (request.args.get("proj") or "").strip()
        if project in ("any", "All", "all", "ALL", "spacer"):
            project = ""
        domain = (request.args.get("domain") or "all").strip()
        if domain == "all" and project:
            domain = project
        status_filter = (request.args.get("status") or "active").strip()
        date_filter = (request.args.get("date") or "all").strip()
        sort_key = (request.args.get("sort") or "target_date").strip()
        statuses = _status_list(status_filter)
        plans = dao.list_plans(
            domain=None if domain.lower() == "all" else domain,
            statuses=statuses,
            date_preset=None if date_filter == "all" else date_filter,
            sort_key=sort_key,
        )
        return jsonify({"plans": plans})

    payload = request.get_json(silent=True) or {}
    parsed, error = _normalize_payload(payload)
    if error:
        return jsonify({"error": error}), 400
    plan_id = dao.create_plan(parsed)
    return jsonify({"ok": True, "plan_id": plan_id})


@money_bp.route("/api/plans/<int:plan_id>", methods=["GET", "PUT", "DELETE"])
def plan_api_route(plan_id):
    if request.method == "GET":
        plan = dao.get_plan(plan_id)
        if not plan:
            return jsonify({"error": "Plan not found"}), 404
        return jsonify({"plan": plan})

    if request.method == "DELETE":
        dao.delete_plan(plan_id)
        return jsonify({"ok": True})

    payload = request.get_json(silent=True) or {}
    parsed, error = _normalize_payload(payload)
    if error:
        return jsonify({"error": error}), 400
    dao.update_plan(plan_id, parsed)
    return jsonify({"ok": True})


@money_bp.route("/api/summary")
def summary_api_route():
    project = (request.args.get("proj") or "").strip()
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    domain = (request.args.get("domain") or "all").strip()
    if domain == "all" and project:
        domain = project
    return jsonify(dao.summary_totals(domain=None if domain.lower() == "all" else domain))


def _status_list(status_filter):
    if status_filter == "active":
        return ["idea", "planned"]
    if status_filter and status_filter != "all":
        return [status_filter]
    return []


def _normalize_payload(payload):
    item = (payload.get("item") or "").strip()
    if not item:
        return None, "Item is required"
    domain = (payload.get("domain") or "General").strip() or "General"
    status = (payload.get("status") or "planned").strip()
    if status not in dao.STATUS_VALUES:
        return None, "Invalid status"
    try:
        estimated_cost = float(payload.get("estimated_cost"))
    except (TypeError, ValueError):
        return None, "Estimated cost must be a number"
    if estimated_cost <= 0:
        return None, "Estimated cost must be positive"
    try:
        priority = int(payload.get("priority") or 3)
    except (TypeError, ValueError):
        return None, "Priority must be a number"
    if priority < 1 or priority > 5:
        return None, "Priority must be between 1 and 5"
    target_date = (payload.get("target_date") or "").strip() or None
    notes = (payload.get("notes") or "").strip() or None
    return {
        "item": item,
        "domain": domain,
        "estimated_cost": estimated_cost,
        "target_date": target_date,
        "priority": priority,
        "status": status,
        "notes": notes,
    }, None
