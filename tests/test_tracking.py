"""Project-tracking maps (v1.2): the "use" field, the "Now" branch check, nodes that moved but kept their title."""
import datetime
import json
import os
import unittest

from helpers import WorkdirCase, build, page_json, run_script, text

NOW = datetime.datetime(2026, 10, 18, 12, 0)       # a Sunday noon; every date in the fixtures is relative to it
NOW_EPOCH = 1792324800                              # the same moment in UTC, for SOURCE_DATE_EPOCH


def parse(outline):
    root, _ = build.parse_outline([("t", i, ln) for i, ln in enumerate(outline.strip("\n").splitlines(), 1)])
    return root


def stale(outline, at=NOW, **meta):
    """Messages of check_now at the moment `at` for an outline whose "now" branch is called Now (or whatever `now` says)."""
    meta.setdefault("now", "Now")
    return build.check_now(parse(outline), meta, at)


EN = """
# Atlas
- Now
  - Needs you
    - Pick the venue [needs-you] | two halls
  - In progress
    - Print flyers [in progress]
  - Waiting on others
    - Hall confirms the booking [waiting]
  - Problems and risks
    - Only one multimeter [risk]
  - Next up
    - 10-19 05:00 Switch the proxy back
    - 11-05 18:00 Committee meeting
  - Later
    - Winter plan [todo] | waits for the date
  - Recently done
    - 10-18
      - Flyers delivered [done]
    - 10-17
      - Guide pinned [done]
- History
  - 10-16
    - Kick-off [done]
"""

ZH = """
# 图
- 现在
  - 要你定的
    - 选场地 【要你定】
  - 在做的
    - 印传单 【进行中】
  - 在等别人的
    - 礼堂确认 【等别人】
  - 问题和风险
    - 万用表只有一只 【风险】
  - 接下来的时间点
    - 10-19 05:00 切回旧站
    - 11-05 18:00 开会
  - 以后再做
    - 冬季计划 【待做】
  - 最近做完的
    - 10-18
      - 传单已投 【已完成】
    - 10-17
      - 指南已贴 【已完成】
- 历程
  - 10-16
"""


class LeadWhenTests(unittest.TestCase):
    TODAY = datetime.date(2026, 10, 18)

    def lead(self, title, today=None):
        return build.lead_when(title, today or self.TODAY)

    def test_date_and_time(self):
        self.assertEqual(self.lead("10-19 05:00 Switch"), (datetime.date(2026, 10, 19), 5, 0))
        self.assertEqual(self.lead("1-5 9:30 Early"), (datetime.date(2027, 1, 5), 9, 30))     # the year nearest to today

    def test_date_alone(self):
        self.assertEqual(self.lead("10-19 Switch"), (datetime.date(2026, 10, 19), None, None))
        self.assertEqual(self.lead("10-19"), (datetime.date(2026, 10, 19), None, None))

    def test_a_year_may_be_written(self):
        self.assertEqual(self.lead("2026-11-05 18:00 Meeting"), (datetime.date(2026, 11, 5), 18, 0))
        self.assertEqual(self.lead("2027-03-01"), (datetime.date(2027, 3, 1), None, None))

    def test_a_full_width_colon_is_read_as_a_colon(self):
        self.assertEqual(self.lead("10-19 05：00 切回旧站"), (datetime.date(2026, 10, 19), 5, 0))
        self.assertEqual(self.lead("18：30 开会"), (None, 18, 30))

    def test_a_time_alone(self):
        self.assertEqual(self.lead("18:00 Meeting"), (None, 18, 0))

    def test_a_weekday_may_sit_between_date_and_time(self):
        self.assertEqual(self.lead("10-19 Mon 05:00 x"), (datetime.date(2026, 10, 19), 5, 0))
        self.assertEqual(self.lead("10-19 周一 05:00 x"), (datetime.date(2026, 10, 19), 5, 0))

    def test_text_that_only_looks_like_a_date_is_not_one(self):
        for title in ("Switch the proxy", "Version 1.2 ships", "100-200 items", "13-40 oops", "24:00 x"):
            with self.subTest(title=title):
                self.assertEqual(self.lead(title)[0], None)
        self.assertEqual(self.lead("24:00 x"), (None, None, None))

    def test_the_year_follows_the_calendar_across_new_year(self):
        self.assertEqual(self.lead("01-03", datetime.date(2026, 12, 30))[0], datetime.date(2027, 1, 3))
        self.assertEqual(self.lead("12-30", datetime.date(2027, 1, 2))[0], datetime.date(2026, 12, 30))

    def test_a_leap_day_and_an_impossible_date(self):
        self.assertEqual(self.lead("02-29", datetime.date(2028, 2, 1))[0], datetime.date(2028, 2, 29))
        self.assertEqual(self.lead("02-30"), (None, None, None))


