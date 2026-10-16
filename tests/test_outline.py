"""Outline parsing: structure, tags, notes, sources, errors and warnings."""
import unittest

from helpers import build


def parse(text, src_sep="; "):
    lines = [("outline.md", i, ln) for i, ln in enumerate(text.splitlines(), 1)]
    return build.parse_outline(lines, src_sep)


def titles(node):
    return [c["t"] for c in node["c"]]


class StructureTests(unittest.TestCase):
    def test_tree_follows_indentation(self):
        root, warnings = parse("# Root\n- A\n  - A1\n    - A1a\n  - A2\n- B\n")
        self.assertEqual(root["t"], "Root")
        self.assertEqual(titles(root), ["A", "B"])
        self.assertEqual(titles(root["c"][0]), ["A1", "A2"])
        self.assertEqual(titles(root["c"][0]["c"][0]), ["A1a"])
        self.assertEqual(warnings, [])

    def test_root_note_tags_and_sources(self):
        root, _ = parse("# Root [active] | The root note [src: notes.txt]\n- A\n")
        self.assertEqual((root["t"], root["n"], root["g"], root["s"]), ("Root", "The root note", ["active"], "notes.txt"))

    def test_blank_lines_and_comments_are_ignored(self):
        root, warnings = parse("# Root\n\n<!-- one line -->\n- A\n<!--\nmulti line\n- not a node\n-->\n- B\n")
        self.assertEqual(titles(root), ["A", "B"])
        self.assertEqual(warnings, [])

    def test_crlf_input(self):
        root, _ = parse("# Root\r\n- A\r\n  - A1\r\n")
        self.assertEqual(titles(root["c"][0]), ["A1"])

    def test_children_can_be_attached_from_a_later_piece(self):
        # pieces are plain text concatenation: a later piece may start deeper and attach to the last node
        root, _ = parse("# Root\n- A\n  - A1\n- B\n  - B1\n    - B1a\n")
        self.assertEqual(titles(root["c"][1]), ["B1"])

    def test_leading_indent_levels_pop_correctly(self):
        root, _ = parse("# R\n- A\n  - A1\n    - A1a\n      - A1a1\n  - A2\n")
        self.assertEqual(titles(root["c"][0]), ["A1", "A2"])


class TagTests(unittest.TestCase):
    def tags(self, text):
        root, _ = parse("# R\n- " + text + "\n")
        return root["c"][0]["g"]

    def test_chinese_tags(self):
        self.assertEqual(self.tags("甲 【在用】 【已定】"), ["active", "decided"])

    def test_all_ten_english_tags(self):
        spelled = ["active", "stopped", "in progress", "todo", "issue", "done", "decided", "waiting", "risk", "proposal"]
        keys = ["active", "stopped", "doing", "todo", "issue", "done", "decided", "waiting", "risk", "proposal"]
        self.assertEqual(self.tags("A " + " ".join("[%s]" % s for s in spelled)), keys)

    def test_all_ten_chinese_tags_map_to_the_same_keys(self):
        zh = ["在用", "已停", "进行中", "待做", "问题", "已完成", "已定", "等别人", "风险", "建议"]
        keys = ["active", "stopped", "doing", "todo", "issue", "done", "decided", "waiting", "risk", "proposal"]
        self.assertEqual(self.tags("甲 " + "".join("【%s】" % s for s in zh)), keys)

    def test_mixed_spellings_keep_text_order_and_drop_duplicates(self):
        self.assertEqual(self.tags("A [done] 【在用】 [Done]"), ["done", "active"])

    def test_case_insensitive(self):
        self.assertEqual(self.tags("A [Active] [IN PROGRESS]"), ["active", "doing"])

    def test_unknown_brackets_stay_in_the_title(self):
        root, _ = parse("# R\n- Array a[0] and [maybe] stay\n")
        self.assertEqual(root["c"][0]["t"], "Array a[0] and [maybe] stay")
        self.assertEqual(root["c"][0]["g"], [])

    def test_escaped_tag_stays_literal(self):
        root, _ = parse("# R\n- Use the \\[todo] marker | and \\[src: x] too\n")
        node = root["c"][0]
        self.assertEqual((node["t"], node["n"], node["g"], node["s"]), ("Use the [todo] marker", "and [src: x] too", [], ""))

    def test_tags_are_removed_from_title_and_note(self):
        root, _ = parse("# R\n- Title [risk] | Note [issue] text\n")
        node = root["c"][0]
        self.assertEqual((node["t"], node["n"], node["g"]), ("Title", "Note  text", ["risk", "issue"]))


