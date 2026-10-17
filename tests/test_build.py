"""build.py end to end: page contents, languages, hostile text, files and the command line."""
import json
import os
import re
import unittest

from helpers import WorkdirCase, build, page_json, run_script, text, load_script, quiet


class PageTests(WorkdirCase):
    def test_default_language_is_chinese_and_says_so(self):
        self.write("meta.json", json.dumps({"title": "T", "id": "t"}))
        self.write("outline.md", "# Root\n- A\n")
        result = build.build(self.wd)
        html = self.html(result)
        self.assertIn('<html lang="zh-CN">', html)
        self.assertEqual(page_json(html, "meta")["lang"], "zh")
        self.assertEqual(page_json(html, "i18n")["btn_home"], "回到「{now}」")
        self.assertEqual(len(result.warnings), 1)
        self.assertIn('no "lang"', result.warnings[0])

    def test_chinese_page(self):
        html = self.html(self.build("# Root\n- A\n", lang="zh"))
        self.assertIn('<html lang="zh-CN">', html)
        self.assertEqual(page_json(html, "i18n")["btn_home"], "回到「{now}」")

    def test_english_page(self):
        html = self.html(self.build("# Root\n- A\n", lang="en"))
        self.assertIn('<html lang="en">', html)
        self.assertEqual(page_json(html, "i18n")["btn_home"], "Back to “{now}”")

    def test_unsupported_language_is_an_error(self):
        with self.assertRaises(build.BuildError) as cm:
            self.build("# Root\n- A\n", lang="fr")
        self.assertIn("unsupported", str(cm.exception))
        self.assertIn("en", str(cm.exception))

    def test_data_block_matches_the_outline(self):
        html = self.html(self.build("# Root | root note\n- A [done] | note [src: s]\n  - A1\n"))
        data = page_json(html, "data")
        self.assertEqual(data["t"], "Root")
        self.assertEqual(data["c"][0]["g"], ["done"])
        self.assertEqual(data["c"][0]["s"], "s")
        self.assertEqual(data["c"][0]["c"][0]["t"], "A1")

    def test_result_reports_counts(self):
        r = self.build("# Root\n- A\n  - A1\n    - A2\n- B\n")
        self.assertEqual((r.nodes, r.depth, r.replies, r.warnings), (5, 3, 0, []))

    def test_meta_fields_reach_the_page(self):
        html = self.html(self.build("# R\n- A\n", id="x1", level="L2", desc="Some description.", search_hint="try: foo"))
        meta = page_json(html, "meta")
        self.assertEqual((meta["id"], meta["level"], meta["desc"], meta["search_hint"]), ("x1", "L2", "Some description.", "try: foo"))

    def test_id_defaults_to_the_title(self):
        self.write_meta(title="My title")
        (self.wd / "outline.md").write_text("# R\n- A\n", encoding="utf-8")
        meta = json.loads((self.wd / "meta.json").read_text(encoding="utf-8"))
        del meta["id"]
        (self.wd / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        html = self.html(build.build(self.wd))
        self.assertEqual(page_json(html, "meta")["id"], "My title")

    def test_page_has_no_external_references(self):
        html = self.html(self.build("# R\n- A\n"))
        self.assertNotRegex(html, r'(src|href)="https?://')
        self.assertIn("default-src 'none'", html)   # content security policy: nothing may load or connect

    def test_no_paths_leaves_local_paths_out(self):
        meta = page_json(self.html(self.build("# R\n- A\n", no_paths=True)), "meta")
        self.assertNotIn("file", meta)
        self.assertNotIn("reply_cmd", meta)

    def test_paths_are_embedded_by_default(self):
        r = self.build("# R\n- A\n")
        meta = page_json(self.html(r), "meta")
        self.assertEqual(meta["file"], str(r.out))
        self.assertIn("reply.py", meta["reply_cmd"])
        self.assertIn(str(self.wd), meta["reply_cmd"])

    def test_reply_command_placeholders_follow_the_language(self):
        zh = page_json(self.html(self.build("# R\n- A\n", lang="zh")), "meta")["reply_cmd"]
        en = page_json(self.html(self.build("# R\n- A\n", lang="en")), "meta")["reply_cmd"]
        self.assertTrue(zh.endswith('<编号> "细节" --summary "一句结论" --status 已做 --orig "用户原话"'))
        self.assertTrue(en.endswith('<id> "details" --summary "one-line conclusion" --status done --orig "the user\'s words"'))

    def test_builds_are_reproducible(self):
        old = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1792000000"
        try:
            first = self.html(self.build("# R\n- A\n"))
            second = self.html(build.build(self.wd))
        finally:
            if old is None:
                del os.environ["SOURCE_DATE_EPOCH"]
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old
        self.assertEqual(first, second)
        self.assertEqual(page_json(first, "meta")["stamp"], "2026-10-14 17:46")   # UTC


class HostileTextTests(WorkdirCase):
    """Text that looks like template placeholders or markup must reach the page unchanged."""

    PLACEHOLDERS = ["{{TITLE}}", "{{HTMLLANG}}", "/*DATA*/", "/*META*/", "/*REPLIES*/", "/*I18N*/", "/*KNOWN*/", "{{CSP}}"]

    def test_placeholders_in_the_outline_are_not_substituted_twice(self):
        hostile = " ".join(self.PLACEHOLDERS)
        outline = "# Root %s | note %s\n- Node %s | more %s\n" % (hostile, hostile, hostile, hostile)
        html = self.html(self.build(outline, title="Title " + hostile, desc="Desc " + hostile, level="Lv " + hostile))
        data = page_json(html, "data")
        self.assertEqual(data["t"], "Root " + hostile)
        self.assertEqual(data["n"], "note " + hostile)
        self.assertEqual(data["c"][0]["t"], "Node " + hostile)
        self.assertEqual(data["c"][0]["n"], "more " + hostile)
        meta = page_json(html, "meta")
        self.assertEqual((meta["title"], meta["desc"], meta["level"]), ("Title " + hostile, "Desc " + hostile, "Lv " + hostile))
        self.assertEqual(page_json(html, "i18n")["btn_home"], "Back to “{now}”")   # the I18N block itself is intact
        self.assertEqual(page_json(html, "replies"), [])
        self.assertIn("<title>Title %s</title>" % hostile, html)
        self.assertIn("<h1>Title %s</h1>" % hostile, html)

    def test_markup_cannot_break_out_of_the_data_block(self):
        nasty = '</script><script>alert(1)</script> <!-- x --> & "quotes" \u2028 \u2029 </SCRIPT>'
        html = self.html(self.build("# Root | %s\n- %s | %s\n" % (nasty, nasty, nasty), title="<b>t</b> & \"q\""))
        plain = self.html(self.build("# Root\n- A\n", title="plain"))
        self.assertEqual(html.lower().count("</script>"), plain.lower().count("</script>"))
        data = page_json(html, "data")
        self.assertEqual(data["n"], nasty)
        self.assertEqual(data["c"][0]["t"], nasty.strip().split(" | ")[0])
        self.assertIn("<title>&lt;b&gt;t&lt;/b&gt; &amp; &quot;q&quot;</title>", html)

    def test_chinese_text_survives(self):
        html = self.html(self.build("# 根 ｜ 说明 〔来源〕\n- 子 【在用】\n"))
        data = page_json(html, "data")
        self.assertEqual((data["t"], data["n"], data["s"], data["c"][0]["g"]), ("根", "说明", "来源", ["active"]))


class FileTests(WorkdirCase):
    def test_parts_are_joined_and_outline_md_is_written(self):
        self.write("a.md", "# R\n- A\n")
        self.write("b.md", "  - A1\n- B\n")
        self.write_meta(parts=["a.md", "b.md"])
        r = build.build(self.wd)
        self.assertEqual(r.nodes, 4)
        self.assertEqual((self.wd / "outline.md").read_bytes(), b"# R\n- A\n  - A1\n- B\n")

    def test_missing_part_is_a_warning_and_the_page_is_still_built(self):
        self.write("a.md", "# R\n- A\n")
        self.write_meta(parts=["a.md", "gone.md"])
        r = build.build(self.wd)
        self.assertEqual(r.nodes, 2)
        self.assertTrue(any("missing part: gone.md" in w for w in r.warnings))

    def test_errors_in_a_part_name_the_file_and_line(self):
        self.write("a.md", "# R\n- A\n")
        self.write("b.md", "- ok\n   - odd indent\n")
        self.write_meta(parts=["a.md", "b.md"])
        with self.assertRaises(build.BuildError) as cm:
            build.build(self.wd)
        self.assertIn("b.md:2", str(cm.exception))

    def test_parts_must_stay_inside_the_work_directory(self):
        (self.tmp / "outside.md").write_text("# R\n- A\n", encoding="utf-8")
        self.write_meta(parts=["../outside.md"])
        with self.assertRaises(build.BuildError) as cm:
            build.build(self.wd)
        self.assertIn("outside the work directory", str(cm.exception))

    def test_outline_md_cannot_be_a_part_of_itself(self):
        self.write("outline.md", "# R\n- A\n")
        self.write_meta(parts=["outline.md"])
        with self.assertRaises(build.BuildError) as cm:
            build.build(self.wd)
        self.assertIn("must not list outline.md", str(cm.exception))

    def test_outline_md_is_used_when_there_are_no_parts(self):
        r = self.build("# R\n- A\n- B\n")
        self.assertEqual(r.nodes, 3)

    def test_missing_outline_is_a_clear_error(self):
        self.write_meta()
        with self.assertRaises(build.BuildError) as cm:
            build.build(self.wd)
        self.assertIn("no outline", str(cm.exception))

    def test_missing_or_broken_meta(self):
        with self.assertRaises(build.BuildError):
            build.build(self.wd)
        self.write("meta.json", "{not json")
        with self.assertRaises(build.BuildError) as cm:
            build.build(self.wd)
        self.assertIn("not valid JSON", str(cm.exception))
        self.write("meta.json", json.dumps({"id": "x"}))
        with self.assertRaises(build.BuildError) as cm:
            build.build(self.wd)
        self.assertIn("title", str(cm.exception))

    def test_unknown_meta_field_is_a_warning(self):
        r = self.build("# R\n- A\n", levle="L2")
        self.assertTrue(any("unknown meta.json field 'levle'" in w for w in r.warnings))

    def test_bom_and_crlf_files_are_accepted(self):
        self.write("meta.json", b"\xef\xbb\xbf" + json.dumps({"title": "T"}).encode("utf-8"), binary=True)
        self.write("outline.md", b"\xef\xbb\xbf# R\r\n- A\r\n  - A1\r\n", binary=True)
        self.assertEqual(build.build(self.wd).nodes, 3)

    def test_output_file_name(self):
        self.assertEqual(self.build("# R\n- A\n", title="Plain title").out.name, "Plain title.html")
        self.assertEqual(self.build("# R\n- A\n", title='A/B: "C"?').out.name, "A-B- -C--.html")
        self.assertEqual(self.build("# R\n- A\n", out="custom.html").out.name, "custom.html")

    def test_out_must_be_a_plain_file_name(self):
        for bad in ("../x.html", "sub/x.html", "..", "/abs.html"):
            with self.assertRaises(build.BuildError, msg=bad):
                self.build("# R\n- A\n", out=bad)

    def test_html_is_written_with_lf_line_endings(self):
        raw = self.build("# R\n- A\n").out.read_bytes()
        self.assertNotIn(b"\r\n", raw)

    def test_replies_are_embedded(self):
        self.write("replies.json", json.dumps([{"id": "F1", "ts": "2026-10-16 10:00:00", "text": "hello", "orig": "o"}]))
        r = self.build("# R\n- A\n")
        self.assertEqual(r.replies, 1)
        self.assertEqual(page_json(self.html(r), "replies")[0]["text"], "hello")

    def test_broken_replies_file_is_a_clear_error(self):
        self.write("replies.json", '{"id": "F1"}')
        with self.assertRaises(build.BuildError) as cm:
            self.build("# R\n- A\n")
        self.assertIn("replies.json", str(cm.exception))


class CommandLineTests(WorkdirCase):
    def test_success_prints_a_summary(self):
        self.write_meta()
        self.write("outline.md", "# R\n- A\n")
        proc = run_script("build", self.wd)
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0, err)
        self.assertRegex(out, r"Wrote .*Test map\.html: 2 nodes, deepest level 1, \d+ KB, 0 replies")
        self.assertIn("\n  A (1 nodes)", out)   # one line per first-level branch
        self.assertEqual(err, "")

    def test_errors_exit_with_status_1(self):
        self.write_meta()
        self.write("outline.md", "# R\n- A\n   - odd\n")
        proc = run_script("build", self.wd)
        out, err = text(proc)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("error: outline.md:3", err)

    def test_warnings_go_to_stderr_and_do_not_fail(self):
        self.write_meta()
        self.write("outline.md", "# R\n- 截断了…\n")
        proc = run_script("build", self.wd)
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("WARNING: an ellipsis", err)

    def test_a_console_that_cannot_print_chinese_does_not_crash(self):
        self.write_meta()
        self.write("outline.md", "# 根\n- 截断了…\n")
        proc = run_script("build", self.wd, env={"PYTHONIOENCODING": "ascii", "PYTHONUTF8": "0"})
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_usage_without_arguments(self):
        proc = run_script("build")
        self.assertNotEqual(proc.returncode, 0)

    def test_no_paths_flag(self):
        self.write_meta()
        self.write("outline.md", "# R\n- A\n")
        proc = run_script("build", self.wd, "--no-paths")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        meta = page_json(next(self.wd.glob("*.html")).read_text(encoding="utf-8"), "meta")
        self.assertNotIn("reply_cmd", meta)
        self.assertNotIn("file", meta)


if __name__ == "__main__":
    unittest.main()
