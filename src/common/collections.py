import sqlite3
from datetime import datetime, timezone

from common import data as db
from common import areas as areas_mod
from common import projects as projects_mod
from common import utils as utils_mod


COLLECTION_STATUSES = ("active", "archived")
COLLECTION_STATUS_LABELS = {
    "active": "Active",
    "archived": "Archived",
}

NOTES_COLLECTION_ADAPTER = {
    "collection_domain": "notes",
    "collection_types": ("notebook", "book"),
    "collection_type_labels": {"notebook": "Notebook", "book": "Book"},
    "singular_label": "Notebook",
    "plural_label": "Notebooks",
    "add_item_label": "Add to Notebook",
    "compatible_item_types": ("note",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": True,
    "default_view": "continuous",
    "source_label": "Available Notes",
    "empty_label": "No notebooks found.",
}

MEDIA_COLLECTION_ADAPTER = {
    "collection_domain": "media",
    "collection_types": ("album",),
    "collection_type_labels": {"album": "Album"},
    "singular_label": "Album",
    "plural_label": "Albums",
    "add_item_label": "Add to Album",
    "compatible_item_types": ("media",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": False,
    "default_view": "grid",
    "source_label": "Available Media",
    "empty_label": "No albums found.",
}

AUDIO_COLLECTION_ADAPTER = {
    "collection_domain": "audio",
    "collection_types": ("playlist",),
    "collection_type_labels": {"playlist": "Playlist"},
    "singular_label": "Playlist",
    "plural_label": "Playlists",
    "add_item_label": "Add to Playlist",
    "compatible_item_types": ("audio",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": False,
    "default_view": "list",
    "source_label": "Available Audio",
    "empty_label": "No playlists found.",
}

HOW_COLLECTION_ADAPTER = {
    "collection_domain": "how",
    "collection_types": ("manual", "runbook"),
    "collection_type_labels": {"manual": "Manual", "runbook": "Runbook"},
    "singular_label": "Manual",
    "plural_label": "Manuals",
    "add_item_label": "Add to Manual",
    "compatible_item_types": ("how",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": True,
    "default_view": "continuous",
    "source_label": "Available How-tos",
    "empty_label": "No manuals found.",
}

FILES_COLLECTION_ADAPTER = {
    "collection_domain": "files",
    "collection_types": ("file_collection", "project_files"),
    "collection_type_labels": {"file_collection": "File Collection", "project_files": "Project Files"},
    "singular_label": "File Collection",
    "plural_label": "File Collections",
    "add_item_label": "Add to File Collection",
    "compatible_item_types": ("file",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": False,
    "default_view": "list",
    "source_label": "Available Files",
    "empty_label": "No file collections found.",
}

PEOPLE_COLLECTION_ADAPTER = {
    "collection_domain": "people",
    "collection_types": ("group",),
    "collection_type_labels": {"group": "Group"},
    "singular_label": "Group",
    "plural_label": "Groups",
    "add_item_label": "Add to Group",
    "compatible_item_types": ("person", "organization"),
    "supports_manual_order": True,
    "supports_headings": False,
    "supports_nested_collections": False,
    "default_view": "list",
    "source_label": "Available Contacts",
    "empty_label": "No groups found.",
}

PLACES_COLLECTION_ADAPTER = {
    "collection_domain": "places",
    "collection_types": ("trip", "region", "place_collection"),
    "collection_type_labels": {"trip": "Trip", "region": "Region", "place_collection": "Place Collection"},
    "singular_label": "Trip",
    "plural_label": "Trips and Regions",
    "add_item_label": "Add to Trip",
    "compatible_item_types": ("place",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": True,
    "default_view": "map",
    "source_label": "Available Places",
    "empty_label": "No trips or regions found.",
}

DATA_COLLECTION_ADAPTER = {
    "collection_domain": "data",
    "collection_types": ("workspace", "dataset"),
    "collection_type_labels": {"workspace": "Data Workspace", "dataset": "Dataset"},
    "singular_label": "Data Workspace",
    "plural_label": "Data Workspaces",
    "add_item_label": "Add to Data Workspace",
    "compatible_item_types": ("data", "data_source", "database", "table", "data_file", "saved_query", "report"),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": True,
    "default_view": "list",
    "source_label": "Available Data Items",
    "empty_label": "No data workspaces found.",
}

THREE_D_COLLECTION_ADAPTER = {
    "collection_domain": "3d",
    "collection_types": ("asset_pack", "scene"),
    "collection_type_labels": {"asset_pack": "Asset Pack", "scene": "Scene"},
    "singular_label": "Asset Pack",
    "plural_label": "Asset Packs and Scenes",
    "add_item_label": "Add to Asset Pack",
    "compatible_item_types": ("3d",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": True,
    "default_view": "grid",
    "source_label": "Available 3D Assets",
    "empty_label": "No asset packs found.",
}

MONEY_COLLECTION_ADAPTER = {
    "collection_domain": "money",
    "collection_types": ("portfolio", "budget", "financial_plan"),
    "collection_type_labels": {"portfolio": "Portfolio", "budget": "Budget", "financial_plan": "Financial Plan"},
    "singular_label": "Portfolio",
    "plural_label": "Portfolios and Budgets",
    "add_item_label": "Add to Portfolio",
    "compatible_item_types": ("money", "account", "investment", "holding", "expense", "income", "budget_category", "financial_plan", "transaction"),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": False,
    "default_view": "list",
    "source_label": "Available Money Records",
    "empty_label": "No portfolios found.",
}

APPS_COLLECTION_ADAPTER = {
    "collection_domain": "apps",
    "collection_types": ("app_group", "stack"),
    "collection_type_labels": {"app_group": "App Group", "stack": "Stack"},
    "singular_label": "App Group",
    "plural_label": "App Groups and Stacks",
    "add_item_label": "Add to App Group",
    "compatible_item_types": ("app",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": True,
    "default_view": "list",
    "source_label": "Available Apps",
    "empty_label": "No app groups found.",
}

CALENDAR_COLLECTION_ADAPTER = {
    "collection_domain": "calendar",
    "collection_types": ("agenda", "calendar"),
    "collection_type_labels": {"agenda": "Agenda", "calendar": "Calendar"},
    "singular_label": "Agenda",
    "plural_label": "Agendas",
    "add_item_label": "Add to Agenda",
    "compatible_item_types": ("event",),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": False,
    "default_view": "chronological",
    "source_label": "Available Events",
    "empty_label": "No agendas found.",
}

GOALS_COLLECTION_ADAPTER = {
    "collection_domain": "goals",
    "collection_types": ("plan", "roadmap"),
    "collection_type_labels": {"plan": "Plan", "roadmap": "Roadmap"},
    "singular_label": "Plan",
    "plural_label": "Plans and Roadmaps",
    "add_item_label": "Add to Plan",
    "compatible_item_types": ("goal", "task", "milestone", "achievement", "evidence", "routine"),
    "supports_manual_order": True,
    "supports_headings": True,
    "supports_nested_collections": True,
    "default_view": "list",
    "source_label": "Available Goals and Tasks",
    "empty_label": "No plans found.",
}

COLLECTION_DOMAIN_ADAPTERS = {
    "notes": NOTES_COLLECTION_ADAPTER,
    "media": MEDIA_COLLECTION_ADAPTER,
    "audio": AUDIO_COLLECTION_ADAPTER,
    "how": HOW_COLLECTION_ADAPTER,
    "files": FILES_COLLECTION_ADAPTER,
    "people": PEOPLE_COLLECTION_ADAPTER,
    "places": PLACES_COLLECTION_ADAPTER,
    "data": DATA_COLLECTION_ADAPTER,
    "3d": THREE_D_COLLECTION_ADAPTER,
    "money": MONEY_COLLECTION_ADAPTER,
    "apps": APPS_COLLECTION_ADAPTER,
    "calendar": CALENDAR_COLLECTION_ADAPTER,
    "goals": GOALS_COLLECTION_ADAPTER,
}

DOMAIN_COLLECTION_TYPES = {
    domain: tuple(adapter["collection_types"])
    for domain, adapter in COLLECTION_DOMAIN_ADAPTERS.items()
}

DOMAIN_ITEM_TYPES = {
    domain: tuple(adapter["compatible_item_types"])
    for domain, adapter in COLLECTION_DOMAIN_ADAPTERS.items()
}

ENTRY_KINDS = ("item", "heading", "divider", "collection")
DEFAULT_VISIBILITY = "private"
DEFAULT_BOOK_COVER_BG_COLOUR = "#2f5d50"
DEFAULT_BOOK_COVER_STYLE = "cloth"
DEFAULT_BOOK_COVER_FONT = "serif"
NOTEBOOK_COVER_PRESETS = [
    {"value": "notebook_covers/notebook-cover-green.png", "label": "Green geometry", "bg_colour": "#173d31"},
    {"value": "notebook_covers/notebook-cover-rust.png", "label": "Rust horizon", "bg_colour": "#b94a2b"},
    {"value": "notebook_covers/notebook-cover-blue.png", "label": "Blue constellation", "bg_colour": "#263f52"},
    {"value": "notebook_covers/notebook-cover-border.png", "label": "Thin border", "bg_colour": "#0d4a47"},
    {"value": "notebook_covers/notebook-cover-technical.png", "label": "Faded technical", "bg_colour": "#24282d"},
    {"value": "notebook_covers/notebook-cover-old-book.png", "label": "Old worn book", "bg_colour": "#4a2d19"},
]
BOOK_COVER_STYLE_OPTIONS = [
    {"value": "cloth", "label": "Cloth"},
    {"value": "paper", "label": "Paper"},
    {"value": "classic", "label": "Classic"},
    {"value": "minimal", "label": "Minimal"},
]
BOOK_COVER_FONT_OPTIONS = [
    {"value": "serif", "label": "Serif"},
    {"value": "sans", "label": "Sans"},
    {"value": "mono", "label": "Mono"},
    {"value": "display", "label": "Display"},
]

COLLECTIONS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_collection (
    collection_id       INTEGER PRIMARY KEY,
    owner_user_id       INTEGER,
    collection_name     TEXT NOT NULL,
    collection_type     TEXT NOT NULL,
    collection_domain   TEXT NOT NULL,
    description         TEXT,
    icon                TEXT,
    book_cover_bg_colour TEXT NOT NULL DEFAULT '#2f5d50',
    book_cover_image    TEXT NOT NULL DEFAULT '',
    book_cover_style    TEXT NOT NULL DEFAULT 'cloth',
    book_cover_font     TEXT NOT NULL DEFAULT 'serif',
    status              TEXT NOT NULL DEFAULT 'active',
    visibility          TEXT NOT NULL DEFAULT 'private',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_collection_domain
ON lp_collection (owner_user_id, collection_domain);

CREATE INDEX IF NOT EXISTS ix_lp_collection_type
ON lp_collection (owner_user_id, collection_type);

CREATE INDEX IF NOT EXISTS ix_lp_collection_status
ON lp_collection (owner_user_id, status);

CREATE TABLE IF NOT EXISTS lp_collection_item (
    collection_item_id          INTEGER PRIMARY KEY,
    owner_user_id               INTEGER,
    collection_id               INTEGER NOT NULL,
    entry_kind                  TEXT NOT NULL,
    item_type                   TEXT,
    item_id                     TEXT,
    child_collection_id         INTEGER,
    parent_collection_item_id   INTEGER,
    sort_order                  INTEGER NOT NULL DEFAULT 100,
    title_override              TEXT,
    comments                    TEXT,
    is_pinned                   INTEGER NOT NULL DEFAULT 0,
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_collection_item_collection
ON lp_collection_item (owner_user_id, collection_id, parent_collection_item_id, is_pinned, sort_order);

CREATE INDEX IF NOT EXISTS ix_lp_collection_item_item
ON lp_collection_item (owner_user_id, item_type, item_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_lp_collection_item_source_once
ON lp_collection_item (owner_user_id, collection_id, item_type, item_id)
WHERE entry_kind = 'item' AND item_type IS NOT NULL AND item_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS lp_collection_area (
    collection_area_id INTEGER PRIMARY KEY,
    owner_user_id      INTEGER,
    collection_id      INTEGER NOT NULL,
    area_id            TEXT NOT NULL,
    is_primary         INTEGER NOT NULL DEFAULT 0,
    sort_order         INTEGER NOT NULL DEFAULT 100,
    created_at         TEXT NOT NULL,
    UNIQUE (owner_user_id, collection_id, area_id)
);

CREATE INDEX IF NOT EXISTS ix_lp_collection_area_area
ON lp_collection_area (owner_user_id, area_id);

CREATE TABLE IF NOT EXISTS lp_collection_project (
    collection_project_id INTEGER PRIMARY KEY,
    owner_user_id         INTEGER,
    collection_id         INTEGER NOT NULL,
    project_id            INTEGER NOT NULL,
    sort_order            INTEGER NOT NULL DEFAULT 100,
    comments              TEXT,
    created_at            TEXT NOT NULL,
    UNIQUE (owner_user_id, collection_id, project_id)
);

CREATE INDEX IF NOT EXISTS ix_lp_collection_project_project
ON lp_collection_project (owner_user_id, project_id);
"""

_COLLECTIONS_SCHEMA_READY_CONN_IDS = set()


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_conn(conn=None):
    conn = db._get_conn() if conn is None else conn
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    return conn


def _current_owner_user_id():
    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "user_id", None)
    except Exception:
        pass
    return None


def _owner_user_id(owner_user_id=None):
    return _current_owner_user_id() if owner_user_id is None else owner_user_id


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _clean_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_book_cover_bg_colour(value, fallback=DEFAULT_BOOK_COVER_BG_COLOUR):
    colour = _clean_text(value) or fallback
    if (
        colour.startswith("#")
        and len(colour) in {4, 7}
        and all(char in "0123456789abcdefABCDEF" for char in colour[1:])
    ):
        return colour.lower()
    return fallback


def _normalize_book_cover_style(value):
    style = _clean_text(value).lower()
    allowed = {option["value"] for option in BOOK_COVER_STYLE_OPTIONS}
    return style if style in allowed else DEFAULT_BOOK_COVER_STYLE


def _normalize_book_cover_font(value):
    font = _clean_text(value).lower()
    allowed = {option["value"] for option in BOOK_COVER_FONT_OPTIONS}
    return font if font in allowed else DEFAULT_BOOK_COVER_FONT


def _default_notebook_cover_image(collection_id=None):
    if not NOTEBOOK_COVER_PRESETS:
        return ""
    idx = 0
    try:
        if collection_id is not None:
            idx = (int(collection_id) - 1) % len(NOTEBOOK_COVER_PRESETS)
    except (TypeError, ValueError):
        idx = 0
    return NOTEBOOK_COVER_PRESETS[idx]["value"]


def notebook_cover_presets():
    return list(NOTEBOOK_COVER_PRESETS)


def book_cover_style_options():
    return list(BOOK_COVER_STYLE_OPTIONS)


def book_cover_font_options():
    return list(BOOK_COVER_FONT_OPTIONS)


def _collection_cover_values(values, domain, before=None):
    before = before or {}
    is_notes = normalize_domain(domain) == "notes"
    bg_value = values.get("book_cover_bg_colour") if "book_cover_bg_colour" in values else before.get("book_cover_bg_colour")
    image_value = values.get("book_cover_image") if "book_cover_image" in values else before.get("book_cover_image")
    style_value = values.get("book_cover_style") if "book_cover_style" in values else before.get("book_cover_style")
    font_value = values.get("book_cover_font") if "book_cover_font" in values else before.get("book_cover_font")
    if not is_notes:
        return (
            _clean_text(bg_value),
            _clean_text(image_value),
            _clean_text(style_value),
            _clean_text(font_value),
        )
    return (
        _normalize_book_cover_bg_colour(bg_value),
        _clean_text(image_value),
        _normalize_book_cover_style(style_value),
        _normalize_book_cover_font(font_value),
    )


def _table_columns(conn, table_name):
    try:
        return {row["name"] if hasattr(row, "keys") else row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    except Exception:
        return set()


def _table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def ensure_collections_schema(conn=None):
    conn = _get_conn(conn)
    conn_id = id(conn)
    if conn_id in _COLLECTIONS_SCHEMA_READY_CONN_IDS and _collections_schema_is_current(conn):
        return
    conn.executescript(COLLECTIONS_SCHEMA_SQL)
    _migrate_collections_schema(conn)
    conn.commit()
    _COLLECTIONS_SCHEMA_READY_CONN_IDS.add(conn_id)


def _collections_schema_is_current(conn):
    return (
        {"collection_id", "collection_name", "collection_type", "collection_domain", "status", "visibility", "book_cover_bg_colour", "book_cover_image", "book_cover_style", "book_cover_font"}.issubset(_table_columns(conn, "lp_collection"))
        and {"collection_item_id", "collection_id", "entry_kind", "sort_order", "parent_collection_item_id"}.issubset(_table_columns(conn, "lp_collection_item"))
        and {"collection_id", "area_id", "is_primary"}.issubset(_table_columns(conn, "lp_collection_area"))
        and {"collection_id", "project_id", "comments"}.issubset(_table_columns(conn, "lp_collection_project"))
    )


def _migrate_collections_schema(conn):
    if _table_exists(conn, "lp_collection"):
        cols = _table_columns(conn, "lp_collection")
        additions = {
            "owner_user_id": "INTEGER",
            "collection_name": "TEXT",
            "collection_type": "TEXT",
            "collection_domain": "TEXT",
            "description": "TEXT",
            "icon": "TEXT",
            "book_cover_bg_colour": "TEXT NOT NULL DEFAULT '#2f5d50'",
            "book_cover_image": "TEXT NOT NULL DEFAULT ''",
            "book_cover_style": "TEXT NOT NULL DEFAULT 'cloth'",
            "book_cover_font": "TEXT NOT NULL DEFAULT 'serif'",
            "status": "TEXT NOT NULL DEFAULT 'active'",
            "visibility": "TEXT NOT NULL DEFAULT 'private'",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for col_name, col_type in additions.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE lp_collection ADD COLUMN {col_name} {col_type}")
        now = _utc_now()
        conn.execute("UPDATE lp_collection SET status = 'active' WHERE COALESCE(status, '') = ''")
        conn.execute("UPDATE lp_collection SET visibility = ? WHERE COALESCE(visibility, '') = ''", (DEFAULT_VISIBILITY,))
        conn.execute("UPDATE lp_collection SET created_at = ? WHERE COALESCE(created_at, '') = ''", (now,))
        conn.execute("UPDATE lp_collection SET updated_at = ? WHERE COALESCE(updated_at, '') = ''", (now,))
    if _table_exists(conn, "lp_collection_item"):
        cols = _table_columns(conn, "lp_collection_item")
        additions = {
            "owner_user_id": "INTEGER",
            "entry_kind": "TEXT",
            "item_type": "TEXT",
            "item_id": "TEXT",
            "child_collection_id": "INTEGER",
            "parent_collection_item_id": "INTEGER",
            "sort_order": "INTEGER NOT NULL DEFAULT 100",
            "title_override": "TEXT",
            "comments": "TEXT",
            "is_pinned": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for col_name, col_type in additions.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE lp_collection_item ADD COLUMN {col_name} {col_type}")
        now = _utc_now()
        conn.execute("UPDATE lp_collection_item SET created_at = ? WHERE COALESCE(created_at, '') = ''", (now,))
        conn.execute("UPDATE lp_collection_item SET updated_at = ? WHERE COALESCE(updated_at, '') = ''", (now,))


def normalize_status(value):
    status = _clean_text(value).lower()
    return status if status in COLLECTION_STATUSES else "active"


def normalize_domain(value):
    domain = _clean_text(value).lower()
    if domain == "three_d":
        domain = "3d"
    if domain == "contacts":
        domain = "people"
    if domain not in DOMAIN_COLLECTION_TYPES:
        raise ValueError("Unsupported collection domain.")
    return domain


def get_domain_adapter(domain):
    return COLLECTION_DOMAIN_ADAPTERS[normalize_domain(domain)]


def collection_domain_options():
    return [
        {"value": domain, "label": adapter["plural_label"]}
        for domain, adapter in COLLECTION_DOMAIN_ADAPTERS.items()
    ]


def normalize_collection_type(value, domain=None):
    collection_type = _clean_text(value).lower()
    aliases = {
        "notebooks": "notebook",
        "books": "book",
        "albums": "album",
        "playlists": "playlist",
        "manuals": "manual",
        "runbooks": "runbook",
        "workspaces": "workspace",
        "data_workspace": "workspace",
        "data_workspaces": "workspace",
        "datasets": "dataset",
        "file_collections": "file_collection",
        "project_file": "project_files",
        "place_collections": "place_collection",
        "asset_packs": "asset_pack",
        "portfolios": "portfolio",
        "budgets": "budget",
        "financial_plans": "financial_plan",
        "app_groups": "app_group",
        "stacks": "stack",
        "agendas": "agenda",
        "calendars": "calendar",
        "groups": "group",
        "plans": "plan",
        "roadmaps": "roadmap",
    }
    collection_type = aliases.get(collection_type, collection_type)
    if domain:
        domain = normalize_domain(domain)
        allowed = DOMAIN_COLLECTION_TYPES[domain]
        if not collection_type:
            return allowed[0]
        if collection_type not in allowed:
            raise ValueError(f"{collection_type} is not supported for {domain} collections.")
    return collection_type


def _normalize_item_type(value):
    text = _clean_text(value).lower()
    aliases = {
        "notes": "note",
        "howto": "how",
        "how-to": "how",
        "howtos": "how",
        "people": "person",
        "contacts": "person",
        "organisation": "organization",
        "organisations": "organization",
        "organizations": "organization",
        "calendar_event": "event",
        "calendar_events": "event",
        "appointment": "event",
        "appointments": "event",
        "reminder": "event",
        "reminders": "event",
        "saved_sql": "saved_query",
        "saved_queries": "saved_query",
        "csv": "data_file",
        "3d_object": "3d",
        "three_d": "3d",
        "ue_asset": "3d",
        "blender_asset": "3d",
        "real_object": "3d",
        "game": "app",
        "games": "app",
        "tool": "app",
        "tools": "app",
        "server_app": "app",
        "server_apps": "app",
    }
    return aliases.get(text, text)


def _validate_item_type_for_domain(domain, item_type):
    item_type = _normalize_item_type(item_type)
    if item_type not in DOMAIN_ITEM_TYPES.get(domain, ()):
        raise ValueError(f"{item_type} is not compatible with {domain} collections.")
    return item_type


def status_options():
    return [{"value": value, "label": COLLECTION_STATUS_LABELS[value]} for value in COLLECTION_STATUSES]


def collection_type_options(domain=None):
    if domain:
        adapter = get_domain_adapter(domain)
        values = adapter["collection_types"]
        labels = adapter.get("collection_type_labels", {})
    else:
        values = sorted({value for values in DOMAIN_COLLECTION_TYPES.values() for value in values})
        labels = {}
    return [{"value": value, "label": labels.get(value) or value.replace("_", " ").title()} for value in values]


def collection_type_label(domain, collection_type):
    adapter = get_domain_adapter(domain)
    collection_type = normalize_collection_type(collection_type, domain)
    return adapter.get("collection_type_labels", {}).get(collection_type) or collection_type.replace("_", " ").title()


def area_options(selected_area_ids=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    areas_mod.ensure_areas_schema(conn)
    selected = set(selected_area_ids or [])
    options = []
    seen = set()
    for row in areas_mod.areas_list_sidebar(conn=conn, owner_user_id=owner_user_id):
        area_id = _clean_text(row.get("area_id"))
        if not area_id or area_id.lower() == "unmapped":
            continue
        seen.add(area_id)
        options.append(
            {
                "area_id": area_id,
                "label": row.get("area_name") or area_id,
                "icon": row.get("icon") or "",
                "selected": area_id in selected,
            }
        )
    for area_id in sorted(selected - seen):
        options.insert(0, {"area_id": area_id, "label": area_id, "icon": "", "selected": True})
    return options


def project_options(selected_project_ids=None, conn=None, owner_user_id=None):
    selected = {int(value) for value in (selected_project_ids or []) if _clean_int(value) is not None}
    rows = projects_mod.project_list(include_archived=True, conn=conn, owner_user_id=owner_user_id)
    return [
        {
            "project_id": row["project_id"],
            "name": row["name"],
            "icon": row.get("icon") or "",
            "selected": int(row["project_id"]) in selected,
        }
        for row in rows
    ]


def get_collection_list(
    domain=None,
    collection_type=None,
    area_id=None,
    project_id=None,
    include_archived=False,
    conn=None,
    owner_user_id=None,
):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    params = [owner_user_id]
    where = ["c.owner_user_id IS ?"]
    if domain:
        where.append("c.collection_domain = ?")
        params.append(normalize_domain(domain))
    if collection_type:
        where.append("c.collection_type = ?")
        params.append(normalize_collection_type(collection_type, domain))
    if not include_archived:
        where.append("c.status != 'archived'")
    area_id = _clean_text(area_id)
    if area_id and area_id.lower() not in {"all", "all areas", "any", "unmapped"}:
        where.append(
            "EXISTS ("
            "SELECT 1 FROM lp_collection_area ca "
            "WHERE ca.owner_user_id IS ? AND ca.collection_id = c.collection_id "
            "AND (lower(ca.area_id) = lower(?) "
            "OR lower(ca.area_id) LIKE lower(?) || '/%' "
            "OR lower(?) LIKE lower(ca.area_id) || '/%'))"
        )
        params.extend([owner_user_id, area_id, area_id, area_id])
    project_id = _clean_int(project_id)
    if project_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM lp_collection_project cp "
            "WHERE cp.owner_user_id IS ? AND cp.collection_id = c.collection_id AND cp.project_id = ?)"
        )
        params.extend([owner_user_id, project_id])
    rows = conn.execute(
        "SELECT c.*, "
        "(SELECT COUNT(1) FROM lp_collection_item i WHERE i.owner_user_id IS c.owner_user_id AND i.collection_id = c.collection_id) AS item_count "
        "FROM lp_collection c WHERE " + " AND ".join(where) + " "
        "ORDER BY CASE c.status WHEN 'active' THEN 0 ELSE 1 END, lower(c.collection_name), c.collection_id",
        params,
    ).fetchall()
    return [_collection_row(row, conn=conn, owner_user_id=owner_user_id) for row in rows]


def get_collection(collection_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT c.*, "
        "(SELECT COUNT(1) FROM lp_collection_item i WHERE i.owner_user_id IS c.owner_user_id AND i.collection_id = c.collection_id) AS item_count "
        "FROM lp_collection c WHERE c.collection_id = ? AND c.owner_user_id IS ?",
        (collection_id, owner_user_id),
    ).fetchone()
    return _collection_row(row, conn=conn, owner_user_id=owner_user_id) if row else None


def create_collection(values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    name = _clean_text(values.get("collection_name") or values.get("name"))
    if not name:
        raise ValueError("Collection name is required.")
    domain = normalize_domain(values.get("collection_domain") or values.get("domain"))
    collection_type = normalize_collection_type(values.get("collection_type") or values.get("type"), domain)
    cover_bg_colour, cover_image, cover_style, cover_font = _collection_cover_values(values, domain)
    now = _utc_now()
    cur = conn.execute(
        "INSERT INTO lp_collection "
        "(owner_user_id, collection_name, collection_type, collection_domain, description, icon, "
        "book_cover_bg_colour, book_cover_image, book_cover_style, book_cover_font, "
        "status, visibility, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            owner_user_id,
            name,
            collection_type,
            domain,
            _clean_text(values.get("description")),
            _clean_text(values.get("icon")),
            cover_bg_colour,
            cover_image,
            cover_style,
            cover_font,
            normalize_status(values.get("status")),
            _clean_text(values.get("visibility")) or DEFAULT_VISIBILITY,
            now,
            now,
        ),
    )
    collection_id = cur.lastrowid
    set_collection_areas(collection_id, values.get("area_ids") or [], conn=conn, owner_user_id=owner_user_id)
    set_collection_projects(collection_id, values.get("project_ids") or [], conn=conn, owner_user_id=owner_user_id)
    conn.commit()
    _log_collection_change(conn, "collection_add", collection_id, after=get_collection(collection_id, conn=conn, owner_user_id=owner_user_id))
    return collection_id


def update_collection(collection_id, values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = get_collection(collection_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    name = _clean_text(values.get("collection_name") or values.get("name"))
    if not name:
        raise ValueError("Collection name is required.")
    domain = normalize_domain(values.get("collection_domain") or values.get("domain") or before["collection_domain"])
    collection_type = normalize_collection_type(values.get("collection_type") or values.get("type") or before["collection_type"], domain)
    cover_bg_colour, cover_image, cover_style, cover_font = _collection_cover_values(values, domain, before=before)
    conn.execute(
        "UPDATE lp_collection SET collection_name = ?, collection_type = ?, collection_domain = ?, "
        "description = ?, icon = ?, book_cover_bg_colour = ?, book_cover_image = ?, "
        "book_cover_style = ?, book_cover_font = ?, status = ?, visibility = ?, updated_at = ? "
        "WHERE collection_id = ? AND owner_user_id IS ?",
        (
            name,
            collection_type,
            domain,
            _clean_text(values.get("description")),
            _clean_text(values.get("icon")),
            cover_bg_colour,
            cover_image,
            cover_style,
            cover_font,
            normalize_status(values.get("status") or before.get("status")),
            _clean_text(values.get("visibility")) or before.get("visibility") or DEFAULT_VISIBILITY,
            _utc_now(),
            collection_id,
            owner_user_id,
        ),
    )
    if "area_ids" in values:
        set_collection_areas(collection_id, values.get("area_ids") or [], conn=conn, owner_user_id=owner_user_id)
    if "project_ids" in values:
        set_collection_projects(collection_id, values.get("project_ids") or [], conn=conn, owner_user_id=owner_user_id)
    conn.commit()
    _log_collection_change(
        conn,
        "collection_update",
        collection_id,
        before=before,
        after=get_collection(collection_id, conn=conn, owner_user_id=owner_user_id),
    )
    return True


def archive_collection(collection_id, conn=None, owner_user_id=None):
    collection = get_collection(collection_id, conn=conn, owner_user_id=owner_user_id)
    if not collection:
        return False
    values = dict(collection)
    values["status"] = "archived"
    values["area_ids"] = [row["area_id"] for row in collection.get("areas", [])]
    values["project_ids"] = [row["project_id"] for row in collection.get("projects", [])]
    return update_collection(collection_id, values, conn=conn, owner_user_id=owner_user_id)


def restore_collection(collection_id, conn=None, owner_user_id=None):
    collection = get_collection(collection_id, conn=conn, owner_user_id=owner_user_id)
    if not collection:
        return False
    values = dict(collection)
    values["status"] = "active"
    values["area_ids"] = [row["area_id"] for row in collection.get("areas", [])]
    values["project_ids"] = [row["project_id"] for row in collection.get("projects", [])]
    return update_collection(collection_id, values, conn=conn, owner_user_id=owner_user_id)


def delete_collection(collection_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = get_collection(collection_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    conn.execute("DELETE FROM lp_collection_item WHERE owner_user_id IS ? AND collection_id = ?", (owner_user_id, collection_id))
    conn.execute("DELETE FROM lp_collection_item WHERE owner_user_id IS ? AND child_collection_id = ?", (owner_user_id, collection_id))
    conn.execute("DELETE FROM lp_collection_area WHERE owner_user_id IS ? AND collection_id = ?", (owner_user_id, collection_id))
    conn.execute("DELETE FROM lp_collection_project WHERE owner_user_id IS ? AND collection_id = ?", (owner_user_id, collection_id))
    cur = conn.execute("DELETE FROM lp_collection WHERE owner_user_id IS ? AND collection_id = ?", (owner_user_id, collection_id))
    conn.commit()
    if cur.rowcount:
        _log_collection_change(conn, "collection_delete", collection_id, before=before, after=None)
    return cur.rowcount > 0


def set_collection_areas(collection_id, area_ids, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    now = _utc_now()
    cleaned = []
    seen = set()
    for area_id in area_ids or []:
        area_id = _clean_text(area_id)
        if not area_id or area_id in seen:
            continue
        seen.add(area_id)
        cleaned.append(area_id)
    conn.execute("DELETE FROM lp_collection_area WHERE owner_user_id IS ? AND collection_id = ?", (owner_user_id, collection_id))
    for idx, area_id in enumerate(cleaned):
        conn.execute(
            "INSERT OR IGNORE INTO lp_collection_area "
            "(owner_user_id, collection_id, area_id, is_primary, sort_order, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (owner_user_id, collection_id, area_id, 1 if idx == 0 else 0, idx * 10, now),
        )
    conn.commit()


def assign_collection_to_area(collection_id, area_id, is_primary=0, sort_order=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if is_primary:
        conn.execute(
            "UPDATE lp_collection_area SET is_primary = 0 WHERE owner_user_id IS ? AND collection_id = ?",
            (owner_user_id, collection_id),
        )
    conn.execute(
        "INSERT OR IGNORE INTO lp_collection_area "
        "(owner_user_id, collection_id, area_id, is_primary, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (owner_user_id, collection_id, _clean_text(area_id), 1 if is_primary else 0, _clean_int(sort_order, 100) or 100, _utc_now()),
    )
    conn.commit()
    return True


def remove_collection_from_area(collection_id, area_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    cur = conn.execute(
        "DELETE FROM lp_collection_area WHERE owner_user_id IS ? AND collection_id = ? AND area_id = ?",
        (owner_user_id, collection_id, _clean_text(area_id)),
    )
    conn.commit()
    return cur.rowcount > 0


def set_collection_projects(collection_id, project_ids, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    now = _utc_now()
    cleaned = []
    seen = set()
    for project_id in project_ids or []:
        project_id = _clean_int(project_id)
        if project_id is None or project_id in seen:
            continue
        seen.add(project_id)
        cleaned.append(project_id)
    conn.execute("DELETE FROM lp_collection_project WHERE owner_user_id IS ? AND collection_id = ?", (owner_user_id, collection_id))
    for idx, project_id in enumerate(cleaned):
        conn.execute(
            "INSERT OR IGNORE INTO lp_collection_project "
            "(owner_user_id, collection_id, project_id, sort_order, comments, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (owner_user_id, collection_id, project_id, idx * 10, "", now),
        )
    conn.commit()


def assign_collection_to_project(collection_id, project_id, sort_order=None, comments="", conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    conn.execute(
        "INSERT OR IGNORE INTO lp_collection_project "
        "(owner_user_id, collection_id, project_id, sort_order, comments, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (owner_user_id, collection_id, _clean_int(project_id), _clean_int(sort_order, 100) or 100, _clean_text(comments), _utc_now()),
    )
    conn.commit()
    return True


def remove_collection_from_project(collection_id, project_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    cur = conn.execute(
        "DELETE FROM lp_collection_project WHERE owner_user_id IS ? AND collection_id = ? AND project_id = ?",
        (owner_user_id, collection_id, _clean_int(project_id)),
    )
    conn.commit()
    return cur.rowcount > 0


def list_collection_areas(collection_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT ca.*, a.area_name, a.icon "
        "FROM lp_collection_area ca "
        "LEFT JOIN lp_areas a ON a.owner_user_id IS ca.owner_user_id AND lower(a.area_id) = lower(ca.area_id) "
        "WHERE ca.owner_user_id IS ? AND ca.collection_id = ? "
        "ORDER BY ca.is_primary DESC, ca.sort_order, lower(COALESCE(a.area_name, ca.area_id))",
        (owner_user_id, collection_id),
    ).fetchall()
    return [dict(row) for row in rows]


def list_collection_projects(collection_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT cp.*, p.name, p.icon, p.status "
        "FROM lp_collection_project cp "
        "LEFT JOIN lp_project_workspaces p ON p.owner_user_id IS cp.owner_user_id AND p.project_id = cp.project_id "
        "WHERE cp.owner_user_id IS ? AND cp.collection_id = ? "
        "ORDER BY cp.sort_order, lower(COALESCE(p.name, cp.project_id))",
        (owner_user_id, collection_id),
    ).fetchall()
    return [dict(row) for row in rows]


def get_collection_items(collection_id, conn=None, owner_user_id=None, include_hidden=False):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT * FROM lp_collection_item WHERE owner_user_id IS ? AND collection_id = ? "
        "ORDER BY COALESCE(parent_collection_item_id, 0), is_pinned DESC, sort_order, collection_item_id",
        (owner_user_id, collection_id),
    ).fetchall()
    items = []
    for row in rows:
        item = _collection_item_row(row, conn=conn, owner_user_id=owner_user_id, include_hidden=include_hidden)
        if include_hidden or item.get("is_visible", True):
            items.append(item)
    return items


def add_item_to_collection(
    collection_id,
    item_type,
    item_id,
    *,
    parent_entry_id=None,
    sort_order=None,
    title_override="",
    comments="",
    is_pinned=0,
    conn=None,
    owner_user_id=None,
):
    collection = get_collection(collection_id, conn=conn, owner_user_id=owner_user_id)
    if not collection:
        raise ValueError("Collection not found.")
    conn = _get_conn(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    item_type = _validate_item_type_for_domain(collection["collection_domain"], item_type)
    item_id = _clean_text(item_id)
    if not item_id:
        raise ValueError("Item id is required.")
    return _insert_collection_entry(
        collection_id,
        "item",
        item_type=item_type,
        item_id=item_id,
        parent_entry_id=parent_entry_id,
        sort_order=sort_order,
        title_override=title_override,
        comments=comments,
        is_pinned=is_pinned,
        conn=conn,
        owner_user_id=owner_user_id,
    )


def add_heading_to_collection(collection_id, title, *, parent_entry_id=None, sort_order=None, comments="", conn=None, owner_user_id=None):
    if not _clean_text(title):
        raise ValueError("Heading title is required.")
    return _insert_collection_entry(
        collection_id,
        "heading",
        parent_entry_id=parent_entry_id,
        sort_order=sort_order,
        title_override=title,
        comments=comments,
        conn=conn,
        owner_user_id=owner_user_id,
    )


def add_divider_to_collection(collection_id, *, parent_entry_id=None, sort_order=None, comments="", conn=None, owner_user_id=None):
    return _insert_collection_entry(
        collection_id,
        "divider",
        parent_entry_id=parent_entry_id,
        sort_order=sort_order,
        comments=comments,
        conn=conn,
        owner_user_id=owner_user_id,
    )


def add_collection_to_collection(
    collection_id,
    child_collection_id,
    *,
    parent_entry_id=None,
    sort_order=None,
    title_override="",
    comments="",
    conn=None,
    owner_user_id=None,
):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    parent = get_collection(collection_id, conn=conn, owner_user_id=owner_user_id)
    child = get_collection(child_collection_id, conn=conn, owner_user_id=owner_user_id)
    if not parent or not child:
        raise ValueError("Collection not found.")
    if parent["collection_domain"] != child["collection_domain"]:
        raise ValueError("Nested collection must use the same domain.")
    if parent["collection_id"] == child["collection_id"] or _would_create_cycle(conn, owner_user_id, parent["collection_id"], child["collection_id"]):
        raise ValueError("Nested collection would create a circular relationship.")
    return _insert_collection_entry(
        collection_id,
        "collection",
        child_collection_id=child_collection_id,
        parent_entry_id=parent_entry_id,
        sort_order=sort_order,
        title_override=title_override,
        comments=comments,
        conn=conn,
        owner_user_id=owner_user_id,
    )


def _insert_collection_entry(
    collection_id,
    entry_kind,
    *,
    item_type=None,
    item_id=None,
    child_collection_id=None,
    parent_entry_id=None,
    sort_order=None,
    title_override="",
    comments="",
    is_pinned=0,
    conn=None,
    owner_user_id=None,
):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if entry_kind not in ENTRY_KINDS:
        raise ValueError("Unsupported collection entry kind.")
    if not get_collection(collection_id, conn=conn, owner_user_id=owner_user_id):
        raise ValueError("Collection not found.")
    parent_entry_id = _clean_int(parent_entry_id)
    if parent_entry_id is not None and not get_collection_item(parent_entry_id, conn=conn, owner_user_id=owner_user_id):
        raise ValueError("Parent collection entry not found.")
    if sort_order is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 10 AS next_order "
            "FROM lp_collection_item WHERE owner_user_id IS ? AND collection_id = ? AND parent_collection_item_id IS ?",
            (owner_user_id, collection_id, parent_entry_id),
        ).fetchone()
        sort_order = row["next_order"] if row else 100
    now = _utc_now()
    try:
        cur = conn.execute(
            "INSERT INTO lp_collection_item "
            "(owner_user_id, collection_id, entry_kind, item_type, item_id, child_collection_id, parent_collection_item_id, "
            "sort_order, title_override, comments, is_pinned, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_user_id,
                collection_id,
                entry_kind,
                _normalize_item_type(item_type) or None,
                _clean_text(item_id) or None,
                _clean_int(child_collection_id),
                parent_entry_id,
                _clean_int(sort_order, 100) or 100,
                _clean_text(title_override),
                _clean_text(comments),
                1 if is_pinned else 0,
                now,
                now,
            ),
        )
        conn.commit()
        return {"collection_item_id": cur.lastrowid, "created": True}
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT collection_item_id FROM lp_collection_item "
            "WHERE owner_user_id IS ? AND collection_id = ? AND entry_kind = 'item' AND item_type = ? AND item_id = ?",
            (owner_user_id, collection_id, _normalize_item_type(item_type), _clean_text(item_id)),
        ).fetchone()
        return {"collection_item_id": row["collection_item_id"] if row else None, "created": False}


def get_collection_item(collection_item_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT * FROM lp_collection_item WHERE owner_user_id IS ? AND collection_item_id = ?",
        (owner_user_id, collection_item_id),
    ).fetchone()
    return dict(row) if row else None


def update_collection_item(collection_item_id, values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = get_collection_item(collection_item_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    conn.execute(
        "UPDATE lp_collection_item SET parent_collection_item_id = ?, sort_order = ?, title_override = ?, comments = ?, "
        "is_pinned = ?, updated_at = ? WHERE owner_user_id IS ? AND collection_item_id = ?",
        (
            _clean_int(values.get("parent_entry_id") or values.get("parent_collection_item_id")),
            _clean_int(values.get("sort_order"), before.get("sort_order") or 100) or 100,
            _clean_text(values.get("title_override")),
            _clean_text(values.get("comments")),
            1 if values.get("is_pinned") in (1, True, "1", "true", "on", "yes") else 0,
            _utc_now(),
            owner_user_id,
            collection_item_id,
        ),
    )
    conn.commit()
    return True


def move_collection_item(collection_item_id, new_parent_item_id=None, new_sort_order=None, direction=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    item = get_collection_item(collection_item_id, conn=conn, owner_user_id=owner_user_id)
    if not item:
        return False
    if direction in {"up", "down"}:
        comparison = "<" if direction == "up" else ">"
        sort_dir = "DESC" if direction == "up" else "ASC"
        other = conn.execute(
            "SELECT collection_item_id, sort_order FROM lp_collection_item "
            "WHERE owner_user_id IS ? AND collection_id = ? AND parent_collection_item_id IS ? "
            f"AND sort_order {comparison} ? ORDER BY sort_order {sort_dir}, collection_item_id {sort_dir} LIMIT 1",
            (owner_user_id, item["collection_id"], item["parent_collection_item_id"], item["sort_order"]),
        ).fetchone()
        if not other:
            return False
        now = _utc_now()
        conn.execute("UPDATE lp_collection_item SET sort_order = ?, updated_at = ? WHERE collection_item_id = ?", (other["sort_order"], now, item["collection_item_id"]))
        conn.execute("UPDATE lp_collection_item SET sort_order = ?, updated_at = ? WHERE collection_item_id = ?", (item["sort_order"], now, other["collection_item_id"]))
    else:
        conn.execute(
            "UPDATE lp_collection_item SET parent_collection_item_id = ?, sort_order = ?, updated_at = ? "
            "WHERE owner_user_id IS ? AND collection_item_id = ?",
            (
                _clean_int(new_parent_item_id),
                _clean_int(new_sort_order, item.get("sort_order") or 100) or 100,
                _utc_now(),
                owner_user_id,
                collection_item_id,
            ),
        )
    conn.commit()
    return True


def remove_item_from_collection(collection_item_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    cur = conn.execute(
        "DELETE FROM lp_collection_item WHERE owner_user_id IS ? AND collection_item_id = ?",
        (owner_user_id, collection_item_id),
    )
    conn.commit()
    return cur.rowcount > 0


def record_collections(item_type, item_id, domain=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    params = [owner_user_id, _normalize_item_type(item_type), _clean_text(item_id)]
    where = ["i.owner_user_id IS ?", "i.item_type = ?", "i.item_id = ?"]
    if domain:
        where.append("c.collection_domain = ?")
        params.append(normalize_domain(domain))
    rows = conn.execute(
        "SELECT i.collection_item_id, c.collection_id, c.collection_name, c.collection_type, c.collection_domain, c.icon, c.status "
        "FROM lp_collection_item i "
        "JOIN lp_collection c ON c.owner_user_id IS i.owner_user_id AND c.collection_id = i.collection_id "
        "WHERE " + " AND ".join(where) + " "
        "ORDER BY lower(c.collection_name), c.collection_id",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def get_notebook_list(**kwargs):
    kwargs["domain"] = "notes"
    return get_collection_list(**kwargs)


def _would_create_cycle(conn, owner_user_id, parent_collection_id, child_collection_id):
    target = int(parent_collection_id)
    stack = [int(child_collection_id)]
    seen = set()
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        rows = conn.execute(
            "SELECT child_collection_id FROM lp_collection_item "
            "WHERE owner_user_id IS ? AND collection_id = ? AND entry_kind = 'collection' AND child_collection_id IS NOT NULL",
            (owner_user_id, current),
        ).fetchall()
        stack.extend(int(row["child_collection_id"]) for row in rows)
    return False


def _collection_row(row, conn=None, owner_user_id=None):
    if not row:
        return None
    collection = dict(row)
    collection["status_label"] = COLLECTION_STATUS_LABELS.get(collection.get("status"), collection.get("status") or "")
    try:
        collection["type_label"] = collection_type_label(collection.get("collection_domain"), collection.get("collection_type"))
    except Exception:
        collection["type_label"] = (collection.get("collection_type") or "").replace("_", " ").title()
    if collection.get("collection_domain") == "notes":
        collection["book_cover_bg_colour"] = _normalize_book_cover_bg_colour(collection.get("book_cover_bg_colour"))
        collection["book_cover_image"] = _clean_text(collection.get("book_cover_image")) or _default_notebook_cover_image(collection.get("collection_id"))
        collection["book_cover_style"] = _normalize_book_cover_style(collection.get("book_cover_style"))
        collection["book_cover_font"] = _normalize_book_cover_font(collection.get("book_cover_font"))
    collection["areas"] = list_collection_areas(collection["collection_id"], conn=conn, owner_user_id=owner_user_id)
    collection["area_ids"] = [area["area_id"] for area in collection["areas"]]
    collection["projects"] = list_collection_projects(collection["collection_id"], conn=conn, owner_user_id=owner_user_id)
    collection["project_ids"] = [project["project_id"] for project in collection["projects"]]
    return collection


def _collection_item_row(row, conn=None, owner_user_id=None, include_hidden=False):
    item = dict(row)
    item["display_title"] = item.get("title_override") or ""
    item["summary"] = None
    item["is_visible"] = True
    if item.get("entry_kind") == "item":
        item["summary"] = _record_summary(item.get("item_type"), item.get("item_id"))
        item["is_visible"] = include_hidden or _can_view_source(item.get("item_type"), item.get("item_id"))
        if item["summary"] and not item["display_title"]:
            item["display_title"] = item["summary"].get("title") or ""
    elif item.get("entry_kind") == "collection":
        child = get_collection(item.get("child_collection_id"), conn=conn, owner_user_id=owner_user_id)
        item["child_collection"] = child
        if child and not item["display_title"]:
            item["display_title"] = child.get("collection_name") or ""
    elif item.get("entry_kind") == "divider":
        item["display_title"] = ""
    return item


def _record_summary(item_type, item_id):
    try:
        from common import links_records

        return links_records.get_record_summary(item_type, item_id)
    except Exception:
        return None


def _can_view_source(item_type, item_id):
    try:
        from flask_login import current_user
        from core import security

        table_map = {
            "note": ("lp_notes", "id"),
            "media": ("lp_media", "media_id"),
            "audio": ("lp_audio", "id"),
            "file": ("lp_files", "id"),
        }
        table = table_map.get(_normalize_item_type(item_type))
        if table:
            return security.can_view_record(table[0], item_id, current_user, id_column=table[1])
    except Exception:
        pass
    return True


def _log_collection_change(conn, action, entity_id, before=None, after=None):
    try:
        utils_mod.lg_usr(
            action=action,
            entity_type="lp_collection",
            entity_id=entity_id,
            before=before,
            after=after,
            context_type="collections",
            context_id=str(entity_id) if entity_id is not None else None,
            conn=conn,
        )
    except Exception:
        pass
