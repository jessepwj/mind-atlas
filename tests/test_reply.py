"""reply.py: write a reply to replies.json and rebuild the page."""
import json
import unittest

from helpers import WorkdirCase, load_script, page_json, run_script, text

reply = load_script("reply")


class ReplyTests(WorkdirCase):
    def setUp(self):
        super().setUp()
        self.write_meta(lang="en")
        self.write("outline.md", "# Root\n- A\n")

    def replies(self):
        return json.loads((self.wd / "replies.json").read_text(encoding="utf-8"))

    def page(self):
        return next(self.wd.glob("*.html")).read_text(encoding="utf-8")

    def test_reply_is_written_and_the_page_is_rebuilt(self):
        proc = run_script("reply", self.wd, "F1016-162301-ab", "Fixed: the node now says what it means.", "--orig", "what does A mean?")
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0, err)
        self.assertIn("Replied to F1016-162301-ab", out)
        self.assertIn("Wrote", out)
        stored = self.replies()
        self.assertEqual(len(stored), 1)
        self.assertEqual((stored[0]["id"], stored[0]["text"], stored[0]["orig"]),
                         ("F1016-162301-ab", "Fixed: the node now says what it means.", "what does A mean?"))
        self.assertRegex(stored[0]["ts"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")
        self.assertEqual(page_json(self.page(), "replies")[0]["text"], "Fixed: the node now says what it means.")

    def test_the_same_feedback_can_be_answered_twice(self):
        run_script("reply", self.wd, "F1", "first")
        run_script("reply", self.wd, "F1", "second")
        self.assertEqual([r["text"] for r in self.replies()], ["first", "second"])
        self.assertEqual(len(page_json(self.page(), "replies")), 2)

    def test_chinese_text_is_stored_readably(self):
        run_script("reply", self.wd, "F2", "已经改了，加了一个节点。", "--orig", "这里少了东西")
        raw = (self.wd / "replies.json").read_text(encoding="utf-8")
        self.assertIn("已经改了，加了一个节点。", raw)    # not \\u escapes
        self.assertEqual(self.replies()[0]["orig"], "这里少了东西")

    def test_a_reply_that_starts_with_a_dash_is_not_an_option(self):
        proc = run_script("reply", self.wd, "F3", "- yes, done")
        self.assertEqual(proc.returncode, 0, text(proc)[1])
        self.assertEqual(self.replies()[0]["text"], "- yes, done")

    def test_orig_may_come_first(self):
        proc = run_script("reply", self.wd, "--orig", "original", "F4", "answer")
        self.assertEqual(proc.returncode, 0, text(proc)[1])
        self.assertEqual((self.replies()[0]["text"], self.replies()[0]["orig"]), ("answer", "original"))

    def test_no_paths_is_passed_on_to_the_build(self):
        proc = run_script("reply", self.wd, "F5", "ok", "--no-paths")
        self.assertEqual(proc.returncode, 0, text(proc)[1])
        self.assertNotIn("file", page_json(self.page(), "meta"))

    def test_not_a_work_directory(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        proc = run_script("reply", empty, "F6", "ok")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no meta.json", text(proc)[1])

    def test_empty_reply_is_refused(self):
        proc = run_script("reply", self.wd, "F7", "   ")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.wd / "replies.json").exists())

    def test_wrong_number_of_arguments_prints_usage(self):
        proc = run_script("reply", self.wd)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Usage:", text(proc)[1])

    def test_corrupt_replies_file_is_reported_and_left_alone(self):
        self.write("replies.json", "{broken")
        proc = run_script("reply", self.wd, "F8", "ok")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual((self.wd / "replies.json").read_text(encoding="utf-8"), "{broken")

    def test_add_reply_returns_the_count(self):
        self.assertEqual(reply.add_reply(self.wd, "F9", "one"), 1)
        self.assertEqual(reply.add_reply(self.wd, "F9", "two"), 2)


if __name__ == "__main__":
    unittest.main()
