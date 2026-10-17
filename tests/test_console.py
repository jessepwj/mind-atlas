"""The long-running console (v1.1): the needs-you tag, root_key and now, fingerprints, structured replies,
embedded feedback, the .stamp.js file and the content-security policy."""
import json
import os
import re
import unittest

from helpers import SCRIPTS, WorkdirCase, build, load_script, page_json, run_script, text

reply = load_script("reply")

OUTLINE = """# Atlas {{updated}} | root note
- Now | what is going on
  - Pick a date [needs-you] | two options
  - Buy a tool [needs you]
  - Order paint [in progress]
  - Hall booking [waiting]
- Rules
  - Be kind [decided]
- Other | note
  - Be kind
"""


class NeedsYouTagTests(unittest.TestCase):
    def parse(self, line):
        root, _ = build.parse_outline([("t", 1, "# R"), ("t", 2, line)])
        return root["c"][0]

    def test_all_spellings_give_the_same_key(self):
        for spelling in ("[needs-you]", "[NEEDS-YOU]", "[Needs-You]", "[needs you]", "【要你定】"):
            with self.subTest(spelling=spelling):
                self.assertEqual(self.parse("- A %s | note" % spelling)["g"], ["needs-you"])

    def test_the_tag_is_removed_from_the_text(self):
        node = self.parse("- Pick a date [NEEDS-YOU] | two options")
        self.assertEqual((node["t"], node["n"]), ("Pick a date", "two options"))

    def test_it_combines_with_other_tags(self):
        self.assertEqual(self.parse("- A [needs-you] [in progress]")["g"], ["needs-you", "doing"])

    def test_an_escaped_tag_stays_literal_text(self):
        self.assertEqual(self.parse("- A \\[needs-you] is a tag")["g"], [])

    def test_both_languages_know_the_same_keys(self):
        self.assertEqual(set(build.TAGS_ZH.values()), set(build.TAGS_EN.values()))
        self.assertIn("needs-you", set(build.TAGS_ZH.values()))
        self.assertEqual(build.TAGS_ZH["要你定"], "needs-you")


class FingerprintTests(unittest.TestCase):
    def test_changes_with_title_tags_or_note(self):
        base = build.fingerprint("A", ["done"], "note")
        self.assertRegex(base, r"^[0-9a-f]{8}$")
        self.assertEqual(base, build.fingerprint("A", ["done"], "note"))
        for changed in (build.fingerprint("B", ["done"], "note"), build.fingerprint("A", ["todo"], "note"),
                        build.fingerprint("A", ["done"], "note."), build.fingerprint("A", [], "note")):
            self.assertNotEqual(base, changed)

    def test_tag_order_does_not_matter(self):
        self.assertEqual(build.fingerprint("A", ["done", "risk"], ""), build.fingerprint("A", ["risk", "done"], ""))

    def test_fields_cannot_blur_into_each_other(self):
        self.assertNotEqual(build.fingerprint("ab", [], "c"), build.fingerprint("a", [], "bc"))

    def test_annotate_names_the_root_by_root_key_and_builds_paths(self):
        root, _ = build.parse_outline([("t", i, ln) for i, ln in enumerate(OUTLINE.splitlines(), 1)])
        keys = build.annotate(root, "Atlas")
        self.assertIn("Atlas", keys)
        self.assertIn("Atlas › Now › Pick a date", keys)
        self.assertEqual(root["k"], "Atlas")
        self.assertTrue(all(len(n["f"]) == 8 for n in keys.values()))

    def test_a_changing_root_title_keeps_every_fingerprint(self):
        def prints(title):
            root, _ = build.parse_outline([("t", 1, "# " + title), ("t", 2, "- A [done] | n"), ("t", 3, "  - A1")])
            build.annotate(root, "Atlas")
            return [n["f"] for n, _, _ in build.walk(root)]

        self.assertEqual(prints("Atlas, updated 10-17 09:00"), prints("Atlas, updated 10-18 21:30"))


