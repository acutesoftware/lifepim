from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from common.utils import get_side_tabs, get_tabs, request_area_param
from modules.how import service


how_bp = Blueprint("how", __name__, url_prefix="/how", template_folder="templates", static_folder="static")


def _area():
    return service.normalize_area(request_area_param(include_form=True, include_id=True))


def _blueprint_name_from_item(item):
    if not item:
        return "Untitled How-to"
    source = item.get("source_filepath") or ""
    if source:
        import os

        return os.path.splitext(os.path.basename(source))[0]
    return item.get("title") or "Untitled How-to"


@how_bp.route("/")
@how_bp.route("/howtos")
def list_how_route():
    area = _area()
    return render_template(
        "how_list.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="HOW",
        content_html="",
        subtab="howtos",
        area=area,
        items=service.list_howtos(area),
    )


@how_bp.route("/howtos/<int:item_id>")
@how_bp.route("/view/<int:item_id>")
def view_how_route(item_id):
    area = _area()
    detail = service.get_howto_detail(item_id)
    if not detail:
        return redirect(url_for("how.list_how_route", area=area))
    return render_template(
        "how_view.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=detail["howto"].get("title") or "HOW",
        content_html="",
        subtab="howtos",
        area=area,
        detail=detail,
        tree=service.build_tree(item_id, max_depth=8),
    )


@how_bp.route("/howtos/new", methods=["GET"])
@how_bp.route("/add", methods=["GET"])
def add_how_route():
    area = _area()
    title = "Untitled How-to"
    markdown = (
        "---\n"
        "status: draft\n"
        "---\n\n"
        "## Summary\n\nTODO\n\n"
        "## Outcome\n\nTODO\n\n"
        "## Steps\n\n1. TODO\n"
    )
    return _render_editor(area, None, markdown, None, blueprint_name=title)


@how_bp.route("/howtos/<int:item_id>/edit", methods=["GET"])
@how_bp.route("/edit/<int:item_id>", methods=["GET"])
def edit_how_route(item_id):
    area = _area()
    item = service.get_howto(item_id)
    if not item:
        return redirect(url_for("how.list_how_route", area=area))
    markdown = item.get("markdown_full_content") or ""
    if not markdown and item.get("source_filepath"):
        try:
            with open(item["source_filepath"], "r", encoding="utf-8", errors="replace") as handle:
                markdown = handle.read()
        except OSError:
            markdown = ""
    return _render_editor(area or item.get("area_id"), item, markdown, None)


def _render_editor(area, item, markdown, preview, blueprint_name=None):
    area = service.normalize_area(area or (item.get("area_id") if item else ""))
    area_options = service.area_options(area)
    selected_area = area or next((opt["area_id"] for opt in area_options if opt.get("selected")), "")
    save_folder = service.how_save_folder(selected_area)
    return render_template(
        "how_edit.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="HOW Blueprint",
        content_html="",
        subtab="howtos",
        area=area,
        item=item,
        markdown=markdown,
        preview=preview,
        blueprint_name=blueprint_name or _blueprint_name_from_item(item),
        area_options=area_options,
        save_folder=save_folder,
    )


@how_bp.route("/howtos/preview", methods=["POST"])
@how_bp.route("/preview", methods=["POST"])
def preview_how_route():
    area = _area()
    item_id = request.form.get("howto_id", type=int)
    item = service.get_howto(item_id) if item_id else None
    markdown = request.form.get("markdown", "")
    blueprint_name = request.form.get("blueprint_name", "").strip()
    preview = service.build_preview_model(markdown, title=blueprint_name, area_id=area)
    if request.headers.get("Accept") == "application/json":
        return jsonify(preview)
    return _render_editor(area, item, markdown, preview, blueprint_name=blueprint_name)


