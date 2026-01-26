import json
import mimetypes
import os
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template, request, url_for, send_file, abort, redirect

from common import data as db
from common import config as cfg
from common.media_schema import ensure_media_schema
from common.search import parse_search_terms
from common.utils import get_side_tabs, get_tabs, paginate_total, build_pagination


media_bp = Blueprint(
    "media",
    __name__,
    url_prefix="/media",
    template_folder="templates",
    static_folder="static",
)


_MEDIA_SCHEMA_READY = False


MEDIA_SEARCH_COLS = [
    "m.filename",
    "m.path",
    "m.ext",
    "meta.camera_make",
    "meta.camera_model",
    "tags.tags_text",
]

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpg", ".mpeg", ".wmv"}


def _ensure_schema():
    global _MEDIA_SCHEMA_READY
    if _MEDIA_SCHEMA_READY:
        return
    conn = db._get_conn()
    ensure_media_schema(conn)
    _MEDIA_SCHEMA_READY = True


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _current_user():
    return db._current_user()


def _parse_utc(value):
    if not value:
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _build_media_path(item):
    path_value = (item.get("path") or "").strip()
    filename = (item.get("filename") or "").strip()
    if path_value and os.path.isfile(path_value):
        return path_value
    if path_value and filename:
        return os.path.join(path_value, filename)
    return path_value or filename


def _is_video(item):
    if (item.get("media_type") or "").lower() == "video":
        return True
    ext = (item.get("ext") or "").lower()
    return f".{ext}" in VIDEO_EXTS


def _coerce_int_list(values):
    items = []
    for value in values or []:
        try:
            items.append(int(value))
        except (TypeError, ValueError):
            continue
    return items


def _normalize_view(value):
    value = (value or "all").strip().lower()
    if value in {"all", "timeline", "albums", "events", "smart"}:
        return value
    return "all"


def _normalize_view_mode(value):
    value = (value or "filmstrip").strip().lower()
    if value in {"filmstrip", "grid", "table"}:
        return value
    return "filmstrip"


def _normalize_sort(value):
    value = (value or "taken_desc").strip().lower()
    if value in {"taken_desc", "mtime_desc", "filename"}:
        return value
    return "taken_desc"


def _normalize_group(value):
    value = (value or "month").strip().lower()
    if value in {"year", "month", "day"}:
        return value
    return "month"


