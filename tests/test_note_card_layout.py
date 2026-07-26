import os
import re
import unittest


ROOT = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + "..")
CSS_PATH = os.path.join(ROOT, "src", "static", "lifepim.css")


def _css_rule(selector):
    with open(CSS_PATH, encoding="utf-8") as handle:
        css = handle.read()
    match = re.search(re.escape(selector) + r"\s*\{(?P<body>.*?)\}", css, re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group("body")).strip()


class TestNoteCardLayout(unittest.TestCase):
    def test_note_card_list_uses_vertical_column_flow(self):
        rule = _css_rule(".note-card-grid")

        self.assertIn("display: block;", rule)
        self.assertIn("column-width: var(--note-card-width, 50ch);", rule)
        self.assertIn("column-gap: 8px;", rule)

    def test_note_cards_resize_to_preview_content(self):
        rule = _css_rule(".note-card")

        self.assertIn("display: inline-block;", rule)
        self.assertIn("width: 100%;", rule)
        self.assertIn("overflow: visible;", rule)
        self.assertIn("break-inside: avoid-column;", rule)

    def test_freeze_headers_keep_card_columns_in_document_flow(self):
        content_rule = _css_rule("body.freeze-headers .content:has(.note-card-page)")
        grid_rule = _css_rule("body.freeze-headers .note-card-page .note-card-grid")

        self.assertIn("display: block;", content_rule)
        self.assertIn("overflow: auto;", content_rule)
        self.assertIn("overflow: visible;", grid_rule)
        self.assertNotIn("flex:", grid_rule)

    def test_note_card_preview_content_is_width_constrained(self):
        self.assertIn("max-width: 100%;", _css_rule(".note-card-raw"))
        self.assertIn("max-width: 100%;", _css_rule(".note-card-markdown"))


if __name__ == "__main__":
    unittest.main()
