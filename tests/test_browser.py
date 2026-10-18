"""Open the built pages in headless Chrome/Chromium and click through them.

Opt in by setting MIND_ATLAS_CHROME to a Chrome, Chromium or Edge executable (or a command on PATH); without it
these tests are skipped, so a plain `python -m unittest discover -s tests` never needs a browser.
"""
import json
import os
import re
import pathlib
import shutil
import tempfile
import unittest

import browser_harness as bh
from helpers import CJK, EXAMPLES, build, page_json, run_script, text

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
        self.assertRegex(en[0], r"\n1\. \[F1016-\d{6}-i\] 10-16 12:3\d\n")
        self.assertRegex(zh[0], r"\n1\. \[F1016-\d{6}-i\] 10月16日 12:3\d\n")
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
        legend = {"en": ["Needs you", "Active", "Done", "In progress", "To do", "Waiting", "Issue", "Risk", "Stopped", "Decided", "Proposal"],
                  "zh": ["要你定", "在用", "已完成", "进行中", "待做", "等别人", "问题", "风险", "已停", "已定", "建议"]}
        for lang, labels in legend.items():
            texts = self.pages[lang][2]["log"][0]["texts"]
            start = texts.index({"en": "Status:", "zh": "状态："}[lang])
            self.assertEqual(texts[start + 1:start + 1 + len(labels)], labels)

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
        self.assertIn("AI reply · 10-16 10:20", texts)
        self.assertIn("Reply to another browser.", texts)
        self.assertIn("written elsewhere", texts)          # the user's words, taken from "orig", when this browser never stored them
        self.assertIn("what about ladders?", texts)
        self.assertIn("Replied", texts)                    # a reply without a status shows the neutral label
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


