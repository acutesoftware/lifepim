from flask import Blueprint, render_template, request, redirect, url_for

from common import config as cfg
from common.utils import build_pagination, get_side_tabs, get_tabs, paginate_total
from utils import importer

from . import dao


contacts_bp = Blueprint(
    "contacts",
    __name__,
    url_prefix="/contacts",
    template_folder="templates",
    static_folder="static",
)


def _fetch_contact_summaries(contact_ids):
    if not contact_ids:
        return {}
    placeholders = ", ".join(["?"] * len(contact_ids))
    conn = dao.db._get_conn()
    rows = conn.execute(
        "SELECT contact_id, fact_type, fact_value FROM lp_contact_facts "
        f"WHERE contact_id IN ({placeholders}) "
        "ORDER BY "
        "CASE fact_type "
        "WHEN 'email' THEN 1 "
        "WHEN 'phone' THEN 2 "
        "WHEN 'org' THEN 3 "
        "WHEN 'url' THEN 4 "
        "WHEN 'address' THEN 5 "
        "WHEN 'note' THEN 6 "
        "ELSE 7 END, fact_value",
        contact_ids,
    ).fetchall()
    summaries = {cid: [] for cid in contact_ids}
    for row in rows:
        cid = row["contact_id"]
        if cid not in summaries:
            summaries[cid] = []
        if len(summaries[cid]) >= 2:
            continue
        summaries[cid].append(f"{row['fact_type']}: {row['fact_value']}")
    return {cid: " | ".join(values) for cid, values in summaries.items()}


@contacts_bp.route("/")
def list_contacts_route():
    return list_contacts_table_route()


