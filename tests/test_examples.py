"""Every example under examples/ must build cleanly and in its own language; the two big ones show off all ten
statuses, the two small "repair-cafe" ones show the long-running console (the "now" branch and the needs-you tag)."""
import json
import re
import shutil
import tempfile
import unittest

from helpers import CJK, EXAMPLES, build, page_json

ALL_STATUSES = {"active", "stopped", "doing", "todo", "issue", "done", "decided", "waiting", "risk", "proposal"}
CONSOLE = "repair-cafe"      # the folder prefix of the long-running console examples


def is_console(path):
    return path.name.startswith(CONSOLE)


def example_dirs():
    return sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and (p / "meta.json").exists())


class ExampleTests(unittest.TestCase):
    def test_there_is_one_example_per_language(self):
        names = [p.name for p in example_dirs()]
        self.assertTrue(any(n.endswith("-zh") for n in names), names)
        self.assertTrue(any(n.endswith("-en") for n in names), names)

    def test_examples_build_without_warnings(self):
        for src in example_dirs():
            with self.subTest(example=src.name):
                tmp = tempfile.mkdtemp(prefix="mind-atlas-example-")
                self.addCleanup(shutil.rmtree, tmp, True)
                work = shutil.copytree(str(src), tmp + "/work")
                result = build.build(work, no_paths=True)
                self.assertEqual(result.warnings, [])
                self.assertTrue((25 if is_console(src) else 40) <= result.nodes <= 70, result.nodes)
                self.assertGreaterEqual(result.depth, 3)
                self.assertEqual(result.replies, 0)

    def test_language_matches_the_folder_name(self):
        for src in example_dirs():
            with self.subTest(example=src.name):
                meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
                self.assertEqual(meta["lang"], src.name.rsplit("-", 1)[1])
                self.assertTrue(meta.get("id"), "a stable id keeps the feedback stored in browsers valid")
                self.assertTrue(meta.get("out", "").endswith(".html"))

    def test_source_files_contain_no_generated_output(self):
        for src in example_dirs():
            with self.subTest(example=src.name):
                names = {p.name for p in src.iterdir()}
                meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
                generated = {"outline.md", "replies.json", "_fb", meta["out"], meta["out"][:-5] + ".stamp.js"}
                # (a developer who built in place has these locally; they are git-ignored)
                self.assertTrue(all(n.endswith(".md") or n == "meta.json" or n in generated for n in names), names)

    def test_the_big_examples_use_all_ten_statuses(self):
        for src in example_dirs():
            if is_console(src):
                continue
            with self.subTest(example=src.name):
                tmp = tempfile.mkdtemp(prefix="mind-atlas-example-")
                self.addCleanup(shutil.rmtree, tmp, True)
                result = build.build(shutil.copytree(str(src), tmp + "/work"), no_paths=True)
                used = {g for n, _, _ in build.walk(result.root) for g in n["g"]}
                self.assertEqual(used, ALL_STATUSES)

    def test_prose_does_not_swallow_a_status_word_as_a_tag(self):
        """A status word anywhere in a line is read as a tag, so text about tags must not contain one."""
        for src in example_dirs():
            with self.subTest(example=src.name):
                tmp = tempfile.mkdtemp(prefix="mind-atlas-example-")
                self.addCleanup(shutil.rmtree, tmp, True)
                result = build.build(shutil.copytree(str(src), tmp + "/work"), no_paths=True)
                problems = [n for n in result.root["c"] if n["t"] in ("Problems and next steps", "问题与下一步")]
                self.assertEqual(len(problems), 1)
                self.assertEqual(problems[0]["g"], [])
                self.assertNotIn("  ", problems[0]["n"])      # a removed word would leave a double space

    def test_the_english_example_has_no_chinese_and_the_chinese_one_is_chinese(self):
        for src in example_dirs():
            with self.subTest(example=src.name):
                body = "".join(p.read_text(encoding="utf-8") for p in src.glob("*.md") if p.name != "outline.md")
                body += (src / "meta.json").read_text(encoding="utf-8")
                if src.name.endswith("-en"):
                    self.assertIsNone(CJK.search(body))
                else:
                    self.assertIsNotNone(CJK.search(body))

    def test_the_console_examples_have_a_now_branch_and_something_that_needs_the_user(self):
        for src in example_dirs():
            if not is_console(src):
                continue
            with self.subTest(example=src.name):
                tmp = tempfile.mkdtemp(prefix="mind-atlas-example-")
                self.addCleanup(shutil.rmtree, tmp, True)
                work = shutil.copytree(str(src), tmp + "/work")
                meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
                result = build.build(work, no_paths=True)
                self.assertEqual([c["t"] for c in result.root["c"]][0], meta["now"], "the now branch comes first")
                self.assertTrue(meta["root_key"])
                tags = [g for n, _, _ in build.walk(result.root) for g in n["g"]]
                self.assertEqual(tags.count("needs-you"), 2)
                self.assertGreaterEqual(tags.count("doing"), 1)
                self.assertGreaterEqual(tags.count("waiting"), 1)
                self.assertNotIn("{{", result.root["t"])       # the update-time placeholder was replaced
                self.assertTrue(any(re.match(r"\d\d-\d\d \d\d:\d\d ", n["t"]) for n, _, _ in build.walk(result.root)),
                                "dated entries for the 'next up' number")

    def test_the_english_example_uses_the_ascii_spellings(self):
        src = EXAMPLES / "tool-library-en"
        body = "".join(p.read_text(encoding="utf-8") for p in src.glob("outline-*.md"))
        self.assertIn(" | ", body)
        self.assertIn("[src: ", body)
        self.assertIn("[in progress]", body)


if __name__ == "__main__":
    unittest.main()
