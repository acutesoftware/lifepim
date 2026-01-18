from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common import config as cfg
from common.utils import get_tabs, get_side_tabs


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
    static_folder="static",
)


_REBUILD_SQL = """
DELETE FROM map_project_folder;

INSERT INTO map_project_folder (
  folder_id, tab, grp, project, tags, confidence,
  matched_prefix, rule_map_id, is_primary, is_enabled, updated_at
)
SELECT
  f.folder_id,
  r.tab,
  r.grp,
  COALESCE(r.project,''),
  r.tags,
  r.confidence,
  r.path_prefix,
  r.map_id,
  r.is_primary,
  r.is_enabled,
  strftime('%Y-%m-%dT%H:%M:%fZ','now')
FROM dim_folder f
JOIN map_folder_project r
  ON r.map_id = (
      SELECT r2.map_id
      FROM map_folder_project r2
      WHERE r2.is_enabled=1
        AND r2.is_primary=1
        AND lower(f.folder_path) LIKE lower(r2.path_prefix) || '%'
      ORDER BY LENGTH(r2.path_prefix) DESC,
               r2.priority DESC,
               r2.confidence DESC,
               r2.map_id DESC
      LIMIT 1
  );
"""


@admin_bp.route("/", methods=["GET", "POST"])
def admin_mapping_route():
    message = ""
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "rebuild":
            conn = db.conn if db.conn is not None else None
            conn = db._get_conn() if conn is None else conn
            conn.executescript(_REBUILD_SQL)
            conn.commit()
            message = "Rebuilt folder cache."

    unmapped_only = request.args.get("unmapped") == "1"
    rules = []
    folders = []
    counts = {}
    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn
    try:
        counts["map_folder_project"] = conn.execute("SELECT COUNT(1) FROM map_folder_project").fetchone()[0]
        counts["map_project_folder"] = conn.execute("SELECT COUNT(1) FROM map_project_folder").fetchone()[0]
        counts["dim_folder"] = conn.execute("SELECT COUNT(1) FROM dim_folder").fetchone()[0]
        rules = conn.execute(
            """
            SELECT map_id, path_prefix, tab, grp, project, tags, confidence, priority, is_primary, is_enabled
            FROM map_folder_project
            ORDER BY tab, grp, path_prefix
            """
        ).fetchall()
        if unmapped_only:
            folders = conn.execute(
                """
                SELECT f.folder_id, f.folder_path, f.is_active, f.last_seen_at
                FROM dim_folder f
                LEFT JOIN map_project_folder mpf
                  ON mpf.folder_id = f.folder_id
                 AND mpf.is_primary = 1
                 AND mpf.is_enabled = 1
                WHERE mpf.folder_id IS NULL
                ORDER BY f.folder_path
                """
            ).fetchall()
        else:
            folders = conn.execute(
                """
                SELECT folder_id, folder_path, is_active, last_seen_at
                FROM dim_folder
                ORDER BY folder_path
                """
            ).fetchall()
    except Exception:
        rules = []
        folders = []
        counts = {}

    return render_template(
        "admin_mapping.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Admin - Folder Mapping",
        content_html="",
        message=message,
        rules=rules,
        folders=folders,
        counts=counts,
        db_file=cfg.DB_FILE,
        unmapped_only=unmapped_only,
        now=datetime.now(),
    )