class ResolveNodeTests(unittest.TestCase):
    def setUp(self):
        root, _ = build.parse_outline([("t", i, ln) for i, ln in enumerate(OUTLINE.splitlines(), 1)])
        self.keys = build.annotate(root, "Atlas")

    def resolve(self, spec):
        return build.resolve_node(spec, self.keys, "Atlas")

    def test_full_path(self):
        self.assertEqual(self.resolve("Atlas › Now › Pick a date"), ("Atlas › Now › Pick a date", ""))

    def test_root_may_be_left_out(self):
        self.assertEqual(self.resolve("Now › Pick a date")[0], "Atlas › Now › Pick a date")

    def test_ascii_separator_works_too(self):
        self.assertEqual(self.resolve("Now > Pick a date")[0], "Atlas › Now › Pick a date")

    def test_a_unique_title_is_enough(self):
        self.assertEqual(self.resolve("Order paint")[0], "Atlas › Now › Order paint")

    def test_a_unique_word_inside_a_title_is_enough(self):
        self.assertEqual(self.resolve("paint")[0], "Atlas › Now › Order paint")

    def test_ambiguous_titles_are_refused(self):
        path, why = self.resolve("Be kind")
        self.assertIsNone(path)
        self.assertIn("write a longer path", why)

    def test_longer_path_resolves_the_ambiguity(self):
        self.assertEqual(self.resolve("Rules › Be kind")[0], "Atlas › Rules › Be kind")

    def test_unknown_nodes_are_reported(self):
        self.assertEqual(self.resolve("No such node"), (None, "not found in the map"))
        self.assertEqual(self.resolve("   ")[0], None)


