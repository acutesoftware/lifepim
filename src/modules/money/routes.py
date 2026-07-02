from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from common.utils import get_tabs, get_side_tabs
from modules.money import dao


money_bp = Blueprint(
    "money",
    __name__,
    url_prefix="/money",
    template_folder="templates",
    static_folder="static",
)


@money_bp.route("/")
def list_money_route():
    return money_section_route("assets")


@money_bp.route("/<section_id>")
def money_section_route(section_id):
    active_section = dao.section(section_id)
    search = (request.args.get("q") or "").strip()
    rows = dao.list_records(active_section["id"], search=search)
    section_summaries = dao.summaries()
    return render_template(
        "money_list.html",
        active_tab="money",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Money",
        content_html="",
        sections=dao.sections(),
        active_section=active_section,
        rows=rows,
        search=search,
        summaries=section_summaries,
        quote_delay_minutes=getattr(dao.cfg, "MONEY_QUOTE_DELAY_MINUTES", 15),
    )


@money_bp.route("/<section_id>/save", methods=["POST"])
def save_money_route(section_id):
    active_section = dao.section(section_id)
    record_id = request.form.get(active_section["pk"], type=int)
    try:
        if record_id:
            dao.update_record(active_section["id"], record_id, request.form)
        else:
            dao.create_record(active_section["id"], request.form)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return redirect(_section_url(active_section["id"]))


@money_bp.route("/<section_id>/delete/<int:record_id>", methods=["POST"])
def delete_money_route(section_id, record_id):
    active_section = dao.section(section_id)
    dao.delete_record(active_section["id"], record_id)
    return redirect(_section_url(active_section["id"]))


@money_bp.route("/<section_id>/refresh-quotes", methods=["POST"])
def refresh_quotes_route(section_id):
    active_section = dao.section(section_id)
    result = dao.refresh_quotes(active_section["id"])
    return redirect(_section_url(active_section["id"], refreshed=result.get("updated", 0)))


@money_bp.route("/api/<section_id>", methods=["GET", "POST"])
def records_api_route(section_id):
    active_section = dao.section(section_id)
    if request.method == "GET":
        return jsonify({"records": dao.list_records(active_section["id"])})
    payload = request.get_json(silent=True) or {}
    try:
        record_id = dao.create_record(active_section["id"], payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "record_id": record_id})


@money_bp.route("/api/<section_id>/<int:record_id>", methods=["GET", "PUT", "DELETE"])
def record_api_route(section_id, record_id):
    active_section = dao.section(section_id)
    if request.method == "GET":
        record = dao.get_record(active_section["id"], record_id)
        if not record:
            return jsonify({"error": "Record not found"}), 404
        return jsonify({"record": record})
    if request.method == "DELETE":
        dao.delete_record(active_section["id"], record_id)
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    try:
        dao.update_record(active_section["id"], record_id, payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})


def _section_url(section_id, **extra):
    args = {key: value for key, value in extra.items() if value not in (None, "")}
    q = (request.args.get("q") or "").strip()
    if q:
        args["q"] = q
    return url_for("money.money_section_route", section_id=section_id, **args)
