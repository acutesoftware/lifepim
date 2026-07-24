import sys
import socket
import os
import time

from datetime import date, datetime

from flask import Flask, g, jsonify, render_template, request, send_from_directory, url_for
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.middleware.proxy_fix import ProxyFix

from common.utils import get_tabs, get_side_tabs, get_table_def, format_duration_friendly, format_duration_label
import common.config as mod_cfg
from common import data as db
from common import search as search_mod
from common import projects as projects_mod
from common import settings as settings_mod
from common.network_log import log_network
from core.security import configure_security
from modules.how.schema import ensure_how_schema


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


def _help_paths():
    src_folder = os.path.dirname(os.path.abspath(__file__))
    app_root = os.path.abspath(os.path.join(src_folder, os.pardir))
    return [
        ("Launch folder", os.getcwd()),
        ("Application root", app_root),
        ("Source folder", src_folder),
        ("User data folder", getattr(mod_cfg, "user_folder", "")),
        ("Database file", getattr(mod_cfg, "DB_FILE", "")),
        ("Notes folder", _notes_live_folder_path()),
        ("Data folder", getattr(mod_cfg, "data_folder", "")),
        ("Index folder", getattr(mod_cfg, "index_folder", "")),
        ("Calendar folder", getattr(mod_cfg, "calendar_folder", "")),
        ("Export data folder", getattr(mod_cfg, "export_data_folder_base", "")),
    ]


def _notes_live_folder_path():
    try:
        notes_tbl = get_table_def("notes")
        if not notes_tbl:
            return ""
        conn = db._get_conn()
        rows = conn.execute(
            f"SELECT path, COUNT(1) AS cnt FROM {notes_tbl['name']} "
            "WHERE COALESCE(path, '') != '' "
            "GROUP BY path "
            "ORDER BY cnt DESC"
        ).fetchall()
    except Exception:
        return ""

    root_counts = {}
    root_display = {}
    for row in rows:
        path = (row["path"] or "").strip().replace("/", "\\")
        if not path:
            continue
        parts = [part for part in path.split("\\") if part]
        root = ""
        for idx in range(len(parts) - 1):
            if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
                root = "\\".join(parts[: idx + 2])
                break
        if not root:
            continue
        key = root.lower()
        root_display.setdefault(key, root)
        root_counts[key] = root_counts.get(key, 0) + int(row["cnt"] or 0)

    if root_counts:
        best_key = max(root_counts, key=root_counts.get)
        return root_display.get(best_key, "")
    return ""


def _python_source_files():
    src_folder = os.path.dirname(os.path.abspath(__file__))
    files = []
    for root, dirs, file_names in os.walk(src_folder):
        dirs[:] = [name for name in dirs if name != "__pycache__"]
        for file_name in file_names:
            if file_name.lower().endswith(".py"):
                files.append(os.path.join(root, file_name))
    return files


def _last_python_source_update():
    src_folder = os.path.dirname(os.path.abspath(__file__))
    latest_mtime = None
    latest_path = ""
    for path in _python_source_files():
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if latest_mtime is None or mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = path
    if latest_mtime is None:
        return "No Python source files found"
    timestamp = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")
    rel_path = os.path.relpath(latest_path, src_folder)
    return f"{timestamp} ({rel_path})"


