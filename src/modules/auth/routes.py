from flask import Blueprint, make_response, redirect, render_template, request, url_for
from flask_login import current_user

from common import data as db
from common.utils import get_side_tabs, get_tabs
from core import security


auth_bp = Blueprint("auth", __name__, template_folder="templates")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(request.args.get("next") or url_for("index"))
    error = ""
    if security.users_count() == 0:
        error = "No administrator exists yet. Run scripts/create_admin.py first."
    if request.method == "POST":
        next_url = request.form.get("next") or url_for("index")
        response = make_response(redirect(next_url))
        result = security.login(
            request.form.get("username", ""),
            request.form.get("password", ""),
            response,
            device_name=request.form.get("device_name", ""),
            trust_device=request.form.get("trust_device") == "1",
        )
        if result.success:
            return response
        error = result.error or security.LOGIN_FAILURE_MESSAGE
    return render_template(
        "login.html",
        active_tab="login",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Login",
        content_html="",
        error=error,
        next_url=request.args.get("next") or request.form.get("next") or "",
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(redirect(url_for("auth.login")))
    forget_device = request.form.get("forget_device", "1") == "1"
    return security.logout(response, forget_device=forget_device)


def _count_visible_records(table_name, table_alias, user):
    conn = db._get_conn()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not exists:
        return 0
    condition, params = security.visible_record_condition(table_alias, user)
    row = conn.execute(f"SELECT COUNT(1) AS cnt FROM {table_name} {table_alias} WHERE {condition}", params).fetchone()
    return row["cnt"] if row else 0


@auth_bp.route("/user_profile")
def user_profile():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return render_template(
        "user_profile.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="User Profile",
        content_html="",
        note_count=_count_visible_records("lp_notes", "t", current_user),
        media_count=_count_visible_records("lp_media", "m", current_user),
    )


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    error = ""
    if request.method == "POST":
        row = security.get_user_by_id(current_user.user_id)
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        if not row or not security.verify_password(row["password_hash"], current_password):
            error = "Current password is incorrect."
        elif not new_password or new_password != confirm_password:
            error = "New passwords do not match."
        else:
            security.update_user_password_hash(current_user.user_id, security.hash_password(new_password))
            security.logout_all_devices(current_user.user_id)
            response = make_response(redirect(url_for("auth.login")))
            return security.logout(response, forget_device=True)
    return render_template(
        "change_password.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Change Password",
        content_html="",
        error=error,
    )