class RelativeWordsTests(unittest.TestCase):
    def test_both_languages(self):
        for title in ("今天要做的", "明天上线", "昨天改完", "今晚切换", "明早开会", "Do it today", "Tomorrow's call", "Yesterday it broke",
                      "Switch tonight", "Ready this afternoon", "Fixed last night"):
            with self.subTest(title=title):
                self.assertTrue(build.REL_DAY.search(title))

    def test_chinese_words_inside_other_words_do_not_match(self):
        for title in ("说明早期方案", "统计落后天数", "提前天数的算法", "10-19 05:00 切回旧站"):
            with self.subTest(title=title):
                self.assertFalse(build.REL_DAY.search(title))
        for title in ("后天上线", "要在前天补完", "明早开会"):
            with self.subTest(title=title):
                self.assertTrue(build.REL_DAY.search(title))

    def test_ordinary_words_do_not_match(self):
        for title in ("Todays", "Intoday", "10-19 05:00 切回旧站", "Festival tickets", "Moon phase"):
            with self.subTest(title=title):
                self.assertFalse(build.REL_DAY.search(title))


class CleanMapTests(unittest.TestCase):
    def test_a_current_english_map_has_nothing_to_report(self):
        self.assertEqual(stale(EN), [])

    def test_a_current_chinese_map_has_nothing_to_report(self):
        self.assertEqual(stale(ZH, now="现在"), [])

    def test_a_map_without_a_now_branch_is_not_checked(self):
        self.assertEqual(build.check_now(parse(EN), {}, NOW), [])
        self.assertEqual(build.check_now(parse(EN), {"now": "Nowhere"}, NOW), [])


class TimePointTests(unittest.TestCase):
    def sec(self, *points):
        return "# R\n- Now\n  - Next up\n" + "".join("    - %s\n" % p for p in points)

    def test_a_point_that_has_passed_is_reported(self):
        out = stale(self.sec("10-18 09:00 Call the hall"))
        self.assertEqual(len(out), 1)
        self.assertIn("Next up › 10-18 09:00 Call the hall", out[0])
        self.assertIn("has passed", out[0])

    def test_less_than_half_an_hour_late_is_still_fine_and_more_is_not(self):
        self.assertEqual(stale(self.sec("10-18 11:40 Call the hall")), [])
        self.assertEqual(len(stale(self.sec("10-18 11:20 Call the hall"))), 1)

    def test_a_date_alone_falls_due_at_the_end_of_that_day(self):
        self.assertEqual(stale(self.sec("10-18 Pay the invoice")), [])
        self.assertEqual(len(stale(self.sec("10-17 Pay the invoice"))), 1)

    def test_a_future_point_and_a_year_in_the_title_are_fine(self):
        self.assertEqual(stale(self.sec("10-19 05:00 Switch", "2026-11-05 18:00 Meeting", "2027-01-10 Review")), [])
        self.assertEqual(len(stale(self.sec("2026-10-01 18:00 Meeting"))), 1)

    def test_a_point_without_a_date_is_reported(self):
        out = stale(self.sec("Switch the proxy back"))
        self.assertEqual(len(out), 1)
        self.assertIn("must start with a date", out[0])

    def test_a_time_without_a_date_is_reported(self):
        out = stale(self.sec("18:00 Committee meeting"))
        self.assertEqual(len(out), 1)
        self.assertIn("a time without a date", out[0])

    def test_a_time_under_a_dated_group_takes_the_date_of_the_group(self):
        ok = "# R\n- Now\n  - Next up\n    - 11-05\n      - 18:00 Committee meeting\n      - 19:30 Dinner\n"
        self.assertEqual(stale(ok), [])
        past = "# R\n- Now\n  - Next up\n    - 10-18\n      - 09:00 Call\n      - 20:00 Dinner\n"
        out = stale(past)
        self.assertEqual(len(out), 1)           # the group is judged by its timed children, so only the call is reported
        self.assertIn("09:00 Call", out[0])

    def test_details_under_a_dated_point_are_not_time_points(self):
        outline = "# R\n- Now\n  - Next up\n    - 10-19 05:00 Switch the proxy back\n      - edit the config\n      - restart it\n"
        self.assertEqual(stale(outline), [])

    def test_an_undated_group_is_looked_into(self):
        outline = "# R\n- Now\n  - Next up\n    - Week 45\n      - 11-05 18:00 Meeting\n      - Call the hall\n"
        out = stale(outline)
        self.assertEqual(len(out), 1)
        self.assertIn("Week 45 › Call the hall", out[0])

    def test_chinese_titles_work_the_same(self):
        out = stale("# 图\n- 现在\n  - 接下来的时间点\n    - 10-17 05:00 切回旧站\n    - 切回新站\n", now="现在")
        self.assertEqual(len(out), 2)

    def test_the_section_is_found_by_its_english_words(self):
        for title in ("Next up", "Upcoming", "Coming up", "Next steps with dates"):
            with self.subTest(title=title):
                out = stale("# R\n- Now\n  - %s\n    - No date here\n" % title)
                self.assertEqual(len(out), 1)

    def test_undated_items_under_later_are_fine(self):
        self.assertEqual(stale("# R\n- Now\n  - Later\n    - Winter plan [todo]\n"), [])


