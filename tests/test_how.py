import os
import sqlite3
import tempfile
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from modules.how.parser import parse_markdown
from modules.how.schema import ensure_how_schema, utc_now
from modules.how.service import apply_markdown, build_preview_model, build_tree, get_howto_detail, list_catalog
from modules.how.service import create_child_stub, convert_howto_to_note, create_howto_from_markdown


COFFEE_MD = """---
key: make-duncans-coffee
title: Make Duncan's Coffee
status: verified
tags:
- coffee
- morning
estimated_minutes: 5
difficulty: easy
last_verified: 2026-07-14
---

# Make Duncan's Coffee

## Summary

Make my normal morning coffee.

## Outcome

A 250 ml coffee with milk.

## Ingredients

- Coffee beans | 18 | g
- Water | 250 | ml
- Milk | 20 | ml | optional

## Equipment

- Coffee grinder
- Coffee machine
- Duncan's blue mug

## Method

1. Fill the coffee machine with fresh water.
   Expected: The water tank contains at least 300 ml.
   Warning: Do not exceed the maximum fill line.

2. Grind 18 grams of coffee beans
   using setting 12.
   Expected: The coffee is medium-fine.

3. Put the coffee into the portafilter.

## Validation

- The coffee should be hot.

## Notes

Use Vittoria beans if needed.
"""


class TestHowParser(unittest.TestCase):
    def test_seed_fixtures_parse(self):
        fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", "how")
        fixture_names = [name for name in os.listdir(fixture_dir) if name.endswith(".md")]
        self.assertGreaterEqual(len(fixture_names), 8)
        for name in fixture_names:
            with open(os.path.join(fixture_dir, name), "r", encoding="utf-8") as handle:
                parsed = parse_markdown(handle.read())
            self.assertTrue(parsed.title, name)
            self.assertFalse([d for d in parsed.diagnostics if d.severity == "ERROR"], name)

    def test_valid_yaml_aliases_multiline_and_metadata(self):
        parsed = parse_markdown(COFFEE_MD)
        self.assertEqual(parsed.metadata["key"], "make-duncans-coffee")
        self.assertEqual(parsed.title, "Make Duncan's Coffee")
        self.assertEqual(len(parsed.parts), 3)
        self.assertEqual(parsed.parts[0].quantity, 18.0)
        self.assertEqual(parsed.parts[0].unit, "g")
        self.assertTrue(parsed.parts[2].optional)
        self.assertEqual(len(parsed.tools), 3)
        self.assertEqual(len(parsed.steps), 3)
        self.assertIn("using setting 12", parsed.steps[1].instruction)
        self.assertEqual(parsed.steps[0].expected_result, "The water tank contains at least 300 ml.")
        self.assertEqual(parsed.steps[0].warning, "Do not exceed the maximum fill line.")

    def test_malformed_yaml_and_title_fallback(self):
        parsed = parse_markdown("---\nbad yaml\n---\n\n# Fallback Title\n\n## Steps\n\n1. Do it.")
        self.assertEqual(parsed.title, "Fallback Title")
        self.assertTrue(any(d.severity == "ERROR" for d in parsed.diagnostics))

    def test_steps_only_and_unknown_sections(self):
        parsed = parse_markdown("# Copy a File\n\n## Steps\n\n1. Open File Explorer.\n\n## Random\n\nIgnored")
        self.assertEqual(parsed.title, "Copy a File")
        self.assertEqual(len(parsed.parts), 0)
        self.assertEqual(len(parsed.tools), 0)
        self.assertEqual(len(parsed.steps), 1)
        self.assertTrue(any(d.code == "SECTION_UNKNOWN" for d in parsed.diagnostics))

    def test_explicit_step_and_howto_references(self):
        md = """---
title: Renovate Bathroom
---

# Renovate Bathroom

## Outcome
Done.

## Steps

1. [[step:buy-materials|Buy materials]]
2. Replace vanity.
   Howto: replace-bathroom-vanity
   Mode: linked
3. [[howto:retile-bathroom-walls|Retile walls]]
"""
        parsed = parse_markdown(md)
        self.assertEqual(parsed.steps[0].step_key, "buy-materials")
        self.assertEqual(parsed.steps[1].child_howto_ref, "replace-bathroom-vanity")
        self.assertEqual(parsed.steps[2].step_type, "howto")
        self.assertEqual(parsed.steps[2].child_howto_ref, "retile-bathroom-walls")


