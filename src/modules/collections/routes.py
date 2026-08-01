from flask import Blueprint, redirect, render_template, request, url_for

from common import collections as collections_mod
from common import data as db
from common import links_records
from common.utils import get_side_tabs, get_tabs, request_area_param


collections_bp = Blueprint("collections", __name__, url_prefix="/collections", template_folder="templates")

DOMAIN_TAB_MAP = {
    "3d": "3d",
    "apps": "apps",
    "audio": "audio",
    "calendar": "calendar",
    "data": "data",
    "files": "files",
    "goals": "goals",
    "how": "how",
    "media": "media",
    "money": "money",
    "notes": "notes",
    "people": "contacts",
    "places": "places",
}


def _area():
    return request_area_param(include_form=True, include_id=True)


def _form_values(adapter, form, area):
    selected_areas = form.getlist("area_ids")
    if not selected_areas and area:
        selected_areas = [area]
    return {
        "collection_name": form.get("collection_name", "").strip(),
        "collection_domain": adapter["collection_domain"],
        "collection_type": form.get("collection_type", "").strip() or adapter["collection_types"][0],
        "description": form.get("description", "").strip(),
        "icon": form.get("icon", "").strip(),
        "area_ids": selected_areas,
        "project_ids": form.getlist("project_ids"),
    }


def _source_options(adapter, collection_items, query):
    if not query:
        return []
    existing = {
        (item.get("item_type"), str(item.get("item_id")))
        for item in collection_items or []
        if item.get("entry_kind") == "item"
    }
    records = links_records.search_records(
        query,
        types=adapter.get("compatible_item_types", ()),
        limit=30,
    )
    for record in records:
        record["already_present"] = (record.get("type"), str(record.get("id"))) in existing
    return records


def _collection_url(domain, area=None, **kwargs):
    values = {"domain": domain}
    if area:
        values["area"] = area
    values.update({key: value for key, value in kwargs.items() if value not in (None, "")})
    return url_for("collections.collection_domain_route", **values)


@collections_bp.route("/<domain>", methods=["GET", "POST"])
def collection_domain_route(domain):
    area = _area()
    adapter = collections_mod.get_domain_adapter(domain)
    domain = adapter["collection_domain"]
    collections_mod.ensure_collections_schema(db._get_conn())
    message = request.args.get("message", "")
    error = ""
    active_status = request.values.get("status", "")
    include_archived = active_status == "all"

    if request.method == "POST":
        action = request.form.get("action", "")
        collection_id = request.form.get("collection_id", type=int)
        try:
            if action == "create":
                collection_id = collections_mod.create_collection(_form_values(adapter, request.form, area))
                message = f"{adapter['singular_label']} created."
            elif action == "save" and collection_id:
                collections_mod.update_collection(collection_id, _form_values(adapter, request.form, area))
                message = f"{adapter['singular_label']} saved."
            elif action == "archive" and collection_id:
                collections_mod.archive_collection(collection_id)
                message = f"{adapter['singular_label']} archived."
            elif action == "restore" and collection_id:
                collections_mod.restore_collection(collection_id)
                message = f"{adapter['singular_label']} restored."
            elif action == "delete" and collection_id:
                collections_mod.delete_collection(collection_id)
                return redirect(_collection_url(domain, area, message=f"{adapter['singular_label']} deleted."))
            elif action == "add_item" and collection_id:
                collections_mod.add_item_to_collection(
                    collection_id,
                    request.form.get("item_type"),
                    request.form.get("item_id"),
                    comments=request.form.get("comments", ""),
                )
            elif action == "add_heading" and collection_id and adapter.get("supports_headings"):
                collections_mod.add_heading_to_collection(collection_id, request.form.get("title_override"))
            elif action == "add_divider" and collection_id and adapter.get("supports_headings"):
                collections_mod.add_divider_to_collection(collection_id)
            elif action == "remove_entry":
                collections_mod.remove_item_from_collection(request.form.get("collection_item_id", type=int))
            elif action in {"move_up", "move_down"} and adapter.get("supports_manual_order"):
                collections_mod.move_collection_item(
                    request.form.get("collection_item_id", type=int),
                    direction="up" if action == "move_up" else "down",
                )
        except Exception as exc:
            error = str(exc)
        if not error:
            args = {"collection_id": collection_id, "status": active_status}
            return redirect(_collection_url(domain, area, **args))

    collection_type = request.args.get("type") or ""
    selected_collection_id = request.args.get("collection_id", type=int)
    collection_list = collections_mod.get_collection_list(
        domain=domain,
        collection_type=collection_type or None,
        area_id=area,
        include_archived=include_archived,
    )
    selected = collections_mod.get_collection(selected_collection_id) if selected_collection_id else None
    if selected and selected.get("collection_domain") != domain:
        selected = None
    if not selected and collection_list:
        selected = collection_list[0]
    collection_items = collections_mod.get_collection_items(selected["collection_id"]) if selected else []
    source_query = request.args.get("q", "").strip()

    return render_template(
        "generic_collections.html",
        active_tab=DOMAIN_TAB_MAP.get(domain, domain),
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=adapter["plural_label"],
        content_html="",
        subtab="manuals" if domain == "how" else "collections",
        adapter=adapter,
        domain=domain,
        area=area,
        message=message,
        error=error,
        collections=collection_list,
        selected_collection=selected,
        collection_items=collection_items,
        source_items=_source_options(adapter, collection_items, source_query) if selected else [],
        source_query=source_query,
        active_status=active_status,
        type_options=collections_mod.collection_type_options(domain),
        area_options=collections_mod.area_options(selected.get("area_ids") if selected else ([area] if area else [])),
        project_options=collections_mod.project_options(selected.get("project_ids") if selected else []),
    )
