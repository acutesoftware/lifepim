import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from utils import markdown_utils


class TestMarkdownUtils(unittest.TestCase):
    def test_lifepim_img_tags_render_through_note_asset_resolver(self):
        html = markdown_utils.render_markdown(
            "Before\n\n[img]animal-melps.jpg[/img]\n\nAfter",
            asset_resolver=lambda name: "/notes/asset/7/" + name,
        )

        self.assertIn('<img src="/notes/asset/7/animal-melps.jpg"', html)
        self.assertNotIn("[img]", html)

    def test_relative_markdown_and_html_images_use_asset_resolver(self):
        html = markdown_utils.render_markdown(
            '![alt](my photo.jpg)\n<img src="Media/diagram.png">',
            asset_resolver=lambda name: "/notes/asset/7/" + name.replace(" ", "%20"),
        )

        self.assertIn('<img src="/notes/asset/7/my%20photo.jpg" alt="alt"', html)
        self.assertIn('src="/notes/asset/7/Media/diagram.png"', html)

    def test_remote_images_are_left_as_remote_images(self):
        html = markdown_utils.render_markdown(
            "![remote](https://example.com/pic.jpg)",
            asset_resolver=lambda name: "/notes/asset/7/" + name,
        )

        self.assertIn("https://example.com/pic.jpg", html)

    def test_fenced_tree_renders_as_code_block(self):
        text = (
            "```text\n"
            "DATA\n"
            "\u251c\u2500\u2500 Overview\n"
            "\u251c\u2500\u2500 Sources\n"
            "\u2502   \u251c\u2500\u2500 Databases\n"
            "\u2502   \u2514\u2500\u2500 File Sources\n"
            "\u2514\u2500\u2500 Tasks\n"
            "```"
        )

        rendered = markdown_utils.render_markdown(text)

        self.assertIn("<pre><code", rendered)
        self.assertIn("DATA\n\u251c\u2500\u2500 Overview", rendered)
        self.assertNotIn("<p><code>", rendered)

    def test_fallback_fenced_tree_renders_as_code_block(self):
        previous_md_lib = markdown_utils.md_lib
        try:
            markdown_utils.md_lib = None
            rendered = markdown_utils.render_markdown("```\nDATA\n\u2514\u2500\u2500 Tasks\n```")
        finally:
            markdown_utils.md_lib = previous_md_lib

        self.assertEqual(rendered, "<pre><code>DATA\n\u2514\u2500\u2500 Tasks</code></pre>")

    def test_safe_markdown_mode_escapes_raw_html(self):
        rendered = markdown_utils.render_markdown(
            '<div class="loose">Loose **bold** text',
            allow_html=False,
        )

        self.assertNotIn("<div", rendered)
        self.assertIn("&lt;div", rendered)
        self.assertIn("<strong>bold</strong>", rendered)


if __name__ == "__main__":
    unittest.main()
