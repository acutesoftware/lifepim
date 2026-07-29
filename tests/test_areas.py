import os
import sqlite3
import tempfile
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import areas


class TestAreas(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        areas.ensure_areas_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_columns(self):
        cols = [row[1] for row in self.conn.execute("PRAGMA table_info(lp_areas)").fetchall()]
        expected = [
            "owner_user_id",
            "area_id",
            "icon",
            "tab",
            "group_name",
            "area_name",
            "is_header",
            "is_system",
            "status",
            "tags",
            "sort_order",
            "pinned",
            "notes",
            "created_utc",
            "updated_utc",
        ]
        self.assertEqual(cols, expected)

        cols = [row[1] for row in self.conn.execute("PRAGMA table_info(lp_area_folders)").fetchall()]
        expected = [
            "area_folder_id",
            "owner_user_id",
            "area_id",
            "path_prefix",
            "folder_role",
            "create_type",
            "is_write_enabled",
            "confidence",
            "tags",
            "notes",
            "sort_order",
            "is_enabled",
            "created_utc",
            "updated_utc",
        ]
        self.assertEqual(cols, expected)

    def test_default_folder_uniqueness(self):
        area_id = "pers.health"
        areas.area_upsert(
            {
                "area_id": area_id,
                "tab": "PERS",
                "group_name": "Health",
                "area_name": "Health",
            },
            conn=self.conn,
        )
        folder1 = areas.area_folder_add(
            area_id,
            r"C:\\Notes\\Health",
            folder_role="include",
            conn=self.conn,
        )
        folder2 = areas.area_folder_add(
            area_id,
            r"C:\\Notes\\Health2",
            folder_role="include",
            conn=self.conn,
        )
        areas.area_folder_set_default(area_id, folder1, conn=self.conn)
        areas.area_folder_set_default(area_id, folder2, conn=self.conn)
        rows = self.conn.execute(
            "SELECT area_folder_id, folder_role, is_write_enabled FROM lp_area_folders "
            "WHERE area_id = ? AND folder_role = 'default'",
            (area_id,),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["area_folder_id"], folder2)
        self.assertEqual(rows[0]["is_write_enabled"], 1)

    def test_default_folder_get(self):
        area_id = "fun.sport"
        areas.area_upsert(
            {
                "area_id": area_id,
                "tab": "FUN",
                "group_name": "Sport",
                "area_name": "Sports",
            },
            conn=self.conn,
        )
        self.assertIsNone(areas.area_default_folder_get(area_id, conn=self.conn))
        folder_id = areas.area_folder_add(
            area_id,
            r"C:\\Notes\\Sport",
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )
        self.assertTrue(folder_id)
        self.assertEqual(
            areas.area_default_folder_get(area_id, conn=self.conn),
            os.path.abspath(r"C:\\Notes\\Sport"),
        )

    def test_shared_folder_allowed(self):
        areas.area_upsert(
            {
                "area_id": "area.one",
                "tab": "WORK",
                "group_name": "One",
                "area_name": "One",
            },
            conn=self.conn,
        )
        areas.area_upsert(
            {
                "area_id": "area.two",
                "tab": "WORK",
                "group_name": "Two",
                "area_name": "Two",
            },
            conn=self.conn,
        )
        path = r"C:\\Notes\\Shared"
        id1 = areas.area_folder_add("area.one", path, conn=self.conn)
        id2 = areas.area_folder_add("area.two", path, conn=self.conn)
        self.assertTrue(id1)
        self.assertTrue(id2)

    def test_area_folders_are_scoped_by_user(self):
        area_id = "pers/health"
        folder_ids = {}
        for owner_id, path in [(1, r"C:\\Users\\One\\notes\\health"), (2, r"C:\\Users\\Two\\notes\\health")]:
            areas.area_upsert(
                {
                    "area_id": area_id,
                    "tab": "PERS",
                    "group_name": "PERS",
                    "area_name": "Health",
                },
                owner_user_id=owner_id,
                conn=self.conn,
            )
            folder_ids[owner_id] = areas.area_folder_add(
                area_id,
                path,
                folder_role="default",
                is_write_enabled=1,
                owner_user_id=owner_id,
                conn=self.conn,
            )

        self.assertIn(
            r"One\notes\health".lower(),
            areas.area_default_folder_get(area_id, owner_user_id=1, conn=self.conn).lower(),
        )
        self.assertIn(
            r"Two\notes\health".lower(),
            areas.area_default_folder_get(area_id, owner_user_id=2, conn=self.conn).lower(),
        )
        self.assertEqual(
            len(areas.area_folders_list(area_id, owner_user_id=1, conn=self.conn)),
            1,
        )
        areas.area_folder_set_default(area_id, folder_ids[2], owner_user_id=1, conn=self.conn)
        self.assertIn(
            r"One\notes\health".lower(),
            areas.area_default_folder_get(area_id, owner_user_id=1, conn=self.conn).lower(),
        )
        areas.area_folder_disable(folder_ids[2], owner_user_id=1, conn=self.conn)
        row = self.conn.execute(
            "SELECT is_enabled FROM lp_area_folders WHERE area_folder_id = ?",
            (folder_ids[2],),
        ).fetchone()
        self.assertEqual(row["is_enabled"], 1)
        areas.area_folder_remove(folder_ids[2], owner_user_id=1, conn=self.conn)
        row = self.conn.execute(
            "SELECT area_folder_id FROM lp_area_folders WHERE area_folder_id = ?",
            (folder_ids[2],),
        ).fetchone()
        self.assertIsNotNone(row)

    def test_default_area_folders_for_new_user_use_user_notes_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.get("LIFEPIM_LAN_USER_ROOT_BASE")
            os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = tmpdir
            try:
                self.conn.execute(
                    """
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        display_name TEXT,
                        password_hash TEXT,
                        role TEXT,
                        is_active INTEGER
                    )
                    """
                )
                self.conn.execute(
                    "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
                    "VALUES (7, 'alice', 'Alice', 'hash', 'user', 1)"
                )
                areas.seed_default_areas_for_user(7, conn=self.conn)

                created = areas.ensure_default_area_folders_for_user(
                    7,
                    username="alice",
                    conn=self.conn,
                    create_dirs=True,
                )

                self.assertGreater(created, 0)
                default_path = areas.area_default_folder_get(
                    "home",
                    owner_user_id=7,
                    conn=self.conn,
                )
                expected_prefix = os.path.join(tmpdir, "alice", "notes")
                self.assertTrue(default_path.lower().startswith(expected_prefix.lower()))
                self.assertTrue(os.path.isdir(os.path.join(tmpdir, "alice", "notes")))
                self.assertTrue(os.path.isdir(os.path.join(tmpdir, "alice", "areas")))
                self.assertTrue(os.path.isdir(os.path.join(tmpdir, "alice", "lists")))
            finally:
                if old_env is None:
                    os.environ.pop("LIFEPIM_LAN_USER_ROOT_BASE", None)
                else:
                    os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = old_env

    def test_default_folder_for_new_area_uses_user_notes_root_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.get("LIFEPIM_LAN_USER_ROOT_BASE")
            os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = tmpdir
            try:
                self.conn.execute(
                    """
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        display_name TEXT,
                        password_hash TEXT,
                        role TEXT,
                        is_active INTEGER
                    )
                    """
                )
                self.conn.execute(
                    "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
                    "VALUES (8, 'alice', 'Alice', 'hash', 'user', 1)"
                )
                areas.save_user_sidebar_rows(
                    [
                        {
                            "area_id": "make/new-game",
                            "area_name": "New Game",
                            "icon": "N",
                            "group_name": "MAKE",
                        }
                    ],
                    owner_user_id=8,
                    conn=self.conn,
                )

                created = areas.ensure_default_area_folder_for_area(
                    "make/new-game",
                    area_name="New Game",
                    owner_user_id=8,
                    username="alice",
                    conn=self.conn,
                    create_dirs=True,
                )
                created_again = areas.ensure_default_area_folder_for_area(
                    "make/new-game",
                    area_name="New Game",
                    owner_user_id=8,
                    username="alice",
                    conn=self.conn,
                    create_dirs=True,
                )

                default_path = areas.area_default_folder_get(
                    "make/new-game",
                    owner_user_id=8,
                    conn=self.conn,
                )
                expected_path = os.path.join(tmpdir, "alice", "notes", "make-new-game")
                self.assertEqual(created, 1)
                self.assertEqual(created_again, 0)
                self.assertEqual(default_path.lower(), expected_path.lower())
                self.assertTrue(os.path.isdir(expected_path))
                rows = self.conn.execute(
                    "SELECT folder_role, create_type, is_write_enabled FROM lp_area_folders "
                    "WHERE owner_user_id = 8 AND area_id = 'make/new-game'"
                ).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["folder_role"], "default")
                self.assertEqual(rows[0]["create_type"], "markdown")
                self.assertEqual(rows[0]["is_write_enabled"], 1)
            finally:
                if old_env is None:
                    os.environ.pop("LIFEPIM_LAN_USER_ROOT_BASE", None)
                else:
                    os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = old_env

    def test_legacy_area_folders_are_claimed_for_duncan_on_migration(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT, password_hash TEXT, role TEXT, is_active INTEGER)"
            )
            conn.execute(
                "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
                "VALUES (3, 'duncan', 'Duncan', 'hash', 'admin', 1)"
            )
            conn.execute(
                """
                CREATE TABLE lp_areas (
                    owner_user_id INTEGER,
                    area_id TEXT,
                    icon TEXT,
                    tab TEXT,
                    group_name TEXT,
                    area_name TEXT,
                    is_header INTEGER,
                    is_system INTEGER,
                    status TEXT,
                    tags TEXT,
                    sort_order INTEGER,
                    pinned INTEGER,
                    notes TEXT,
                    created_utc TEXT,
                    updated_utc TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO lp_areas VALUES (3, 'pers/health', '', 'PERS', 'PERS', 'Health', 0, 0, 'active', NULL, 10, 0, NULL, 'now', 'now')"
            )
            conn.execute(
                """
                CREATE TABLE lp_area_folders (
                    area_folder_id INTEGER PRIMARY KEY,
                    area_id TEXT NOT NULL,
                    path_prefix TEXT NOT NULL,
                    folder_role TEXT NOT NULL,
                    create_type TEXT NOT NULL DEFAULT 'none',
                    is_write_enabled INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    tags TEXT,
                    notes TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 100,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO lp_area_folders VALUES "
                "(11, 'pers/health', 'N:\\duncan\\LifePIM_Data\\DATA\\notes\\10-Pers\\12-Health', "
                "'default', 'none', 1, 1.0, NULL, NULL, 100, 1, 'now', 'now')"
            )

            areas.ensure_areas_schema(conn)

            row = conn.execute(
                "SELECT owner_user_id, path_prefix FROM lp_area_folders WHERE area_folder_id = 11"
            ).fetchone()
            self.assertEqual(row["owner_user_id"], 3)
            self.assertEqual(row["path_prefix"], r"N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health")
        finally:
            conn.close()

    def test_user_sidebar_can_be_saved_and_reset(self):
        areas.seed_default_areas_for_user(1, conn=self.conn)
        default_rows = areas.areas_side_tabs(owner_user_id=1, conn=self.conn, seed=False)
        self.assertGreater(len(default_rows), 1)

        areas.save_user_sidebar_rows(
            [
                {
                    "area_id": "All",
                    "area_name": "All Areas",
                    "icon": "*",
                    "group_name": "Areas",
                    "is_system": 1,
                },
                {
                    "area_id": "work/client",
                    "area_name": "Client",
                    "icon": "W",
                    "group_name": "WORK",
                },
            ],
            owner_user_id=1,
            conn=self.conn,
        )
        rows = areas.areas_side_tabs(owner_user_id=1, conn=self.conn, seed=False)
        self.assertEqual([row["id"] for row in rows], ["All", "work/client"])

        areas.seed_default_areas_for_user(1, conn=self.conn, replace=True)
        reset_rows = areas.areas_side_tabs(owner_user_id=1, conn=self.conn, seed=False)
        self.assertEqual(len(reset_rows), len(default_rows))

    def test_user_sidebar_save_logs_area_changes(self):
        areas.save_user_sidebar_rows(
            [
                {
                    "area_id": "work/client",
                    "area_name": "Client",
                    "icon": "W",
                    "group_name": "WORK",
                },
            ],
            owner_user_id=1,
            conn=self.conn,
        )

        row = self.conn.execute(
            "SELECT action, entity_type, entity_id, context_type FROM sys_user_log "
            "WHERE entity_type = 'lp_areas' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["action"], "area_add")
        self.assertEqual(row["entity_id"], "work/client")
        self.assertEqual(row["context_type"], "areas_edit")

    def test_area_id_rename_updates_exact_references_and_delete_keeps_content(self):
        areas.area_upsert(
            {
                "area_id": "work/client",
                "tab": "WORK",
                "group_name": "WORK",
                "area_name": "Client",
            },
            owner_user_id=1,
            conn=self.conn,
        )
        areas.area_folder_add(
            "work/client",
            r"C:\\Notes\\Client",
            folder_role="default",
            owner_user_id=1,
            conn=self.conn,
        )
        self.conn.execute("CREATE TABLE lp_notes (id INTEGER PRIMARY KEY, owner_user_id INTEGER, area TEXT)")
        self.conn.execute("CREATE TABLE lp_tasks (id INTEGER PRIMARY KEY, area TEXT)")
        self.conn.execute("CREATE TABLE lp_howto (howto_id INTEGER PRIMARY KEY, area_id TEXT)")
        self.conn.execute("INSERT INTO lp_notes VALUES (1, 1, 'work/client')")
        self.conn.execute("INSERT INTO lp_notes VALUES (2, 2, 'work/client')")
        self.conn.execute("INSERT INTO lp_tasks VALUES (1, 'work/client')")
        self.conn.execute("INSERT INTO lp_howto VALUES (1, 'work/client')")

        areas.save_user_sidebar_rows(
            [
                {
                    "original_area_id": "work/client",
                    "area_id": "work/customer",
                    "area_name": "Customer",
                    "icon": "W",
                    "group_name": "WORK",
                }
            ],
            owner_user_id=1,
            conn=self.conn,
        )

        self.assertIsNone(areas.area_get("work/client", owner_user_id=1, conn=self.conn))
        self.assertIsNotNone(areas.area_get("work/customer", owner_user_id=1, conn=self.conn))
        self.assertEqual(
            self.conn.execute("SELECT area_id FROM lp_area_folders WHERE owner_user_id = 1").fetchone()["area_id"],
            "work/customer",
        )
        self.assertEqual(self.conn.execute("SELECT area FROM lp_notes WHERE id = 1").fetchone()["area"], "work/customer")
        self.assertEqual(self.conn.execute("SELECT area FROM lp_notes WHERE id = 2").fetchone()["area"], "work/client")
        self.assertEqual(self.conn.execute("SELECT area FROM lp_tasks WHERE id = 1").fetchone()["area"], "work/customer")
        self.assertEqual(self.conn.execute("SELECT area_id FROM lp_howto WHERE howto_id = 1").fetchone()["area_id"], "work/customer")

        areas.save_user_sidebar_rows([], owner_user_id=1, conn=self.conn)

        self.assertIsNone(areas.area_get("work/customer", owner_user_id=1, conn=self.conn))
        self.assertEqual(self.conn.execute("SELECT area FROM lp_notes WHERE id = 1").fetchone()["area"], "work/customer")
        self.assertEqual(
            self.conn.execute("SELECT area_id FROM lp_area_folders WHERE owner_user_id = 1").fetchone()["area_id"],
            "work/customer",
        )

    def test_flat_legacy_sidebar_is_restored_to_default_structure(self):
        for area_id, name in [("work/job", "Job"), ("make/design", "Design")]:
            areas.area_upsert(
                {
                    "area_id": area_id,
                    "tab": "LEGACY",
                    "group_name": "Legacy",
                    "area_name": name,
                    "sort_order": 100,
                },
                owner_user_id=1,
                conn=self.conn,
            )

        count = areas.seed_default_areas_for_user(1, conn=self.conn)
        rows = areas.areas_side_tabs(owner_user_id=1, conn=self.conn, seed=False)

        self.assertGreater(count, 2)
        self.assertEqual(rows[0]["id"], "All")
        self.assertTrue(any(row["is_header"] for row in rows))
        self.assertTrue(any(row["icon"] for row in rows))
        self.assertIn("All", [row["id"] for row in rows])


if __name__ == "__main__":
    unittest.main()
