import csv
import importlib.util
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


repo_root = Path(__file__).resolve().parent.parent
script_path = repo_root / "scripts" / "prod" / "util_notes_fix_obsidian_links.py"
spec = importlib.util.spec_from_file_location("util_notes_fix_obsidian_links", script_path)
fixer = importlib.util.module_from_spec(spec)
sys.modules["util_notes_fix_obsidian_links"] = fixer
spec.loader.exec_module(fixer)


class TestUtilNotesFixObsidianLinks(unittest.TestCase):
    def test_dry_run_reports_unique_conversion_and_preserves_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "42-4-misc" / "_HOWTO__SQL.md"
            source = root / "Diary" / "Today.md"
            target.parent.mkdir()
            source.parent.mkdir()
            target.write_text("# SQL\n", encoding="utf-8")
            source.write_text("See [[_HOWTO__SQL|SQL Notes]]\n", encoding="utf-8")

            summary = self.run_silent(root, dry_run=True)

            self.assertEqual(summary.files_scanned, 2)
            self.assertEqual(summary.converted, 1)
            self.assertEqual(summary.files_modified, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), "See [[_HOWTO__SQL|SQL Notes]]\n")

            rows = self.read_report(root)
            self.assertEqual(rows[0]["status"], "converted")
            self.assertEqual(rows[0]["original_link"], "[[_HOWTO__SQL|SQL Notes]]")
            self.assertEqual(rows[0]["resolved_path"], "../42-4-misc/_HOWTO__SQL.md")

    def test_real_run_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "howto" / "SQL.md"
            source = root / "diary" / "today.md"
            target.parent.mkdir()
            source.parent.mkdir()
            target.write_text("# SQL\n", encoding="utf-8")
            source.write_text("See [[SQL]].\n", encoding="utf-8")

            first = self.run_silent(root, dry_run=False)
            self.assertEqual(first.converted, 1)
            self.assertEqual(first.files_modified, 1)
            self.assertEqual(source.read_text(encoding="utf-8"), "See [[../howto/SQL.md]].\n")

            second = self.run_silent(root, dry_run=False)
            self.assertEqual(second.converted, 0)
            self.assertEqual(second.already_explicit, 1)
            self.assertEqual(second.files_modified, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), "See [[../howto/SQL.md]].\n")

    def test_ambiguous_and_missing_links_are_reported_but_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Projects").mkdir()
            (root / "HowTo").mkdir()
            (root / "notes").mkdir()
            (root / "Projects" / "SQL.md").write_text("# SQL\n", encoding="utf-8")
            (root / "HowTo" / "SQL.md").write_text("# SQL\n", encoding="utf-8")
            source = root / "notes" / "test.md"
            original = "[[SQL]] and [[Missing]]\n"
            source.write_text(original, encoding="utf-8")

            summary = self.run_silent(root, dry_run=False)

            self.assertEqual(summary.ambiguous, 1)
            self.assertEqual(summary.missing, 1)
            self.assertEqual(summary.converted, 0)
            self.assertEqual(summary.files_modified, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), original)

            statuses = {row["original_link"]: row["status"] for row in self.read_report(root)}
            self.assertEqual(statuses["[[SQL]]"], "ambiguous")
            self.assertEqual(statuses["[[Missing]]"], "missing")

    def test_folder_link_is_resolved_to_canonical_relative_markdown_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "howto" / "SQL.md"
            source = root / "diary" / "today.md"
            target.parent.mkdir()
            source.parent.mkdir()
            target.write_text("# SQL\n", encoding="utf-8")
            source.write_text("See [[howto/SQL]]\n", encoding="utf-8")

            summary = self.run_silent(root, dry_run=False)

            self.assertEqual(summary.converted, 1)
            self.assertEqual(source.read_text(encoding="utf-8"), "See [[../howto/SQL.md]]\n")

    def test_explicit_markdown_link_is_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "howto" / "SQL.md"
            source = root / "diary" / "today.md"
            target.parent.mkdir()
            source.parent.mkdir()
            target.write_text("# SQL\n", encoding="utf-8")
            source.write_text("See [[../howto/SQL.md|SQL]]\n", encoding="utf-8")

            summary = self.run_silent(root, dry_run=False)

            self.assertEqual(summary.already_explicit, 1)
            self.assertEqual(summary.converted, 0)
            self.assertEqual(summary.files_modified, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), "See [[../howto/SQL.md|SQL]]\n")

    def test_parent_lookup_finds_unique_notes_outside_processing_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "notes"
            process_root = vault / "40-Dev" / "44-UE4"
            target = vault / "50-Fun" / "51-Games" / "Game_Development_-_3D_Gaming.md"
            source = process_root / "44-1-UE4 How TO" / "UE4_-_Enemys_and_AI.md"
            target.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            target.write_text("# Games\n", encoding="utf-8")
            source.write_text("[[Game_Development_-_3D_Gaming]]\n", encoding="utf-8")

            summary = self.run_silent(process_root, dry_run=False, lookup_parent_levels=2)

            self.assertEqual(summary.files_scanned, 1)
            self.assertEqual(summary.converted, 1)
            self.assertEqual(summary.files_modified, 1)
            self.assertEqual(
                source.read_text(encoding="utf-8"),
                "[[../../../50-Fun/51-Games/Game_Development_-_3D_Gaming.md]]\n",
            )

    def test_simple_link_prefers_same_folder_before_global_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            process_root = vault / "DATA" / "notes"
            health = process_root / "10-Pers" / "12-Health"
            backup = vault / "BACKUP" / "old_notes"
            source = health / "Alex_-_Diabetes.md"
            target = health / "_INDEX__Health.md"
            duplicate = backup / "_INDEX__Health.md"
            health.mkdir(parents=True)
            backup.mkdir(parents=True)
            source.write_text("[[_INDEX__Health]]\n", encoding="utf-8")
            target.write_text("# Health\n", encoding="utf-8")
            duplicate.write_text("# Old health\n", encoding="utf-8")

            summary = self.run_silent(process_root, dry_run=False, lookup_parent_levels=2)

            self.assertEqual(summary.converted, 1)
            self.assertEqual(summary.ambiguous, 0)
            self.assertEqual(source.read_text(encoding="utf-8"), "[[_INDEX__Health.md]]\n")

    def test_default_report_and_log_are_written_to_scanned_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.md").write_text("No links\n", encoding="utf-8")

            with redirect_stdout(StringIO()):
                summary = fixer.run(
                    root_folder=root,
                    dry_run=True,
                    backup_files=False,
                    verbose=False,
                    case_sensitive=False,
                    recursive=True,
                    lookup_parent_levels=0,
                )

            self.assertEqual(summary.files_scanned, 1)
            self.assertTrue((root / "util_notes_fix_obsidian_links.csv").exists())
            self.assertTrue((root / "util_notes_fix_obsidian_links.log").exists())

    def run_silent(self, root, dry_run, lookup_parent_levels=0):
        with redirect_stdout(StringIO()):
            return fixer.run(
                root_folder=root,
                dry_run=dry_run,
                backup_files=False,
                verbose=False,
                case_sensitive=False,
                recursive=True,
                lookup_parent_levels=lookup_parent_levels,
                log_file=root / "util_notes_fix_obsidian_links.log",
                csv_report_file=root / "util_notes_fix_obsidian_links.csv",
            )

    def read_report(self, root):
        with (root / "util_notes_fix_obsidian_links.csv").open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
