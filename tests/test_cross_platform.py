import os
import sys
import tempfile
import unittest
from unittest.mock import patch


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import areas, user_paths
from modules.admin import routes as admin_routes
from modules.apps import schema as apps_model


class TestCrossPlatformPaths(unittest.TestCase):
    def test_normalize_path_preserves_posix_and_windows_styles(self):
        self.assertEqual(
            user_paths.normalize_path("/home/alice/LifePIM/DATA/notes/"),
            "/home/alice/LifePIM/DATA/notes",
        )
        self.assertEqual(
            user_paths.normalize_path(r"n:\duncan\LifePIM_Data\DATA\notes\\"),
            r"N:\duncan\LifePIM_Data\DATA\notes",
        )

    def test_paths_from_root_uses_root_separator_style(self):
        self.assertEqual(
            user_paths.paths_from_root("/home/alice/LifePIM"),
            {
                "file_root_path": "/home/alice/LifePIM",
                "notes_root_path": "/home/alice/LifePIM/notes",
                "areas_root_path": "/home/alice/LifePIM/areas",
                "lists_root_path": "/home/alice/LifePIM/lists",
            },
        )
        self.assertEqual(
            user_paths.paths_from_root(r"N:\duncan\LifePIM_Data\DATA"),
            {
                "file_root_path": r"N:\duncan\LifePIM_Data\DATA",
                "notes_root_path": r"N:\duncan\LifePIM_Data\DATA\notes",
                "areas_root_path": r"N:\duncan\LifePIM_Data\DATA\areas",
                "lists_root_path": r"N:\duncan\LifePIM_Data\DATA\lists",
            },
        )

    def test_default_paths_do_not_mix_separators_for_configured_windows_root(self):
        with patch.dict(os.environ, {"LIFEPIM_LAN_USER_ROOT_BASE": r"N:\duncan\LifePIM_Data\DATA\lan_users"}):
            self.assertEqual(
                user_paths.default_paths_for_username("alice")["notes_root_path"],
                r"N:\duncan\LifePIM_Data\DATA\lan_users\alice\notes",
            )

    def test_notes_root_derivation_supports_posix_and_windows_paths(self):
        self.assertEqual(
            user_paths._notes_root_from_path("/srv/lifepim/DATA/notes/10-Pers"),
            "/srv/lifepim/DATA/notes",
        )
        self.assertEqual(
            user_paths._notes_root_from_path(r"N:\duncan\LifePIM_Data\DATA\notes\10-Pers"),
            r"N:\duncan\LifePIM_Data\DATA\notes",
        )

    def test_absolute_path_validation_accepts_foreign_platform_paths_without_rewriting(self):
        self.assertEqual(areas.normalize_path_prefix("/srv/lifepim/DATA/notes/"), "/srv/lifepim/DATA/notes")
        self.assertEqual(areas.normalize_path_prefix(r"C:\Users\alice\LifePIM"), r"C:\Users\alice\LifePIM")
        with self.assertRaisesRegex(ValueError, "absolute path"):
            areas.normalize_path_prefix("relative/path")

    def test_username_placeholder_replacement_preserves_separator_style(self):
        self.assertEqual(
            admin_routes._resolve_username_segment("/srv/lan_users/username/notes", "alice"),
            "/srv/lan_users/alice/notes",
        )
        self.assertEqual(
            admin_routes._resolve_username_segment(r"N:\lan_users\username\notes", "alice"),
            r"N:\lan_users\alice\notes",
        )

    def test_open_file_action_uses_cross_platform_default_opener(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            note_path = os.path.join(tmpdir, "note.txt")
            with open(note_path, "w", encoding="utf-8") as handle:
                handle.write("ok")
            with patch("modules.apps.schema._open_with_system_default") as opener:
                result = apps_model._execute_action({"action_type": "OPEN_FILE", "command": note_path})

        self.assertIsNone(result)
        opener.assert_called_once_with(note_path)


if __name__ == "__main__":
    unittest.main()
