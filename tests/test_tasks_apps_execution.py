import os
import sqlite3
import sys
import unittest
from unittest.mock import patch


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import areas, data, links, projects
from modules.apps import schema as apps_model
from modules.tasks import schema as tasks_model


class TestTasksAppsExecution(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.old_conn = data.conn
        data.conn = self.conn
        areas.ensure_areas_schema(self.conn)
        projects.ensure_projects_schema(self.conn)
        links.ensure_links_schema(self.conn)
        apps_model.ensure_apps_schema(self.conn)
        tasks_model.ensure_tasks_schema(self.conn)

    def tearDown(self):
        data.conn = self.old_conn
        self.conn.close()

    def test_app_action_ids_survive_edit_and_new_actions_get_new_ids(self):
        app_id = apps_model.create_app(
            {
                "title": "CSV Loader",
                "kind": "Script",
                "actions": [
                    {"action_name": "Load CSV", "action_type": "EXECUTABLE", "command": "python", "arguments": "load.py", "is_default": 1}
                ],
            },
            conn=self.conn,
            owner_user_id=1,
        )
        original = apps_model.app_get(app_id, conn=self.conn, owner_user_id=1)["actions"][0]

        apps_model.update_app(
            app_id,
            {
                "title": "CSV Loader",
                "kind": "Script",
                "actions": [
                    {
                        "app_action_id": original["app_action_id"],
                        "action_name": "Load CSV Edited",
                        "action_type": "EXECUTABLE",
                        "command": "python",
                        "arguments": "load_csv.py",
                        "is_default": 1,
                    },
                    {"action_name": "Validate", "action_type": "COMMAND", "command": "echo", "arguments": "ok"},
                ],
            },
            conn=self.conn,
            owner_user_id=1,
        )

        actions = apps_model.app_get(app_id, conn=self.conn, owner_user_id=1)["actions"]
        edited = next(action for action in actions if action["action_name"] == "Load CSV Edited")
        added = next(action for action in actions if action["action_name"] == "Validate")
        self.assertEqual(edited["app_action_id"], original["app_action_id"])
        self.assertNotEqual(added["app_action_id"], original["app_action_id"])

    def test_removed_unreferenced_action_is_deleted_and_referenced_action_is_refused(self):
        app_id = apps_model.create_app(
            {
                "title": "Backup",
                "kind": "Script",
                "actions": [
                    {"action_name": "Backup", "action_type": "COMMAND", "command": "echo", "arguments": "backup", "is_default": 1},
                    {"action_name": "Verify", "action_type": "COMMAND", "command": "echo", "arguments": "verify"},
                ],
            },
            conn=self.conn,
            owner_user_id=1,
        )
        actions = apps_model.app_get(app_id, conn=self.conn, owner_user_id=1)["actions"]
        backup = next(action for action in actions if action["action_name"] == "Backup")
        verify = next(action for action in actions if action["action_name"] == "Verify")
        tasks_model.create_task({"title": "Run Backup", "app_action_id": backup["app_action_id"]}, conn=self.conn, owner_user_id=1)

        apps_model.set_app_actions(
            app_id,
            [
                {
                    "app_action_id": backup["app_action_id"],
                    "action_name": "Backup",
                    "action_type": "COMMAND",
                    "command": "echo",
                    "arguments": "backup",
                    "is_default": 1,
                }
            ],
            conn=self.conn,
            owner_user_id=1,
        )
        remaining_ids = {row["app_action_id"] for row in apps_model.list_app_actions(app_id, conn=self.conn, owner_user_id=1)}
        self.assertNotIn(verify["app_action_id"], remaining_ids)

        with self.assertRaisesRegex(ValueError, "cannot be deleted"):
            apps_model.set_app_actions(app_id, [], conn=self.conn, owner_user_id=1)

    def test_parameter_schema_validation_and_argument_rendering_windows_paths(self):
        schema = {
            "version": 1,
            "parameters": [
                {"name": "input_file", "type": "file", "required": True},
                {"name": "load_mode", "type": "select", "required": True, "default": "replace", "options": ["append", "replace"]},
            ],
        }

        rendered = apps_model.render_argument_template(
            '--input "{input_file}" --mode "{load_mode}"',
            schema,
            {"input_file": r"D:\Tax Files\bank august.csv", "load_mode": "replace"},
        )

        self.assertEqual(rendered, r'--input "D:\Tax Files\bank august.csv" --mode "replace"')
        self.assertEqual(apps_model.split_arguments(rendered), ["--input", r"D:\Tax Files\bank august.csv", "--mode", "replace"])
        with self.assertRaisesRegex(ValueError, "Unknown argument placeholder"):
            apps_model.render_argument_template("--bad {missing}", schema, {"input_file": "x", "load_mode": "replace"})
        with self.assertRaisesRegex(ValueError, "must be one of"):
            apps_model.validate_parameter_values(schema, {"input_file": "x", "load_mode": "merge"})

    def test_parameterless_launch_updates_usage_count(self):
        app_id = apps_model.create_app(
            {
                "title": "Echo",
                "kind": "Command",
                "actions": [{"action_name": "Echo", "action_type": "COMMAND", "command": "echo", "arguments": "hello", "is_default": 1}],
            },
            conn=self.conn,
            owner_user_id=1,
        )

        with patch("modules.apps.schema.subprocess.Popen") as popen:
            apps_model.launch_action(app_id, conn=self.conn, owner_user_id=1)

        popen.assert_called_once()
        app = apps_model.app_get(app_id, conn=self.conn, owner_user_id=1)
        self.assertEqual(app["usage_count"], 1)
        self.assertTrue(app["last_used_date"])

    def test_old_task_schema_is_replaced_and_orphans_removed(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE lp_tasks (id INTEGER PRIMARY KEY, title TEXT, content TEXT, area TEXT)")
        conn.execute("INSERT INTO lp_tasks (id, title, content, area) VALUES (7, 'Dummy', '', 'test')")
        areas.ensure_areas_schema(conn)
        links.ensure_links_schema(conn)
        projects.ensure_projects_schema(conn)
        links.create_link(conn, {"src_type": "task", "src_id": "7", "dst_type": "task", "dst_id": "8", "link_type": "depends_on"})
        project_id = projects.create_project({"name": "Old"}, conn=conn, owner_user_id=1)
        projects.add_project_item(project_id, "task", "7", conn=conn, owner_user_id=1)

        tasks_model.ensure_tasks_schema(conn)

        cols = {row["name"] for row in conn.execute("PRAGMA table_info(lp_tasks)").fetchall()}
        self.assertIn("app_action_id", cols)
        self.assertEqual(conn.execute("SELECT COUNT(1) AS cnt FROM lp_tasks").fetchone()["cnt"], 0)
        self.assertEqual(conn.execute("SELECT COUNT(1) AS cnt FROM lp_links").fetchone()["cnt"], 0)
        self.assertEqual(conn.execute("SELECT COUNT(1) AS cnt FROM lp_project_items").fetchone()["cnt"], 0)
        conn.close()

    def test_quick_add_creates_human_task_and_status_transitions(self):
        task_id = tasks_model.quick_add("Buy milk", area="home", conn=self.conn, owner_user_id=1)
        task = tasks_model.task_get(task_id, conn=self.conn, owner_user_id=1)
        self.assertEqual(task["task_kind"], "task")
        self.assertEqual(task["status"], "open")
        self.assertIsNone(task["app_action_id"])
        self.assertEqual(task["parameters_json"] or None, None)

        tasks_model.set_status(task_id, "done", conn=self.conn, owner_user_id=1)
        self.assertTrue(tasks_model.task_get(task_id, conn=self.conn, owner_user_id=1)["completed_date"])
        tasks_model.set_status(task_id, "open", conn=self.conn, owner_user_id=1)
        self.assertEqual(tasks_model.task_get(task_id, conn=self.conn, owner_user_id=1)["completed_date"] or "", "")

    def test_executable_task_delegates_to_apps_and_does_not_complete(self):
        schema = {
            "version": 1,
            "parameters": [{"name": "name", "type": "text", "required": True}],
        }
        app_id = apps_model.create_app(
            {
                "title": "Hello",
                "kind": "Command",
                "actions": [
                    {
                        "action_name": "Say",
                        "action_type": "COMMAND",
                        "command": "echo",
                        "arguments": '"{name}"',
                        "parameter_schema_json": schema,
                        "is_default": 1,
                    }
                ],
            },
            conn=self.conn,
            owner_user_id=1,
        )
        action = apps_model.app_get(app_id, conn=self.conn, owner_user_id=1)["actions"][0]
        task_id = tasks_model.create_task(
            {"title": "Say hello", "app_action_id": action["app_action_id"], "parameter_values": {"name": "Duncan"}},
            conn=self.conn,
            owner_user_id=1,
        )

        with patch("modules.apps.schema.subprocess.Popen") as popen:
            launched = tasks_model.run_task(task_id, conn=self.conn, owner_user_id=1)

        self.assertEqual(launched["action_name"], "Say")
        popen.assert_called_once()
        self.assertEqual(tasks_model.task_get(task_id, conn=self.conn, owner_user_id=1)["status"], "open")

    def test_missing_app_action_and_template_create(self):
        task_id = tasks_model.create_task({"title": "Broken", "app_action_id": None}, conn=self.conn, owner_user_id=1)
        self.conn.execute("UPDATE lp_tasks SET app_action_id = 999 WHERE id = ?", (task_id,))
        broken = tasks_model.task_get(task_id, conn=self.conn, owner_user_id=1)
        self.assertTrue(broken["missing_app_action"])
        self.assertEqual(broken["run_with_label"], "Missing App Action")

        template_id = tasks_model.create_task({"title": "Backup Notes", "task_kind": "template", "area": "lifepim"}, conn=self.conn, owner_user_id=1)
        occurrence_id = tasks_model.create_task_from_template(template_id, conn=self.conn, owner_user_id=1)
        occurrence = tasks_model.task_get(occurrence_id, conn=self.conn, owner_user_id=1)
        self.assertEqual(occurrence["task_kind"], "task")
        self.assertEqual(occurrence["status"], "open")
        self.assertEqual(occurrence["title"], "Backup Notes")

    def test_no_task_run_process_or_job_tables_created(self):
        forbidden = {"lp_task_run", "lp_process", "lp_process_run", "lp_job", "lp_job_run"}
        tables = {row["name"] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        self.assertFalse(forbidden & tables)


if __name__ == "__main__":
    unittest.main()
