from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from common.utils import get_side_tabs, get_tabs
from modules.how import service


how_bp = Blueprint("how", __name__, url_prefix="/how", template_folder="templates", static_folder="static")


def _project():
    return service.normalize_project(
        request.form.get("project_id") or request.args.get("proj") or request.form.get("proj") or ""
    )


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
    project = _project()
    return render_template(
        "how_list.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="HOW",
        content_html="",
        subtab="howtos",
        project=project,
        items=service.list_howtos(project),
    )


@how_bp.route("/howtos/<int:item_id>")
@how_bp.route("/view/<int:item_id>")
def view_how_route(item_id):
    project = _project()
    detail = service.get_howto_detail(item_id)
    if not detail:
        return redirect(url_for("how.list_how_route", proj=project))
    return render_template(
        "how_view.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=detail["howto"].get("title") or "HOW",
        content_html="",
        subtab="howtos",
        project=project,
        detail=detail,
        tree=service.build_tree(item_id, max_depth=8),
    )


@how_bp.route("/howtos/new", methods=["GET"])
@how_bp.route("/add", methods=["GET"])
def add_how_route():
    project = _project()
    title = "Untitled How-to"
    markdown = (
        "---\n"
        "status: draft\n"
        "---\n\n"
        "## Summary\n\nTODO\n\n"
        "## Outcome\n\nTODO\n\n"
        "## Steps\n\n1. TODO\n"
    )
    return _render_editor(project, None, markdown, None, blueprint_name=title)


@how_bp.route("/howtos/<int:item_id>/edit", methods=["GET"])
@how_bp.route("/edit/<int:item_id>", methods=["GET"])
def edit_how_route(item_id):
    project = _project()
    item = service.get_howto(item_id)
    if not item:
        return redirect(url_for("how.list_how_route", proj=project))
    markdown = item.get("markdown_full_content") or ""
    if not markdown and item.get("source_filepath"):
        try:
            with open(item["source_filepath"], "r", encoding="utf-8", errors="replace") as handle:
                markdown = handle.read()
        except OSError:
            markdown = ""
    return _render_editor(project or item.get("project_id"), item, markdown, None)


def _render_editor(project, item, markdown, preview, blueprint_name=None):
    project = service.normalize_project(project or (item.get("project_id") if item else ""))
    project_options = service.project_options(project)
    selected_project = project or next((opt["project_id"] for opt in project_options if opt.get("selected")), "")
    save_folder = service.how_save_folder(selected_project)
    return render_template(
        "how_edit.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="HOW Blueprint",
        content_html="",
        subtab="howtos",
        project=project,
        item=item,
        markdown=markdown,
        preview=preview,
        blueprint_name=blueprint_name or _blueprint_name_from_item(item),
        project_options=project_options,
        save_folder=save_folder,
    )


@how_bp.route("/howtos/preview", methods=["POST"])
@how_bp.route("/preview", methods=["POST"])
def preview_how_route():
    project = _project()
    item_id = request.form.get("howto_id", type=int)
    item = service.get_howto(item_id) if item_id else None
    markdown = request.form.get("markdown", "")
    blueprint_name = request.form.get("blueprint_name", "").strip()
    preview = service.build_preview_model(markdown, title=blueprint_name, project_id=project)
    if request.headers.get("Accept") == "application/json":
        return jsonify(preview)
    return _render_editor(project, item, markdown, preview, blueprint_name=blueprint_name)


@how_bp.route("/howtos/save", methods=["POST"])
@how_bp.route("/save", methods=["POST"])
def save_how_route():
    project = _project()
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
            project_id=project,
            blueprint_name=blueprint_name,
        )
    except Exception as exc:
        preview = service.build_preview_model(markdown, title=blueprint_name, project_id=project)
        preview["save_error"] = str(exc)
        return _render_editor(project, item, markdown, preview, blueprint_name=blueprint_name)
    return redirect(url_for("how.view_how_route", item_id=howto_id, proj=project))


@how_bp.route("/catalog/<kind>")
def catalog_route(kind):
    if kind not in {"tools", "parts", "steps"}:
        return redirect(url_for("how.list_how_route", proj=_project()))
    project = _project()
    return render_template(
        "how_catalog.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="HOW",
        content_html="",
        subtab=kind,
        project=project,
        kind=kind,
        items=service.list_catalog(kind, project),
        edit_item=None,
    )


@how_bp.route("/catalog/<kind>/add", methods=["POST"])
def catalog_add_route(kind):
    service.upsert_catalog(kind, request.form)
    return redirect(url_for("how.catalog_route", kind=kind, proj=_project()))


@how_bp.route("/tree/<int:item_id>")
def tree_route(item_id):
    return jsonify(service.build_tree(item_id))


@how_bp.route("/howtos/<int:item_id>/create-child", methods=["POST"])
def create_child_route(item_id):
    child_key = request.form.get("child_key", "")
    try:
        child_id = service.create_child_stub(item_id, child_key)
    except Exception:
        return redirect(url_for("how.view_how_route", item_id=item_id, proj=_project()))
    return redirect(url_for("how.edit_how_route", item_id=child_id, proj=_project()))


@how_bp.route("/delete/<int:item_id>", methods=["POST"])
def delete_how_route(item_id):
    conn = service.get_conn()
    conn.execute("DELETE FROM lp_howto WHERE howto_id = ?", (item_id,))
    conn.commit()
    return redirect(url_for("how.list_how_route", proj=_project()))


@how_bp.route("/howtos/<int:item_id>/convert-to-note", methods=["POST"])
def convert_howto_to_note_route(item_id):
    project = _project()
    try:
        note_id = service.convert_howto_to_note(item_id)
    except Exception:
        return redirect(url_for("how.list_how_route", proj=project))
    return redirect(url_for("notes.view_note_route", note_id=note_id))
