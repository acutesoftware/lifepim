import os

from flask import Blueprint, abort, render_template, send_file, url_for

from common import data as db
from utils import markdown_utils


public_bp = Blueprint("public", __name__, url_prefix="/public", template_folder="templates")


@public_bp.route("/")
def public_index_route():
    return public_blog_route()


@public_bp.route("/blog")
def public_blog_route():
    rows = db._get_conn().execute(
        """
        SELECT id, file_name, path, rec_extract_date, show_in_blog
        FROM lp_notes
        WHERE is_public=1 AND show_in_blog=1
        ORDER BY rec_extract_date DESC
        LIMIT 100
        """
    ).fetchall()
    notes = [dict(row) for row in rows]
    return render_template("public_blog.html", notes=notes)


@public_bp.route("/notes/<int:note_id>")
def public_note_route(note_id):
    row = db._get_conn().execute(
        "SELECT id, file_name, path, is_public FROM lp_notes WHERE id=? AND is_public=1",
        (note_id,),
    ).fetchone()
    if not row:
        abort(404)
    note = dict(row)
    note_path = _note_path(note)
    text = ""
    if note_path and os.path.isfile(note_path):
        with open(note_path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    content_html = markdown_utils.render_markdown(text)
    return render_template("public_note.html", note=note, content_html=content_html)


@public_bp.route("/media/<int:media_id>")
def public_media_file_route(media_id):
    row = db._get_conn().execute(
        "SELECT media_id, path, filename, is_public FROM lp_media WHERE media_id=? AND is_public=1",
        (media_id,),
    ).fetchone()
    if not row:
        abort(404)
    item = dict(row)
    full_path = item.get("path") or ""
    if full_path and item.get("filename") and os.path.isdir(full_path):
        full_path = os.path.join(full_path, item["filename"])
    if not full_path or not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path)


def _note_path(note):
    path = (note.get("path") or "").strip()
    file_name = (note.get("file_name") or "").strip()
    if path and file_name:
        return os.path.join(path, file_name)
    return path or file_name
