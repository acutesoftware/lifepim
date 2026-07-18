from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import abort, current_app, g, redirect, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user
from flask_wtf.csrf import CSRFProtect

from common import data as db
from common.network_log import log_network
from common import user_paths


TRUSTED_DEVICE_COOKIE = "lifepim_trusted_device"
TRUSTED_DEVICE_MAX_AGE = 60 * 60 * 24 * 365 * 5
LOGIN_FAILURE_MESSAGE = "Invalid username or password"

login_manager = LoginManager()
csrf = CSRFProtect()
password_hasher = PasswordHasher()


@dataclass
class LoginResult:
    success: bool
    user: "LifePIMUser | None" = None
    error: str | None = None
    rate_limited: bool = False


class LifePIMUser(UserMixin):
    def __init__(self, user_id, username, display_name, role, is_active=True):
        self.id = str(user_id)
        self.user_id = int(user_id)
        self.username = username
        self.display_name = display_name
        self.role = role
        self._is_active = bool(is_active)

    @property
    def is_active(self):
        return self._is_active


def _utc_now():
    return datetime.now(timezone.utc)


def _utc_now_sql():
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def configure_sqlite_connection(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass


def _client_ip(req=None):
    req = req or request
    forwarded = (req.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded or req.remote_addr or ""


def _user_agent(req=None):
    req = req or request
    return (req.headers.get("User-Agent") or "")[:500]


def _secure_cookies_enabled(app=None):
    app = app or current_app
    return bool(app.config.get("LIFEPIM_SECURE_COOKIES", True))


def _set_trusted_cookie(response, raw_token):
    response.set_cookie(
        TRUSTED_DEVICE_COOKIE,
        raw_token,
        max_age=TRUSTED_DEVICE_MAX_AGE,
        secure=_secure_cookies_enabled(),
        httponly=True,
        samesite="Lax",
    )


def _clear_trusted_cookie(response):
    response.delete_cookie(TRUSTED_DEVICE_COOKIE, secure=_secure_cookies_enabled(), httponly=True, samesite="Lax")


def _table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return set()
    return {row[1] for row in rows}


def _add_column_if_missing(conn, table_name, column_name, column_type):
    columns = _table_columns(conn, table_name)
    if columns and column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _ensure_visibility_columns(conn, table_name):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    if not exists:
        return
    _add_column_if_missing(conn, table_name, "owner_user_id", "INTEGER")
    _add_column_if_missing(conn, table_name, "visibility", "TEXT NOT NULL DEFAULT 'private'")
    _add_column_if_missing(conn, table_name, "show_in_blog", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, table_name, "is_public", "INTEGER NOT NULL DEFAULT 0")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_owner_user ON {table_name}(owner_user_id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_visibility ON {table_name}(visibility)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_public ON {table_name}(is_public)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_blog ON {table_name}(show_in_blog)")


def ensure_security_schema(conn=None):
    conn = db._get_conn() if conn is None else conn
    configure_sqlite_connection(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_key TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user', 'guest')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            modified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login_at TEXT,
            password_changed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS auth_trusted_devices (
            trusted_device_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            device_name TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            revoked_at TEXT,
            created_ip TEXT,
            last_ip TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS auth_login_attempts (
            login_attempt_id INTEGER PRIMARY KEY,
            username TEXT,
            user_id INTEGER,
            was_successful INTEGER NOT NULL CHECK (was_successful IN (0, 1)),
            attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_device_token_hash ON auth_trusted_devices(token_hash);
        CREATE INDEX IF NOT EXISTS idx_auth_device_user ON auth_trusted_devices(user_id);
        CREATE INDEX IF NOT EXISTS idx_auth_device_active ON auth_trusted_devices(user_id, revoked_at);
        CREATE INDEX IF NOT EXISTS idx_login_attempt_username_time ON auth_login_attempts(username, attempted_at);
        CREATE INDEX IF NOT EXISTS idx_login_attempt_ip_time ON auth_login_attempts(ip_address, attempted_at);
        """
    )
    _ensure_visibility_columns(conn, "lp_notes")
    _ensure_visibility_columns(conn, "lp_media")
    user_paths.ensure_user_path_columns(conn)
    user_paths.backfill_duncan_user_paths(conn)
    try:
        from common import projects as projects_mod

        rows = conn.execute(
            "SELECT user_id FROM users WHERE lower(username) = 'duncan'"
        ).fetchall()
        for row in rows:
            projects_mod.claim_legacy_project_folders_for_user(row["user_id"], conn=conn)
    except Exception:
        pass
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(migration_key, applied_at) VALUES (?, ?)",
        ("20260713_auth_security", _utc_now_sql()),
    )
    conn.commit()


def configure_security(app):
    env_name = os.getenv("LIFEPIM_ENV", "development").strip().lower()
    allow_insecure = (
        os.getenv("LIFEPIM_ALLOW_INSECURE_COOKIES", "").strip().lower() in {"1", "true", "yes", "on"}
        or env_name != "production"
    )
    secret_key = os.getenv("LIFEPIM_SECRET_KEY") or app.config.get("SECRET_KEY")
    if not secret_key:
        if env_name != "production":
            secret_key = "dev-only-change-me"
        else:
            raise RuntimeError("LIFEPIM_SECRET_KEY must be set before starting LifePIM.")
    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not allow_insecure,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=not allow_insecure,
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        WTF_CSRF_TIME_LIMIT=None,
        LIFEPIM_SECURE_COOKIES=not allow_insecure,
    )
    ensure_security_schema()
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "basic"
    login_manager.init_app(app)
    csrf.init_app(app)
    if "pocket_api" in app.blueprints:
        csrf.exempt(app.blueprints["pocket_api"])

    @app.before_request
    def _security_before_request():
        restore_login_from_trusted_device(request)
        if _route_is_public():
            return None
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.full_path if request.query_string else request.path))
        return None

    @app.after_request
    def _security_after_request(response):
        if getattr(g, "clear_trusted_device_cookie", False):
            _clear_trusted_cookie(response)
        return response

    @app.context_processor
    def _security_context():
        return {"security_current_user": current_user}


def _route_is_public():
    endpoint = request.endpoint or ""
    if endpoint in {"static", "auth.login"}:
        return True
    if endpoint.startswith("static") or endpoint.startswith("public."):
        return True
    if endpoint.startswith("pocket_api.") or request.path.startswith("/api/pocket/v1/"):
        return True
    if request.path.startswith("/static/") or request.path.startswith("/public/"):
        return True
    return False


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return None
    row = db._get_conn().execute(
        "SELECT user_id, username, display_name, role, is_active FROM users WHERE user_id=? AND is_active=1",
        (user_id_int,),
    ).fetchone()
    return _row_to_user(row)


def _row_to_user(row):
    if not row:
        return None
    return LifePIMUser(row["user_id"], row["username"], row["display_name"], row["role"], row["is_active"])


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password_hash, supplied_password):
    try:
        return password_hasher.verify(password_hash, supplied_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        return False


def get_user_by_username(username):
    username = (username or "").strip()
    if not username:
        return None
    return db._get_conn().execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()


def get_user_by_id(user_id):
    return db._get_conn().execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def update_user_password_hash(user_id, password_hash):
    conn = db._get_conn()
    now = _utc_now_sql()
    conn.execute(
        "UPDATE users SET password_hash=?, modified_at=?, password_changed_at=? WHERE user_id=?",
        (password_hash, now, now, user_id),
    )
    conn.commit()


def authenticate_user(username, password):
    row = get_user_by_username(username)
    if not row or not row["is_active"] or not verify_password(row["password_hash"], password):
        return None
    if password_hasher.check_needs_rehash(row["password_hash"]):
        update_user_password_hash(row["user_id"], hash_password(password))
    return _row_to_user(row)


def generate_trusted_device_token():
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash


def _hash_trusted_token(raw_token):
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def login(username, password, response, device_name=None, trust_device=True):
    username = (username or "").strip()
    log_network(
        "login_attempt",
        username=username,
        trust_device=trust_device,
        device_name=device_name,
        remote_addr=_client_ip(),
        user_agent=_user_agent(),
    )
    if is_login_rate_limited(username, request):
        record_login_failure(username, request)
        log_network("login_failure", username=username, reason="rate_limited", remote_addr=_client_ip())
        return LoginResult(False, error=LOGIN_FAILURE_MESSAGE, rate_limited=True)
    row = get_user_by_username(username)
    if not row or not row["is_active"] or not verify_password(row["password_hash"], password):
        record_login_failure(username, request, user_id=row["user_id"] if row else None)
        log_network(
            "login_failure",
            username=username,
            reason="invalid_credentials_or_inactive",
            user_id=row["user_id"] if row else None,
            remote_addr=_client_ip(),
        )
        return LoginResult(False, error=LOGIN_FAILURE_MESSAGE)
    if password_hasher.check_needs_rehash(row["password_hash"]):
        update_user_password_hash(row["user_id"], hash_password(password))
    user = _row_to_user(row)
    login_user(user)
    session.permanent = True
    now = _utc_now_sql()
    conn = db._get_conn()
    conn.execute("UPDATE users SET last_login_at=?, modified_at=? WHERE user_id=?", (now, now, user.user_id))
    conn.commit()
    record_login_success(user.user_id, request)
    log_network("login_success", username=user.username, user_id=user.user_id, trust_device=trust_device, remote_addr=_client_ip())
    if trust_device:
        trusted_device_id = create_trusted_device(user.user_id, response, device_name=device_name)
        log_network("trusted_device_created", username=user.username, user_id=user.user_id, trusted_device_id=trusted_device_id, device_name=device_name)
    return LoginResult(True, user=user)


def logout(response, forget_device=False):
    username = getattr(current_user, "username", "")
    user_id = getattr(current_user, "user_id", None)
    if forget_device:
        raw_token = request.cookies.get(TRUSTED_DEVICE_COOKIE)
        if raw_token:
            db._get_conn().execute(
                "UPDATE auth_trusted_devices SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                (_utc_now_sql(), _hash_trusted_token(raw_token)),
            )
            db._get_conn().commit()
            log_network("trusted_device_revoked_current", username=username, user_id=user_id, remote_addr=_client_ip())
        _clear_trusted_cookie(response)
    log_network("logout", username=username, user_id=user_id, forget_device=forget_device, remote_addr=_client_ip())
    logout_user()
    return response


def logout_all_devices(user_id):
    conn = db._get_conn()
    conn.execute(
        "UPDATE auth_trusted_devices SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
        (_utc_now_sql(), user_id),
    )
    conn.commit()
    log_network("trusted_devices_revoked_for_user", user_id=user_id)


def revoke_trusted_device(trusted_device_id):
    conn = db._get_conn()
    conn.execute(
        "UPDATE auth_trusted_devices SET revoked_at=? WHERE trusted_device_id=? AND revoked_at IS NULL",
        (_utc_now_sql(), trusted_device_id),
    )
    conn.commit()
    log_network("trusted_device_revoked", trusted_device_id=trusted_device_id)


def create_trusted_device(user_id, response, device_name=None):
    raw_token, token_hash = generate_trusted_device_token()
    name = (device_name or "").strip() or _default_device_name()
    conn = db._get_conn()
    cur = conn.execute(
        """
        INSERT INTO auth_trusted_devices
        (user_id, token_hash, device_name, created_at, last_used_at, created_ip, last_ip, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, token_hash, name, _utc_now_sql(), _utc_now_sql(), _client_ip(), _client_ip(), _user_agent()),
    )
    conn.commit()
    _set_trusted_cookie(response, raw_token)
    return cur.lastrowid


def _default_device_name():
    return _user_agent()[:80] or "Trusted device"


def restore_login_from_trusted_device(req, response=None):
    if current_user.is_authenticated:
        return None
    raw_token = req.cookies.get(TRUSTED_DEVICE_COOKIE)
    if not raw_token:
        return None
    row = db._get_conn().execute(
        """
        SELECT d.*, u.username, u.display_name, u.role, u.is_active
        FROM auth_trusted_devices d
        JOIN users u ON u.user_id = d.user_id
        WHERE d.token_hash=?
        """,
        (_hash_trusted_token(raw_token),),
    ).fetchone()
    if not row or not _trusted_device_row_is_active(row):
        g.clear_trusted_device_cookie = True
        log_network("trusted_device_restore_failed", reason="missing_revoked_expired_or_inactive", remote_addr=_client_ip(req), user_agent=_user_agent(req))
        return None
    user = LifePIMUser(row["user_id"], row["username"], row["display_name"], row["role"], row["is_active"])
    login_user(user)
    session.permanent = True
    update_trusted_device_last_used(row["trusted_device_id"], req)
    log_network(
        "trusted_device_restore_ok",
        username=user.username,
        user_id=user.user_id,
        trusted_device_id=row["trusted_device_id"],
        remote_addr=_client_ip(req),
    )
    return user


def _trusted_device_row_is_active(row):
    if row["revoked_at"] or not row["is_active"]:
        return False
    expires_at = row["expires_at"]
    if not expires_at:
        return True
    try:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return exp > _utc_now()


def rotate_trusted_device_token(trusted_device_id, response):
    raw_token, token_hash = generate_trusted_device_token()
    conn = db._get_conn()
    conn.execute(
        "UPDATE auth_trusted_devices SET token_hash=?, last_used_at=? WHERE trusted_device_id=?",
        (token_hash, _utc_now_sql(), trusted_device_id),
    )
    conn.commit()
    _set_trusted_cookie(response, raw_token)


def update_trusted_device_last_used(trusted_device_id, req):
    conn = db._get_conn()
    conn.execute(
        "UPDATE auth_trusted_devices SET last_used_at=?, last_ip=?, user_agent=? WHERE trusted_device_id=?",
        (_utc_now_sql(), _client_ip(req), _user_agent(req), trusted_device_id),
    )
    conn.commit()


def get_trusted_devices(user_id=None):
    params = []
    where = ""
    if user_id is not None:
        where = "WHERE d.user_id = ?"
        params.append(user_id)
    rows = db._get_conn().execute(
        f"""
        SELECT d.*, u.username, u.display_name
        FROM auth_trusted_devices d
        JOIN users u ON u.user_id = d.user_id
        {where}
        ORDER BY d.revoked_at IS NOT NULL, d.last_used_at DESC
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def get_current_user():
    return current_user


def require_login():
    if not current_user.is_authenticated:
        abort(401)
    return True


def require_role(*roles):
    require_login()
    if current_user.role not in roles:
        abort(403)
    return True


def require_permission(permission_name):
    if permission_name in {"users.manage", "security.manage"}:
        return require_role("admin")
    return require_login()


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            require_role(*roles)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def _fetch_record(table_name, record_id, id_column=None):
    if table_name not in {"lp_notes", "lp_media", "lp_calendar_events", "lp_tasks", "lp_files", "lp_audio"}:
        return None
    id_column = id_column or ("media_id" if table_name == "lp_media" else "id")
    try:
        row = db._get_conn().execute(f"SELECT * FROM {table_name} WHERE {id_column}=?", (record_id,)).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _security_schema_active(table_name=None):
    conn = db._get_conn()
    users = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if not users:
        return False
    if table_name:
        columns = _table_columns(conn, table_name)
        if not {"owner_user_id", "visibility", "is_public"}.issubset(columns):
            return False
    return True


def is_owner(record, user):
    if not record or user is None or not getattr(user, "is_authenticated", False):
        return False
    owner = record.get("owner_user_id")
    return owner is not None and str(owner) == str(getattr(user, "user_id", ""))


def is_family_visible(record):
    return (record or {}).get("visibility") == "family"


def is_public_record(record):
    return int((record or {}).get("is_public") or 0) == 1


def is_blog_visible(record):
    return int((record or {}).get("show_in_blog") or 0) == 1


def can_view_record(table_name, record_id, user=None, id_column=None):
    if not _security_schema_active(table_name):
        return True
    record = _fetch_record(table_name, record_id, id_column=id_column)
    user = user or current_user
    if not record:
        return False
    if table_name == "lp_media":
        return user is not None and getattr(user, "is_authenticated", False)
    if is_public_record(record):
        return True
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return is_owner(record, user) or is_family_visible(record)


def can_edit_record(table_name, record_id, user=None, id_column=None):
    if not _security_schema_active(table_name):
        return True
    record = _fetch_record(table_name, record_id, id_column=id_column)
    user = user or current_user
    if not record or user is None or not getattr(user, "is_authenticated", False):
        return False
    return is_owner(record, user)


def can_delete_record(table_name, record_id, user=None, id_column=None):
    return can_edit_record(table_name, record_id, user, id_column=id_column)


def can_view_note(note_id, user=None):
    return can_view_record("lp_notes", note_id, user, id_column="id")


def can_edit_note(note_id, user=None):
    return can_edit_record("lp_notes", note_id, user, id_column="id")


def can_delete_note(note_id, user=None):
    return can_delete_record("lp_notes", note_id, user, id_column="id")


def can_publish_note(note_id, user=None):
    return can_edit_note(note_id, user)


def can_view_media(media_id, user=None):
    return can_view_record("lp_media", media_id, user, id_column="media_id")


def can_edit_media(media_id, user=None):
    return can_edit_record("lp_media", media_id, user, id_column="media_id")


def can_delete_media(media_id, user=None):
    return can_delete_record("lp_media", media_id, user, id_column="media_id")


def can_view_calendar_item(calendar_item_id, user=None):
    return can_view_record("lp_calendar_events", calendar_item_id, user, id_column="id")


def can_edit_calendar_item(calendar_item_id, user=None):
    return can_edit_record("lp_calendar_events", calendar_item_id, user, id_column="id")


def visible_record_condition(table_alias, user=None):
    table_map = {"t": "lp_notes", "m": "lp_media"}
    table_name = table_map.get(table_alias or "")
    if table_name and not _security_schema_active(table_name):
        return "1=1", []
    user = user or current_user
    prefix = f"{table_alias}." if table_alias else ""
    if user is not None and getattr(user, "is_authenticated", False):
        if table_name == "lp_media":
            return "1=1", []
        return f"({prefix}owner_user_id = ? OR {prefix}visibility = 'family' OR {prefix}is_public = 1)", [user.user_id]
    return f"({prefix}is_public = 1)", []


def record_login_success(user_id, req):
    conn = db._get_conn()
    conn.execute(
        "INSERT INTO auth_login_attempts(username, user_id, was_successful, ip_address, user_agent) "
        "SELECT username, user_id, 1, ?, ? FROM users WHERE user_id=?",
        (_client_ip(req), _user_agent(req), user_id),
    )
    conn.commit()


def record_login_failure(username, req, user_id=None):
    conn = db._get_conn()
    conn.execute(
        "INSERT INTO auth_login_attempts(username, user_id, was_successful, ip_address, user_agent) VALUES (?, ?, 0, ?, ?)",
        ((username or "").strip(), user_id, _client_ip(req), _user_agent(req)),
    )
    conn.commit()


def is_login_rate_limited(username, req):
    cutoff = (_utc_now() - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = db._get_conn().execute(
        """
        SELECT COUNT(1) AS cnt
        FROM auth_login_attempts
        WHERE was_successful=0
          AND attempted_at >= ?
          AND (lower(username)=lower(?) OR ip_address=?)
        """,
        (cutoff, (username or "").strip(), _client_ip(req)),
    ).fetchone()
    return bool(row and row["cnt"] >= 5)


def create_user(username, display_name, password, role="user", is_active=True, file_paths=None):
    conn = db._get_conn()
    username = (username or "").strip()
    display_name = (display_name or "").strip()
    preserve_existing_paths = username.lower() == "duncan"
    savepoint = "lifepim_create_user"
    try:
        conn.execute(f"SAVEPOINT {savepoint}")
        cur = conn.execute(
            "INSERT INTO users(username, display_name, password_hash, role, is_active, password_changed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, display_name, hash_password(password), role, 1 if is_active else 0, _utc_now_sql()),
        )
        user_id = cur.lastrowid
        if file_paths and not preserve_existing_paths:
            user_paths.set_user_paths(conn, user_id, file_paths, create_dirs=True)
        else:
            user_paths.initialize_user_paths(
                conn,
                user_id,
                username,
                preserve_existing=preserve_existing_paths,
                create_dirs=not preserve_existing_paths,
                force=True,
            )
        conn.execute(f"RELEASE {savepoint}")
    except Exception:
        conn.execute(f"ROLLBACK TO {savepoint}")
        conn.execute(f"RELEASE {savepoint}")
        raise
    from common import projects as projects_mod

    if preserve_existing_paths:
        projects_mod.claim_legacy_project_folders_for_user(user_id, conn=conn)
    else:
        projects_mod.seed_default_projects_for_user(user_id, conn=conn, replace=False)
    return user_id


def update_user(user_id, username, display_name, role, is_active=True):
    conn = db._get_conn()
    conn.execute(
        "UPDATE users SET username=?, display_name=?, role=?, is_active=?, modified_at=? WHERE user_id=?",
        ((username or "").strip(), (display_name or "").strip(), role, 1 if is_active else 0, _utc_now_sql(), user_id),
    )
    conn.commit()


def reset_user_password(user_id, new_password, revoke_devices=True):
    update_user_password_hash(user_id, hash_password(new_password))
    if revoke_devices:
        logout_all_devices(user_id)


def list_users():
    rows = db._get_conn().execute(
        """
        SELECT u.*,
               (SELECT COUNT(1) FROM auth_trusted_devices d WHERE d.user_id=u.user_id AND d.revoked_at IS NULL) AS active_device_count
        FROM users u
        ORDER BY lower(username)
        """
    ).fetchall()
    return [dict(row) for row in rows]


def users_count():
    row = db._get_conn().execute("SELECT COUNT(1) AS cnt FROM users").fetchone()
    return row["cnt"] if row else 0


def assign_unowned_records_to_user(user_id):
    conn = db._get_conn()
    for table_name in ("lp_notes", "lp_media"):
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
        if exists:
            conn.execute(f"UPDATE {table_name} SET owner_user_id=? WHERE owner_user_id IS NULL", (user_id,))
    conn.commit()
