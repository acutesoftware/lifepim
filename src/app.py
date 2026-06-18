import sys
import socket
import os

from datetime import date, datetime

from flask import Flask, render_template, request, url_for
from jinja2 import ChoiceLoader, FileSystemLoader

from common.utils import get_tabs, get_side_tabs, get_table_def
import common.config as mod_cfg
from common import data as db
from common import search as search_mod
from common import projects as projects_mod
from common import settings as settings_mod


APP_NAME = "LifePIM"
GITHUB_REPO_URL = "https://github.com/acutesoftware/lifepim"

def _dbg(msg):
    print(f"[app] {msg}", file=sys.stderr, flush=True)


def _connect_host_for_bind_host(host):
    if host in ("", "0.0.0.0", "::"):
        return "127.0.0.1"
    return host


def _is_port_in_use(host, port):
    connect_host = _connect_host_for_bind_host(host)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((connect_host, int(port))) == 0


def _exit_if_server_already_running(host, port):
    if not _is_port_in_use(host, port):
        return

    print(
        f"LifePIM server appears to already be running at http://{host}:{port}. "
        "Exiting without starting another copy.",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(0)


def _table_has_column(conn, table_name, column_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return False
    return any(row["name"] == column_name for row in rows)


def _table_exists(conn, table_name):
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
            [table_name],
        ).fetchone()
    except Exception:
        return False
    return row is not None


def _last_data_source_update(conn):
    latest = None
    for table_def in getattr(mod_cfg, "table_def", []):
        table_name = table_def.get("name")
        if not table_name or not _table_exists(conn, table_name):
            continue
        if not _table_has_column(conn, table_name, "rec_extract_date"):
            continue
        try:
            row = conn.execute(f"SELECT MAX(rec_extract_date) AS updated FROM {table_name}").fetchone()
        except Exception:
            continue
        updated = row["updated"] if row else None
        if updated and (latest is None or updated > latest):
            latest = updated
    return latest


def _help_paths():
    src_folder = os.path.dirname(os.path.abspath(__file__))
    app_root = os.path.abspath(os.path.join(src_folder, os.pardir))
    return [
        ("Launch folder", os.getcwd()),
        ("Application root", app_root),
        ("Source folder", src_folder),
        ("User data folder", getattr(mod_cfg, "user_folder", "")),
        ("Database file", getattr(mod_cfg, "DB_FILE", "")),
        ("Data folder", getattr(mod_cfg, "data_folder", "")),
        ("Index folder", getattr(mod_cfg, "index_folder", "")),
        ("Calendar folder", getattr(mod_cfg, "calendar_folder", "")),
        ("Export data folder", getattr(mod_cfg, "export_data_folder_base", "")),
    ]


_dbg("Creating Flask app")
app = Flask(__name__)
projects_mod.ensure_projects_schema(db._get_conn())
settings_mod.ensure_settings_schema(db._get_conn())

# Register blueprints
_dbg("Importing blueprints")
from modules.calendar.routes import calendar_bp
from modules.data.routes import data_bp
from modules.files.routes import files_bp
from modules.media.routes import media_bp
from modules.audio.routes import audio_bp
from modules.three_d.routes import three_d_bp
from modules.apps.routes import apps_bp
from modules.goals.routes import goals_bp
from modules.how.routes import how_bp
from modules.notes.routes import notes_bp
from modules.places.routes import places_bp
from modules.money.routes import money_bp
from modules.contacts.routes import contacts_bp
from modules.tasks.tasks import tasks_bp
from modules.admin.routes import admin_bp
from modules.links.routes import links_bp
from modules.projects.routes import projects_bp

_dbg("Registering blueprints")
app.register_blueprint(calendar_bp, url_prefix="/calendar")
app.register_blueprint(data_bp, url_prefix="/data")
app.register_blueprint(files_bp, url_prefix="/files")
app.register_blueprint(media_bp, url_prefix="/media")
app.register_blueprint(audio_bp, url_prefix="/audio")
app.register_blueprint(three_d_bp, url_prefix="/3d")
app.register_blueprint(apps_bp, url_prefix="/apps")
app.register_blueprint(goals_bp, url_prefix="/goals")
app.register_blueprint(how_bp, url_prefix="/how")
app.register_blueprint(notes_bp, url_prefix="/notes")
app.register_blueprint(places_bp, url_prefix="/places")
app.register_blueprint(money_bp, url_prefix="/money")
app.register_blueprint(contacts_bp, url_prefix="/contacts")
app.register_blueprint(tasks_bp, url_prefix="/tasks")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(links_bp, url_prefix="/links")
app.register_blueprint(projects_bp, url_prefix="/projects")
_dbg("Blueprints registered")

@app.route('/')
def index():
    today = date.today()
    notes = []
    tasks = []
    events_today = []

    notes_tbl = get_table_def("notes")
    if notes_tbl:
        rows = db.get_data(
            db.conn,
            notes_tbl["name"],
            ["id"] + notes_tbl["col_list"] + ["rec_extract_date as updated"],
            "1=1",
            [],
        )
        notes = [dict(row) for row in rows]
        notes.sort(key=lambda n: n.get("updated") or "", reverse=True)
        notes = notes[:10]

    tasks_tbl = get_table_def("tasks")
    if tasks_tbl:
        rows = db.get_data(
            db.conn,
            tasks_tbl["name"],
            ["id"] + tasks_tbl["col_list"] + ["rec_extract_date as updated"],
            "1=1",
            [],
        )
        tasks = [dict(row) for row in rows]
        tasks.sort(key=lambda t: t.get("updated") or "", reverse=True)
        tasks = tasks[:5]

    cal_tbl = get_table_def("calendar")
    month_weeks = []
    days_with_events = set()
    if cal_tbl:
        month_weeks = __import__("calendar").monthcalendar(today.year, today.month)
        rows = db.get_data(
            db.conn,
            cal_tbl["name"],
            ["id"] + cal_tbl["col_list"],
            "event_date LIKE ?",
            [f"{today.year:04d}-{today.month:02d}%"],
        )
        events = [dict(row) for row in rows]
        for ev in events:
            try:
                day_num = int((ev.get("event_date") or "").split("-")[2])
            except (IndexError, ValueError, AttributeError):
                continue
            days_with_events.add(day_num)
        events_today = [
            ev for ev in events if (ev.get("event_date") or "").startswith(today.strftime("%Y-%m-%d"))
        ]
        events_today.sort(key=lambda e: e.get("event_date") or "")

    return render_template(
        'overview.html',
        active_tab='home',
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title='Overview',
        content_html='',
        today=today,
        month_weeks=month_weeks,
        month=today.month,
        year=today.year,
        month_name=__import__("calendar").month_name[today.month],
        days_with_events=days_with_events,
        highlight_day_data=mod_cfg.CAL_HIGHLIGHT_DAY_DATA,
        highlight_day_today=mod_cfg.CAL_HIGHLIGHT_DAY_TODAY,
        col_bg_day=mod_cfg.CAL_COL_BG_DAY,
        col_bg_weekend=mod_cfg.CAL_COL_BG_WEEKEND,
        col_bg_today=mod_cfg.CAL_COL_BG_TODAY,
        notes=notes,
        tasks=tasks,
        events_today=events_today,
        overview_grid_w=mod_cfg.OVERVIEW_GRID_W,
        overview_grid_h=mod_cfg.OVERVIEW_GRID_H,
    )


@app.route("/search")
def search_route():
    query = (request.args.get("q") or "").strip()
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    route = request.args.get("route") or "home"
    scope = (request.args.get("scope") or "titles").strip().lower()
    include_note_content = scope == "all"
    tab_ids = {t.get("id") for t in get_tabs()}
    active_tab = route if route in tab_ids else "home"
    results = search_mod.search_all(
        query,
        project=project,
        route=route,
        include_note_content=include_note_content,
    )
    for item in results["primary"] + results["secondary"]:
        params = {item["id_param"]: item["id"]}
        if project:
            params["proj"] = project
        item["url"] = url_for(item["view_route"], **params)
    audio_playlists = []
    has_audio = any(item.get("route") == "audio" for item in results["primary"] + results["secondary"])
    if has_audio:
        from modules.audio import routes as audio_routes

        conn = audio_routes._ensure_playlist_schema()
        audio_routes._ensure_default_playlist(conn)
        audio_playlists = audio_routes._list_playlists(conn)
    return render_template(
        "search_results.html",
        active_tab=active_tab,
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Search",
        content_html="",
        query=query,
        project=project,
        route=route,
        results_primary=results["primary"],
        results_secondary=results["secondary"],
        audio_playlists=audio_playlists,
    )


@app.route("/help")
def help_route():
    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn
    return render_template(
        "help.html",
        active_tab="help",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="",
        content_html="",
        app_name=APP_NAME,
        app_version=getattr(mod_cfg, "WEB_VERSION", "DEV"),
        last_data_update=_last_data_source_update(conn) or "No imported data found",
        paths=_help_paths(),
        github_repo_url=GITHUB_REPO_URL,
    )

if __name__ == "__main__":
    #app.run(debug=True)
    _exit_if_server_already_running(mod_cfg.base_url, mod_cfg.port_num)

    app.run(
        host=mod_cfg.base_url,
        port=mod_cfg.port_num,
        debug=False
    )


"""


port_num=9741           # port to browse to, eg. http://127.0.0.1:9741/
WEB_VERSION = "DEV"     # to show debug lines in web server
base_url = 'https://www.lifepim.com'    # testing, point to live site for API
base_url = '127.0.0.1'             # running local (default)

# Auto-register all modules as blueprints
for _, modname, _ in pkgutil.iter_modules(['modules']):
    module = importlib.import_module(f'modules.{modname}.views')
    if hasattr(module, 'bp'):
        app.register_blueprint(module.bp, url_prefix=f'/{modname}')

        

SIDE_TABS = [
 { 'icon': '*', 'id': 'any', 'label': 'All Projects'},
 { 'icon': '🔒', 'id': 'pers', 'label': 'Personal'},
 { 'icon': '💊', 'id': 'health', 'label': 'Health'},
 { 'icon': '👪', 'id': 'family', 'label': 'Family'},
 { 'icon': '🏈', 'id': 'sport', 'label': 'Sport'},
 { 'icon': '🏚️', 'id': 'house', 'label': 'House'},
 { 'icon': '🍕', 'id': 'food', 'label': 'Food'},
 { 'icon': '🚗', 'id': 'car', 'label': 'Car'},
 { 'icon': '🎉', 'id': 'fun', 'label': 'Fun'},
 { 'icon': '🕹️', 'id': 'games', 'label': 'Games'},
 { 'icon': '🖥️', 'id': 'dev', 'label': 'Dev'},
 { 'icon': '🖥️', 'id': 'dev/UE5', 'label': 'UE5'},
 { 'icon': '🖥️', 'id': 'dev/Python', 'label': 'Python'},
 { 'icon': '📐', 'id': 'design', 'label': 'Design'},
 { 'icon': '📐', 'id': 'design/write', 'label': 'Writing'},
 { 'icon': '📐', 'id': 'design/programs', 'label': 'Program Design'},
 { 'icon': '📻', 'id': 'make', 'label': 'Make'},
 { 'icon': '📻', 'id': 'make/rasbpi', 'label': 'RasbPI'},
 { 'icon': '📻', 'id': 'make/pc', 'label': 'PC'},
 { 'icon': '💼', 'id': 'work', 'label': 'Work'},
 { 'icon': '💼', 'id': 'work/business', 'label': 'Business'},
 { 'icon': '💼', 'id': 'work/side', 'label': 'Side Gigs'},
 { 'icon': '👩🏻‍🎓', 'id': 'learn', 'label': 'Learn'},
 { 'icon': '🕵', 'id': 'ai', 'label': 'AI'},
 { 'icon': '🧰', 'id': 'support', 'label': 'Support'},
]

TABS = [
 { 'icon': '🏠', 'id': 'home', 'label': 'Overview', 'desc': 'Overview Dashboard'},
 { 'icon': '📝', 'id': 'notes', 'label': 'Notes', 'desc': 'Notes'},
 { 'icon': '🕐', 'id': 'calendar', 'label': 'Cal', 'desc': 'Calendar, Appointments, Events, Reminders (WHEN)'},
 { 'icon': '📝', 'id': 'tasks', 'label': 'Tasks', 'desc': 'Tasks (actual list of things to do)'},
 { 'icon': '🗄️', 'id': 'data', 'label': 'Data', 'desc': 'Data' },
 { 'icon': '🎮', 'id': 'apps', 'label': 'Apps', 'desc': 'Apps'},
 { 'icon': '📂', 'id': 'files', 'label': 'Files', 'desc': 'Files'},
 { 'icon': '💿', 'id': 'media', 'label': 'Media', 'desc': 'Images, Audio, Video'},
 { 'icon': '🧱', 'id': '3d', 'label': '3D', 'desc': 'Objects / 3D / Things'},
 { 'icon': '👤', 'id': 'contacts', 'label': 'People', 'desc': 'Contacts (WHO)'},
 { 'icon': '🌏', 'id': 'places', 'label': 'Places', 'desc': 'Places (WHERE - real life, URL or virt location)'},
 { 'icon': '💲', 'id': 'money', 'label': 'Money', 'desc': 'Money'},
 { 'icon': '💻', 'id': 'etl', 'label': 'ETL', 'desc': 'ETL'},
]
        
 """