@unittest.skipUnless(CHROME, "set MIND_ATLAS_CHROME to a Chrome/Chromium/Edge executable to run the browser tests")
class ConsoleBrowserTests(unittest.TestCase):
    """The long-running console: the five numbers, their lists, the filters, the new/edited marks, the panel."""

    COPY = {
        "en": {"example": "repair-cafe-en", "words": ["Needs you", "New replies", "Recently changed", "In progress", "Waiting"],
               "a": "Can we also take small appliances?", "b": "Which date do you pick?", "ask": "Which date do you prefer?",
               "ra": "Yes, small appliances are fine.", "node_a": "Purpose and rules › Fix what neighbors bring, for free",
               "node_b": "Pick the date of the autumn session", "changed": "Print the new sign-up sheet"},
        "zh": {"example": "repair-cafe-zh", "words": ["要你定", "新回复", "最近变了", "在做", "等别人"],
               "a": "小家电也可以收吗？", "b": "你选哪一天？", "ask": "你倾向哪一天？",
               "ra": "可以，小家电也收。", "node_a": "目的与规矩 › 免费帮邻居修他们带来的东西",
               "node_b": "选定秋季场的日期", "changed": "印新的签到表"},
    }

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-console-"))
        cls.runs = {}
        for lang, c in cls.COPY.items():
            work = pathlib.Path(shutil.copytree(str(EXAMPLES / c["example"]), str(cls.tmp / lang)))
            (work / "replies.json").write_text(json.dumps([
                {"id": "F-A", "ts": "2026-10-16 10:20:00", "text": c["ra"] + " Details follow.", "summary": c["ra"], "status": "done", "nodes": [c["node_a"]]},
                {"id": "F-B", "ts": "2026-10-16 10:30:00", "text": "", "summary": c["ask"], "status": "needs-you", "ask": c["ask"], "nodes": [c["node_b"]]},
            ], ensure_ascii=False), encoding="utf-8")
            result = build.build(work, no_paths=True)
            html = result.out.read_text(encoding="utf-8")
            meta, data = page_json(html, "meta"), page_json(html, "data")
            root = meta["root_key"]
            items = [{"id": "F-A", "ts": "2026-10-16 10:10:00", "text": c["a"], "quotes": [], "ctx": None, "sent": "2026-10-16 10:11:00", "replaces": None},
                     {"id": "F-B", "ts": "2026-10-16 10:25:00", "text": c["b"], "quotes": [{"p": [root, "Now", "x"], "x": ""}], "ctx": None, "sent": "2026-10-16 10:26:00", "replaces": None}]
            # the snapshot of what the user last saw: one node was edited since, one is new
            snap = {}
            for key, node in cls.walk_keys(data, root):
                if node["t"] == c["changed"]:
                    snap[bh.fnv_key(key)] = "00000000"          # edited since
                elif node["t"] not in ("Flyers delivered to 40 mailboxes", "传单已投进 40 个信箱"):
                    snap[bh.fnv_key(key)] = node["f"]           # unchanged; the flyers node is missing = new
            cls.runs[lang] = (result, bh.run_scenario(result.out, "a", seed=(meta["id"], items), chrome=CHROME, scenario=bh.CONSOLE_JS,
                                                      extra_storage={"mm:%s:snap" % meta["id"]: snap, "mm:%s:snapTs" % meta["id"]: "2026-10-15 09:00:00"}))

    @staticmethod
    def walk_keys(node, root_key, path=None):
        path = (path or []) + [root_key if path is None else node["t"]]
        yield " › ".join(path), node
        for child in node["c"]:
            for item in ConsoleBrowserTests.walk_keys(child, root_key, path):
                yield item

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.tmp), ignore_errors=True)

    def numbers(self, run, key="chips"):
        return {c["k"]: c["n"] for c in run[key]}

    def test_no_errors_and_no_blocked_requests(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertEqual(run["errors"], [])
                self.assertEqual(run["violations"], [])

    def test_the_five_numbers_are_counted_and_labelled(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                chips = [c for c in run["chips"] if c["k"] != "next"]
                self.assertEqual([c["label"] for c in chips], self.COPY[lang]["words"])
                self.assertEqual([c["k"] for c in chips], ["ask", "new", "chg", "doing", "wait"])
                # ask: the needs-you reply + the one needs-you node it does not cover; new: both replies unseen;
                # chg: one edited + one new node; doing and waiting: two tagged items each in the now branch
                self.assertEqual([c["n"] for c in chips], ["2", "2", "2", "2", "2"])
                self.assertTrue(all("hot" in c["cls"] for c in chips[:3]))
                self.assertTrue(all("zero" not in c["cls"] for c in chips))
                self.assertTrue(all(c["title"] for c in chips))

    def test_the_next_time_point_shows_beside_the_numbers(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                nxt = next(c for c in run["chips"] if c["k"] == "next")
                self.assertTrue(nxt["shown"])
                self.assertTrue(nxt["sub"])      # a relative time such as "in 20 days"

    def test_each_number_opens_a_list_with_that_many_items(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                pops = run["pops"]
                for key, expected in (("ask", 2), ("new", 2), ("chg", 2), ("doing", 2), ("wait", 2)):
                    self.assertTrue(pops[key]["open"], key)
                    self.assertEqual(len(pops[key]["items"]), expected, (key, pops[key]["items"]))
                    self.assertIn("(%d)" % expected if lang == "en" else "（%d）" % expected, pops[key]["head"])
                self.assertTrue(pops["next"]["items"])
                if lang == "en":
                    self.assertTrue(any("Which date" in t for t in pops["ask"]["items"]), pops["ask"]["items"])
                    self.assertTrue(any("soldering" in t for t in pops["ask"]["items"]), pops["ask"]["items"])

    def test_a_list_item_jumps_to_its_node(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertTrue(run["jumped"])

    def test_filters_hide_everything_else(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertLess(run["filters"]["ask"]["visible"], run["nodes"])
                self.assertEqual(run["allVisible"], run["nodes"])
                self.assertTrue(run["filters"]["ask"]["banner"])
                self.assertTrue(run["filters"]["prob"]["visible"] >= 3)

    def test_new_and_edited_nodes_are_marked(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                marks = dict(m.rsplit(":", 1) for m in run["marks"])
                self.assertEqual(sorted(marks.values()), sorted(["New", "Edited"] if lang == "en" else ["新", "改"]))
                self.assertIn(self.COPY[lang]["changed"], marks)

    def test_the_right_panel_orders_needs_you_first_and_shows_status_labels(self):
        en = self.runs["en"][1]
        self.assertEqual(en["sections"], ["Needs you", "New replies"])
        self.assertIn("Needs you", en["pills"])
        self.assertIn("Done", en["pills"])
        zh = self.runs["zh"][1]
        self.assertEqual(zh["sections"], ["要你定", "新回复"])
        self.assertIn("要你定", zh["pills"])
        self.assertIn("已做", zh["pills"])

    def test_reply_badges_on_nodes_carry_a_red_dot_while_unread(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertEqual(len(run["nodeBadges"]), 2, run["nodeBadges"])
                self.assertTrue(all(b.endswith(":hot") for b in run["nodeBadges"]))

    def test_chinese_page_has_the_exact_chinese_labels_and_english_page_no_chinese(self):
        zh = self.runs["zh"][1]
        self.assertEqual(zh["home"], "回到「现在」")
        self.assertEqual(zh["flt"], ["全部", "要你定", "在做", "等别人", "问题", "最近变了"])
        self.assertTrue(zh["age"].startswith("内容更新于 "))
        en = self.runs["en"][1]
        self.assertEqual(en["home"], "Back to “Now”")
        self.assertEqual(en["flt"], ["All", "Needs you", "In progress", "Waiting", "Issues", "Recently changed"])
        self.assertTrue(en["age"].startswith("Updated "))
        blob = json.dumps([en["chips"], en["pops"], en["filters"], en["legend"], en["hmeta"], en["sections"], en["cards"], en["pills"], en["marks"]], ensure_ascii=False)
        self.assertIsNone(CJK.search(blob))

    def test_the_now_branch_is_a_branch_of_its_own(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertGreaterEqual(run["nowExpanded"], 10)     # the now branch and everything under it carry .nowb

    def test_marking_replies_read_clears_the_new_number_but_not_the_open_questions(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertEqual(self.numbers(run)["new"], "2")
                self.assertEqual(self.numbers(run, "after")["new"], "0")
                self.assertEqual(self.numbers(run, "after")["ask"], "2")      # questions stay until answered
                self.assertEqual(run["sectionCounts"], ["2", "2"])
                self.assertEqual(run["countsAfter"], ["2", "0"])              # the group header follows the read marks


@unittest.skipUnless(CHROME, "set MIND_ATLAS_CHROME to a Chrome/Chromium/Edge executable to run the browser tests")
class TrackingBrowserTests(unittest.TestCase):
    """Project-tracking maps: the purpose in the header, and quotes and reply chips that follow a node which moved."""

    OUTLINES = {
        "en": ("# Atlas ({{updated}})\n- Now\n  - Next up\n    - 2026-10-19 08:00 Year-dated point\n    - 2026-10-21\n      - 09:30 Timed child\n    - 11-05 18:00 Later point\n  - Recently done\n    - 10-18\n      - Fresh item [done]\n- History\n  - 10-17\n"
               "    - Flyers delivered [done]\n  - 10-16\n    - Same title [done]\n    - Other path\n      - Same title [done]\n  - constructor\n",
               "Atlas", ["Now", "Recently done", "Flyers delivered"], "Same title", "Gone"),
        "zh": ("# 图（{{更新}}）\n- 现在\n  - 接下来的时间点\n    - 2026-10-19 08:00 带年份的点\n    - 2026-10-21\n      - 09:30 分组下的点\n    - 11-05 18:00 靠后的点\n  - 最近做完的\n    - 10-18\n      - 新的 【已完成】\n- 历程\n  - 10-17\n"
               "    - 传单已投 【已完成】\n  - 10-16\n    - 同名 【已完成】\n    - 另一支\n      - 同名 【已完成】\n  - constructor\n",
               "图", ["现在", "最近做完的", "传单已投"], "同名", "不在了"),
    }

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-tracking-"))
        cls.runs = {}
        for lang, (outline, root, moved, same, gone) in cls.OUTLINES.items():
            work = cls.tmp / lang
            work.mkdir()
            (work / "meta.json").write_text(json.dumps({
                "title": "Tracking " + lang, "id": "tracking-" + lang, "lang": lang, "use": "project tracking" if lang == "en" else "跟进项目",
                "level": "L2", "desc": "A test.", "root_key": root, "now": moved[0]}, ensure_ascii=False), encoding="utf-8")
            (work / "outline.md").write_text(outline, encoding="utf-8")
            (work / "replies.json").write_text(json.dumps([{"id": "F-R", "ts": "2026-10-18 10:00:00", "text": "Done.", "summary": "Done.",
                                                            "status": "done", "nodes": [" › ".join(moved)]}], ensure_ascii=False), encoding="utf-8")
            result = build.build(work, no_paths=True)
            quote = lambda path: {"p": [root] + path, "x": ""}
            items = [{"id": "F-%d" % i, "ts": "2026-10-18 09:%02d:00" % i, "text": "about %d" % i, "quotes": [q], "ctx": None, "sent": None,
                      "replaces": None} for i, q in enumerate([
                          quote(moved),                                  # the node moved to History: found by its last title
                          quote(["History", "10-17", moved[2]]),         # its real path
                          quote(moved[:2] + [same]),                     # two nodes have this title: not guessed
                          quote(moved[:2] + [gone])])]                   # no such node
            cls.runs[lang] = (result, bh.run_scenario(result.out, "a", seed=("tracking-" + lang, items), chrome=CHROME, scenario=bh.TRACKING_JS))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.tmp), ignore_errors=True)

    def test_no_errors(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertEqual(run["errors"], [])
                self.assertEqual(run["violations"], [])
                self.assertEqual(run["nodes"], self.runs[lang][0].nodes)    # a node called "constructor" does not break the lookups

    def test_the_header_says_what_the_map_is_for(self):
        self.assertTrue(self.runs["en"][1]["hmeta"].startswith("Use: project tracking. Level: L2. A test. "), self.runs["en"][1]["hmeta"])
        self.assertTrue(self.runs["zh"][1]["hmeta"].startswith("用途：跟进项目。梳理等级：L2。A test. "), self.runs["zh"][1]["hmeta"])
        self.assertIsNone(CJK.search(self.runs["en"][1]["hmeta"]))

    def test_the_nearest_time_point_reads_a_year_and_a_date_on_a_parent(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                self.assertTrue(run["next"]["shown"])
                self.assertEqual(run["next"]["tm"], "2026-10-19 08:00")
                self.assertEqual(run["next"]["lb"], {"en": "Year-dated point", "zh": "带年份的点"}[lang])
                self.assertEqual(len(run["nextItems"]), 3)
                # in time order: the year-dated point, the one under the dated group (not read as month 26), the last one
                self.assertTrue(run["nextItems"][0].startswith("2026-10-19 08:00"), run["nextItems"])
                self.assertTrue(run["nextItems"][1].startswith("09:30"), run["nextItems"])
                self.assertTrue(run["nextItems"][2].startswith("11-05 18:00"), run["nextItems"])

    def test_a_use_that_is_a_property_name_is_shown_as_written(self):
        work = self.tmp / "odd-use"
        work.mkdir()
        (work / "meta.json").write_text(json.dumps({"title": "Odd use", "id": "odd-use", "lang": "en", "use": "toString"}), encoding="utf-8")
        (work / "outline.md").write_text("# R\n- A\n", encoding="utf-8")
        run = bh.run_scenario(build.build(work, no_paths=True).out, "a", chrome=CHROME, scenario=bh.TRACKING_JS)
        self.assertEqual(run["errors"], [])
        self.assertTrue(run["hmeta"].startswith("Use: toString. "), run["hmeta"])

    def test_a_quote_of_a_moved_node_still_finds_it(self):
        for lang, (_, run) in self.runs.items():
            moved = self.OUTLINES[lang][2][2]
            with self.subTest(lang=lang):
                self.assertEqual(len(run["quotes"]), 4)
                self.assertEqual(run["quotes"][0]["selected"], moved)       # old path, found by its last title
                self.assertEqual(run["quotes"][0]["toast"], "")
                self.assertEqual(run["quotes"][1]["selected"], moved)       # real path

    def test_a_title_shared_by_two_nodes_or_missing_is_not_guessed(self):
        for lang, (_, run) in self.runs.items():
            with self.subTest(lang=lang):
                for q in run["quotes"][2:]:
                    self.assertIsNone(q["selected"])
                    self.assertTrue(q["toast"], q)

    def test_the_reply_chip_and_the_badges_follow_the_moved_node(self):
        for lang, (_, run) in self.runs.items():
            moved = self.OUTLINES[lang][2][2]
            with self.subTest(lang=lang):
                self.assertEqual(run["chips"], [{"text": moved, "selected": moved}])
                self.assertIn(moved, run["badges"])


@unittest.skipUnless(CHROME, "set MIND_ATLAS_CHROME to a Chrome/Chromium/Edge executable to run the browser tests")
class StampBrowserTests(unittest.TestCase):
    """A page left open offers a refresh when its .stamp.js says there is a newer build."""

    def run_with_stamp(self, newer):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-stamp-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        work = pathlib.Path(shutil.copytree(str(EXAMPLES / "repair-cafe-en"), str(tmp / "work")))
        result = build.build(work)                      # with paths: the page knows its .stamp.js
        stamp = result.out.with_suffix(".stamp.js")
        self.assertTrue(stamp.exists())
        if newer:
            stamp.write_text('window.__MM_LATEST={"stamp_full":"2099-01-01 00:00:00"};\n', encoding="utf-8")
        return bh.run_scenario(result.out, "a", chrome=CHROME, scenario=bh.CONSOLE_JS)

    def test_a_newer_build_shows_the_refresh_button(self):
        run = self.run_with_stamp(newer=True)
        self.assertEqual(run["violations"], [])
        self.assertEqual(run["errors"], [])
        self.assertTrue(run["newverShown"])

    def test_the_same_build_shows_nothing(self):
        run = self.run_with_stamp(newer=False)
        self.assertEqual(run["violations"], [])
        self.assertFalse(run["newverShown"])


@unittest.skipUnless(CHROME, "set MIND_ATLAS_CHROME to a Chrome/Chromium/Edge executable to run the browser tests")
class PullFeedbackBrowserTests(unittest.TestCase):
    """pull_feedback.py against a LevelDB that a real browser wrote."""

    def test_feedback_stored_by_the_page_in_a_real_browser_can_be_pulled(self):
        import time
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-pull-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        items = [{"id": "F1017-101500-ab", "ts": "2026-10-17 10:15:00", "text": "ladders? " + "x" * 3000 + " 中文",
                  "quotes": [{"p": ["Root", "A"], "x": ""}], "ctx": None, "sent": None, "replaces": None},
                 {"id": "F1017-101600-cd", "ts": "2026-10-17 10:16:00", "text": "second", "quotes": [], "ctx": ["Root", "A"],
                  "sent": None, "replaces": None}]
        page = tmp / "seed.html"
        page.write_text("<!doctype html><body><script>localStorage.setItem(%s, %s); document.body.textContent = 'ok';</script></body>"
                        % (json.dumps("mm:pull-test:items"), json.dumps(json.dumps(items))), encoding="utf-8")
        profile = tmp / "profile"
        started = time.time()
        # Chrome commits localStorage to disk a few seconds after the write, so wait before stopping it
        bh.run_chrome(CHROME, page.as_uri(), ["--dump-dom"], profile=str(profile), budget_ms=3000, timeout=60,
                      done=lambda t: t.rstrip().endswith("</html>") and time.time() - started > 8)
        leveldb = profile / "Default" / "Local Storage" / "leveldb"
        self.assertTrue(leveldb.exists(), "the browser wrote no local storage")
        work = tmp / "work"
        work.mkdir()
        (work / "meta.json").write_text(json.dumps({"title": "Pull test", "id": "pull-test", "lang": "en"}), encoding="utf-8")
        (work / "outline.md").write_text("# Root\n- A\n", encoding="utf-8")
        proc = run_script("pull_feedback", work, "--leveldb", leveldb)
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0, err)
        self.assertIn("2 new", out)
        stored = [json.loads(line) for line in (work / "_fb" / "inbox.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([{k: v for k, v in r.items() if k in items[0]} for r in stored], items)


if __name__ == "__main__":
    unittest.main()