_dbg("Creating Flask app")
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("LIFEPIM_MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
app.config["LIFEPIM_POCKET_MAX_SYNC_PAYLOAD_BYTES"] = int(os.getenv("LIFEPIM_POCKET_MAX_SYNC_PAYLOAD_BYTES", str(10 * 1024 * 1024)))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.jinja_env.filters["duration_friendly"] = format_duration_friendly
app.jinja_env.filters["duration_label"] = format_duration_label
projects_mod.ensure_projects_schema(db._get_conn())
settings_mod.ensure_settings_schema(db._get_conn())
db.ensure_notes_schema(db._get_conn())
ensure_how_schema(db._get_conn())


def _should_network_log():
    path = request.path or ""
    if path.startswith("/static/"):
        return False
    return True


@app.before_request
def _network_log_request_start():
    if not _should_network_log():
        return None
    g.network_log_start = time.perf_counter()
    log_network(
        "request_start",
        method=request.method,
        path=request.path,
        query=request.query_string.decode("utf-8", errors="replace")[:500],
        endpoint=request.endpoint,
        scheme=request.scheme,
        host=request.host,
        remote_addr=request.remote_addr,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        forwarded_proto=request.headers.get("X-Forwarded-Proto"),
        user_agent=(request.headers.get("User-Agent") or "")[:300],
        has_authorization=bool(request.headers.get("Authorization")),
        has_cookie=bool(request.headers.get("Cookie")),
    )


@app.after_request
def _network_log_request_finish(response):
    if _should_network_log():
        started = getattr(g, "network_log_start", None)
        duration_ms = None
        if started is not None:
            duration_ms = int((time.perf_counter() - started) * 1000)
        log_network(
            "request_finish",
            method=request.method,
            path=request.path,
            endpoint=request.endpoint,
            status_code=response.status_code,
            duration_ms=duration_ms,
            location=response.headers.get("Location"),
            content_type=response.headers.get("Content-Type"),
        )
    return response


@app.teardown_request
def _network_log_request_exception(exc):
    if exc is None or not _should_network_log():
        return None
    started = getattr(g, "network_log_start", None)
    duration_ms = None
    if started is not None:
        duration_ms = int((time.perf_counter() - started) * 1000)
    log_network(
        "request_exception",
        method=request.method,
        path=request.path,
        endpoint=request.endpoint,
        duration_ms=duration_ms,
        error_type=type(exc).__name__,
        error=str(exc),
    )

# Register blueprints
_dbg("Importing blueprints")
from modules.auth.routes import auth_bp
from modules.public.routes import public_bp
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
from modules.pocket_api.routes import pocket_api_bp

_dbg("Registering blueprints")
app.register_blueprint(auth_bp)
app.register_blueprint(public_bp)
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
app.register_blueprint(pocket_api_bp)
configure_security(app)
_dbg("Blueprints registered")


@app.context_processor
def inject_layout_settings():
    general_settings = settings_mod.get_general_settings()
    return {
        "freeze_headers": general_settings.get("freeze_headers", False),
        "mobile_font_size": general_settings.get("mobile_font_size", 14),
    }


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
    scope = (request.args.get("scope") or "metadata").strip().lower()
    if scope in {"titles", "all"}:
        scope = "metadata"
    if scope not in {"metadata", "note_content"}:
        scope = "metadata"
    sort_col = request.args.get("sort") or "file_name"
    sort_dir = request.args.get("dir") or "asc"
    tab_ids = {t.get("id") for t in get_tabs()}
    active_tab = route if route in tab_ids else "home"
    if route not in tab_ids:
        route = "home"
    if scope == "note_content":
        results = search_mod.search_note_content(query, project=project, route=route)
    else:
        results = search_mod.search_all(query, project=project, route=route)
    for item in results["primary"] + results["secondary"]:
        params = {item["id_param"]: item["id"]}
        if project:
            params["proj"] = project
        item["url"] = url_for(item["view_route"], **params)
    more_results_links = []
    for item in results.get("more", []):
        args = {"q": query, "route": item["route"], "scope": scope}
        if project:
            args["proj"] = project
        more_results_links.append(
            {
                "table": item["table"],
                "url": url_for("search_route", **args),
            }
        )
    audio_playlists = []
    audio_search_items = None
    audio_search_col_list = []
    audio_other_results = []
    media_search = None
    media_other_results = []
    if route == "media" and query and scope != "note_content":
        from modules.media import routes as media_routes

        media_search = media_routes.build_media_search_context(query, request.args)
        media_other_results = [
            item
            for item in results["primary"] + results["secondary"]
            if item.get("route") != "media"
        ]
    has_audio = any(item.get("route") == "audio" for item in results["primary"] + results["secondary"])
    if scope != "note_content" and (has_audio or route == "audio"):
        from modules.audio import routes as audio_routes

        conn = audio_routes._ensure_playlist_schema()
        audio_routes._ensure_default_playlist(conn)
        audio_playlists = audio_routes._list_playlists(conn)
        if route == "audio" and query:
            audio_search_items = audio_routes._fetch_audio_search(
                project,
                query,
                sort_col=sort_col,
                sort_dir=sort_dir,
            )
            tbl = audio_routes._get_tbl()
            audio_search_col_list = [
                col for col in audio_routes.AUDIO_TABLE_COLUMNS if tbl and col in tbl["col_list"]
            ]
            audio_other_results = [
                item
                for item in results["primary"] + results["secondary"]
                if item.get("route") != "audio"
            ]
    total_results = len(results["primary"]) + len(results["secondary"])
    if audio_search_items is not None:
        total_results = len(audio_search_items) + len(audio_other_results)
    if media_search is not None:
        total_results = media_search["total"] + len(media_other_results)
    search_all_areas_url = ""
    if query and route in tab_ids and route != "home":
        all_areas_args = {"q": query, "route": "home", "scope": scope}
        if project:
            all_areas_args["proj"] = project
        search_all_areas_url = url_for("search_route", **all_areas_args)
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
        total_results=total_results,
        search_all_areas_url=search_all_areas_url,
        more_results_links=more_results_links,
        results_primary=results["primary"],
        results_secondary=results["secondary"],
        audio_playlists=audio_playlists,
        audio_search_items=audio_search_items,
        audio_search_col_list=audio_search_col_list,
        audio_other_results=audio_other_results,
        audio_sort_col=sort_col,
        audio_sort_dir=sort_dir,
        media_search=media_search,
        media_other_results=media_other_results,
    )


@app.route("/favicon.ico")
def favicon_route():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/site.webmanifest")
def site_webmanifest():
    icon_url = url_for("static", filename="favicon.ico")
    response = jsonify(
        {
            "name": APP_NAME,
            "short_name": APP_NAME,
            "start_url": url_for("index"),
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#243447",
            "icons": [
                {
                    "src": icon_url,
                    "sizes": "16x16 32x32 48x48 64x64 128x128 256x256",
                    "type": "image/x-icon",
                    "purpose": "any",
                }
            ],
        }
    )
    response.headers["Content-Type"] = "application/manifest+json"
    return response


@app.route("/help")
def help_route():
    return render_template(
        "help.html",
        active_tab="help",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="",
        content_html="",
        app_name=APP_NAME,
        app_version=getattr(mod_cfg, "APP_VERSION", "DEV"),
        last_source_update=_last_python_source_update(),
        paths=_help_paths(),
        github_repo_url=GITHUB_REPO_URL,
    )

if __name__ == "__main__":
    #app.run(debug=True)
    auto_reload = bool(getattr(mod_cfg, "APP_AUTO_RELOAD", False))
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not (auto_reload and is_reloader_child):
        _exit_if_server_already_running(mod_cfg.base_url, mod_cfg.port_num)

    app.run(
        host=mod_cfg.base_url,
        port=mod_cfg.port_num,
        debug=False,
        use_reloader=auto_reload,
        extra_files=_python_source_files(),
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
