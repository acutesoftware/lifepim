import os
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common.utils import format_duration_friendly, format_duration_label


class TestFormatting(unittest.TestCase):
    def test_format_duration_keeps_raw_value(self):
        self.assertEqual(format_duration_friendly("3665"), "3665 (1 hour 1 min 5 sec)")

    def test_format_short_duration(self):
        self.assertEqual(format_duration_friendly("42"), "42 (42 sec)")

    def test_format_millisecond_like_large_duration(self):
        self.assertEqual(format_duration_friendly("6458483"), "6458483 (1 hour 47 min 38 sec)")

    def test_format_duration_label_omits_raw_value(self):
        self.assertEqual(format_duration_label("289.2277551020408"), "4 min 49 sec")


if __name__ == "__main__":
    unittest.main()
