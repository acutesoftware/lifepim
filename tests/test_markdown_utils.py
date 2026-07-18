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


if __name__ == "__main__":
    unittest.main()