class SeparatorAndSourceTests(unittest.TestCase):
    def node(self, text, sep="; "):
        root, _ = parse("# R\n- " + text + "\n", sep)
        return root["c"][0]

    def test_fullwidth_separator(self):
        n = self.node("标题 ｜ 说明")
        self.assertEqual((n["t"], n["n"]), ("标题", "说明"))

    def test_ascii_separator(self):
        n = self.node("Title | Note")
        self.assertEqual((n["t"], n["n"]), ("Title", "Note"))

    def test_first_separator_wins_and_later_pipes_stay_in_the_note(self):
        n = self.node("Title | Note | more ｜ even more")
        self.assertEqual((n["t"], n["n"]), ("Title", "Note | more ｜ even more"))

    def test_pipe_without_spaces_does_not_split(self):
        n = self.node("a|b and c || d")
        self.assertEqual((n["t"], n["n"]), ("a|b and c || d", ""))

    def test_separator_after_a_tag(self):
        n = self.node("Title [done] | Note")
        self.assertEqual((n["t"], n["n"], n["g"]), ("Title", "Note", ["done"]))

    def test_chinese_and_english_sources_merge(self):
        n = self.node("Title | Note 〔a.md〕 [src: b.md] [Source: c.md]", "; ")
        self.assertEqual(n["s"], "a.md; b.md; c.md")
        self.assertEqual(n["n"], "Note")

    def test_source_separator_follows_the_language(self):
        self.assertEqual(self.node("标题 〔甲〕〔乙〕", "；")["s"], "甲；乙")

    def test_source_may_sit_anywhere_in_the_line(self):
        n = self.node("Title [src: x] | Note")
        self.assertEqual((n["t"], n["n"], n["s"]), ("Title", "Note", "x"))


class ContinuationTests(unittest.TestCase):
    def test_continuation_joins_the_note(self):
        root, warnings = parse("# R\n- A | first\n    second\n    third\n- B\n")
        self.assertEqual(root["c"][0]["n"], "first second third")
        self.assertEqual(warnings, [])

    def test_continuation_without_a_note_starts_one(self):
        root, _ = parse("# R\n- A\n    only continuation\n")
        self.assertEqual(root["c"][0]["n"], "only continuation")

    def test_continuation_line_is_all_note_text(self):
        root, _ = parse("# R\n- A | note\n    a | b ｜ c\n")
        self.assertEqual(root["c"][0]["n"], "note a | b ｜ c")

    def test_continuation_can_carry_tags_and_sources(self):
        root, _ = parse("# R\n- A [todo]\n    more [done] [src: s2]\n", "; ")
        node = root["c"][0]
        self.assertEqual((node["g"], node["s"], node["n"]), (["todo", "done"], "s2", "more"))

    def test_continuation_after_the_root(self):
        root, _ = parse("# R | note\nmore note\n- A\n")
        self.assertEqual(root["n"], "note more note")


class ErrorTests(unittest.TestCase):
    def assertError(self, text, *fragments):
        with self.assertRaises(build.BuildError) as cm:
            parse(text)
        for f in fragments:
            self.assertIn(f, str(cm.exception))
        return str(cm.exception)

    def test_tab_indentation(self):
        self.assertError("# R\n- A\n\t- A1\n", "outline.md:3", "tab")

    def test_odd_indentation(self):
        self.assertError("# R\n- A\n   - A1\n", "outline.md:3", "multiple of 2")

    def test_skipped_level(self):
        self.assertError("# R\n- A\n      - deep\n", "outline.md:3", "skips a level")

    def test_first_level_must_not_be_indented(self):
        self.assertError("# R\n  - A\n", "outline.md:2", "skips a level")

    def test_second_root(self):
        self.assertError("# R\n- A\n# Another\n", "outline.md:3", "second '# '")

    def test_node_before_root(self):
        self.assertError("- A\n# R\n", "outline.md:1", "must start with a '# Root title'")

    def test_text_before_root(self):
        self.assertError("just text\n# R\n", "outline.md:1")

    def test_empty_outline(self):
        self.assertError("\n\n<!-- nothing -->\n", "empty")

    def test_error_names_the_piece_file(self):
        lines = [("part-a.md", 1, "# R"), ("part-b.md", 4, "   - bad")]
        with self.assertRaises(build.BuildError) as cm:
            build.parse_outline(lines)
        self.assertIn("part-b.md:4", str(cm.exception))


class WarningTests(unittest.TestCase):
    def test_star_bullet_warns(self):
        _, warnings = parse("# R\n- A\n  * not a node\n")
        self.assertEqual(len(warnings), 1)
        self.assertIn("only '- ' starts a node", warnings[0])

    def test_markdown_heading_line_warns(self):
        _, warnings = parse("# R\n- A\n  ## Heading from a report\n")
        self.assertEqual(len(warnings), 1)
        self.assertIn("not a node", warnings[0])

    def test_shallow_continuation_warns(self):
        _, warnings = parse("# R\n- A\n  - A1\n  text at the node's own indent\n")
        self.assertEqual(len(warnings), 1)
        self.assertIn("not indented deeper", warnings[0])

    def test_ellipsis_warns(self):
        root, _ = parse("# R\n- A cut off…\n- B | and so on...\n")
        warnings = build.check_nodes(root)
        self.assertTrue(any("ellipsis" in w and "A cut off" in w for w in warnings))

    def test_empty_title_warns(self):
        root, _ = parse("# R\n- \n")
        self.assertTrue(any("empty title" in w for w in build.check_nodes(root)))

    def test_duplicate_siblings_warn_but_same_title_elsewhere_does_not(self):
        root, _ = parse("# R\n- A\n  - X\n- B\n  - X\n- A\n")
        warnings = build.check_nodes(root)
        self.assertEqual(len(warnings), 1)
        self.assertIn("duplicate sibling title 'A'", warnings[0])

    def test_root_without_children_warns(self):
        root, _ = parse("# R\n")
        self.assertTrue(any("no child nodes" in w for w in build.check_nodes(root)))


if __name__ == "__main__":
    unittest.main()