class RelativeDayCheckTests(unittest.TestCase):
    def test_a_title_with_today_or_tomorrow_is_reported_wherever_it_sits(self):
        out = stale("# R\n- Now\n  - In progress\n    - Fix the sign today [in progress]\n  - Problems and risks\n    - 明天可能断网 【风险】\n")
        self.assertEqual(len(out), 2)
        self.assertTrue(all("wrong a day later" in m for m in out))

    def test_notes_may_say_today(self):
        self.assertEqual(stale("# R\n- Now\n  - In progress\n    - Fix the sign [in progress] | started today\n"), [])

    def test_the_rest_of_the_map_is_not_looked_at(self):
        self.assertEqual(stale("# R\n- Now\n  - Next up\n    - 10-19 Go\n- Notes\n  - What we did today\n"), [])


class DoneSectionTests(unittest.TestCase):
    def done(self, *lines):
        return "# R\n- Now\n  - Recently done\n" + "".join("    %s\n" % ln for ln in lines)

    def test_more_than_ten_items_are_reported(self):
        flat = [("- Item %d [done]" % i) for i in range(11)]
        out = stale(self.done(*flat))
        self.assertEqual(len(out), 1)
        self.assertIn("11 items, more than 10", out[0])
        self.assertEqual(stale(self.done(*flat[:10])), [])

    def test_items_inside_day_groups_are_counted_not_the_groups(self):
        lines = ["- 10-18"] + ["  - Item %d" % i for i in range(6)] + ["- 10-17"] + ["  - Other %d" % i for i in range(6)]
        out = stale(self.done(*lines))
        self.assertEqual(len(out), 1)
        self.assertIn("12 items", out[0])

    def test_done_max_changes_the_limit(self):
        lines = ["- Item %d" % i for i in range(4)]
        self.assertEqual(stale(self.done(*lines)), [])
        self.assertEqual(len(stale(self.done(*lines), done_max=3)), 1)
        self.assertEqual(stale(self.done(*lines), done_max=20), [])

    def test_a_group_two_days_old_or_more_is_reported(self):
        out = stale(self.done("- 10-16", "  - Kick-off"))
        self.assertEqual(len(out), 1)
        self.assertIn("Recently done › 10-16", out[0])
        self.assertIn("two days old or more", out[0])

    def test_yesterday_and_today_stay(self):
        self.assertEqual(stale(self.done("- 10-18", "  - A", "- 10-17 evening", "  - B")), [])

    def test_a_group_title_may_carry_words_after_the_date(self):
        self.assertEqual(len(stale(self.done("- 10-15 late night", "  - A"))), 1)

    def test_unfinished_work_does_not_belong_here(self):
        out = stale(self.done("- Fix the router [done]", "- Order paint [in progress]", "- Pick a hall [needs-you] [risk]", "- 传单 【问题】"))
        self.assertEqual(len(out), 3)
        self.assertIn("[in progress]", out[0])
        self.assertIn("[needs-you] [risk]", out[1])
        self.assertIn("move it to the section it belongs to", out[0])

    def test_a_done_item_may_carry_done_and_decided(self):
        self.assertEqual(stale(self.done("- Fix the router [done]", "- Venue chosen [decided]")), [])

    def test_unfinished_items_inside_a_day_group_are_found_too(self):
        out = stale(self.done("- 10-18", "  - Fix the router [done]", "  - Still open [waiting]"))
        self.assertEqual(len(out), 1)
        self.assertIn("[waiting]", out[0])

    def test_chinese_section(self):
        lines = "# 图\n- 现在\n  - 最近做完的\n    - 10-15\n      - 旧的\n    - 还在做 【进行中】\n"
        self.assertEqual(len(stale(lines, now="现在")), 2)


