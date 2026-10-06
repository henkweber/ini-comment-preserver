import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from ini_comment_preserver import INICommentPreserver, ParseError


class TestRoundTrip(unittest.TestCase):
    def test_preserves_full_comment_lines(self):
        text = (
            "# top comment\n"
            "[server]\n"
            "; host line\n"
            "host = localhost\n"
            "port = 8080\n"
        )
        p = INICommentPreserver()
        p.read_string(text)
        out = p.write_string()
        self.assertIn("# top comment", out)
        self.assertIn("; host line", out)
        self.assertIn("host=localhost", out)
        self.assertEqual(p.get("server", "host"), "localhost")

    def test_preserves_key_order(self):
        text = (
            "[a]\n"
            "z = 1\n"
            "m = 2\n"
            "a = 3\n"
        )
        p = INICommentPreserver()
        p.read_string(text)
        self.assertEqual(p.keys("a"), ["z", "m", "a"])

    def test_preserves_section_order(self):
        text = (
            "[zeta]\n"
            "x = 1\n"
            "[alpha]\n"
            "y = 2\n"
        )
        p = INICommentPreserver()
        p.read_string(text)
        self.assertEqual(p.sections(), ["zeta", "alpha"])

    def test_blank_lines_kept_between_sections(self):
        text = (
            "[a]\n"
            "\n"
            "[b]\n"
            "k = v\n"
        )
        p = INICommentPreserver()
        p.read_string(text)
        out = p.write_string()
        self.assertIn("[a]\n\n[b]", out)


class TestComments(unittest.TestCase):
    def test_comment_then_key_then_comment_order_preserved(self):
        text = (
            "[s]\n"
            "# first\n"
            "a = 1\n"
            "# second\n"
            "b = 2\n"
        )
        p = INICommentPreserver()
        p.read_string(text)
        out = p.write_string()
        lines = out.splitlines()
        self.assertIn("# first", lines)
        self.assertIn("a=1", lines)
        self.assertIn("# second", lines)
        self.assertIn("b=2", lines)
        self.assertLess(lines.index("# first"), lines.index("a=1"))
        self.assertLess(lines.index("a=1"), lines.index("# second"))
        self.assertLess(lines.index("# second"), lines.index("b=2"))

    def test_comment_survives_key_deletion(self):
        text = (
            "[s]\n"
            "# pre\n"
            "k = 1\n"
            "# post\n"
        )
        p = INICommentPreserver()
        p.read_string(text)
        self.assertTrue(p.remove("s", "k"))
        out = p.write_string()
        self.assertIn("# pre", out)
        self.assertIn("# post", out)
        self.assertNotIn("k=1", out)

    def test_both_comment_markers_supported(self):
        text = (
            "[s]\n"
            "# hash\n"
            "; semi\n"
            "k = v\n"
        )
        p = INICommentPreserver()
        p.read_string(text)
        out = p.write_string()
        self.assertIn("# hash", out)
        self.assertIn("; semi", out)


class TestValues(unittest.TestCase):
    def test_value_with_equals_sign(self):
        p = INICommentPreserver()
        p.read_string("[s]\nexpr = a=b\n")
        self.assertEqual(p.get("s", "expr"), "a=b")
        self.assertEqual(p.write_string().strip().splitlines()[-1], "expr=a=b")

    def test_value_with_hash_is_literal(self):
        p = INICommentPreserver()
        p.read_string("[s]\nv = x#y\n")
        self.assertEqual(p.get("s", "v"), "x#y")

    def test_set_new_key_appends(self):
        p = INICommentPreserver()
        p.read_string("[s]\nold = 1\n")
        p.set("s", "new", "2")
        self.assertEqual(p.keys("s"), ["old", "new"])

    def test_set_existing_key_preserves_position(self):
        p = INICommentPreserver()
        p.read_string("[s]\nfirst = 1\nmid = 2\nlast = 3\n")
        p.set("s", "mid", "99")
        self.assertEqual(p.keys("s"), ["first", "mid", "last"])
        self.assertEqual(p.get("s", "mid"), "99")

    def test_set_creates_section_if_missing(self):
        p = INICommentPreserver()
        p.set("newsec", "k", "v")
        self.assertEqual(p.sections(), ["newsec"])
        self.assertEqual(p.get("newsec", "k"), "v")

    def test_value_rstripped_and_lstripped(self):
        p = INICommentPreserver()
        p.read_string("[s]\nk =    spaced   \n")
        self.assertEqual(p.get("s", "k"), "spaced")


class TestErrors(unittest.TestCase):
    def test_kv_before_section_raises(self):
        p = INICommentPreserver()
        with self.assertRaises(ParseError):
            p.read_string("orphan = 1\n[s]\n")

    def test_duplicate_section_raises(self):
        p = INICommentPreserver()
        with self.assertRaises(ParseError):
            p.read_string("[s]\n[s]\n")

    def test_missing_value_raises(self):
        p = INICommentPreserver()
        with self.assertRaises(ParseError):
            p.read_string("[s]\n= nokey\n")

    def test_remove_missing_returns_false(self):
        p = INICommentPreserver()
        p.read_string("[s]\n\n")
        self.assertFalse(p.remove("s", "nope"))

    def test_get_missing_returns_none(self):
        p = INICommentPreserver()
        p.read_string("[s]\n\n")
        self.assertIsNone(p.get("s", "missing"))


class TestEdgeLines(unittest.TestCase):
    def test_section_without_terminating_newline(self):
        p = INICommentPreserver()
        p.read_string("[s]\nk=v")
        self.assertEqual(p.get("s", "k"), "v")

    def test_empty_section_name_allowed(self):
        p = INICommentPreserver()
        p.read_string("[]\n")
        self.assertEqual(p.sections(), [""])

    def test_blank_line_in_section_kept(self):
        text = "[s]\n\nk = 1\n\nm = 2\n"
        p = INICommentPreserver()
        p.read_string(text)
        out = p.write_string()
        self.assertIn("\n\nk=1\n\nm=2", out)

    def test_crlf_handled_gracefully(self):
        text = "[s]\r\nk = 1\r\n"
        p = INICommentPreserver()
        p.read_string(text)
        self.assertEqual(p.get("s", "k"), "1")

    def test_trailing_preamble_before_section(self):
        text = "# header\n\n[s]\nk = 1\n"
        p = INICommentPreserver()
        p.read_string(text)
        out = p.write_string()
        self.assertTrue(out.startswith("# header\n\n[s]"))


if __name__ == "__main__":
    unittest.main()