class TestHowDatabaseAndTree(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        ensure_how_schema(self.conn)
        self.conn.execute(
            "CREATE TABLE dim_folder (folder_id INTEGER PRIMARY KEY, folder_path TEXT UNIQUE, last_seen_at TEXT, is_active INTEGER)"
        )
        self.conn.execute(
            "CREATE TABLE lp_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT, path TEXT, folder_id INTEGER, "
            "size TEXT, date_modified TEXT, project TEXT, user_name TEXT, rec_extract_date TEXT)"
        )
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()
        self.conn.close()

    def _path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_preview_does_not_write_and_apply_creates_catalogs(self):
        preview = build_preview_model(COFFEE_MD, self.conn)
        self.assertEqual(preview["status"], "OK")
        self.assertEqual(self.conn.execute("SELECT COUNT(1) FROM lp_howto").fetchone()[0], 0)
        howto_id = apply_markdown(COFFEE_MD, source_filepath=self._path("coffee.md"), conn=self.conn)
        detail = get_howto_detail(howto_id, conn=self.conn)
        self.assertEqual(detail["howto"]["title"], "Make Duncan's Coffee")
        self.assertEqual(len(detail["parts"]), 3)
        self.assertEqual(len(detail["tools"]), 3)
        self.assertEqual(len(detail["steps"]), 3)

    def test_blueprint_name_supplies_title_without_yaml_title_or_h1(self):
        md = """---
status: draft
---

## Summary

Short outline.

## Outcome

Done.

## Steps

1. Do the thing.
"""
        preview = build_preview_model(md, self.conn, title="New Blueprint")
        self.assertEqual(preview["status"], "OK")
        self.assertEqual(preview["parsed"]["title"], "New Blueprint")
        self.assertEqual(preview["parsed"]["metadata"]["key"], "new-blueprint")
        howto_id = apply_markdown(
            md,
            source_filepath=self._path("New Blueprint.md"),
            conn=self.conn,
            title="New Blueprint",
            blueprint_name="New Blueprint",
        )
        detail = get_howto_detail(howto_id, conn=self.conn)
        self.assertEqual(detail["howto"]["title"], "New Blueprint")
        self.assertEqual(detail["howto"]["howto_key"], "new-blueprint")

    def test_independent_catalog_and_step_reuse(self):
        now = utc_now()
        cur = self.conn.execute(
            "INSERT INTO lp_howto_steps (step_key, instruction, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("turn-off-water", "Turn off the water supply.", now, now),
        )
        step_id = cur.lastrowid
        md1 = """---
key: replace-vanity
title: Replace Vanity
---

# Replace Vanity
## Outcome
Done.
## Steps
1. [[step:turn-off-water|Turn off the water supply.]]
"""
        md2 = md1.replace("replace-vanity", "fix-tap").replace("Replace Vanity", "Fix Tap")
        apply_markdown(md1, source_filepath=self._path("vanity.md"), conn=self.conn)
        apply_markdown(md2, source_filepath=self._path("tap.md"), conn=self.conn)
        rows = self.conn.execute("SELECT howto_id, step_order FROM lp_howto_step_links WHERE step_id = ?", (step_id,)).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(list_catalog("steps", conn=self.conn)[0]["used_by_count"], 2)

    def test_part_quantities_are_link_specific_and_reparse_replaces_links(self):
        md1 = """---
key: coffee-one
title: Coffee One
---
# Coffee One
## Outcome
Done.
## Parts
- Water | 250 | ml
## Steps
1. Do it.
"""
        md2 = md1.replace("coffee-one", "coffee-two").replace("Coffee One", "Coffee Two").replace("250", "500")
        id1 = apply_markdown(md1, source_filepath=self._path("one.md"), conn=self.conn)
        id2 = apply_markdown(md2, source_filepath=self._path("two.md"), conn=self.conn)
        q1 = self.conn.execute("SELECT quantity FROM lp_howto_part_links WHERE howto_id = ?", (id1,)).fetchone()[0]
        q2 = self.conn.execute("SELECT quantity FROM lp_howto_part_links WHERE howto_id = ?", (id2,)).fetchone()[0]
        self.assertEqual(q1, 250.0)
        self.assertEqual(q2, 500.0)
        updated = md1.replace("- Water | 250 | ml", "- Water | 250 | ml\n- Milk | 20 | ml")
        apply_markdown(updated, source_filepath=self._path("one.md"), conn=self.conn)
        self.assertEqual(self.conn.execute("SELECT COUNT(1) FROM lp_howto_part_links WHERE howto_id = ?", (id1,)).fetchone()[0], 2)
        self.assertGreaterEqual(self.conn.execute("SELECT COUNT(1) FROM lp_howto_parts").fetchone()[0], 2)

    def test_unresolved_child_and_nested_tree_cycle_marker(self):
        child = """---
key: replace-bathroom-vanity
title: Replace Bathroom Vanity
---
# Replace Bathroom Vanity
## Outcome
Done.
## Steps
1. Confirm dimensions.
"""
        parent = """---
key: renovate-bathroom
title: Renovate Bathroom
---
# Renovate Bathroom
## Outcome
Done.
## Steps
1. Buy materials.
2. Replace vanity.
   Howto: replace-bathroom-vanity
3. Retile walls.
   Howto: retile-bathroom-walls
"""
        apply_markdown(child, source_filepath=self._path("child.md"), conn=self.conn)
        parent_id = apply_markdown(parent, source_filepath=self._path("parent.md"), conn=self.conn)
        tree = build_tree(parent_id, conn=self.conn)
        self.assertEqual(tree["steps"][1]["child"]["howto"]["howto_key"], "replace-bathroom-vanity")
        self.assertEqual(tree["steps"][2]["unresolved_child"], "retile-bathroom-walls")

        a = parent.replace("replace-bathroom-vanity", "cycle-b").replace("retile-bathroom-walls", "missing-x")
        b = """---
key: cycle-b
title: Cycle B
---
# Cycle B
## Outcome
Done.
## Steps
1. Back to A.
   Howto: renovate-bathroom
"""
        apply_markdown(b, source_filepath=self._path("b.md"), conn=self.conn)
        parent_id = apply_markdown(a, source_filepath=self._path("parent.md"), conn=self.conn)
        cycle_tree = build_tree(parent_id, conn=self.conn)
        self.assertTrue(cycle_tree["steps"][1]["child"]["steps"][0]["child"]["cycle"])

    def test_create_child_stub_from_missing_reference(self):
        parent = """---
key: parent-howto
title: Parent Howto
---
# Parent Howto
## Outcome
Done.
## Steps
1. Missing child.
   Howto: child-outline
"""
        parent_id = apply_markdown(parent, source_filepath=self._path("parent.md"), conn=self.conn)
        child_id = create_child_stub(parent_id, "child-outline", conn=self.conn)
        child = get_howto_detail(child_id, conn=self.conn)["howto"]
        self.assertEqual(child["howto_key"], "child-outline")
        self.assertEqual(child["status"], "outline")

    def test_convert_howto_to_note_preserves_markdown_and_removes_howto(self):
        markdown = """---
status: draft
---

## Summary

Original HOW markdown.

## Steps

1. Keep this content.
"""
        howto_id = apply_markdown(
            markdown,
            source_filepath=self._path("Original How.md"),
            conn=self.conn,
            title="Original How",
            blueprint_name="Original How",
        )
        note_id = convert_howto_to_note(howto_id, conn=self.conn)
        self.assertIsNone(self.conn.execute("SELECT 1 FROM lp_howto WHERE howto_id = ?", (howto_id,)).fetchone())
        note = self.conn.execute("SELECT * FROM lp_notes WHERE id = ?", (note_id,)).fetchone()
        self.assertIsNotNone(note)
        note_path = os.path.join(note["path"], note["file_name"])
        with open(note_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), markdown)

    def test_create_howto_from_note_markdown_is_not_parsed(self):
        markdown = "# Existing Note\n\nFree-form note content."
        howto_id = create_howto_from_markdown(
            "Existing Note",
            markdown,
            project_id="proj/dev",
            source_filepath=self._path("Existing Note.md"),
            conn=self.conn,
        )
        row = self.conn.execute("SELECT * FROM lp_howto WHERE howto_id = ?", (howto_id,)).fetchone()
        self.assertEqual(row["title"], "Existing Note")
        self.assertEqual(row["project_id"], "proj/dev")
        self.assertEqual(row["markdown_full_content"], markdown)
        self.assertEqual(row["parse_status"], "NOT_PARSED")
        self.assertEqual(self.conn.execute("SELECT COUNT(1) FROM lp_howto_step_links").fetchone()[0], 0)

    def test_ambiguous_plain_name_blocks_save(self):
        now = utc_now()
        self.conn.execute(
            "INSERT INTO lp_howto_tools_needed (tool_name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Hammer", now, now),
        )
        self.conn.execute(
            "INSERT INTO lp_howto_tools_needed (tool_name, created_at, updated_at) VALUES (?, ?, ?)",
            ("Hammer", now, now),
        )
        md = """---
key: use-hammer
title: Use Hammer
---
# Use Hammer
## Outcome
Done.
## Tools
- Hammer
## Steps
1. Use it.
"""
        preview = build_preview_model(md, self.conn)
        self.assertEqual(preview["parsed"]["tools"][0]["resolution"], "ambiguous")
        with self.assertRaises(ValueError):
            apply_markdown(md, source_filepath=self._path("hammer.md"), conn=self.conn)


if __name__ == "__main__":
    unittest.main()