class AskSectionTests(unittest.TestCase):
    def test_an_empty_needs_you_section_is_reported(self):
        out = stale("# R\n- Now\n  - Needs you\n  - In progress\n")
        self.assertEqual(len(out), 1)
        self.assertIn("nothing needs the user", out[0])

    def test_saying_that_nothing_needs_you_is_enough(self):
        self.assertEqual(stale("# R\n- Now\n  - Needs you\n    - Nothing needs you right now\n"), [])

    def test_the_english_titles(self):
        for title in ("Needs you", "Needs your decision", "Your call", "To decide"):
            with self.subTest(title=title):
                self.assertEqual(len(stale("# R\n- Now\n  - %s\n" % title)), 1)

    def test_chinese_title(self):
        self.assertEqual(len(stale("# 图\n- 现在\n  - 要你定的\n", now="现在")), 1)


class SectionRoleTests(unittest.TestCase):
    def test_english_and_chinese_titles(self):
        cases = {
            "ask": ["Needs you", "Needs your decision", "要你定的"],
            "doing": ["In progress", "Under way", "Underway", "在做的"],
            "waiting": ["Waiting on others", "Waiting", "在等别人的", "等别人的"],
            "issues": ["Problems and risks", "Open issues", "问题和风险"],
            "next": ["Next up", "Upcoming", "Coming up", "接下来的时间点"],
            "later": ["Later", "Backlog", "以后再做"],
            "done": ["Recently done", "Done recently", "Finished", "最近做完的", "最近完成的"],
        }
        for role, titles in cases.items():
            for title in titles:
                with self.subTest(role=role, title=title):
                    self.assertEqual(build.now_role(title, None), role)

    def test_next_is_recognized_only_at_the_start_of_a_title_like_the_page_does(self):
        self.assertEqual(build.now_role("Up next", None), "")
        self.assertEqual(build.now_role("Next steps with dates", None), "next")
        self.assertEqual(build.now_role("Up next", {"next": "Up next"}), "next")

    def test_other_titles_are_nothing_in_particular(self):
        for title in ("Overview", "Contexts", "Notes", "Undone work"):
            with self.subTest(title=title):
                self.assertEqual(build.now_role(title, None), "")

    def test_now_sections_names_a_section_that_the_words_would_not_find(self):
        outline = "# R\n- Now\n  - Booked\n    - Switch the proxy back\n  - Wrapped up\n    - A\n    - B\n"
        self.assertEqual(stale(outline), [])
        out = stale(outline, now_sections={"next": "Booked", "done": "Wrapped up"}, done_max=1)
        self.assertEqual(len(out), 2)
        self.assertIn("must start with a date", out[0])
        self.assertIn("2 items, more than 1", out[1])

    def test_a_named_title_wins_over_the_words_in_it(self):
        self.assertEqual(build.now_role("Next up", {"later": "Next up"}), "later")


