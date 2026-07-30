import os
import unittest

from flask import Blueprint, Flask, render_template


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

        projects_bp = Blueprint("projects", __name__)

        @projects_bp.route("/")
        def list_projects_route():
            return ""

        @projects_bp.route("/add")
        def add_project_route():
            return ""

        app.register_blueprint(projects_bp, url_prefix="/projects")

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

    def test_projects_heading_links_to_filtered_project_list(self):
        app = self._app()
        with app.test_request_context("/notes/cards?area=make/build"):
            html = render_template(
                "layout.html",
                active_tab="notes",
                tabs=[
                    {"id": "home", "label": "Overview", "icon": "", "desc": "Overview Dashboard"},
                    {"id": "notes", "label": "Notes", "icon": "", "desc": "Notes"},
                ],
                side_tabs=[
                    {"id": "All", "label": "All Areas", "icon": ""},
                    {"id": "make/build", "label": "Build", "icon": ""},
                ],
                sidebar_projects=[],
                active_project_id=None,
                sidebar_area_label="Build",
                content_title="Notes",
                content_html="",
            )

        self.assertIn('href="/projects/?area=make/build"', html)
        self.assertIn("Projects (Build)", html)
        self.assertIn('id="sidebarWidthResizer"', html)
        self.assertIn('id="sidebarProjectsResizer"', html)


if __name__ == "__main__":
    unittest.main()
