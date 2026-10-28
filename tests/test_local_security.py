import os
import sqlite3
import sys
import unittest

from flask import Blueprint, Flask
from flask_wtf.csrf import generate_csrf


SRC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from common import data
from core.security import configure_security
from run_waitress import validate_loopback_host
from utils.markdown_utils import render_markdown


class TestLocalSecurity(unittest.TestCase):
    def setUp(self):
        self.old_conn = data.conn
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        data.conn = self.conn
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)

        @self.app.route("/private")
        def private():
            return "private"

        @self.app.route("/mutate", methods=["POST"])
        def mutate():
            return "changed"

        for name, path in (
            ("public", "/public-test"),
            ("pocket_api", "/pocket-test"),
            ("logger_api", "/logger-test"),
        ):
            blueprint = Blueprint(name, name)
            blueprint.add_url_rule(path, endpoint="probe", view_func=lambda: "enabled")
            self.app.register_blueprint(blueprint)

        self.app.add_url_rule("/login", endpoint="auth.login", view_func=generate_csrf)
        configure_security(self.app)
        self.client = self.app.test_client()

    def tearDown(self):
        data.conn = self.old_conn
        self.conn.close()

    def test_waitress_accepts_only_loopback(self):
        for host in ("127.0.0.1", "::1", "localhost"):
            self.assertEqual(validate_loopback_host(host), host)
        for host in ("0.0.0.0", "192.168.1.10", "", "example.com"):
            with self.assertRaises(RuntimeError):
                validate_loopback_host(host)

    def test_disallowed_host_is_rejected(self):
        response = self.client.get("/private", headers={"Host": "evil.example"})
        self.assertEqual(response.status_code, 400)

    def test_private_route_still_requires_login(self):
        response = self.client.get("/private", headers={"Host": "localhost"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_cross_site_mutation_is_rejected_before_csrf(self):
        csrf_token = self.client.get("/login", headers={"Host": "localhost"}).get_data(as_text=True)
        response = self.client.post(
            "/mutate",
            headers={"Host": "localhost", "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
            data={"csrf_token": csrf_token},
        )
        self.assertEqual(response.status_code, 403)

    def test_other_loopback_origin_is_not_same_origin(self):
        csrf_token = self.client.get("/login", headers={"Host": "localhost"}).get_data(as_text=True)
        response = self.client.post(
            "/mutate",
            headers={"Host": "localhost", "Origin": "http://localhost:9999"},
            data={"csrf_token": csrf_token},
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_csrf_is_rejected(self):
        response = self.client.post("/mutate", headers={"Host": "localhost"})
        self.assertEqual(response.status_code, 400)

    def test_network_companion_endpoints_are_disabled_by_default(self):
        for path in ("/public-test", "/pocket-test", "/logger-test"):
            response = self.client.get(path, headers={"Host": "localhost"})
            self.assertEqual(response.status_code, 404)

    def test_markdown_sanitizer_blocks_executable_markup(self):
        rendered = render_markdown(
            '<script>alert(1)</script><img src="javascript:alert(2)" onerror="alert(3)">'
            '<a href="javascript:alert(4)">bad</a><table><tr><td>safe</td></tr></table>'
            '\n\n```mermaid\ngraph TD; A-->B\n```'
        )
        lowered = rendered.lower()
        self.assertNotIn("<script", lowered)
        self.assertNotIn("javascript:", lowered)
        self.assertNotIn("onerror", lowered)
        self.assertIn("<table>", lowered)
        self.assertIn('class="language-mermaid"', lowered)


if __name__ == "__main__":
    unittest.main()
