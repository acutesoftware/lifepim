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

    def test_obsidian_wiki_link_renders_resolved_link(self):
        rendered = markdown_utils.render_markdown(
            "See [[Target Note]].",
            wiki_link_resolver=lambda title: {
                "status": "resolved",
                "url": "/notes/view/12",
                "title": title,
            },
        )

        self.assertIn('<a class="wiki-link wiki-link-resolved" href="/notes/view/12"', rendered)
        self.assertIn(">Target Note</a>", rendered)
        self.assertNotIn("[[Target Note]]", rendered)

    def test_obsidian_wiki_link_marks_ambiguous_and_broken_links(self):
        def resolver(title):
            if title == "Duplicate":
                return {"status": "ambiguous", "count": 2}
            return {"status": "broken"}

        rendered = markdown_utils.render_markdown(
            "[[Duplicate]] and [[Missing]]",
            wiki_link_resolver=resolver,
        )

        self.assertIn('class="wiki-link wiki-link-ambiguous"', rendered)
        self.assertIn("Ambiguous link: 2 notes match", rendered)
        self.assertIn('class="wiki-link wiki-link-broken"', rendered)
        self.assertIn("Broken link: no matching note", rendered)

    def test_obsidian_image_is_not_treated_as_wiki_link(self):
        rendered = markdown_utils.render_markdown(
            "![[photo.jpg]] and [[Target]]",
            asset_resolver=lambda name: "/notes/asset/7/" + name,
            wiki_link_resolver=lambda title: {
                "status": "resolved",
                "url": "/notes/view/12",
                "title": title,
            },
        )

        self.assertIn('<img src="/notes/asset/7/photo.jpg"', rendered)
        self.assertIn('href="/notes/view/12"', rendered)

    def test_obsidian_wiki_link_passes_target_note_id_to_resolver(self):
        seen = {}

        def resolver(title, target_note_id=None):
            seen["title"] = title
            seen["target_note_id"] = target_note_id
            return {
                "status": "resolved",
                "url": f"/notes/view/{target_note_id}",
                "title": title,
            }

        rendered = markdown_utils.render_markdown(
            "[[Display Title|note:42]]",
            wiki_link_resolver=resolver,
        )

        self.assertEqual(seen, {"title": "Display Title", "target_note_id": "42"})
        self.assertIn('href="/notes/view/42"', rendered)

    def test_obsidian_wiki_link_uses_alias_as_label(self):
        rendered = markdown_utils.render_markdown(
            "[[folder/Target Note|Readable Label]]",
            wiki_link_resolver=lambda title: {
                "status": "resolved",
                "url": "/notes/view/12",
                "title": title,
            },
        )

        self.assertIn('href="/notes/view/12"', rendered)
        self.assertIn(">Readable Label</a>", rendered)
        self.assertNotIn(">folder/Target Note</a>", rendered)

    def test_obsidian_wiki_link_label_keeps_literal_asterisks(self):
        rendered = markdown_utils.render_markdown(
            "[[*HOWTO* UE4 Animation|note:1512]]",
            wiki_link_resolver=lambda title, target_note_id=None: {
                "status": "resolved",
                "url": f"/notes/view/{target_note_id}",
                "title": title,
            },
        )

        self.assertIn('href="/notes/view/1512"', rendered)
        self.assertIn("&#42;HOWTO&#42; UE4 Animation</a>", rendered)
        self.assertNotIn("<em>HOWTO</em>", rendered)

    def test_relative_markdown_note_link_uses_link_resolver(self):
        rendered = markdown_utils.render_markdown(
            "[_HOWTO__SQL](42-4-misc/_HOWTO__SQL.md)",
            link_resolver=lambda target: {
                "status": "resolved",
                "url": "/notes/view/99",
                "title": target,
            },
        )

        self.assertIn('class="note-link note-link-resolved"', rendered)
        self.assertIn('href="/notes/view/99"', rendered)
        self.assertIn(">_HOWTO__SQL</a>", rendered)
        self.assertNotIn('href="42-4-misc/_HOWTO__SQL.md"', rendered)

    def test_external_and_non_markdown_links_are_not_resolved_as_notes(self):
        seen = []

        rendered = markdown_utils.render_markdown(
            "[Web](https://example.com) [PDF](files/doc.pdf)",
            link_resolver=lambda target: seen.append(target) or {"status": "broken"},
        )

        self.assertEqual(seen, [])
        self.assertIn('href="https://example.com"', rendered)
        self.assertIn('href="files/doc.pdf"', rendered)
        self.assertNotIn("note-link-broken", rendered)


if __name__ == "__main__":
    unittest.main()
