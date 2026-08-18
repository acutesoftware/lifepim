import os
import sys
import unittest


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from utils import note_inspect


def _special_tokens(result):
    return [token for token in result["tokens"] if token["kind"] != note_inspect.KIND_NORMAL]


class TestNoteInspect(unittest.TestCase):
    def test_plain_ascii_has_no_warnings_and_text_is_unchanged(self):
        result = note_inspect.inspect_note_bytes(b"Hello world")

        self.assertEqual(result["summary"]["non_ascii"], 0)
        self.assertEqual(result["summary"]["suspicious"], 0)
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertEqual(result["tokens"], [{"kind": "normal", "text": "Hello world", "title": "", "line": None, "column": None, "byte_offset": None}])

    def test_printable_unicode_is_valid_non_ascii(self):
        result = note_inspect.inspect_note_bytes("François paid £20 — Tuesday".encode("utf-8"))
        tokens = _special_tokens(result)

        self.assertEqual([token["text"] for token in tokens], ["ç", "£", "—"])
        self.assertTrue(all(token["kind"] == note_inspect.KIND_UNICODE for token in tokens))
        self.assertEqual(result["summary"]["errors"], 0)

    def test_nbsp_is_suspicious_and_visible(self):
        result = note_inspect.inspect_note_bytes("hello\u00a0world".encode("utf-8"))
        tokens = _special_tokens(result)

        self.assertEqual(tokens[0]["kind"], note_inspect.KIND_SUSPICIOUS)
        self.assertEqual(tokens[0]["text"], "[NBSP]")
        self.assertIn("NO-BREAK SPACE", tokens[0]["title"])

    def test_zero_width_space_is_suspicious_and_visible(self):
        result = note_inspect.inspect_note_bytes("customer\u200bname".encode("utf-8"))
        tokens = _special_tokens(result)

        self.assertEqual(tokens[0]["kind"], note_inspect.KIND_SUSPICIOUS)
        self.assertEqual(tokens[0]["text"], "[ZWSP]")
        self.assertIn("ZERO WIDTH SPACE", tokens[0]["title"])

    def test_nul_is_error_and_visible(self):
        result = note_inspect.inspect_note_bytes(b"hello\x00world")
        tokens = _special_tokens(result)

        self.assertEqual(tokens[0]["kind"], note_inspect.KIND_ERROR)
        self.assertEqual(tokens[0]["text"], "[NUL]")
        self.assertIn("U+0000", tokens[0]["title"])

    def test_replacement_character_is_error(self):
        result = note_inspect.inspect_note_bytes("\ufffd".encode("utf-8"))
        tokens = _special_tokens(result)

        self.assertEqual(tokens[0]["kind"], note_inspect.KIND_ERROR)
        self.assertEqual(tokens[0]["text"], "[REPLACEMENT U+FFFD]")
        self.assertIn("REPLACEMENT CHARACTER", tokens[0]["title"])

    def test_bidi_override_is_error_and_visible(self):
        result = note_inspect.inspect_note_bytes("abc\u202etxt".encode("utf-8"))
        tokens = _special_tokens(result)

        self.assertEqual(tokens[0]["kind"], note_inspect.KIND_ERROR)
        self.assertEqual(tokens[0]["text"], "[RLO U+202E]")
        self.assertIn("RIGHT-TO-LEFT OVERRIDE", tokens[0]["title"])

    def test_invalid_utf8_is_preserved_as_invalid_byte_token(self):
        result = note_inspect.inspect_note_bytes(bytes.fromhex("48 65 6C 6C 6F FF 57 6F 72 6C 64"))

        self.assertEqual("".join(token["text"] for token in result["tokens"]), "Hello[INVALID UTF-8: FF]World")
        invalid = _special_tokens(result)[0]
        self.assertEqual(invalid["kind"], note_inspect.KIND_ERROR)
        self.assertIn("Bytes: FF", invalid["title"])
        self.assertEqual(invalid["byte_offset"], 5)

    def test_html_input_remains_plain_text_token(self):
        result = note_inspect.inspect_note_bytes(b'<script>alert("test")</script>')

        self.assertEqual(result["tokens"][0]["text"], '<script>alert("test")</script>')
        self.assertEqual(result["summary"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
