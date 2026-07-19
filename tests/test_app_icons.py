import os
import sys
import unittest


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from app import app


class TestAppIcons(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_favicon_is_public(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/vnd.microsoft.icon")

    def test_webmanifest_uses_static_favicon(self):
        response = self.client.get("/site.webmanifest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/manifest+json")
        data = response.get_json()
        self.assertEqual(data["name"], "LifePIM")
        self.assertEqual(data["icons"][0]["src"], "/static/favicon.ico")
        self.assertEqual(data["icons"][0]["type"], "image/x-icon")


if __name__ == "__main__":
    unittest.main()