class OpenOutsideNowTests(unittest.TestCase):
    def find(self, outline, **meta):
        meta.setdefault("now", "Now")
        return build.open_outside_now(parse(outline), meta)

    def test_in_progress_and_waiting_outside_now_are_listed_with_their_path(self):
        found = self.find("# R\n- Now\n  - In progress\n    - A [in progress]\n- Parts\n  - Router\n    - Flash it [in progress]\n"
                          "    - Await the part [waiting]\n    - Done already [done]\n")
        self.assertEqual(found, ["Parts › Router › Flash it", "Parts › Router › Await the part"])

    def test_nodes_inside_now_are_not_listed(self):
        self.assertEqual(self.find("# R\n- Now\n  - A [in progress]\n  - B [waiting]\n- Parts\n  - C [issue]\n"), [])

    def test_a_snapshot_branch_is_skipped_in_either_language(self):
        outline = ("# R\n- Now\n- Snapshot of 10-01\n  - Old [in progress]\n- 10-02 快照\n  - 旧的 【等别人】\n"
                   "- Plan\n  - Real [in progress]\n")
        self.assertEqual(self.find(outline), ["Plan › Real"])

    def test_chinese_tags_count_too(self):
        self.assertEqual(self.find("# 图\n- 现在\n- 细节\n  - 甲 【进行中】\n  - 乙 【等别人】\n", now="现在"), ["细节 › 甲", "细节 › 乙"])


