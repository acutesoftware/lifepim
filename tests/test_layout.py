import os
import unittest

from flask import Flask, render_template


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")


class TestLayoutNavigation(unittest.TestCase):
    def _app(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(root_folder, "templates"),
            static_folder=os.path.join(root_folder, "static"),
        )

        @app.route("/site.webmanifest")
        def site_webmanifest():
            return {}

        @app.route("/search")
        def search_route():
            return ""

        return app

    def test_overview_area_links_stay_on_root_route(self):
        app = self._app()
        with app.test_request_context("/?area=make/build"):
            html = render_template(
                "layout.html",
                active_tab="home",
                tabs=[
                    {"id": "home", "label": "Overview", "icon": "", "desc": "Overview Dashboard"},
                    {"id": "notes", "label": "Notes", "icon": "", "desc": "Notes"},
                ],
                side_tabs=[
                    {"id": "All", "label": "All Areas", "icon": ""},
                    {"id": "make/build", "label": "Build", "icon": ""},
                ],
                content_title="Overview",
                content_html="",
            )

        self.assertIn('href="/?area=make/build"', html)
        self.assertIn('value="/?area=make/build"', html)
        self.assertNotIn("/home?area=make/build", html)


if __name__ == "__main__":
    unittest.main()
