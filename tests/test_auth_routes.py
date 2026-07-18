import os
import sys
import unittest

from flask import Flask

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from modules.auth.routes import auth_bp
from core.security import login_manager


class TestAuthRoutes(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = "test-secret"
        app.register_blueprint(auth_bp)
        login_manager.init_app(app)
        self.client = app.test_client()

    def test_logout_aliases_redirect_to_login(self):
        for path in ("/logout", "/auth/logout"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/login")


if __name__ == "__main__":
    unittest.main()
