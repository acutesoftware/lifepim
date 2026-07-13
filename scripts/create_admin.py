import getpass
import os
import sys


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from core import security


def main():
    security.ensure_security_schema()
    username = input("Username: ").strip()
    display_name = input("Display name: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not username or not display_name:
        raise SystemExit("Username and display name are required.")
    if not password or password != confirm:
        raise SystemExit("Passwords do not match.")
    user_id = security.create_user(username, display_name, password, role="admin", is_active=True)
    security.assign_unowned_records_to_user(user_id)
    print(f"Created administrator {username} with user_id {user_id}.")


if __name__ == "__main__":
    main()
