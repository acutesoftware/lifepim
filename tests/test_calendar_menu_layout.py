import os
import unittest
import re

from jinja2 import Environment, FileSystemLoader


ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + "..")
CSS_PATH = os.path.join(ROOT, "src", "static", "lifepim.css")
MENU_PATH = os.path.join(ROOT, "src", "templates", "widgets", "wid_calendar_import_menu.html")
SOURCE_MENU_PATH = os.path.join(ROOT, "src", "templates", "widgets", "wid_calendar_source_box.html")


class TestCalendarMenuLayout(unittest.TestCase):
    def test_wrapped_more_menu_can_flip_away_from_left_edge(self):
        with open(CSS_PATH, encoding="utf-8") as handle:
            css = handle.read()
        with open(MENU_PATH, encoding="utf-8") as handle:
            template = handle.read()

        self.assertIn(".calendar-import-menu-items.calendar-import-menu-items-align-start", css)
        self.assertIn("right: auto;", css)
        self.assertIn("left: 0;", css)
        self.assertIn('menu.addEventListener("toggle"', template)
        self.assertIn('items.classList.toggle("calendar-import-menu-items-align-start"', template)
        self.assertIn('menu.closest(".content")', template)

    def test_source_groups_drive_one_set_of_named_source_inputs(self):
        with open(SOURCE_MENU_PATH, encoding="utf-8") as handle:
            template = handle.read()

        self.assertIn("data-calendar-source-group", template)
        self.assertIn("data-calendar-source-custom-open", template)
        self.assertIn('name="source"', template)
        self.assertNotIn('name="source_group"', template)
        self.assertIn("groupInput.indeterminate", template)
        self.assertIn("sourceInput.checked = checked", template)

    def test_overlapping_groups_render_each_source_input_once(self):
        environment = Environment(
            loader=FileSystemLoader(os.path.join(ROOT, "src", "templates")),
            autoescape=True,
        )
        template = environment.get_template("widgets/wid_calendar_source_box.html")
        rows = [
            {"source_key": key, "source_name": key.replace("_", " ").title()}
            for key in (
                "manual",
                "recurring",
                "birthdays",
                "tasks",
                "audio",
                "media",
                "files",
                "usage",
                "holidays_au",
                "holidays_sa",
                "external_events",
            )
        ]
        rendered = template.render(
            source_action_url="/calendar",
            source_hidden_fields=[],
            day_sources={
                "rows": rows,
                "selected": {"manual", "external_events"},
                "groups": [
                    {"label": "Events", "source_keys": ("manual", "recurring"), "state": "mixed"},
                    {"label": "External", "source_keys": ("manual", "external_events"), "state": "all"},
                ],
            },
        )

        submitted_sources = re.findall(r'<input\s+[^>]*name="source"[^>]*value="([^"]+)"', rendered)
        self.assertEqual(len(submitted_sources), 11)
        self.assertEqual(len(submitted_sources), len(set(submitted_sources)))


if __name__ == "__main__":
    unittest.main()