class BuildIntegrationTests(WorkdirCase):
    def setUp(self):
        super().setUp()
        os.environ["SOURCE_DATE_EPOCH"] = str(NOW_EPOCH)       # the clock stands still, so dates in the fixtures never go stale
        self.addCleanup(os.environ.pop, "SOURCE_DATE_EPOCH", None)

    def test_a_map_without_now_has_nothing_checked(self):
        r = self.build("# R\n- A [in progress]\n")
        self.assertIsNone(r.stale)
        self.assertEqual(r.open_outside, [])
        out, err = text(run_script("build", self.wd))
        self.assertNotIn("Now", out)
        self.assertEqual(err, "")

    def test_stale_findings_are_reported_but_the_page_is_still_built(self):
        outline = "# R\n- Now\n  - Next up\n    - 10-01 05:00 Switch\n  - Recently done\n    - 10-01\n      - Old\n"
        r = self.build(outline, now="Now")
        self.assertTrue(r.out.exists())
        self.assertEqual(len(r.stale), 2)
        self.assertEqual(r.warnings, [])                 # they have their own list; the page is built either way

    def test_the_clock_decides(self):
        outline = "# R\n- Now\n  - Next up\n    - 10-19 05:00 Switch\n"
        for epoch, count in ((1792000000, 0), (1792400000, 1)):      # 2026-10-14 and 2026-10-19 (UTC)
            with self.subTest(epoch=epoch):
                os.environ["SOURCE_DATE_EPOCH"] = str(epoch)
                self.addCleanup(os.environ.pop, "SOURCE_DATE_EPOCH", None)
                self.assertEqual(len(self.build(outline, now="Now").stale), count)

    def test_the_command_line_prints_warnings_and_the_open_nodes_to_stderr(self):
        self.write_meta(now="Now")
        self.write("outline.md", "# R\n- Now\n  - Needs you\n  - Next up\n    - Switch it\n- Parts\n  - Router [in progress]\n")
        proc = run_script("build", self.wd)
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0, err)
        self.assertIn('WARNING: "Now" branch is behind: "Needs you" is empty', err)
        self.assertIn('WARNING: "Now" branch is behind: "Next up › Switch it": a time point must start with a date', err)
        self.assertIn("NOTE: 1 node(s) outside the \"Now\" branch are still tagged [in progress] or [waiting]", err)
        self.assertIn("\n  Parts › Router\n", err)
        self.assertNotIn("check passed", out)

    def test_a_clean_map_says_so(self):
        self.write_meta(now="Now")
        self.write("outline.md", EN)
        proc = run_script("build", self.wd)
        out, err = text(proc)
        self.assertIn('"Now" branch check passed', out)
        self.assertNotIn("behind", err)

    def test_a_long_list_of_open_nodes_is_cut_with_a_count(self):
        self.write_meta(now="Now")
        self.write("outline.md", "# R\n- Now\n  - A\n- Parts\n" + "".join("  - Part %d [in progress]\n" % i for i in range(15)))
        err = text(run_script("build", self.wd))[1]
        self.assertIn("15 node(s) outside", err)
        self.assertIn("(and 3 more)", err)

    def test_done_max_and_now_sections_are_checked(self):
        for field, bad in (("done_max", 0), ("done_max", "10"), ("done_max", True), ("now_sections", ["next"]),
                           ("now_sections", {"next": 5})):
            with self.subTest(field=field, bad=bad), self.assertRaises(build.BuildError):
                self.build("# R\n- Now\n", now="Now", **{field: bad})

    def test_an_unknown_kind_in_now_sections_is_a_warning(self):
        r = self.build("# R\n- Now\n", now="Now", now_sections={"nxt": "Booked"})
        self.assertTrue(any("unknown kind 'nxt'" in w for w in r.warnings), r.warnings)

    def test_the_new_meta_fields_are_known(self):
        r = self.build("# R\n- Now\n  - Booked\n", now="Now", use="project tracking", done_max=5, now_sections={"next": "Booked"})
        self.assertEqual(r.warnings, [])

    def test_a_now_sections_title_that_matches_no_section_is_a_warning(self):
        r = self.build("# R\n- Now\n  - Booked\n", now="Now", now_sections={"next": "Bokked"})
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("'Bokked' is not the title of any section", r.warnings[0])

    def test_the_recognized_kinds_are_reported(self):
        self.assertEqual(self.build(EN, now="Now").now_roles, sorted(build.NOW_ROLE_KEYS))
        self.assertEqual(self.build("# R\n- Now\n  - Booked\n  - Done recently\n", now="Now").now_roles, ["done"])
        self.assertIsNone(self.build("# R\n- A\n").now_roles)
        self.assertIsNone(self.build("# R\n- A\n", now="Nowhere").now_roles)

    def test_the_command_line_does_not_say_passed_when_it_could_not_check(self):
        self.write_meta(now="Now")
        self.write("outline.md", "# R\n- Now\n  - Booked\n    - 10-01 05:00 Switch\n")
        out, err = text(run_script("build", self.wd))
        self.assertNotIn("check passed", out)
        self.assertIn('no section was recognized as Needs you, Next up, Recently done', out)
        self.assertNotIn("behind", err)               # nothing was looked at, so nothing is claimed either way

    def test_a_partly_recognized_map_names_only_what_is_missing(self):
        self.write_meta(now="Now")
        self.write("outline.md", "# R\n- Now\n  - Next up\n    - 10-19 05:00 Switch\n")
        out = text(run_script("build", self.wd))[0]
        self.assertIn("no section was recognized as Needs you, Recently done", out)
        self.assertNotIn("Next up,", out)


class UseTests(WorkdirCase):
    def meta(self, **fields):
        return page_json(self.html(self.build("# R\n- A\n", **fields)), "meta")

    def test_every_spelling_gives_one_key(self):
        spellings = {"learning": ["learning", "Learning", "学习理解", "学习"],
                     "tracking": ["project tracking", "Project Tracking", "project-tracking", "tracking", "跟进项目", "跟进"],
                     "decision": ["decision", "Decision", "deciding", "做决定", "决定"]}
        for key, words in spellings.items():
            for word in words:
                with self.subTest(use=word):
                    self.assertEqual(self.meta(use=word)["use"], key)

    def test_no_use_is_an_empty_string(self):
        self.assertEqual(self.meta()["use"], "")

    def test_known_values_give_no_warning(self):
        self.assertEqual(self.build("# R\n- A\n", use="learning").warnings, [])

    def test_another_value_is_shown_as_written_with_a_warning(self):
        r = self.build("# R\n- A\n", use="research")
        self.assertEqual(page_json(self.html(r), "meta")["use"], "research")
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("learning, project tracking and decision", r.warnings[0])

    def test_use_must_be_a_string(self):
        with self.assertRaises(build.BuildError):
            self.build("# R\n- A\n", use=3)

    def test_the_page_has_the_labels_in_both_languages(self):
        page = page_json(self.html(self.build("# R\n- A\n", use="learning")), "i18n")
        self.assertEqual(page["meta_use"], "Use: {use}. ")
        self.assertEqual(page["uses"]["tracking"], "project tracking")
        zh = page_json(self.html(self.build("# R\n- A\n", use="learning", lang="zh")), "i18n")
        self.assertEqual((zh["meta_use"], zh["uses"]["tracking"]), ("用途：{use}。", "跟进项目"))