class ConsoleBuildTests(WorkdirCase):
    def test_meta_fields_reach_the_page_without_a_warning(self):
        result = self.build(OUTLINE, id="atlas", root_key="Atlas", now="Now")
        self.assertEqual(result.warnings, [])
        meta = page_json(self.html(result), "meta")
        self.assertEqual((meta["root_key"], meta["now"]), ("Atlas", "Now"))
        self.assertEqual(meta["statuses"], ["done", "doing", "planned", "dropped", "needs-you"])
        self.assertRegex(meta["stamp_full"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_root_key_defaults_to_the_root_title(self):
        meta = page_json(self.html(self.build("# Root title\n- A\n")), "meta")
        self.assertEqual(meta["root_key"], "Root title")
        self.assertEqual(meta["now"], "")

    def test_a_now_branch_that_does_not_exist_is_a_warning(self):
        result = self.build("# R\n- A\n", now="Nope")
        self.assertTrue(any("Nope" in w and "first-level" in w for w in result.warnings), result.warnings)

    def test_root_key_and_now_must_be_strings(self):
        for field in ("root_key", "now"):
            with self.subTest(field=field), self.assertRaises(build.BuildError):
                self.build("# R\n- A\n", **{field: 5})

    def test_updated_placeholder_in_the_root_title_is_replaced_in_each_language(self):
        os.environ["SOURCE_DATE_EPOCH"] = "1792000000"
        self.addCleanup(os.environ.pop, "SOURCE_DATE_EPOCH", None)
        en = page_json(self.html(self.build("# Atlas ({{updated}})\n- A\n", lang="en", root_key="Atlas")), "data")
        zh = page_json(self.html(self.build("# 图（{{更新}}）\n- A\n", lang="zh", root_key="图")), "data")
        self.assertEqual(en["t"], "Atlas (updated 10-14 17:46)")
        self.assertEqual(zh["t"], "图（10-14 17:46 更新）")

    def test_both_placeholder_spellings_work_in_both_languages(self):
        os.environ["SOURCE_DATE_EPOCH"] = "1792000000"
        self.addCleanup(os.environ.pop, "SOURCE_DATE_EPOCH", None)
        data = page_json(self.html(self.build("# A {{更新}} B {{updated}}\n- A\n", lang="en")), "data")
        self.assertEqual(data["t"], "A updated 10-14 17:46 B updated 10-14 17:46")

    def test_nodes_carry_fingerprints_that_survive_a_new_root_title(self):
        first = page_json(self.html(self.build("# Atlas {{updated}}\n- A [done] | n\n", root_key="Atlas")), "data")
        os.environ["SOURCE_DATE_EPOCH"] = "1792000000"
        self.addCleanup(os.environ.pop, "SOURCE_DATE_EPOCH", None)
        second = page_json(self.html(self.build("# Atlas {{updated}}\n- A [done] | n\n", root_key="Atlas")), "data")
        self.assertNotEqual(first["t"], second["t"])
        self.assertEqual(first["f"], second["f"])
        self.assertEqual(first["c"][0]["f"], second["c"][0]["f"])
        self.assertNotIn("k", first)           # the full paths are only used while building

    def test_an_edited_note_changes_only_that_fingerprint(self):
        a = page_json(self.html(self.build("# R\n- A | one\n- B | two\n", root_key="R")), "data")
        b = page_json(self.html(self.build("# R\n- A | one\n- B | two, edited\n", root_key="R")), "data")
        self.assertEqual(a["f"], b["f"])
        self.assertEqual(a["c"][0]["f"], b["c"][0]["f"])
        self.assertNotEqual(a["c"][1]["f"], b["c"][1]["f"])

    def test_the_summary_line_counts_the_console_items(self):
        r = self.build(OUTLINE)
        self.assertEqual(r.tagged, {"needs-you": 2, "doing": 1, "waiting": 1})
        proc = run_script("build", self.wd)
        self.assertIn("tagged: 2 needs-you, 1 in progress, 1 waiting", text(proc)[0])


class StampAndPolicyTests(WorkdirCase):
    def test_a_stamp_file_is_written_beside_the_page(self):
        r = self.build("# R\n- A\n")
        stamp = r.out.with_suffix(".stamp.js")
        body = stamp.read_text(encoding="utf-8")
        self.assertTrue(body.startswith("window.__MM_LATEST="))
        latest = json.loads(body[len("window.__MM_LATEST="):].rstrip(";\n"))
        meta = page_json(self.html(r), "meta")
        self.assertEqual(latest, {"stamp_full": meta["stamp_full"]})
        self.assertEqual(meta["stamp_js"], stamp.name)

    def test_no_paths_writes_no_stamp_file_and_no_reference_to_it(self):
        r = self.build("# R\n- A\n", no_paths=True)
        self.assertFalse(r.out.with_suffix(".stamp.js").exists())
        self.assertNotIn("stamp_js", page_json(self.html(r), "meta"))

    def test_the_policy_allows_the_stamp_script_only_for_a_local_page(self):
        local = self.html(self.build("# R\n- A\n"))
        shared = self.html(self.build("# R\n- A\n", no_paths=True))
        self.assertIn("script-src 'unsafe-inline' file:", local)
        self.assertIn("script-src 'unsafe-inline';", shared)
        for html in (local, shared):
            self.assertIn("default-src 'none'", html)
            self.assertNotIn("connect-src", html)

    def test_the_stamp_changes_with_the_build_time(self):
        os.environ["SOURCE_DATE_EPOCH"] = "1792000000"
        self.addCleanup(os.environ.pop, "SOURCE_DATE_EPOCH", None)
        first = self.build("# R\n- A\n").out.with_suffix(".stamp.js").read_text(encoding="utf-8")
        os.environ["SOURCE_DATE_EPOCH"] = "1792000100"
        second = self.build("# R\n- A\n").out.with_suffix(".stamp.js").read_text(encoding="utf-8")
        self.assertNotEqual(first, second)
        self.assertIn("2026-10-14 17:46:40", first)


class ReplyFieldTests(WorkdirCase):
    OUT = "# Atlas\n- Now\n  - Pick a date [needs-you]\n  - Other\n"

    def setUp(self):
        super().setUp()
        self.write_meta(lang="en", root_key="Atlas")
        self.write("outline.md", self.OUT)

    def stored(self):
        return json.loads((self.wd / "replies.json").read_text(encoding="utf-8"))

    def page_replies(self):
        return page_json(next(self.wd.glob("*.html")).read_text(encoding="utf-8"), "replies")

    def test_structured_reply_is_stored_and_resolved_on_the_page(self):
        proc = run_script("reply", self.wd, "F1", "Long details here.", "--summary", "Decided: the 19th.",
                          "--status", "needs-you", "--node", "Pick a date", "--ask", "Is the 19th fine?", "--orig", "when?")
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0, err)
        self.assertIn("Replied to F1 (needs-you)", out)
        rec = self.stored()[0]
        self.assertEqual((rec["summary"], rec["status"], rec["nodes"], rec["ask"], rec["orig"]),
                         ("Decided: the 19th.", "needs-you", ["Pick a date"], "Is the 19th fine?", "when?"))
        shown = self.page_replies()[0]
        self.assertEqual(shown["nodes"], ["Atlas › Now › Pick a date"])
        self.assertEqual(shown["status"], "needs-you")
        self.assertRegex(shown["rid"], r"^[0-9a-f]{10}$")
        self.assertNotIn("WARNING", err)

    def test_summary_alone_is_enough(self):
        proc = run_script("reply", self.wd, "F2", "--summary", "Done, thanks.", "--status", "done")
        self.assertEqual(proc.returncode, 0, text(proc)[1])
        self.assertEqual(self.stored()[0]["text"], "")
        self.assertNotIn("nodes", self.stored()[0])
        self.assertNotIn("ask", self.stored()[0])

    def test_neither_text_nor_summary_is_refused(self):
        proc = run_script("reply", self.wd, "F3", "--status", "done")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--summary", text(proc)[1])
        self.assertFalse((self.wd / "replies.json").exists())

    def test_status_may_be_written_in_either_language_and_is_stored_in_english(self):
        for spelling, key in (("已做", "done"), ("在做", "doing"), ("定了待做", "planned"), ("不做", "dropped"), ("要你定", "needs-you"),
                              ("done", "done"), ("in progress", "doing"), ("Planned", "planned"), ("DROPPED", "dropped"), ("needs you", "needs-you")):
            with self.subTest(spelling=spelling):
                self.assertEqual(reply.normalize_status(spelling), key)

    def test_unknown_status_is_refused_with_the_valid_values(self):
        proc = run_script("reply", self.wd, "F4", "x", "--status", "finished")
        self.assertNotEqual(proc.returncode, 0)
        err = text(proc)[1]
        for word in ("done", "doing", "planned", "dropped", "needs-you"):
            self.assertIn(word, err)
        self.assertFalse((self.wd / "replies.json").exists())

    def test_ask_without_status_means_needs_you(self):
        run_script("reply", self.wd, "F5", "x", "--ask", "Which one?", "--node", "Pick a date")
        rec = self.stored()[0]
        self.assertEqual((rec["status"], rec["ask"]), ("needs-you", "Which one?"))

    def test_needs_you_without_ask_uses_the_summary_as_the_question(self):
        run_script("reply", self.wd, "F6", "--summary", "Pick one of the two dates.", "--status", "needs-you", "--node", "Pick a date")
        self.assertEqual(self.stored()[0]["ask"], "Pick one of the two dates.")

    def test_needs_you_without_node_warns_in_the_reply_and_the_build(self):
        proc = run_script("reply", self.wd, "F7", "x", "--status", "needs-you")
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("no --node", err)
        self.assertIn("marked needs-you but points at no node tagged [NEEDS-YOU]", err)

    def test_needs_you_pointing_at_an_untagged_node_warns_at_build_time(self):
        proc = run_script("reply", self.wd, "F8", "x", "--status", "needs-you", "--node", "Other")
        self.assertIn("points at no node tagged [NEEDS-YOU]", text(proc)[1])

    def test_node_may_be_repeated_and_unknown_nodes_warn(self):
        proc = run_script("reply", self.wd, "F9", "x", "--node", "Pick a date", "--node", "Nowhere", "--node", "Now")
        self.assertEqual(self.stored()[0]["nodes"], ["Pick a date", "Nowhere", "Now"])
        self.assertIn("node 'Nowhere': not found in the map", text(proc)[1])
        self.assertEqual(self.page_replies()[0]["nodes"], ["Atlas › Now › Pick a date", "Atlas › Now"])

    def test_no_build_only_writes_the_file(self):
        proc = run_script("reply", self.wd, "F10", "x", "--no-build")
        self.assertEqual(proc.returncode, 0, text(proc)[1])
        self.assertTrue((self.wd / "replies.json").exists())
        self.assertEqual(list(self.wd.glob("*.html")), [])
        self.assertNotIn("Wrote", text(proc)[0])

    def test_option_without_a_value_is_an_error(self):
        for option in ("--summary", "--status", "--node", "--ask", "--orig"):
            with self.subTest(option=option):
                proc = run_script("reply", self.wd, "F11", "x", option)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("needs a value", text(proc)[1])

    def test_a_chinese_status_in_a_hand_written_replies_file_is_understood_by_the_build(self):
        self.write("replies.json", json.dumps([{"id": "F12", "ts": "2026-10-16 10:00:00", "text": "t", "status": "已做"}]))
        r = build.build(self.wd)
        self.assertEqual(r.warnings, [])
        self.assertEqual(self.page_replies()[0]["status"], "done")

    def test_a_status_the_build_does_not_know_is_a_warning(self):
        self.write("replies.json", json.dumps([{"id": "F13", "ts": "2026-10-16 10:00:00", "text": "t", "status": "maybe"}]))
        self.assertTrue(any("maybe" in w for w in build.build(self.wd).warnings))

    def test_old_replies_without_the_new_fields_still_build_cleanly(self):
        self.write("replies.json", json.dumps([{"id": "F14", "ts": "2026-10-16 10:00:00", "text": "old style", "orig": "q"}]))
        r = build.build(self.wd)
        self.assertEqual(r.warnings, [])
        self.assertEqual(self.page_replies()[0]["nodes"], [])

    def test_reply_ids_are_unique_even_for_the_same_feedback_and_second(self):
        self.write("replies.json", json.dumps([{"id": "F15", "ts": "2026-10-16 10:00:00", "text": "a"},
                                               {"id": "F15", "ts": "2026-10-16 10:00:00", "text": "b"}]))
        build.build(self.wd)
        rids = [r["rid"] for r in self.page_replies()]
        self.assertEqual(len(set(rids)), 2)

    def test_both_scripts_agree_on_the_status_names(self):
        self.assertEqual(reply.STATUS_ALIASES, build.STATUS_ALIASES)
        self.assertEqual(reply.STATUSES, build.STATUSES)

    def test_add_reply_accepts_the_new_arguments(self):
        n = reply.add_reply(self.wd, "F16", "d", summary="s", status="在做", nodes=["Pick a date"], ask="")
        self.assertEqual(n, 1)
        rec = self.stored()[0]
        self.assertEqual((rec["status"], rec["summary"], rec["nodes"]), ("doing", "s", ["Pick a date"]))


class EmbeddedFeedbackTests(WorkdirCase):
    def known(self, html):
        return page_json(html, "known")

    def test_known_json_and_inbox_are_embedded_and_trimmed_to_the_known_fields(self):
        self.write_meta()
        self.write("outline.md", "# R\n- A\n")
        self.write("_fb/known.json", json.dumps([{"id": "F1", "ts": "t1", "text": "one", "secret": "x", "sent": "t"}]))
        self.write("_fb/inbox.jsonl", json.dumps({"id": "F2", "ts": "t2", "text": "two", "pulled_at": "now", "source": "chrome"})
                   + "\n\nnot json\n" + json.dumps({"no": "id"}) + "\n")
        r = build.build(self.wd)
        known = self.known(r.out.read_text(encoding="utf-8"))
        self.assertEqual(sorted(known), ["F1", "F2"])
        self.assertEqual(known["F1"], {"id": "F1", "ts": "t1", "text": "one"})
        self.assertEqual(known["F2"], {"id": "F2", "ts": "t2", "text": "two"})
        self.assertEqual(r.known, 2)

    def test_the_inbox_wins_over_known_for_the_same_id(self):
        self.write_meta()
        self.write("outline.md", "# R\n- A\n")
        self.write("_fb/known.json", json.dumps([{"id": "F1", "text": "old"}]))
        self.write("_fb/inbox.jsonl", json.dumps({"id": "F1", "text": "new"}) + "\n")
        known = self.known(build.build(self.wd).out.read_text(encoding="utf-8"))
        self.assertEqual(known["F1"]["text"], "new")

    def test_without_a_feedback_folder_the_block_is_an_empty_object(self):
        self.assertEqual(self.known(self.html(self.build("# R\n- A\n"))), {})

    def test_known_json_must_be_a_list(self):
        self.write_meta()
        self.write("outline.md", "# R\n- A\n")
        self.write("_fb/known.json", "{}")
        with self.assertRaises(build.BuildError):
            build.build(self.wd)

    def test_markup_in_embedded_feedback_cannot_break_the_page(self):
        self.write_meta()
        self.write("outline.md", "# R\n- A\n")
        self.write("_fb/inbox.jsonl", json.dumps({"id": "F1", "text": "</script><script>alert(1)</script>"}) + "\n")
        html = build.build(self.wd).out.read_text(encoding="utf-8")
        plain = self.html(self.build("# R\n- A\n"))
        self.assertEqual(html.lower().count("</script>"), plain.lower().count("</script>"))
        self.assertEqual(self.known(html)["F1"]["text"], "</script><script>alert(1)</script>")


class TemplateContractTests(unittest.TestCase):
    """The page script and the build script must agree on names."""

    TEMPLATE = (SCRIPTS / "template.html").read_text(encoding="utf-8")

    def test_the_page_script_has_no_chinese_status_names(self):
        for word in ("要你定", "进行中", "等别人", "已做"):
            self.assertNotIn(word, self.TEMPLATE)

    def test_the_page_reads_every_new_meta_field(self):
        for field in ("META.root_key", "META.now", "META.stamp_js", "META.stamp_full"):
            self.assertIn(field, self.TEMPLATE)

    def test_the_page_embeds_the_known_feedback_block(self):
        self.assertIn('<script id="known" type="application/json">/*KNOWN*/</script>', self.TEMPLATE)

    def test_every_status_the_page_styles_is_one_the_build_writes(self):
        styled = set(re.findall(r"\.st-([a-z-]+)\{", self.TEMPLATE))
        self.assertEqual(styled, set(build.STATUSES) | {"pending"})

    def test_every_tag_the_build_knows_is_styled(self):
        styled = set()
        for group in re.findall(r"((?:\.tag-[a-z-]+,?)+)\{", self.TEMPLATE):
            styled |= set(re.findall(r"\.tag-([a-z-]+)", group))
        self.assertEqual(styled, set(build.TAGS_ZH.values()))


if __name__ == "__main__":
    unittest.main()