def _normalize_bool(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _query_string(args):
    if not args:
        return ""
    clean = {k: v for k, v in args.items() if v not in (None, "", False)}
    if not clean:
        return ""
    return urlencode(clean)


def _build_search_conditions(terms, where, params):
    if not terms:
        return
    for term in terms:
        like_value = f"%{term.lower()}%"
        clause = " OR ".join([f"lower({col}) LIKE ?" for col in MEDIA_SEARCH_COLS])
        where.append(f"({clause})")
        params.extend([like_value] * len(MEDIA_SEARCH_COLS))


def _build_media_filters(
    scope,
    album_id,
    event_id,
    search_everywhere,
    media_type,
    base_terms,
    extra_terms,
    year_filter,
):
    joins = []
    where = ["1=1"]
    params = []
    if scope == "album" and album_id and not search_everywhere:
        joins.append("JOIN lp_album_items ai ON ai.media_id = m.media_id AND ai.album_id = ?")
        params.append(album_id)
    if scope == "event" and event_id and not search_everywhere:
        joins.append("JOIN lp_event_items ei ON ei.media_id = m.media_id AND ei.event_id = ?")
        params.append(event_id)
    if media_type:
        where.append("m.media_type = ?")
        params.append(media_type)
    if year_filter:
        where.append("substr(COALESCE(meta.taken_utc, m.mtime_utc), 1, 4) = ?")
        params.append(str(year_filter))
    _build_search_conditions(base_terms, where, params)
    _build_search_conditions(extra_terms, where, params)
    return joins, where, params


def _media_order_clause(sort_key):
    if sort_key == "mtime_desc":
        return "m.mtime_utc DESC"
    if sort_key == "filename":
        return "m.filename ASC"
    return "sort_utc DESC"


def _fetch_media(conn, joins, where, params, sort_key, limit=None, offset=None):
    select_cols = [
        "m.media_id",
        "m.path",
        "m.filename",
        "m.ext",
        "m.media_type",
        "m.size_bytes",
        "m.mtime_utc",
        "m.ctime_utc",
        "m.hash",
        "meta.taken_utc",
        "meta.width",
        "meta.height",
        "meta.duration_sec",
        "meta.fps",
        "meta.codec",
        "meta.camera_make",
        "meta.camera_model",
        "tags.tags_text",
        "COALESCE(meta.taken_utc, m.mtime_utc) AS sort_utc",
    ]
    sql = (
        "SELECT "
        + ", ".join(select_cols)
        + " FROM lp_media m "
        + "LEFT JOIN lp_media_meta meta ON meta.media_id = m.media_id "
        + "LEFT JOIN ("
        "  SELECT mt.media_id, group_concat(t.tag, ' ') AS tags_text "
        "  FROM lp_media_tags mt "
        "  JOIN lp_tags t ON t.tag_id = mt.tag_id "
        "  GROUP BY mt.media_id"
        ") tags ON tags.media_id = m.media_id "
        + (" ".join(joins) + " " if joins else "")
        + "WHERE "
        + " AND ".join(where)
        + " ORDER BY "
        + _media_order_clause(sort_key)
    )
    sql_params = list(params)
    if limit is not None:
        sql += " LIMIT ?"
        sql_params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            sql_params.append(int(offset))
    rows = conn.execute(sql, sql_params).fetchall()
    return [dict(row) for row in rows]


def _count_media(conn, joins, where, params):
    sql = (
        "SELECT COUNT(1) AS cnt FROM lp_media m "
        "LEFT JOIN lp_media_meta meta ON meta.media_id = m.media_id "
        "LEFT JOIN ("
        "  SELECT mt.media_id, group_concat(t.tag, ' ') AS tags_text "
        "  FROM lp_media_tags mt "
        "  JOIN lp_tags t ON t.tag_id = mt.tag_id "
        "  GROUP BY mt.media_id"
        ") tags ON tags.media_id = m.media_id "
        + (" ".join(joins) + " " if joins else "")
        + "WHERE "
        + " AND ".join(where)
    )
    row = conn.execute(sql, params).fetchone()
    return row["cnt"] if row else 0


def _fetch_timeline_years(conn, joins, where, params):
    sql = (
        "SELECT substr(COALESCE(meta.taken_utc, m.mtime_utc), 1, 4) AS yr, "
        "COUNT(1) AS cnt "
        "FROM lp_media m "
        "LEFT JOIN lp_media_meta meta ON meta.media_id = m.media_id "
        + (" ".join(joins) + " " if joins else "")
        + "WHERE "
        + " AND ".join(where)
        + " GROUP BY yr "
        " ORDER BY yr DESC"
    )
    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        if item.get("yr"):
            results.append(item)
    return results


def _group_media(items, group_by):
    groups = []
    current_label = None
    current_items = []
    for item in items:
        sort_utc = item.get("sort_utc") or ""
        date_part = sort_utc[:10] if sort_utc else "Unknown"
        if group_by == "year":
            label = date_part[:4] if date_part else "Unknown"
        elif group_by == "day":
            label = date_part or "Unknown"
        else:
            label = date_part[:7] if date_part else "Unknown"
        if label != current_label:
            if current_items:
                groups.append({"label": current_label, "items": current_items})
            current_label = label
            current_items = []
        current_items.append(item)
    if current_items:
        groups.append({"label": current_label, "items": current_items})
    return groups


def _list_albums(conn):
    rows = conn.execute(
        "SELECT a.album_id, a.title, a.description, a.cover_media_id, a.album_type, "
        "  (SELECT COUNT(1) FROM lp_album_items i WHERE i.album_id = a.album_id) AS item_count, "
        "  m.path AS cover_path, m.filename AS cover_filename "
        "FROM lp_albums a "
        "LEFT JOIN lp_media m ON m.media_id = a.cover_media_id "
        "ORDER BY lower(a.title)"
    ).fetchall()
    return [dict(row) for row in rows]


def _get_album(conn, album_id):
    if not album_id:
        return None
    row = conn.execute(
        "SELECT album_id, title, description, cover_media_id, album_type, created_utc, updated_utc "
        "FROM lp_albums WHERE album_id = ?",
        (album_id,),
    ).fetchone()
    return dict(row) if row else None


def _list_events(conn):
    rows = conn.execute(
        "SELECT e.event_id, e.title, e.start_utc, e.end_utc, e.location_label, e.event_source, "
        "  (SELECT COUNT(1) FROM lp_event_items i WHERE i.event_id = e.event_id) AS item_count "
        "FROM lp_events e ORDER BY e.start_utc DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def _get_event(conn, event_id):
    if not event_id:
        return None
    row = conn.execute(
        "SELECT event_id, title, start_utc, end_utc, location_label, event_source, created_utc "
        "FROM lp_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    return dict(row) if row else None


def _list_smart_views(conn):
    rows = conn.execute(
        "SELECT smart_view_id, title, description, filter_json, sort_json, created_utc, updated_utc "
        "FROM lp_smart_views ORDER BY lower(title)"
    ).fetchall()
    return [dict(row) for row in rows]


def _get_smart_view(conn, smart_view_id):
    if not smart_view_id:
        return None
    row = conn.execute(
        "SELECT smart_view_id, title, description, filter_json, sort_json, created_utc, updated_utc "
        "FROM lp_smart_views WHERE smart_view_id = ?",
        (smart_view_id,),
    ).fetchone()
    return dict(row) if row else None


def _smart_view_filters(smart_view):
    if not smart_view:
        return {}
    raw = smart_view.get("filter_json") or ""
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _smart_view_sort(smart_view):
    if not smart_view:
        return ""
    raw = smart_view.get("sort_json") or ""
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return ""
    return payload.get("sort") or ""


def _fetch_tags_for_media(conn, media_id):
    rows = conn.execute(
        "SELECT t.tag FROM lp_media_tags mt "
        "JOIN lp_tags t ON t.tag_id = mt.tag_id "
        "WHERE mt.media_id = ? "
        "ORDER BY t.tag",
        (media_id,),
    ).fetchall()
    return [row["tag"] for row in rows]


def _fetch_album_memberships(conn, media_id):
    rows = conn.execute(
        "SELECT a.album_id, a.title FROM lp_album_items i "
        "JOIN lp_albums a ON a.album_id = i.album_id "
        "WHERE i.media_id = ? ORDER BY lower(a.title)",
        (media_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_event_memberships(conn, media_id):
    rows = conn.execute(
        "SELECT e.event_id, e.title FROM lp_event_items i "
        "JOIN lp_events e ON e.event_id = i.event_id "
        "WHERE i.media_id = ? ORDER BY e.start_utc DESC",
        (media_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _update_album_cover_if_missing(conn, album_id):
    if not album_id:
        return
    row = conn.execute(
        "SELECT cover_media_id FROM lp_albums WHERE album_id = ?",
        (album_id,),
    ).fetchone()
    if not row or row["cover_media_id"]:
        return
    first = conn.execute(
        "SELECT media_id FROM lp_album_items WHERE album_id = ? ORDER BY sort_order, media_id LIMIT 1",
        (album_id,),
    ).fetchone()
    if not first:
        return
    conn.execute(
        "UPDATE lp_albums SET cover_media_id = ?, updated_utc = ? WHERE album_id = ?",
        (first["media_id"], _utc_now(), album_id),
    )


def _add_media_tags(conn, media_ids, tags_text):
    tags = []
    for raw in (tags_text or "").replace(",", " ").split():
        val = raw.strip().lower()
        if val and val not in tags:
            tags.append(val)
    if not tags or not media_ids:
        return
    now = _utc_now()
    user = _current_user()
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO lp_tags (tag) VALUES (?)", (tag,))
        row = conn.execute("SELECT tag_id FROM lp_tags WHERE tag = ?", (tag,)).fetchone()
        if not row:
            continue
        tag_id = row["tag_id"]
        for media_id in media_ids:
            conn.execute(
                "INSERT OR IGNORE INTO lp_media_tags "
                "(media_id, tag_id, created_utc, created_by) VALUES (?, ?, ?, ?)",
                (media_id, tag_id, now, user),
            )
    conn.commit()


def _add_album_items(conn, album_id, media_ids):
    if not album_id or not media_ids:
        return
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) AS max_sort FROM lp_album_items WHERE album_id = ?",
        (album_id,),
    ).fetchone()
    sort_order = (row["max_sort"] if row else 0) + 1
    now = _utc_now()
    user = _current_user()
    for media_id in media_ids:
        conn.execute(
            "INSERT OR IGNORE INTO lp_album_items "
            "(album_id, media_id, sort_order, added_utc, added_by) VALUES (?, ?, ?, ?, ?)",
            (album_id, media_id, sort_order, now, user),
        )
        sort_order += 1
    _update_album_cover_if_missing(conn, album_id)
    conn.commit()


def _remove_album_items(conn, album_id, media_ids):
    if not album_id or not media_ids:
        return
    placeholders = ", ".join(["?"] * len(media_ids))
    conn.execute(
        f"DELETE FROM lp_album_items WHERE album_id = ? AND media_id IN ({placeholders})",
        [album_id, *media_ids],
    )
    conn.commit()


def _rebuild_events(conn, gap_hours=2.0, split_on_day=True):
    rows = conn.execute(
        "SELECT m.media_id, COALESCE(meta.taken_utc, m.mtime_utc) AS sort_utc "
        "FROM lp_media m "
        "LEFT JOIN lp_media_meta meta ON meta.media_id = m.media_id "
        "WHERE COALESCE(meta.taken_utc, m.mtime_utc) IS NOT NULL "
        "ORDER BY sort_utc"
    ).fetchall()
    items = [(row["media_id"], row["sort_utc"]) for row in rows]
    if not items:
        return 0
    conn.execute("DELETE FROM lp_event_items")
    conn.execute("DELETE FROM lp_events")
    now = _utc_now()
    gap = timedelta(hours=float(gap_hours))
    clusters = []
    current = []
    last_dt = None
    for media_id, ts in items:
        dt = _parse_utc(ts)
        if dt is None:
            continue
        new_cluster = False
        if last_dt is None:
            new_cluster = True
        elif dt - last_dt > gap:
            new_cluster = True
        elif split_on_day and dt.date() != last_dt.date():
            new_cluster = True
        if new_cluster:
            if current:
                clusters.append(current)
            current = []
        current.append((media_id, dt))
        last_dt = dt
    if current:
        clusters.append(current)

    created = 0
    for cluster in clusters:
        start_dt = cluster[0][1]
        end_dt = cluster[-1][1]
        title = f"Event {start_dt.strftime('%Y-%m-%d')}"
        conn.execute(
            "INSERT INTO lp_events (title, start_utc, end_utc, location_label, event_source, created_utc) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                title,
                start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                None,
                "auto",
                now,
            ),
        )
        event_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        for media_id, _ in cluster:
            conn.execute(
                "INSERT OR IGNORE INTO lp_event_items (event_id, media_id, confidence) VALUES (?, ?, ?)",
                (event_id, media_id, None),
            )
        created += 1
    conn.commit()
    return created


@media_bp.route("/")
def media_explorer_route():
    _ensure_schema()
    conn = db._get_conn()

    view = _normalize_view(request.args.get("view"))
    view_mode = _normalize_view_mode(request.args.get("view_mode"))
    raw_sort = request.args.get("sort")
    sort_key = _normalize_sort(raw_sort)
    group_by = _normalize_group(request.args.get("group"))
    year_filter = request.args.get("year", type=int)
    raw_media_type = (request.args.get("media_type") or "").strip().lower()
    media_type = raw_media_type
    q = (request.args.get("q") or "").strip()
    search_everywhere = _normalize_bool(request.args.get("search_everywhere"))

    album_id = request.args.get("album_id", type=int)
    event_id = request.args.get("event_id", type=int)
    smart_view_id = request.args.get("smart_view_id", type=int)

    albums = _list_albums(conn)
    events = _list_events(conn)
    smart_views = _list_smart_views(conn)

    album = _get_album(conn, album_id)
    event = _get_event(conn, event_id)
    smart_view = _get_smart_view(conn, smart_view_id)

    base_filters = _smart_view_filters(smart_view) if view == "smart" else {}
    base_q = (base_filters.get("q") or "").strip()
    base_terms = parse_search_terms(base_q) if not search_everywhere else []
    extra_terms = parse_search_terms(q)
    if view == "smart" and not raw_media_type and not search_everywhere:
        media_type = (base_filters.get("media_type") or "").strip().lower()

    if view == "smart" and not raw_sort:
        sort_key = _normalize_sort(_smart_view_sort(smart_view) or sort_key)

    scope = "all"
    if view == "albums" and album:
        scope = "album"
    elif view == "events" and event:
        scope = "event"
    elif view == "smart" and smart_view:
        scope = "smart"

    joins, where, params = _build_media_filters(
        scope,
        album_id,
        event_id,
        search_everywhere,
        media_type,
        base_terms,
        extra_terms,
        year_filter,
    )

    focus_id = request.args.get("focus_id", type=int)
    base_args = {
        "view": view,
        "view_mode": view_mode,
        "sort": sort_key,
        "group": group_by,
        "year": year_filter or None,
        "media_type": media_type or None,
        "q": q or None,
        "search_everywhere": "1" if search_everywhere else None,
        "album_id": album_id if album_id else None,
        "event_id": event_id if event_id else None,
        "smart_view_id": smart_view_id if smart_view_id else None,
        "focus_id": focus_id if focus_id else None,
    }
    base_args_clean = {k: v for k, v in base_args.items() if v not in (None, "", False)}
    nav_args = dict(base_args_clean)
    for key in ("view", "year", "album_id", "event_id", "smart_view_id", "focus_id"):
        nav_args.pop(key, None)
    focus_args = dict(base_args_clean)
    focus_args.pop("focus_id", None)
    base_query = _query_string(base_args_clean)
    focus_query = _query_string(focus_args)
    nav_query = _query_string(nav_args)

    skip_results = (
        (view == "albums" and not album)
        or (view == "events" and not event)
        or (view == "smart" and not smart_view)
    )

    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    timeline_years = []
    if view == "timeline":
        year_joins, year_where, year_params = _build_media_filters(
            scope,
            album_id,
            event_id,
            search_everywhere,
            media_type,
            base_terms,
            extra_terms,
            None,
        )
        timeline_years = _fetch_timeline_years(conn, year_joins, year_where, year_params)

    if skip_results:
        items = []
        groups = []
        page = 1
        total_pages = 1
        pages = []
        first_url = ""
        last_url = ""
    else:
        total = _count_media(conn, joins, where, list(params))
        page_data = paginate_total(total, page, per_page)
        page = page_data["page"]
        total_pages = page_data["total_pages"]
        offset = (page - 1) * per_page
        items = _fetch_media(conn, joins, where, list(params), sort_key, limit=per_page, offset=offset)
        groups = _group_media(items, group_by) if view == "timeline" else []
        pagination = build_pagination(
            url_for,
            "media.media_explorer_route",
            base_args_clean,
            page,
            total_pages,
        )
        pages = pagination["pages"]
        first_url = pagination["first_url"]
        last_url = pagination["last_url"]

    focus_item = None
    focus_tags = []
    focus_albums = []
    focus_events = []
    if focus_id:
        focus_list = [item for item in items if item.get("media_id") == focus_id]
        focus_item = focus_list[0] if focus_list else None
    if not focus_item and items:
        focus_item = items[0]
    if focus_item:
        focus_tags = _fetch_tags_for_media(conn, focus_item["media_id"])
        focus_albums = _fetch_album_memberships(conn, focus_item["media_id"])
        focus_events = _fetch_event_memberships(conn, focus_item["media_id"])

    return render_template(
        "media_explorer.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Media Explorer",
        content_html="",
        view=view,
        view_mode=view_mode,
        sort_key=sort_key,
        group_by=group_by,
        media_type=media_type,
        q=q,
        search_everywhere=search_everywhere,
        album_id=album_id,
        event_id=event_id,
        smart_view_id=smart_view_id,
        albums=albums,
        events=events,
        smart_views=smart_views,
        album=album,
        event=event,
        smart_view=smart_view,
        items=items,
        groups=groups,
        focus_item=focus_item,
        focus_tags=focus_tags,
        focus_albums=focus_albums,
        focus_events=focus_events,
        timeline_years=timeline_years,
        timeline_year=year_filter,
        page=page,
        total_pages=total_pages,
        pages=pages,
        first_url=first_url,
        last_url=last_url,
        base_args=base_args_clean,
        nav_args=nav_args,
        base_query=base_query,
        focus_query=focus_query,
        nav_query=nav_query,
    )


@media_bp.route("/actions", methods=["POST"])
def media_actions_route():
    _ensure_schema()
    conn = db._get_conn()
    action = (request.form.get("action") or "").strip().lower()
    media_ids = _coerce_int_list(request.form.getlist("media_id"))
    album_id = request.form.get("album_id", type=int)
    tags_text = request.form.get("tags") or ""

    if action == "add_to_album":
        _add_album_items(conn, album_id, media_ids)
    elif action == "remove_from_album":
        _remove_album_items(conn, album_id, media_ids)
    elif action == "tag":
        _add_media_tags(conn, media_ids, tags_text)

    return redirect(url_for("media.media_explorer_route", **_redirect_args(request.form)))


@media_bp.route("/albums/create", methods=["POST"])
def create_album_route():
    _ensure_schema()
    conn = db._get_conn()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    if title:
        now = _utc_now()
        conn.execute(
            "INSERT INTO lp_albums (title, description, cover_media_id, album_type, created_utc, updated_utc) "
            "VALUES (?, ?, NULL, ?, ?, ?)",
            (title, description, "manual", now, now),
        )
        conn.commit()
    return redirect(url_for("media.media_explorer_route", **_redirect_args(request.form)))


@media_bp.route("/albums/<int:album_id>/rename", methods=["POST"])
def rename_album_route(album_id):
    _ensure_schema()
    conn = db._get_conn()
    title = (request.form.get("title") or "").strip()
    if title:
        conn.execute(
            "UPDATE lp_albums SET title = ?, updated_utc = ? WHERE album_id = ?",
            (title, _utc_now(), album_id),
        )
        conn.commit()
    return redirect(url_for("media.media_explorer_route", **_redirect_args(request.form)))


@media_bp.route("/albums/<int:album_id>/delete", methods=["POST"])
def delete_album_route(album_id):
    _ensure_schema()
    conn = db._get_conn()
    conn.execute("DELETE FROM lp_album_items WHERE album_id = ?", (album_id,))
    conn.execute("DELETE FROM lp_albums WHERE album_id = ?", (album_id,))
    conn.commit()
    return redirect(url_for("media.media_explorer_route", view="albums"))


@media_bp.route("/smart_views/create", methods=["POST"])
def create_smart_view_route():
    _ensure_schema()
    conn = db._get_conn()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    q = (request.form.get("q") or "").strip()
    media_type = (request.form.get("media_type") or "").strip()
    sort_key = _normalize_sort(request.form.get("sort"))
    if not title:
        return redirect(url_for("media.media_explorer_route", **_redirect_args(request.form)))
    filter_spec = {}
    if q:
        filter_spec["q"] = q
    if media_type:
        filter_spec["media_type"] = media_type
    sort_spec = {"sort": sort_key} if sort_key else {}
    now = _utc_now()
    conn.execute(
        "INSERT INTO lp_smart_views (title, description, filter_json, sort_json, created_utc, updated_utc) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            title,
            description,
            json.dumps(filter_spec, ensure_ascii=True),
            json.dumps(sort_spec, ensure_ascii=True) if sort_spec else None,
            now,
            now,
        ),
    )
    conn.commit()
    return redirect(url_for("media.media_explorer_route", view="smart"))


@media_bp.route("/smart_views/<int:smart_view_id>/rename", methods=["POST"])
def rename_smart_view_route(smart_view_id):
    _ensure_schema()
    conn = db._get_conn()
    title = (request.form.get("title") or "").strip()
    if title:
        conn.execute(
            "UPDATE lp_smart_views SET title = ?, updated_utc = ? WHERE smart_view_id = ?",
            (title, _utc_now(), smart_view_id),
        )
        conn.commit()
    return redirect(url_for("media.media_explorer_route", **_redirect_args(request.form)))


@media_bp.route("/smart_views/<int:smart_view_id>/delete", methods=["POST"])
def delete_smart_view_route(smart_view_id):
    _ensure_schema()
    conn = db._get_conn()
    conn.execute("DELETE FROM lp_smart_views WHERE smart_view_id = ?", (smart_view_id,))
    conn.commit()
    return redirect(url_for("media.media_explorer_route", view="smart"))


@media_bp.route("/events/rebuild", methods=["POST"])
def rebuild_events_route():
    _ensure_schema()
    conn = db._get_conn()
    gap_hours = request.form.get("gap_hours", type=float) or 2.0
    split_on_day = _normalize_bool(request.form.get("split_on_day"))
    _rebuild_events(conn, gap_hours=gap_hours, split_on_day=split_on_day)
    return redirect(url_for("media.media_explorer_route", view="events"))


@media_bp.route("/events/<int:event_id>/rename", methods=["POST"])
def rename_event_route(event_id):
    _ensure_schema()
    conn = db._get_conn()
    title = (request.form.get("title") or "").strip()
    if title:
        conn.execute(
            "UPDATE lp_events SET title = ? WHERE event_id = ?",
            (title, event_id),
        )
        conn.commit()
    return redirect(url_for("media.media_explorer_route", **_redirect_args(request.form)))


@media_bp.route("/player")
def media_player_route():
    _ensure_schema()
    conn = db._get_conn()
    sort_key = _normalize_sort(request.args.get("sort"))
    limit = request.args.get("limit", type=int) or 200
    joins, where, params = _build_media_filters("all", None, None, False, "", [], [], None)
    items = _fetch_media(conn, joins, where, params, sort_key, limit=limit, offset=0)
    playlist = []
    for item in items:
        playlist.append(
            {
                "id": item.get("media_id"),
                "title": item.get("filename") or "",
                "path": item.get("path") or "",
                "url": url_for("media.media_file_route", media_id=item.get("media_id")),
                "is_video": _is_video(item),
            }
        )
    start_id = request.args.get("id", type=int)
    return render_template(
        "media_player.html",
        items=playlist,
        start_id=start_id,
        sort_col=sort_key,
        sort_dir="desc",
        limit=limit,
        project=None,
    )


@media_bp.route("/view/<int:media_id>")
def view_media_route(media_id):
    return redirect(url_for("media.media_explorer_route", focus_id=media_id, view="all"))


@media_bp.route("/file/<int:media_id>")
def media_file_route(media_id):
    _ensure_schema()
    conn = db._get_conn()
    row = conn.execute(
        "SELECT media_id, path, filename, ext, media_type FROM lp_media WHERE media_id = ?",
        (media_id,),
    ).fetchone()
    if not row:
        abort(404)
    item = dict(row)
    full_path = _build_media_path(item)
    if not os.path.exists(full_path):
        abort(404)
    mime_type, _ = mimetypes.guess_type(full_path)
    return send_file(full_path, mimetype=mime_type or "application/octet-stream")


def _redirect_args(form):
    keys = [
        "view",
        "view_mode",
        "sort",
        "group",
        "year",
        "media_type",
        "q",
        "search_everywhere",
        "album_id",
        "event_id",
        "smart_view_id",
        "focus_id",
        "page",
    ]
    args = {}
    for key in keys:
        value = form.get(key)
        if value:
            args[key] = value
    return args
