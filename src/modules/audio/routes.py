import mimetypes
import os
import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, url_for, send_file, abort, redirect

from common import data as db
from common.utils import get_side_tabs, get_table_def, get_tabs, paginate_total, build_pagination
from common import config as cfg


audio_bp = Blueprint(
    "audio",
    __name__,
    url_prefix="/audio",
    template_folder="templates",
    static_folder="static",
)


AUDIO_PLAYLIST_SCHEMA = """
CREATE TABLE IF NOT EXISTS lp_audio_playlists (
    playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_audio_playlists_name
ON lp_audio_playlists (name);

CREATE TABLE IF NOT EXISTS lp_audio_playlist_items (
    playlist_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL,
    audio_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 100,
    added_utc TEXT NOT NULL,
    UNIQUE (playlist_id, audio_id)
);

CREATE INDEX IF NOT EXISTS ix_audio_playlist_items_playlist
ON lp_audio_playlist_items (playlist_id, sort_order);

CREATE INDEX IF NOT EXISTS ix_audio_playlist_items_audio
ON lp_audio_playlist_items (audio_id);
"""

DEFAULT_PLAYLIST_NAME = "Recent 50"


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_playlist_schema(conn=None):
    conn = db._get_conn() if conn is None else conn
    conn.executescript(AUDIO_PLAYLIST_SCHEMA)
    conn.commit()
    return conn