@how_bp.route("/howtos/save", methods=["POST"])
@how_bp.route("/save", methods=["POST"])
def save_how_route():
    area = _area()
    item_id = request.form.get("howto_id", type=int)
    item = service.get_howto(item_id) if item_id else None
    source_filepath = item.get("source_filepath") if item else request.form.get("source_filepath")
    markdown = request.form.get("markdown", "")
    blueprint_name = request.form.get("blueprint_name", "").strip()
    try:
        howto_id = service.apply_markdown(
            markdown,
            source_filepath=source_filepath,
            title=blueprint_name,
            area_id=area,
            blueprint_name=blueprint_name,
        )
    except Exception as exc:
        preview = service.build_preview_model(markdown, title=blueprint_name, area_id=area)
        preview["save_error"] = str(exc)
        return _render_editor(area, item, markdown, preview, blueprint_name=blueprint_name)
    return redirect(url_for("how.view_how_route", item_id=howto_id, area=area))


@how_bp.route("/catalog/<kind>")
def catalog_route(kind):
    if kind not in {"tools", "parts", "steps"}:
        return redirect(url_for("how.list_how_route", area=_area()))
    area = _area()
    message = request.args.get("message", "")
    selected_area = area
    return render_template(
        "how_catalog.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="HOW",
        content_html="",
        subtab=kind,
        area=area,
        kind=kind,
        items=service.list_catalog(kind, area),
        edit_item=None,
        message=message,
        area_options=service.area_options(selected_area, include_blank=True, select_first=False),
    )


@how_bp.route("/catalog/<kind>/add", methods=["POST"])
def catalog_add_route(kind):
    service.upsert_catalog(kind, request.form)
    return redirect(url_for("how.catalog_route", kind=kind, area=_area()))


@how_bp.route("/catalog/<kind>/<int:item_id>/edit", methods=["GET", "POST"])
def catalog_edit_route(kind, item_id):
    if kind not in {"tools", "parts"}:
        return redirect(url_for("how.catalog_route", kind=kind, area=_area()))
    area = _area()
    if request.method == "POST":
        service.upsert_catalog(kind, request.form, item_id=item_id)
        return redirect(url_for("how.catalog_route", kind=kind, area=area))
    return render_template(
        "how_catalog.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="HOW",
        content_html="",
        subtab=kind,
        area=area,
        kind=kind,
        items=service.list_catalog(kind, area),
        edit_item=service.get_catalog_item(kind, item_id),
        message="",
        area_options=service.area_options(
            (service.get_catalog_item(kind, item_id) or {}).get("area_id") or area,
            include_blank=True,
            select_first=False,
        ),
    )


@how_bp.route("/catalog/<kind>/<int:item_id>/delete", methods=["POST"])
def catalog_delete_route(kind, item_id):
    area = _area()
    try:
        service.delete_catalog_item(kind, item_id)
        message = ""
    except Exception as exc:
        message = str(exc)
    return redirect(url_for("how.catalog_route", kind=kind, area=area, message=message))


@how_bp.route("/tree/<int:item_id>")
def tree_route(item_id):
    return jsonify(service.build_tree(item_id))


@how_bp.route("/howtos/<int:item_id>/create-child", methods=["POST"])
def create_child_route(item_id):
    child_key = request.form.get("child_key", "")
    try:
        child_id = service.create_child_stub(item_id, child_key)
    except Exception:
        return redirect(url_for("how.view_how_route", item_id=item_id, area=_area()))
    return redirect(url_for("how.edit_how_route", item_id=child_id, area=_area()))


@how_bp.route("/delete/<int:item_id>", methods=["POST"])
def delete_how_route(item_id):
    conn = service.get_conn()
    conn.execute("DELETE FROM lp_howto WHERE howto_id = ?", (item_id,))
    conn.commit()
    return redirect(url_for("how.list_how_route", area=_area()))


@how_bp.route("/howtos/<int:item_id>/convert-to-note", methods=["POST"])
def convert_howto_to_note_route(item_id):
    area = _area()
    try:
        note_id = service.convert_howto_to_note(item_id)
    except Exception:
        return redirect(url_for("how.list_how_route", area=area))
    return redirect(url_for("notes.view_note_route", note_id=note_id))
