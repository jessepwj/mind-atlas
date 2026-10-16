"""Open the built pages in headless Chrome/Chromium and click through them.

Opt in by setting MIND_ATLAS_CHROME to a Chrome, Chromium or Edge executable (or a command on PATH); without it
these tests are skipped, so a plain `python -m unittest discover -s tests` never needs a browser.
"""
import json
import os
import pathlib
import shutil
import tempfile
import unittest

import browser_harness as bh
from helpers import CJK, EXAMPLES, build, page_json

CHROME = bh.find_chrome() if os.environ.get("MIND_ATLAS_CHROME") else None


@unittest.skipUnless(CHROME, "set MIND_ATLAS_CHROME to a Chrome/Chromium/Edge executable to run the browser tests")
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-browser-"))
        cls.pages = {}
        for lang, name, term in (("en", "tool-library-en", "drill"), ("zh", "book-corner-zh", "绘本")):
            work = pathlib.Path(shutil.copytree(str(EXAMPLES / name), str(cls.tmp / name)))
            result = build.build(work, no_paths=True)
            cls.pages[lang] = (result, term, cls.run_page(result, term))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.tmp), ignore_errors=True)

    @staticmethod
    def run_page(result, term):
        return bh.run_scenario(result.out, term, chrome=CHROME)

    def test_node_count_and_status_line(self):
        for lang, (result, _, run) in self.pages.items():
            with self.subTest(lang=lang):
                self.assertEqual(run["nodes"], result.nodes)
                self.assertEqual(run["connClass"], "conn ok")
                self.assertEqual(run["conn"], {"en": "Saved in this browser", "zh": "存在这个浏览器里"}[lang])

    def test_no_script_errors_and_no_blocked_requests(self):
        for lang, (_, _, run) in self.pages.items():
            with self.subTest(lang=lang):
                self.assertEqual(run["errors"], [])
                self.assertEqual(run["violations"], [])

    def test_document_language_and_title(self):
        self.assertEqual(self.pages["en"][2]["lang"], "en")
        self.assertEqual(self.pages["zh"][2]["lang"], "zh-CN")
        self.assertEqual(self.pages["en"][2]["title"], "Neighborhood Tool Library (example)")

    def test_english_page_never_shows_chinese(self):
        run = self.pages["en"][2]
        shown = [t for step in run["log"] for t in step["texts"]] + run["clips"]
        shown += [v for step in run["log"] for v in step["values"].values()]
        self.assertEqual([t for t in shown if CJK.search(t)], [])

    def test_chinese_page_shows_chinese_ui(self):
        run = self.pages["zh"][2]
        first = run["log"][0]["texts"]
        for expected in ("全部展开", "大纲视图", "适应窗口", "反馈", "复制给 AI"):
            self.assertIn(expected, first)

    def test_copy_for_ai_blocks(self):
        en = self.pages["en"][2]["clips"]
        zh = self.pages["zh"][2]["clips"]
        self.assertTrue(en and zh)
        self.assertTrue(en[0].startswith("[Mind map feedback] Neighborhood Tool Library (example), 2 items\n"))
        self.assertTrue(zh[0].startswith("【导图反馈】小区旧书漂流角全貌（示例），2 条\n"))
        self.assertIn("\n1. [F1016-123456-i] 10-16 12:34\n", en[0])
        self.assertIn("\n1. [F1016-123456-i] 10月16日 12:34\n", zh[0])
        self.assertIn("   Says: First feedback\n      second line", en[0])
        self.assertIn("   说：First feedback\n      second line", zh[0])
        # a no-paths page carries no page path or reply command
        self.assertNotIn("Page file:", en[0])
        self.assertNotIn("页面文件", zh[0])

    def test_search_finds_the_term(self):
        for lang, (_, term, run) in self.pages.items():
            with self.subTest(lang=lang):
                step = next(s for s in run["log"] if s["label"] == "search-hit")
                self.assertTrue(any(" / " in t or " of " in t for t in step["texts"]), step["texts"][:12])
                none = next(s for s in run["log"] if s["label"] == "search-none")
                self.assertTrue(any(t in ("No matches", "没找到") for t in none["texts"]))

    def test_status_legend_uses_the_page_language(self):
        legend = {"en": ["Active", "Done", "In progress", "To do", "Waiting", "Issue", "Risk", "Stopped", "Decided", "Proposal"],
                  "zh": ["在用", "已完成", "进行中", "待做", "等别人", "问题", "风险", "已停", "已定", "建议"]}
        for lang, labels in legend.items():
            texts = self.pages[lang][2]["log"][0]["texts"]
            start = texts.index({"en": "Status:", "zh": "状态："}[lang])
            self.assertEqual(texts[start + 1:start + 11], labels)

    def test_replies_show_up_under_the_feedback(self):
        work = pathlib.Path(shutil.copytree(str(EXAMPLES / "tool-library-en"), str(self.tmp / "with-replies")))
        (work / "replies.json").write_text(json.dumps([
            {"id": "F1016-101500-ab", "ts": "2026-10-16 10:20:00", "text": "Added a node for it.", "orig": "what about ladders?"},
            {"id": "F1016-090000-zz", "ts": "2026-10-16 09:10:00", "text": "Reply to another browser.", "orig": "written elsewhere"},
        ]), encoding="utf-8")
        result = build.build(work, no_paths=True)
        root = page_json(result.out.read_text(encoding="utf-8"), "data")["t"]
        seed = ("demo-tool-library", [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:15:00", "text": "what about ladders?",
                                       "quotes": [{"p": [root, "Purpose and rules"], "x": ""}], "ctx": None,
                                       "sent": "2026-10-16 10:16:00", "replaces": None}])
        run = bh.run_scenario(result.out, "drill", seed=seed, chrome=CHROME)
        texts = run["log"][0]["texts"]
        self.assertIn("Added a node for it.", texts)
        self.assertIn("Reply · 10-16 10:20", texts)
        self.assertIn("Reply to another browser.", texts)
        self.assertIn("written elsewhere", texts)
        self.assertIn("Not saved in this browser: written elsewhere, or deleted here. Showing your original words and the reply.", texts)
        self.assertEqual(run["errors"], [])

    def test_hostile_text_is_inert(self):
        """Markup in titles, notes, sources and replies is shown as text and never becomes elements or runs."""
        bad = '<img src=x onerror="window.__pwned=1"><svg onload="window.__pwned=2"></svg></script><script>window.__pwned=3</script>'
        work = pathlib.Path(self.tmp / "hostile")
        work.mkdir()
        (work / "meta.json").write_text(json.dumps({"title": "Hostile " + bad, "id": "hostile", "lang": "en", "desc": bad,
                                                    "search_hint": bad}), encoding="utf-8")
        (work / "outline.md").write_text("# Root %s | %s [src: %s]\n- Child %s [done] | note %s\n- Second\n- Third | %s\n" % ((bad,) * 6), encoding="utf-8")
        (work / "replies.json").write_text(json.dumps([{"id": "F1", "ts": "2026-10-16 10:00:00", "text": bad, "orig": bad}]), encoding="utf-8")
        result = build.build(work, no_paths=True)
        run = bh.run_scenario(result.out, "img", chrome=CHROME)
        self.assertEqual(run["suspicious"], 0)
        self.assertIsNone(run["pwned"])
        self.assertEqual(run["errors"], [])
        self.assertEqual(run["nodes"], 4)
        shown = [t for step in run["log"] for t in step["texts"]]
        self.assertTrue(any(bad in t for t in shown))      # visible as plain text


if __name__ == "__main__":
    unittest.main()