def _get_playlist(conn, playlist_id):
    if not playlist_id:
        return None
    row = conn.execute(
        "SELECT playlist_id, name, description, is_default "
        "FROM lp_audio_playlists WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()
    return dict(row) if row else None


def _list_playlists(conn):
    rows = conn.execute(
        "SELECT p.playlist_id, p.name, p.description, p.is_default, "
        "  (SELECT COUNT(1) FROM lp_audio_playlist_items i WHERE i.playlist_id = p.playlist_id) AS track_count "
        "FROM lp_audio_playlists p "
        "ORDER BY p.is_default DESC, p.name"
    ).fetchall()
    return [dict(row) for row in rows]


def _seed_default_playlist(conn, playlist_id):
    if not playlist_id:
        return
    row = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_audio_playlist_items WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()
    if row and row["cnt"]:
        return
    tbl = _get_tbl()
    if not tbl:
        return
    audio_exts = [
        "mp3",
        "wav",
        "flac",
        "aac",
        "m4a",
        "m4b",
        "ogg",
        "opus",
        "wma",
        "aiff",
        "aif",
        "alac",
    ]
    file_name_clause = " OR ".join(["lower(file_name) LIKE ?" for _ in audio_exts])
    file_type_clause = " OR ".join(["lower(file_type) = ?" for _ in audio_exts])
    if file_name_clause and file_type_clause:
        where_clause = f"({file_name_clause} OR {file_type_clause})"
    elif file_name_clause:
        where_clause = f"({file_name_clause})"
    else:
        where_clause = "1=1"
    params = [f"%.{ext}" for ext in audio_exts] + audio_exts
    rows = conn.execute(
        f"SELECT id FROM {tbl['name']} WHERE {where_clause} "
        "ORDER BY COALESCE(NULLIF(date_modified, ''), rec_extract_date) DESC, id DESC "
        "LIMIT 50",
        params,
    ).fetchall()
    now = _utc_now()
    sort_order = 1
    for row in rows:
        audio_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        conn.execute(
            "INSERT OR IGNORE INTO lp_audio_playlist_items "
            "(playlist_id, audio_id, sort_order, added_utc) VALUES (?, ?, ?, ?)",
            (playlist_id, audio_id, sort_order, now),
        )
        sort_order += 1
    conn.commit()


def _ensure_default_playlist(conn):
    row = conn.execute(
        "SELECT playlist_id, name, description, is_default "
        "FROM lp_audio_playlists WHERE is_default = 1 ORDER BY playlist_id LIMIT 1"
    ).fetchone()
    if not row:
        now = _utc_now()
        try:
            conn.execute(
                "INSERT INTO lp_audio_playlists "
                "(name, description, is_default, created_utc, updated_utc) "
                "VALUES (?, ?, 1, ?, ?)",
                (DEFAULT_PLAYLIST_NAME, "Auto playlist (50 most recent songs)", now, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        row = conn.execute(
            "SELECT playlist_id, name, description, is_default "
            "FROM lp_audio_playlists WHERE name = ? ORDER BY playlist_id LIMIT 1",
            (DEFAULT_PLAYLIST_NAME,),
        ).fetchone()
        if row and not row["is_default"]:
            conn.execute(
                "UPDATE lp_audio_playlists SET is_default = 1, updated_utc = ? WHERE playlist_id = ?",
                (now, row["playlist_id"]),
            )
            conn.commit()
            row = conn.execute(
                "SELECT playlist_id, name, description, is_default "
                "FROM lp_audio_playlists WHERE playlist_id = ?",
                (row["playlist_id"],),
            ).fetchone()
    playlist = dict(row) if row else None
    if playlist:
        _seed_default_playlist(conn, playlist["playlist_id"])
    return playlist


def _fetch_playlist_items(conn, playlist_id):
    tbl = _get_tbl()
    if not tbl or not playlist_id:
        return []
    cols = ["id"] + tbl["col_list"]
    select_cols = ", ".join([f"a.{col}" for col in cols])
    rows = conn.execute(
        "SELECT "
        f"{select_cols}, i.sort_order, i.added_utc "
        "FROM lp_audio_playlist_items i "
        f"JOIN {tbl['name']} a ON a.id = i.audio_id "
        "WHERE i.playlist_id = ? "
        "ORDER BY i.sort_order, i.playlist_item_id",
        (playlist_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _get_tbl():
    return get_table_def("audio")


def _fetch_audio(project=None, sort_col=None, sort_dir=None, limit=None, offset=None):
    tbl = _get_tbl()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    order_map = {
        "file_name": "t.file_name",
        "path": "t.path",
        "file_type": "t.file_type",
        "size": "t.size",
        "date_modified": "t.date_modified",
        "artist": "t.artist",
        "album": "t.album",
        "song": "t.song",
        "project": "t.project",
    }
    sort_key = order_map.get(sort_col or "file_name", "t.file_name")
    sort_dir = sort_dir or "asc"
    order_by = f"{sort_key} {sort_dir}"
    rows = db.get_mapped_rows(
        db.conn,
        tbl["name"],
        cols,
        tab=project,
        limit=limit,
        offset=offset,
        order_by=order_by,
    )
    return [dict(row) for row in rows]


def _sort_items(items, sort_col, sort_dir):
    reverse = sort_dir == "desc"
    return sorted(items, key=lambda i: (i.get(sort_col) or ""), reverse=reverse)


@audio_bp.route("/")
def list_audio_route():
    return list_audio_table_route()


@audio_bp.route("/table")
def list_audio_table_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "file_name"
    sort_dir = request.args.get("dir") or "asc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_audio(project, sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "audio.list_audio_table_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    tbl = _get_tbl()
    col_list = tbl["col_list"] if tbl else []
    conn = _ensure_playlist_schema()
    _ensure_default_playlist(conn)
    playlists = _list_playlists(conn)
    return render_template(
        "audio_list_table.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Audio ({project or 'All'})",
        content_html="",
        items=items,
        col_list=col_list,
        project=project,
        playlists=playlists,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@audio_bp.route("/list")
def list_audio_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_audio(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "audio.list_audio_list_route",
        {"proj": project},
        page,
        total_pages,
    )
    conn = _ensure_playlist_schema()
    _ensure_default_playlist(conn)
    playlists = _list_playlists(conn)
    return render_template(
        "audio_list_list.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Audio ({project or 'All'})",
        content_html="",
        items=items,
        project=project,
        playlists=playlists,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@audio_bp.route("/player")
def audio_player_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "file_name"
    sort_dir = request.args.get("dir") or "asc"
    limit = request.args.get("limit", type=int) or 200
    start_id = request.args.get("id", type=int)
    playlist_id = request.args.get("playlist_id", type=int)
    playlist_name = None
    if playlist_id:
        conn = _ensure_playlist_schema()
        playlist = _get_playlist(conn, playlist_id)
        if playlist:
            playlist_name = playlist.get("name")
            items = _fetch_playlist_items(conn, playlist_id)
        else:
            items = _fetch_audio(project, sort_col, sort_dir, limit=limit, offset=0)
    else:
        items = _fetch_audio(project, sort_col, sort_dir, limit=limit, offset=0)
    tracks = []
    for item in items:
        audio_url = url_for("audio.audio_file_route", item_id=item.get("id"))
        tracks.append(
            {
                "id": item.get("id"),
                "title": item.get("song") or item.get("file_name") or "",
                "artist": item.get("artist") or "",
                "album": item.get("album") or "",
                "path": item.get("path") or "",
                "url": audio_url,
            }
        )
    return render_template(
        "audio_player.html",
        tracks=tracks,
        project=project,
        start_id=start_id,
        sort_col=sort_col,
        sort_dir=sort_dir,
        limit=limit,
        playlist_name=playlist_name,
        show_freq_bar=(getattr(cfg, "AUDIO_SHOW_FREQ_BAR", "Y") or "Y").upper() == "Y",
    )


@audio_bp.route("/playlists/create", methods=["POST"])
def create_playlist_route():
    project = request.args.get("proj")
    name = (request.form.get("playlist_name") or "").strip()
    if not name:
        return redirect(url_for("audio.list_audio_list_route", proj=project))
    conn = _ensure_playlist_schema()
    now = _utc_now()
    try:
        conn.execute(
            "INSERT INTO lp_audio_playlists "
            "(name, description, is_default, created_utc, updated_utc) "
            "VALUES (?, '', 0, ?, ?)",
            (name, now, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return redirect(url_for("audio.list_audio_list_route", proj=project))


@audio_bp.route("/playlists/add", methods=["POST"])
def add_playlist_items_route():
    project = request.args.get("proj")
    playlist_id = request.form.get("playlist_id", type=int)
    item_ids = []
    for val in request.form.getlist("item_id"):
        if not val:
            continue
        try:
            item_ids.append(int(val))
        except (TypeError, ValueError):
            continue
    if not playlist_id or not item_ids:
        return redirect(url_for("audio.list_audio_list_route", proj=project))
    conn = _ensure_playlist_schema()
    playlist = _get_playlist(conn, playlist_id)
    if not playlist:
        return redirect(url_for("audio.list_audio_list_route", proj=project))
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS max_sort "
        "FROM lp_audio_playlist_items WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()
    sort_order = (row["max_sort"] if row else 0) + 1
    now = _utc_now()
    for item_id in item_ids:
        conn.execute(
            "INSERT OR IGNORE INTO lp_audio_playlist_items "
            "(playlist_id, audio_id, sort_order, added_utc) VALUES (?, ?, ?, ?)",
            (playlist_id, item_id, sort_order, now),
        )
        sort_order += 1
    conn.commit()
    return redirect(url_for("audio.list_audio_list_route", proj=project))


@audio_bp.route("/playlists/<int:playlist_id>")
def view_playlist_route(playlist_id):
    project = request.args.get("proj")
    conn = _ensure_playlist_schema()
    _ensure_default_playlist(conn)
    playlist = _get_playlist(conn, playlist_id)
    if not playlist:
        return redirect(url_for("audio.list_audio_list_route", proj=project))
    items = _fetch_playlist_items(conn, playlist_id)
    player_url = url_for("audio.audio_player_route", playlist_id=playlist_id)
    return render_template(
        "audio_playlist_view.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Playlist: {playlist.get('name')}",
        content_html="",
        playlist=playlist,
        items=items,
        project=project,
        player_url=player_url,
    )


@audio_bp.route("/playlists/<int:playlist_id>/delete", methods=["POST"])
def delete_playlist_route(playlist_id):
    project = request.args.get("proj")
    conn = _ensure_playlist_schema()
    conn.execute("DELETE FROM lp_audio_playlist_items WHERE playlist_id = ?", (playlist_id,))
    conn.execute("DELETE FROM lp_audio_playlists WHERE playlist_id = ?", (playlist_id,))
    conn.commit()
    return redirect(url_for("audio.list_audio_list_route", proj=project))


@audio_bp.route("/playlists/<int:playlist_id>/remove/<int:audio_id>", methods=["POST"])
def remove_playlist_item_route(playlist_id, audio_id):
    project = request.args.get("proj")
    conn = _ensure_playlist_schema()
    conn.execute(
        "DELETE FROM lp_audio_playlist_items WHERE playlist_id = ? AND audio_id = ?",
        (playlist_id, audio_id),
    )
    conn.commit()
    return redirect(url_for("audio.view_playlist_route", playlist_id=playlist_id, proj=project))


@audio_bp.route("/import", methods=["GET", "POST"])
def import_audio_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = _get_tbl()
    imported = None
    error = ""
    if request.method == "POST" and tbl:
        folder_path = request.form.get("audio_folder", "").strip()
        if not folder_path:
            error = "No folder provided."
        elif not os.path.isdir(folder_path):
            error = "Folder not found."
        else:
            count = 0
            for root, _, files in os.walk(folder_path):
                for name in files:
                    full_path = os.path.join(root, name)
                    if not os.path.isfile(full_path):
                        continue
                    ext = os.path.splitext(name)[1].lower()
                    file_type = ext.lstrip(".")
                    values = [
                        name,
                        root,
                        "",
                        file_type,
                        "",
                        "",
                        "",
                        "",
                        "",
                        project,
                    ]
                    record_id = db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
                    if record_id:
                        count += 1
            imported = count
    return render_template(
        "audio_import.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Audio Folder",
        content_html="",
        project=project,
        imported=imported,
        error=error,
    )


@audio_bp.route("/view/<int:item_id>")
def view_audio_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
        if rows:
            item = dict(rows[0])
    if not item:
        return list_audio_table_route()
    full_path = os.path.join(item.get("path") or "", item.get("file_name") or "")
    audio_url = url_for("audio.audio_file_route", item_id=item_id)
    return render_template(
        "audio_view.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("file_name", "Audio"),
        content_html="",
        item=item,
        project=project,
        audio_url=audio_url,
        file_exists=os.path.exists(full_path),
    )


@audio_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_audio_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
        if rows:
            item = dict(rows[0])
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.update_record(db.conn, tbl["name"], item_id, tbl["col_list"], values)
        return redirect(url_for("audio.view_audio_route", item_id=item_id, proj=project))
    return render_template(
        "audio_edit.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Audio",
        content_html="",
        item=item,
        project=project,
        col_list=tbl["col_list"] if tbl else [],
    )


@audio_bp.route("/delete/<int:item_id>")
def delete_audio_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("audio.list_audio_table_route", proj=project))


@audio_bp.route("/file/<int:item_id>")
def audio_file_route(item_id):
    tbl = _get_tbl()
    if not tbl:
        abort(404)
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    if not rows:
        abort(404)
    item = dict(rows[0])
    full_path = os.path.join(item.get("path") or "", item.get("file_name") or "")
    if not os.path.exists(full_path):
        abort(404)
    mime_type, _ = mimetypes.guess_type(full_path)
    return send_file(full_path, mimetype=mime_type or "application/octet-stream")
