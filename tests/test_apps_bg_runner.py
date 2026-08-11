import contextlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import areas, data
from modules.apps import runner
from modules.apps import schema as apps_model


class TestAppsBackgroundRunner(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "lifepim.db")
        self.log_dir = os.path.join(self.tempdir.name, "app_runs")
        self.old_conn = data.conn
        self.old_db_file = data.DB_FILE
        self.old_log_dir = os.environ.get("LIFEPIM_APP_RUNS_DIR")
        os.environ["LIFEPIM_APP_RUNS_DIR"] = self.log_dir
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        data.conn = self.conn
        data.DB_FILE = self.db_path
        areas.ensure_areas_schema(self.conn)
        apps_model.ensure_apps_schema(self.conn)

    def tearDown(self):
        data.conn = self.old_conn
        data.DB_FILE = self.old_db_file
        if self.old_log_dir is None:
            os.environ.pop("LIFEPIM_APP_RUNS_DIR", None)
        else:
            os.environ["LIFEPIM_APP_RUNS_DIR"] = self.old_log_dir
        self.conn.close()
        self.tempdir.cleanup()

    def _script(self, name, body):
        path = os.path.join(self.tempdir.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def _app(self, title, command, arguments="", app_key="test-app"):
        return apps_model.create_app(
            {
                "title": title,
                "app_key": app_key,
                "kind": "Script",
                "actions": [
                    {
                        "action_name": "Run",
                        "action_type": "EXECUTABLE",
                        "command": command,
                        "arguments": arguments,
                        "is_default": 1,
                    }
                ],
            },
            conn=self.conn,
            owner_user_id=None,
        )

    def test_successful_app_records_lifecycle_and_logs(self):
        script = self._script(
            "ok_app.py",
            "import sys\nprint('hello stdout')\nprint('hello stderr', file=sys.stderr)\n",
        )
        app_id = self._app("OK App", sys.executable, f'"{script}"')

        run = apps_model.create_app_run(app_id, trigger_source="cli", conn=self.conn, owner_user_id=None)
        self.assertEqual(run["status"], "Starting")

        finished = apps_model.run_app_worker(run["app_run_id"], conn=self.conn)

        self.assertEqual(finished["status"], "Completed")
        self.assertEqual(finished["exit_code"], 0)
        self.assertTrue(finished["started_at"])
        self.assertTrue(finished["finished_at"])
        with open(finished["stdout_log"], encoding="utf-8") as handle:
            self.assertIn("hello stdout", handle.read())
        with open(finished["stderr_log"], encoding="utf-8") as handle:
            self.assertIn("hello stderr", handle.read())

    def test_failed_app_records_nonzero_exit(self):
        script = self._script("bad_app.py", "import sys\nsys.exit(7)\n")
        app_id = self._app("Bad App", sys.executable, f'"{script}"')

        run = apps_model.create_app_run(app_id, conn=self.conn, owner_user_id=None)
        finished = apps_model.run_app_worker(run["app_run_id"], conn=self.conn)

        self.assertEqual(finished["status"], "Failed")
        self.assertEqual(finished["exit_code"], 7)

    def test_missing_executable_fails_with_error_message(self):
        app_id = self._app("Missing App", os.path.join(self.tempdir.name, "missing.exe"))

        run = apps_model.create_app_run(app_id, conn=self.conn, owner_user_id=None)
        finished = apps_model.run_app_worker(run["app_run_id"], conn=self.conn)

        self.assertEqual(finished["status"], "Failed")
        self.assertTrue(finished["error_message"])

    def test_cli_lookup_and_argument_passthrough(self):
        argv_path = os.path.join(self.tempdir.name, "argv.txt")
        script = self._script(
            "argv_app.py",
            "import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('\\n'.join(sys.argv[2:]), encoding='utf-8')\n",
        )
        app_id = self._app("Argument App", sys.executable, f'"{script}" "{argv_path}"', app_key="argument-app")
        self.assertEqual(apps_model.resolve_app_identifier("argument-app", conn=self.conn)["app_id"], app_id)

        run = apps_model.create_app_run(
            app_id,
            extra_args=["--foo", "bar"],
            trigger_source="cli",
            conn=self.conn,
            owner_user_id=None,
        )
        finished = apps_model.run_app_worker(run["app_run_id"], conn=self.conn)

        self.assertEqual(finished["status"], "Completed")
        with open(argv_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(), ["--foo", "bar"])

    def test_cli_launcher_returns_promptly_after_spawning_worker(self):
        self._app("CLI App", sys.executable, "-c \"print('ok')\"", app_key="cli-app")

        stdout = io.StringIO()
        with patch("modules.apps.schema.subprocess.Popen") as popen, contextlib.redirect_stdout(stdout):
            exit_code = runner.main(["cli-app", "--foo", "bar"])

        self.assertEqual(exit_code, 0)
        popen.assert_called_once()
        self.assertIn("Run ID:", stdout.getvalue())
        run = apps_model.latest_app_run(app_id=apps_model.resolve_app_identifier("cli-app", conn=self.conn)["app_id"], conn=self.conn)
        self.assertEqual(run["status"], "Starting")
        self.assertEqual(run["trigger_source"], "cli")

    def test_old_app_schema_without_app_key_migrates_cleanly(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE lp_app ("
                "app_id INTEGER PRIMARY KEY, owner_user_id INTEGER, title TEXT NOT NULL, "
                "kind TEXT NOT NULL DEFAULT 'Other', enabled INTEGER NOT NULL DEFAULT 1, "
                "favorite INTEGER NOT NULL DEFAULT 0, usage_count INTEGER NOT NULL DEFAULT 0, "
                "created_date TEXT, modified_date TEXT)"
            )
            conn.execute(
                "INSERT INTO lp_app (app_id, owner_user_id, title, kind, created_date, modified_date) "
                "VALUES (1, NULL, 'Legacy App', 'Script', '2026-08-10T00:00:00Z', '2026-08-10T00:00:00Z')"
            )

            apps_model.ensure_apps_schema(conn)

            cols = {row["name"] for row in conn.execute("PRAGMA table_info(lp_app)").fetchall()}
            self.assertIn("app_key", cols)
            self.assertIn("lp_app_run", {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()})
            self.assertIsNotNone(apps_model.app_get(1, conn=conn, owner_user_id=None))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