class MovedNodeTests(unittest.TestCase):
    """A node that moved but kept its title is still found by its last title."""

    OUTLINE = "# Atlas\n- Now\n  - Recently done\n    - Kept\n- History\n  - 10-17\n    - Flyers delivered\n    - Same title\n  - 10-16\n    - Same title\n"

    def setUp(self):
        self.keys = build.annotate(parse(self.OUTLINE), "Atlas")

    def resolve(self, spec):
        return build.resolve_node(spec, self.keys, "Atlas")

    def test_the_old_path_finds_the_node_by_its_last_title(self):
        self.assertEqual(self.resolve("Now › Recently done › Flyers delivered"), ("Atlas › History › 10-17 › Flyers delivered", ""))
        self.assertEqual(self.resolve("Atlas › Now › Recently done › Flyers delivered")[0], "Atlas › History › 10-17 › Flyers delivered")
        self.assertEqual(self.resolve("Recently done > Flyers delivered")[0], "Atlas › History › 10-17 › Flyers delivered")

    def test_two_nodes_with_that_title_are_not_guessed(self):
        self.assertEqual(self.resolve("Now › Recently done › Same title"), (None, "not found in the map"))

    def test_a_path_that_still_exists_wins_over_the_fallback(self):
        self.assertEqual(self.resolve("Now › Recently done › Kept")[0], "Atlas › Now › Recently done › Kept")

    def test_a_title_that_is_nowhere_is_still_not_found(self):
        self.assertEqual(self.resolve("Now › Recently done › Gone"), (None, "not found in the map"))

    def test_a_single_title_behaves_as_before(self):
        self.assertEqual(self.resolve("Flyers delivered")[0], "Atlas › History › 10-17 › Flyers delivered")
        self.assertEqual(self.resolve("Same title")[1], "2 node paths end with it; write a longer path")


class MovedNodeBuildTests(WorkdirCase):
    def test_a_reply_that_points_at_the_old_place_follows_the_node(self):
        self.write_meta(root_key="Atlas")
        self.write("outline.md", MovedNodeTests.OUTLINE)
        self.write("replies.json", json.dumps([{"id": "F1", "ts": "2026-10-18 10:00:00", "text": "t", "summary": "s", "status": "done",
                                                "nodes": ["Atlas › Now › Recently done › Flyers delivered", "Now › Recently done › Gone"]}]))
        r = build.build(self.wd)
        replies = page_json(self.html(r), "replies")
        self.assertEqual(replies[0]["nodes"], ["Atlas › History › 10-17 › Flyers delivered"])
        self.assertEqual(len(r.warnings), 1)
        self.assertIn("Gone", r.warnings[0])


class TemplateTests(unittest.TestCase):
    TEMPLATE = (build.SCRIPT_DIR / "template.html").read_text(encoding="utf-8")

    def test_the_page_finds_moved_nodes_by_their_last_title(self):
        for piece in ("function findKey(k)", "const byLast", "findKey(b.dataset.key)", "const n = findKey(k)"):
            self.assertIn(piece, self.TEMPLATE)
        self.assertNotIn("filter(k => byKey[k]);", self.TEMPLATE.split("function buildThreads")[1].split("return T;")[0])

    def test_the_page_shows_the_use_in_the_header(self):
        self.assertIn("META.use", self.TEMPLATE)
        self.assertIn("useLabel", self.TEMPLATE)


if __name__ == "__main__":
    unittest.main()