@contacts_bp.route("/table")
def list_contacts_table_route():
    sort_col = request.args.get("sort") or "display_name"
    sort_dir = request.args.get("dir") or "asc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = dao.count_contacts()
    offset = (page - 1) * per_page
    items = dao.list_contacts(sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "contacts.list_contacts_table_route",
        {"sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    col_list = ["display_name", "normalized_name", "updated_utc", "fact_count"]
    return render_template(
        "contacts_list_table.html",
        active_tab="contacts",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Contacts",
        content_html="",
        items=items,
        col_list=col_list,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@contacts_bp.route("/list")
def list_contacts_list_route():
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = dao.count_contacts()
    offset = (page - 1) * per_page
    items = dao.list_contacts("display_name", "asc", limit=per_page, offset=offset)
    contact_ids = [item["contact_id"] for item in items]
    summaries = _fetch_contact_summaries(contact_ids)
    for item in items:
        item["summary"] = summaries.get(item["contact_id"], "")
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "contacts.list_contacts_list_route",
        {},
        page,
        total_pages,
    )
    return render_template(
        "contacts_list_list.html",
        active_tab="contacts",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Contacts",
        content_html="",
        items=items,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@contacts_bp.route("/cards")
def list_contacts_cards_route():
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = dao.count_contacts()
    offset = (page - 1) * per_page
    items = dao.list_contacts("display_name", "asc", limit=per_page, offset=offset)
    contact_ids = [item["contact_id"] for item in items]
    summaries = _fetch_contact_summaries(contact_ids)
    card_values = [
        [
            item.get("display_name"),
            summaries.get(item.get("contact_id"), ""),
            url_for("contacts.view_contact_route", contact_id=item.get("contact_id")),
        ]
        for item in items
    ]
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "contacts.list_contacts_cards_route",
        {},
        page,
        total_pages,
    )
    return render_template(
        "contacts_list_cards.html",
        active_tab="contacts",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Contacts",
        content_html="",
        card_values=card_values,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@contacts_bp.route("/view/<int:contact_id>")
def view_contact_route(contact_id):
    contact = dao.get_contact(contact_id)
    if not contact:
        return redirect(url_for("contacts.list_contacts_table_route"))
    facts = dao.list_facts(contact_id)
    return render_template(
        "contacts_view.html",
        active_tab="contacts",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=contact.get("display_name") or "Contact",
        content_html="",
        contact=contact,
        facts=facts,
        fact_types=dao.FACT_TYPES,
    )


@contacts_bp.route("/add", methods=["GET", "POST"])
def add_contact_route():
    if request.method == "POST":
        display_name = request.form.get("display_name", "")
        contact_id = dao.create_contact(display_name)
        if contact_id:
            return redirect(url_for("contacts.view_contact_route", contact_id=contact_id))
    return render_template(
        "contacts_edit.html",
        active_tab="contacts",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Contact",
        content_html="",
        contact=None,
    )


@contacts_bp.route("/edit/<int:contact_id>", methods=["GET", "POST"])
def edit_contact_route(contact_id):
    contact = dao.get_contact(contact_id)
    if not contact:
        return redirect(url_for("contacts.list_contacts_table_route"))
    if request.method == "POST":
        display_name = request.form.get("display_name", "")
        dao.update_contact(contact_id, display_name)
        return redirect(url_for("contacts.view_contact_route", contact_id=contact_id))
    return render_template(
        "contacts_edit.html",
        active_tab="contacts",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Contact",
        content_html="",
        contact=contact,
    )


@contacts_bp.route("/delete/<int:contact_id>")
def delete_contact_route(contact_id):
    dao.delete_contact(contact_id)
    return redirect(url_for("contacts.list_contacts_table_route"))


@contacts_bp.route("/fact/add/<int:contact_id>", methods=["POST"])
def add_fact_route(contact_id):
    fact_type = request.form.get("fact_type", "")
    fact_value = request.form.get("fact_value", "")
    source_system = request.form.get("source_system", "")
    source_ref = request.form.get("source_ref", "")
    confidence = request.form.get("confidence", "")
    conf_value = None
    if confidence:
        try:
            conf_value = float(confidence)
        except ValueError:
            conf_value = None
    dao.add_fact(contact_id, fact_type, fact_value, source_system, source_ref, conf_value)
    return redirect(url_for("contacts.view_contact_route", contact_id=contact_id))


@contacts_bp.route("/fact/delete/<int:fact_id>")
def delete_fact_route(fact_id):
    contact_id = request.args.get("contact_id", type=int)
    dao.delete_fact(fact_id)
    if contact_id:
        return redirect(url_for("contacts.view_contact_route", contact_id=contact_id))
    return redirect(url_for("contacts.list_contacts_table_route"))


@contacts_bp.route("/import", methods=["GET", "POST"])
def import_contacts_route():
    csv_path = request.form.get("csv_path") or ""
    action = request.form.get("action") or ""
    csv_headers = []
    mappings = {}
    imported = None
    error = ""
    source_system = (request.form.get("source_system") or "csv").strip() or "csv"
    source_ref = (request.form.get("source_ref") or "").strip()
    confidence = (request.form.get("confidence") or "").strip()
    upload = request.files.get("csv_file")
    if upload and upload.filename:
        csv_path = importer.save_upload(upload)
    if csv_path:
        csv_headers = importer.read_csv_headers(csv_path)
    if csv_headers:
        for idx, header in enumerate(csv_headers):
            mapping_value = request.form.get(f"map_{idx}") or ""
            if mapping_value:
                mappings[header] = mapping_value
    if request.method == "POST" and action == "import":
        if not csv_path:
            error = "Please select a CSV file."
        else:
            conf_value = None
            if confidence:
                try:
                    conf_value = float(confidence)
                except ValueError:
                    error = "Confidence must be a number between 0 and 1."
            if not error:
                try:
                    result = dao.import_contacts_from_csv(
                        csv_path,
                        mappings,
                        source_system=source_system,
                        source_ref=source_ref,
                        confidence=conf_value,
                    )
                    imported = result
                except ValueError as exc:
                    error = str(exc)
    return render_template(
        "contacts_import.html",
        active_tab="contacts",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Contacts",
        content_html="",
        csv_path=csv_path,
        csv_headers=csv_headers,
        mappings=mappings,
        imported=imported,
        error=error,
        source_system=source_system,
        source_ref=source_ref,
        confidence=confidence,
        fact_types=dao.FACT_TYPES,
    )
