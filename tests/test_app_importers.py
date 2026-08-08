import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from modules.apps import schema as apps_model
from modules.apps.importers import (
    DevFolderAppImporter,
    DesktopAppImporter,
    TaskbarAppImporter,
    import_selected_candidates,
    mark_candidate_duplicates,
)
from modules.apps.importers.base import AppImportCandidate, SOURCE_DESKTOP, SOURCE_DEV_FOLDER
from modules.apps.importers.service import normalize_duplicate_value
from modules.apps.importers.windows_shortcuts import ShortcutInfo


class TestAppImporters(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apps_model.ensure_apps_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_dev_folder_scan_immediate_children_markers_and_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = os.path.join(tmpdir, "LifePIM")
            nested = os.path.join(project, "src")
            plain = os.path.join(tmpdir, "PlainFolder")
            os.makedirs(os.path.join(project, ".git"))
            os.makedirs(nested)
            os.makedirs(plain)
            with open(os.path.join(project, "package.json"), "w", encoding="utf-8") as handle:
                handle.write("{}")

            result = DevFolderAppImporter(tmpdir, default_area_id="dev").scan()

            self.assertEqual([candidate.name for candidate in result.candidates], ["LifePIM", "PlainFolder"])
            self.assertNotIn("src", [candidate.name for candidate in result.candidates])
            lifepim = result.candidates[0]
            self.assertEqual(lifepim.kind, "Development Project")
            self.assertEqual(lifepim.area_id, "dev")
            self.assertEqual(lifepim.action_name, "Open Folder")
            self.assertEqual(lifepim.action_type, "OPEN_FOLDER")
            self.assertIn("Git repository", lifepim.metadata["project_hints"])
            self.assertIn("Node project", lifepim.metadata["project_hints"])

    def test_dev_folder_scan_missing_root_is_empty(self):
        result = DevFolderAppImporter(r"Z:\definitely_missing_lifepim_import_root").scan()

        self.assertEqual(result.candidates, [])
        self.assertTrue(result.messages)

    def test_duplicate_path_normalization_marks_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = os.path.join(tmpdir, "ExistingApp")
            os.makedirs(project)
            apps_model.create_app(
                {
                    "title": "Existing App",
                    "kind": "Development Project",
                    "path": project.upper() + os.sep,
                    "actions": [
                        {
                            "action_name": "Open Folder",
                            "action_type": "OPEN_FOLDER",
                            "command": project.upper() + os.sep,
                            "is_default": 1,
                        }
                    ],
                },
                conn=self.conn,
                owner_user_id=1,
            )

            result = DevFolderAppImporter(tmpdir).scan()
            mark_candidate_duplicates(result.candidates, conn=self.conn, owner_user_id=1)

            self.assertEqual(result.candidates[0].status, "EXISTS")
            self.assertFalse(result.candidates[0].selected)
            self.assertEqual(
                normalize_duplicate_value(project + os.sep),
                normalize_duplicate_value(project.upper()),
            )

    def test_desktop_scan_filters_shortcuts_and_handles_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            shortcut = os.path.join(tmpdir, "Broken.lnk")
            normal_file = os.path.join(tmpdir, "notes.txt")
            with open(shortcut, "w", encoding="utf-8") as handle:
                handle.write("")
            with open(normal_file, "w", encoding="utf-8") as handle:
                handle.write("ignore")

            def resolver(path):
                return ShortcutInfo(name="Broken", shortcut_path=path, is_valid=False, error="bad shortcut")

            result = DesktopAppImporter(desktop_paths=[tmpdir], shortcut_resolver=resolver).scan()

            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.candidates[0].name, "Broken")
            self.assertEqual(result.candidates[0].status, "INVALID")
            self.assertFalse(result.candidates[0].selected)

    def test_desktop_url_shortcut_becomes_web_app(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            shortcut = os.path.join(tmpdir, "Fabric.url")
            with open(shortcut, "w", encoding="utf-8") as handle:
                handle.write("[InternetShortcut]\nURL=https://fabric.example/app\n")

            result = DesktopAppImporter(default_area_id="data", desktop_paths=[tmpdir]).scan()

            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.candidates[0].name, "Fabric")
            self.assertEqual(result.candidates[0].kind, "Web App")
            self.assertEqual(result.candidates[0].action_type, "OPEN_URL")
            self.assertEqual(result.candidates[0].target, "https://fabric.example/app")
            self.assertEqual(result.candidates[0].area_id, "data")

    def test_taskbar_scan_lnk_shortcuts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            shortcut = os.path.join(tmpdir, "Code.lnk")
            with open(shortcut, "w", encoding="utf-8") as handle:
                handle.write("")

            def resolver(path):
                return ShortcutInfo(
                    name="Visual Studio Code",
                    shortcut_path=path,
                    target=r"C:\Program Files\Microsoft VS Code\Code.exe",
                    arguments="--reuse-window",
                    working_directory=r"C:\Dev",
                )

            result = TaskbarAppImporter(
                default_area_id="dev",
                taskbar_paths=[tmpdir],
                shortcut_resolver=resolver,
                icon_extractor=lambda path: "/static/app_icons/code.ico",
            ).scan()

            self.assertEqual(len(result.candidates), 1)
            candidate = result.candidates[0]
            self.assertEqual(candidate.name, "Visual Studio Code")
            self.assertEqual(candidate.kind, "Application")
            self.assertEqual(candidate.action_type, "EXECUTABLE")
            self.assertEqual(candidate.arguments, "--reuse-window")
            self.assertEqual(candidate.working_directory, r"C:\Dev")
            self.assertEqual(candidate.icon, "/static/app_icons/code.ico")
            self.assertEqual(candidate.metadata["extracted_icon"], "/static/app_icons/code.ico")

    def test_import_selected_creates_app_area_action_and_provenance(self):
        selected = AppImportCandidate(
            candidate_id="one",
            source_type=SOURCE_DEV_FOLDER,
            name="New Project",
            kind="Development Project",
            area_id="dev",
            target=r"C:\Dev\New Project",
            source_path=r"C:\Dev\New Project",
            selected=True,
            action_name="Open Folder",
            action_type="OPEN_FOLDER",
            metadata={"project_hints": ["Git repository"]},
        )
        unselected = AppImportCandidate(
            candidate_id="two",
            source_type=SOURCE_DESKTOP,
            name="Skip Me",
            kind="Application",
            target=r"C:\Tools\skip.exe",
            source_path=r"C:\Users\me\Desktop\Skip Me.lnk",
            selected=False,
            action_type="EXECUTABLE",
        )
        existing = AppImportCandidate(
            candidate_id="three",
            source_type=SOURCE_DEV_FOLDER,
            name="Dupe Project",
            kind="Development Project",
            target=r"C:\Dev\New Project\\",
            source_path=r"C:\Dev\New Project\\",
            selected=True,
            action_type="OPEN_FOLDER",
        )

        result = import_selected_candidates([selected, unselected, existing], conn=self.conn, owner_user_id=1)

        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.skipped_unselected_count, 1)
        self.assertEqual(result.skipped_existing_count, 1)
        app = apps_model.app_get(result.created_app_ids[0], conn=self.conn, owner_user_id=1)
        self.assertEqual(app["title"], "New Project")
        self.assertEqual(app["area_ids"], ["dev"])
        self.assertEqual(app["actions"][0]["action_type"], "OPEN_FOLDER")
        self.assertEqual(app["import_source"], SOURCE_DEV_FOLDER)
        self.assertEqual(app["import_source_path"], r"C:\Dev\New Project")
        self.assertIn("Git repository", app["import_metadata"])

    def test_static_icon_value_renders_as_image_url(self):
        app_id = apps_model.create_app(
            {
                "title": "Icon App",
                "kind": "Application",
                "icon": "/static/app_icons/icon-app.ico",
                "path": r"C:\Tools\IconApp.exe",
            },
            conn=self.conn,
            owner_user_id=1,
        )

        app = apps_model.app_get(app_id, conn=self.conn, owner_user_id=1)

        self.assertEqual(app["icon_image_url"], "/static/app_icons/icon-app.ico")
        self.assertEqual(app["kind_icon"], "")

    def test_import_executable_extracts_icon_at_import_time(self):
        candidate = AppImportCandidate(
            candidate_id="exe",
            source_type=SOURCE_DESKTOP,
            name="Executable App",
            kind="Application",
            target=r"C:\Tools\ExecutableApp.exe",
            source_path=r"C:\Users\me\Desktop\Executable App.lnk",
            selected=True,
            action_type="EXECUTABLE",
        )

        with patch(
            "modules.apps.importers.service.get_executable_icon_value",
            return_value="/static/app_icons/executable-app.ico",
        ):
            result = import_selected_candidates([candidate], conn=self.conn, owner_user_id=1)

        app = apps_model.app_get(result.created_app_ids[0], conn=self.conn, owner_user_id=1)
        self.assertEqual(app["icon"], "/static/app_icons/executable-app.ico")
        self.assertEqual(app["icon_image_url"], "/static/app_icons/executable-app.ico")
        self.assertIn("executable-app.ico", app["import_metadata"])


if __name__ == "__main__":
    unittest.main()
