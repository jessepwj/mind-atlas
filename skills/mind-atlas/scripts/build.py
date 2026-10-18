#!/usr/bin/env python3
"""Build a single-file, double-click-to-open HTML mind map from an outline.

Usage:
    python3 build.py <workdir> [--no-paths]

The work directory holds:
    meta.json      {"title": ..., "id": ..., "lang": "zh" | "en", "level": ..., "desc": ...,
                    "search_hint": ..., "parts": [outline files, joined in order], "out": ...,
                    "root_key": the root's fixed name inside node paths, "now": title of the "now" branch,
                    "use": what the map is for (learning / project tracking / decision),
                    "done_max": most items "Recently done" keeps (default 10),
                    "now_sections": titles of the "now" sections, only when they do not use the usual words}
    outline-*.md   outline pieces (or a single outline.md when "parts" is not given)
    replies.json   replies to the user's feedback (written by reply.py; optional)
    _fb/           feedback already pulled back (pull_feedback.py writes inbox.jsonl; known.json is an
                   optional list of feedback items you collected by hand); both are embedded in the page
Output: <workdir>/<title>.html (or meta "out") and, unless --no-paths, <workdir>/<title>.stamp.js (just the
build time: a page left open reads it when you return to the tab and offers a refresh). When "parts" is used,
the joined outline is also written to <workdir>/outline.md for inspection (never list outline.md in "parts").
The node count of every first-level branch is printed, so a node hung under the wrong parent stands out.

Long-running console (v1.1): every node gets a content fingerprint, so the page can mark nodes that are new or
edited since the user last looked; "root_key" keeps node paths stable when the root title carries the update
time ("{{updated}}" in the root title becomes "updated MM-DD HH:MM"); "now" names the first-level branch that
holds what is going on right now (it takes no colour, starts expanded, and its [in progress] / [waiting] /
[needs-you] nodes feed the five numbers at the top of the page).

Project-tracking maps (v1.2): when meta.json has "now", the build also checks that the "now" branch has not gone stale
and prints what it finds (it never stops the build): time points that passed more than 30 minutes ago, time points
that do not start with a date, "today" / "tomorrow" style wording, a "Recently done" section with too many items or a
group from two days ago or more, unfinished work filed under "done", and an empty "needs you" section. It also lists
the nodes outside "now" that are still tagged [in progress] or [waiting] (a branch whose title has "snapshot" is
skipped). A node that moved but kept its title is still found by its last title when a reply points at it.

Outline syntax (two spaces per level, spaces only):
    # Root title | root note
    - Node title [active] | Note text [src: where it came from]
      - Child node
        A deeper-indented line that does not start with "- " continues the note above.

    Chinese spelling works too:  - 标题 【在用】 ｜ 说明 〔来源〕
    Status tags (both spellings): needs-you/要你定  active/在用  stopped/已停  in progress/进行中
    todo/待做  issue/问题  done/已完成  decided/已定  waiting/等别人  risk/风险  proposal/建议

--no-paths leaves the local page path and reply command out of the page, for pages
that will be shared or published.

Standard library only; Python 3.9 or newer.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATE = SCRIPT_DIR / "template.html"
I18N_FILE = SCRIPT_DIR / "i18n.json"

DEFAULT_LANG = "zh"
META_FIELDS = {"title", "id", "lang", "level", "desc", "search_hint", "parts", "out", "root_key", "now", "use", "done_max",
               "now_sections"}

# Status tags: spelling -> canonical key (the key is what the page stores and styles).
TAGS_ZH = {
    "要你定": "needs-you", "在用": "active", "已停": "stopped", "进行中": "doing", "待做": "todo", "问题": "issue",
    "已完成": "done", "已定": "decided", "等别人": "waiting", "风险": "risk", "建议": "proposal",
}
TAGS_EN = {
    "needs-you": "needs-you", "needs you": "needs-you", "active": "active", "stopped": "stopped", "in progress": "doing", "todo": "todo", "issue": "issue",
    "done": "done", "decided": "decided", "waiting": "waiting", "risk": "risk", "proposal": "proposal",
}
_TAG_ZH_ALT = "|".join(map(re.escape, TAGS_ZH))
_TAG_EN_ALT = "|".join(map(re.escape, TAGS_EN))
TAG_RE = re.compile("【(" + _TAG_ZH_ALT + ")】|(?<!\\\\)\\[(" + _TAG_EN_ALT + ")\\]", re.IGNORECASE)
SRC_RE = re.compile("〔([^〕]*)〕|(?<!\\\\)\\[(?:src|source):\\s*([^\\]]*)\\]", re.IGNORECASE)
ESCAPED_RE = re.compile("\\\\(\\[(?:" + _TAG_EN_ALT + "|src:|source:))", re.IGNORECASE)
SEP_RE = re.compile(" ｜ | \\| ")
# What a map is for ("use" in meta.json): canonical key -> accepted spellings, lower case. The page shows the label in
# its own language (i18n.json "uses"); a value that is none of these is shown as written, with a warning.
USES = {
    "learning": ("learning", "学习理解", "学习"),
    "tracking": ("project tracking", "project-tracking", "tracking", "跟进项目", "跟进"),
    "decision": ("decision", "deciding", "decision making", "做决定", "决定"),
}
# Reply statuses: canonical key -> accepted spellings (Chinese, English, and the key itself).
# reply.py keeps an identical copy of STATUS_ALIASES (a test checks that they agree).
STATUSES = ["done", "doing", "planned", "dropped", "needs-you"]
STATUS_ALIASES = {
    "已做": "done", "done": "done",
    "在做": "doing", "doing": "doing", "in progress": "doing", "in-progress": "doing",
    "定了待做": "planned", "planned": "planned",
    "不做": "dropped", "dropped": "dropped",
    "要你定": "needs-you", "needs-you": "needs-you", "needs you": "needs-you",
}
BAD_FILENAME_CHARS = re.compile('[\\\\/:*?"<>|\\x00-\\x1f]')

# `stale` lists what is out of date in the "now" branch of a project-tracking map (empty: it looks current; None: the map
# has no "now" branch to check) and `open_outside` the nodes outside it that are still tagged in progress or waiting (see
# check_now); `now_roles` is the kinds of section it recognized in "Now" (None without the branch). None of them is counted in
# `warnings`.
BuildResult = collections.namedtuple("BuildResult", "out nodes depth kb replies warnings root known tagged stale open_outside now_roles")


class BuildError(Exception):
    """A problem the user has to fix (bad outline, bad meta.json, missing file)."""


def parse_fields(text, src_sep):
    """Pull status tags and sources out of a text fragment. Returns (text, tags, sources)."""
    tags = []
    for m in TAG_RE.finditer(text):
        key = TAGS_ZH[m.group(1)] if m.group(1) else TAGS_EN[m.group(2).lower()]
        if key not in tags:
            tags.append(key)
    text = TAG_RE.sub("", text)
    srcs = [(m.group(1) if m.group(1) is not None else m.group(2)).strip() for m in SRC_RE.finditer(text)]
    text = SRC_RE.sub("", text)
    text = ESCAPED_RE.sub(lambda m: m.group(1), text)
    return text, tags, src_sep.join(s for s in srcs if s)


def parse_item(text, src_sep="; "):
    """Parse the text after "- " (or after "# "): title, note, tags, sources."""
    text, tags, src = parse_fields(text, src_sep)
    m = SEP_RE.search(text)
    title, note = (text[:m.start()], text[m.end():]) if m else (text, "")
    return {"t": title.strip(), "n": note.strip(), "g": tags, "s": src, "c": []}


def parse_outline(lines, src_sep="; "):
    """Parse outline lines into a tree.

    `lines` yields (origin, line_number, text). Returns (root, warnings).
    Raises BuildError with "origin:line:" in the message for a structural mistake.
    """
    root, stack, warnings = None, [], []   # stack: (level, node); the root has level -1
    in_comment = False
    for origin, ln, raw in lines:
        line = raw.rstrip("\r\n")
        where = "%s:%d" % (origin, ln)
        stripped_all = line.strip()
        if in_comment:
            in_comment = "-->" not in line
            continue
        if not stripped_all:
            continue
        if stripped_all.startswith("<!--"):
            in_comment = "-->" not in line
            continue
        lead = line[: len(line) - len(line.lstrip())]
        if "\t" in lead:
            raise BuildError("%s: a tab in the indentation; indent with two spaces per level" % where)
        if line.startswith("# "):
            if root is not None:
                raise BuildError("%s: a second '# ' root line; an outline has exactly one root, "
                                 "and the other nodes are '- ' lines" % where)
            root = parse_item(line[2:], src_sep)
            stack = [(-1, root)]
            continue
        if root is None:
            raise BuildError("%s: the outline must start with a '# Root title' line" % where)
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if stripped.startswith("- "):
            if indent % 2:
                raise BuildError("%s: indent of %d spaces; use a multiple of 2 (two spaces per level)" % (where, indent))
            level = indent // 2
            while stack[-1][0] >= level:
                stack.pop()
            if level > stack[-1][0] + 1:
                raise BuildError("%s: indent of %d spaces skips a level; a child of '%s' is indented %d spaces"
                                 % (where, indent, stack[-1][1]["t"], (stack[-1][0] + 1) * 2))
            node = parse_item(stripped[2:], src_sep)
            stack[-1][1]["c"].append(node)
            stack.append((level, node))
        else:
            # continuation line: all of it is note text for the previous node
            level, node = stack[-1]
            if stripped.startswith("#"):
                warnings.append("%s: a line starting with '#' is not a node (only the single '# Root' line is); "
                                "it was merged into the note of '%s'. Turn Markdown headings into '- ' nodes"
                                % (where, node["t"]))
            elif stripped[:2] in ("* ", "+ "):
                warnings.append("%s: line starts with '%s'; only '- ' starts a node, so this was "
                                "merged into the note of '%s'" % (where, stripped[0], node["t"]))
            elif level >= 0 and indent <= level * 2:
                warnings.append("%s: continuation line is not indented deeper than its node "
                                "'%s'; it was merged into that node's note" % (where, node["t"]))
            text, tags, src = parse_fields(stripped, src_sep)
            node["n"] = (node["n"] + " " + text.strip()).strip()
            if src:
                node["s"] = (node["s"] + src_sep + src) if node["s"] else src
            for g in tags:
                if g not in node["g"]:
                    node["g"].append(g)
    if root is None:
        raise BuildError("the outline is empty; it needs a '# Root title' line")
    return root, warnings


def count_nodes(node):
    return 1 + sum(count_nodes(c) for c in node["c"])


def walk(node, depth=0, path=()):
    yield node, depth, path
    for child in node["c"]:
        for item in walk(child, depth + 1, path + (node["t"],)):
            yield item


def check_nodes(root):
    """Quality warnings that do not stop the build."""
    warnings = []
    nodes = list(walk(root))
    bad = [n["t"] for n, _, _ in nodes if "…" in (n["t"] + n["n"]) or "..." in (n["t"] + n["n"])]
    if bad:
        warnings.append("an ellipsis ('…' or '...') truncates the text in: " + "; ".join(bad)
                        + ". Write short complete sentences instead")
    empty = sum(1 for n, _, _ in nodes if not n["t"])
    if empty:
        warnings.append("%d node(s) have an empty title" % empty)
    for n, _, path in nodes:
        seen = set()
        for c in n["c"]:
            if c["t"] and c["t"] in seen:
                warnings.append("duplicate sibling title '%s' under '%s'; feedback quotes find nodes by "
                                "title path, so give siblings different titles" % (c["t"], n["t"]))
            seen.add(c["t"])
    if not root["c"]:
        warnings.append("the root has no child nodes")
    return warnings


# ---- Project-tracking maps: has the "now" branch gone stale? -----------------------------------------------------------
# A tracking map is only worth having while its "Now" is true. These checks run on every build of a map that has "now" in
# meta.json. They only report; the page is built either way. Chinese and English spellings are both understood.

# Wording that is wrong a day later ("today", "tomorrow", "tonight" ...); a date such as 10-19 stays true.
REL_DAY = re.compile(r"今天|明天|昨天|今晚|明晚|今早|今晨|明晨|(?<!说)明早|后天(?!数)|前天(?!数)"
                     r"|\b(?:today|tomorrow|yesterday|tonight|this (?:morning|afternoon|evening)|last night)\b", re.IGNORECASE)
# A title may start with a date (MM-DD or YYYY-MM-DD, then maybe a weekday) and then a time (HH:MM), or with a time alone.
DATE_LEAD = re.compile(r"^\s*(?:(\d{4})-)?(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])(?!\d)"
                       r"(?:\s*(?:周[一二三四五六日天]|(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?))?", re.IGNORECASE)
TIME_LEAD = re.compile(r"\s*(\d{1,2})[:：](\d{2})(?!\d)")
# Tags that say "not finished": they do not belong under "Recently done".
UNFINISHED = ("needs-you", "doing", "todo", "issue", "risk", "waiting", "proposal")
TAG_SPELLING = {"doing": "in progress"}      # the English spelling of a tag where it differs from the key
# What the sections of the "now" branch are, by the words in their titles (first match wins). A map whose sections use
# other words says so in meta.json "now_sections".
NOW_ROLES = tuple((role, re.compile(words, re.IGNORECASE)) for role, words in (
    ("ask", r"要你定|needs[ -]you|your (?:decision|call)|to decide"),
    ("next", r"^\s*(?:接下来|(?:next|upcoming|coming up)\b)"),     # like the page, which looks for a title that starts so
    ("later", r"以后|\b(?:later|someday|backlog)\b|not (?:yet )?scheduled"),
    ("done", r"做完|完成|\b(?:done|finished|completed)\b"),
    ("issues", r"问题|风险|\b(?:problems?|issues?|risks?)\b"),
    ("doing", r"在做|\b(?:in progress|under ?way|doing)\b|working on"),
    ("waiting", r"在等|等别人|\bwaiting\b|\bblocked\b|on others"),
))
NOW_ROLE_KEYS = tuple(role for role, _ in NOW_ROLES)
LATE_GRACE = datetime.timedelta(minutes=30)


def nearest_date(month, day, today):
    """The date with this month and day (no year written) that lies closest to today; None when there is none."""
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            cand = datetime.date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    return best


def lead_when(title, today):
    """What a title starts with. Returns (day, hour, minute): day is a datetime.date when it starts with a date, and hour
    and minute are numbers when a time follows (or the title starts with a time alone); each is None when absent."""
    day, rest = None, title
    m = DATE_LEAD.match(title)
    if m:
        month, dom = int(m.group(2)), int(m.group(3))
        try:
            day = datetime.date(int(m.group(1)), month, dom) if m.group(1) else nearest_date(month, dom, today)
        except ValueError:
            day = None
        if day is None:
            return None, None, None
        rest = title[m.end():]
    t = TIME_LEAD.match(rest)
    if t and int(t.group(1)) < 24 and int(t.group(2)) < 60:
        return day, int(t.group(1)), int(t.group(2))
    return day, None, None


def due_moment(day, hour, minute):
    """When a time point falls due: its time, or the end of its day when only a date is written."""
    if hour is None:
        return datetime.datetime.combine(day, datetime.time(23, 59))
    return datetime.datetime.combine(day, datetime.time(hour, minute))


def now_role(title, mapping):
    """Which section of the "now" branch a title is: first the titles listed in meta.json "now_sections", then the words in it."""
    for role, named in (mapping or {}).items():
        if named == title:
            return role
    for role, words in NOW_ROLES:
        if words.search(title):
            return role
    return ""


def tag_names(keys):
    return " ".join("[%s]" % TAG_SPELLING.get(k, k) for k in sorted(keys))


def check_time_points(section, now, warnings):
    """Every time point under the "next" section must start with a date and must not be long past."""
    today = now.date()

    def late(name, day, hour, minute):
        if due_moment(day, hour, minute) < now - LATE_GRACE:
            shown = "%02d-%02d%s" % (day.month, day.day, "" if hour is None else " %02d:%02d" % (hour, minute))
            warnings.append('"%s": %s has passed. If it happened, move it to the done section; if not, give it a new date '
                            'or say what it is waiting for' % (name, shown))

    def visit(node, path, parent_day):
        name = " › ".join(path + [node["t"]])
        day, hour, minute = lead_when(node["t"], today)
        if day is None and hour is not None:                 # "18:00 ...": the date comes from the group above it
            day = parent_day
            if day is None:
                warnings.append('"%s": a time without a date; start the title with the date (10-19 05:00 ...)' % name)
                return
        if day is None:
            if parent_day is not None:                       # a detail under a dated point, not a time point itself
                return
            if node["c"]:                                    # a plain group ("Week 45"): look at what is inside
                for child in node["c"]:
                    visit(child, path + [node["t"]], None)
            else:
                warnings.append('"%s": a time point must start with a date (10-19 05:00 ...); put it under "Later" '
                                'if it has no date yet' % name)
            return
        timed_kids = [c for c in node["c"] if lead_when(c["t"], today)[0] is None and lead_when(c["t"], today)[1] is not None]
        if not (timed_kids and hour is None):                # a day group such as "11-05" is judged by its timed children
            late(name, day, hour, minute)
        for child in node["c"]:
            visit(child, path + [node["t"]], day)

    for child in section["c"]:
        visit(child, [section["t"]], None)


def check_done(section, meta, now, warnings):
    """"Recently done" keeps about two days and at most done_max items, and holds nothing that is still open."""
    today = now.date()
    cap = meta.get("done_max", 10)
    items = []
    for child in section["c"]:
        day, hour, _ = lead_when(child["t"], today)
        if child["c"] and not child["g"] and day is not None and hour is None:      # a group for one day: "10-18"
            items.extend(child["c"])
            if (today - day).days >= 2:
                warnings.append('"%s › %s" is two days old or more; move the whole group into the history branch under '
                                'that day, keeping the titles' % (section["t"], child["t"]))
        else:
            items.append(child)
    if len(items) > cap:
        warnings.append('"%s" has %d items, more than %d; move the older ones into the history branch under their day '
                        '(keep the titles, quotes find nodes by them) and leave the latest here' % (section["t"], len(items), cap))
    for item in items:
        left = set(UNFINISHED) & set(item["g"])
        if left:
            warnings.append('"%s › %s" carries %s, so it is not finished; move it to the section it belongs to (Needs you, '
                            'In progress, Waiting on others, Problems and risks or Later)' % (section["t"], item["t"], tag_names(left)))


def check_now(root, meta, now):
    """Is the "now" branch of a project-tracking map out of date? Returns a list of messages (empty when it looks current).

    `now` is a naive datetime. Nothing here stops a build: a map that is behind is still worth reading, and the agent
    is told what to fix."""
    title = meta.get("now")
    node = next((c for c in root["c"] if c["t"] == title), None) if title else None
    if node is None:
        return []
    warnings = []
    for n, _, _ in walk(node):
        if REL_DAY.search(n["t"]):
            warnings.append('"%s": wording like "today" or "tomorrow" is wrong a day later; write the date (10-19)' % n["t"])
    for section in node["c"]:
        role = now_role(section["t"], meta.get("now_sections"))
        if role == "ask" and not section["c"]:
            warnings.append('"%s" is empty; add one node saying nothing needs the user right now, so it does not look '
                            'forgotten' % section["t"])
        elif role == "next":
            check_time_points(section, now, warnings)
        elif role == "done":
            check_done(section, meta, now, warnings)
    return warnings


def open_outside_now(root, meta):
    """Paths of the nodes outside "now" that are still tagged [in progress] or [waiting]. Detail branches are the easiest
    place to forget an update. A branch whose title has "snapshot" is skipped: it deliberately keeps an old state."""
    found = []

    def visit(node, path):
        if "快照" in node["t"] or "snapshot" in node["t"].lower():
            return
        here = path + [node["t"]]
        if {"doing", "waiting"} & set(node["g"]):
            found.append(" › ".join(here))
        for child in node["c"]:
            visit(child, here)

    for child in root["c"]:
        if child["t"] != meta.get("now"):
            visit(child, [])
    return found


def now_roles_found(root, meta):
    """The kinds of section (ask, next, done ...) that the first-level "now" branch has, found by title; None without the branch."""
    title = meta.get("now")
    node = next((c for c in root["c"] if c["t"] == title), None) if title else None
    if node is None:
        return None
    return sorted({now_role(c["t"], meta.get("now_sections")) for c in node["c"]} - {""})


def js(obj):
    """JSON for embedding inside a <script> element."""
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def split_lines(text):
    """Split on \\n, \\r\\n or \\r only (str.splitlines() would also cut at U+2028 and other rarities)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def read_text(path):
    """Read UTF-8 text (a leading BOM is tolerated); a clear error when the file is missing."""
    try:
        return pathlib.Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise BuildError("file not found: %s" % path)
    except UnicodeDecodeError:
        raise BuildError("%s is not valid UTF-8" % path)


def write_text(path, text):
    """Write UTF-8 with LF line endings on every platform."""
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def load_json(path, default=None):
    p = pathlib.Path(path)
    if not p.exists():
        if default is not None:
            return default
        raise BuildError("file not found: %s" % p)
    try:
        return json.loads(read_text(p))
    except ValueError as e:
        raise BuildError("%s is not valid JSON: %s" % (p, e))


def load_i18n():
    return json.loads(I18N_FILE.read_text(encoding="utf-8"))


def now_moment():
    """Local time, or UTC from SOURCE_DATE_EPOCH (reproducible builds)."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "")
    if epoch.isdigit():
        return datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
    return datetime.datetime.now()


def now_stamp():
    return now_moment().strftime("%Y-%m-%d %H:%M")


def normalize_status(value):
    """Canonical reply status for any accepted spelling (Chinese or English), or None."""
    return STATUS_ALIASES.get(str(value).strip().lower())


def normalize_use(value):
    """Canonical key (learning, tracking, decision) for any accepted spelling, or None."""
    word = " ".join(str(value).strip().lower().split())
    for key, spellings in USES.items():
        if word in spellings:
            return key
    return None


def fingerprint(title, tags, note):
    """Eight hex digits that change when a node's title, status tags or note change."""
    raw = "\x1f".join([title, ",".join(sorted(tags)), note])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]


def annotate(root, root_key):
    """Give every node its fingerprint "f" and full path "k" (the root is named root_key).

    Returns {path: first node with that path}. The page recomputes paths itself, so "k" is dropped before embedding.
    """
    keys = {}

    def rec(node, path):
        title = root_key if not path else node["t"]
        here = path + [title]
        node["f"] = fingerprint(title, node["g"], node["n"])
        node["k"] = " › ".join(here)
        keys.setdefault(node["k"], node)
        for child in node["c"]:
            rec(child, here)

    rec(root, [])
    return keys


def resolve_node(spec, keys, root_key):
    """Turn a --node value into a full node path. The root may be left out, and a unique tail or a unique
    title is enough. Returns (path or None, reason when None)."""
    s = spec.strip()
    if s in keys:
        return s, ""
    parts = [x.strip() for x in re.split(r"\s*›\s*|\s+>\s+", s) if x.strip()]
    if not parts:
        return None, "empty"
    tail = " › ".join(parts)
    full = [k for k in keys if k == root_key + " › " + tail]
    if full:
        return full[0], ""
    ends = [k for k in keys if k.endswith(" › " + tail) or k == tail]
    if len(ends) == 1:
        return ends[0], ""
    if len(ends) > 1:
        return None, "%d node paths end with it; write a longer path" % len(ends)
    if len(parts) == 1:
        same = [k for k in keys if k.rsplit(" › ", 1)[-1] == parts[0]]
        if len(same) == 1:
            return same[0], ""
        if len(same) > 1:
            return None, "%d nodes have this title; write a longer path" % len(same)
        inside = [k for k in keys if parts[0] in k.rsplit(" › ", 1)[-1]]
        if len(inside) == 1:
            return inside[0], ""
        if len(inside) > 1:
            return None, "%d node titles contain these words; write a longer path" % len(inside)
    else:
        # The node moved (say from "Recently done" into a history branch) but kept its title: the last title alone
        # is enough when only one node has it. The page finds quotes the same way.
        moved = [k for k in keys if k.rsplit(" › ", 1)[-1] == parts[-1]]
        if len(moved) == 1:
            return moved[0], ""
    return None, "not found in the map"


def load_jsonl(path):
    """Read a JSON-lines file; blank and unreadable lines are skipped."""
    out = []
    if path.exists():
        for line in read_text(path).splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def csp(with_stamp):
    """Content-Security-Policy for the page. A local page also lets the sibling .stamp.js load."""
    script = "'unsafe-inline' file:" if with_stamp else "'unsafe-inline'"
    return ("default-src 'none'; script-src %s; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'" % script)


def default_out_name(title):
    name = BAD_FILENAME_CHARS.sub("-", title).strip(" .")
    return (name or "mindmap") + ".html"


def collect_lines(wd, meta, warnings):
    """Return the outline as (origin, line_number, text) triples; write outline.md when joining parts."""
    parts = meta.get("parts")
    if not parts:
        f = wd / "outline.md"
        text = read_text(f) if f.exists() else None
        if text is None:
            raise BuildError("no outline: put the outline in %s, or list the files in meta.json \"parts\"" % f)
        return [("outline.md", i, ln) for i, ln in enumerate(split_lines(text), 1)]
    if not isinstance(parts, list) or not all(isinstance(p, str) for p in parts):
        raise BuildError("meta.json \"parts\" must be a list of file names")
    lines, chunks = [], []
    for name in parts:
        f = (wd / name).resolve()
        try:
            f.relative_to(wd)
        except ValueError:
            raise BuildError("meta.json \"parts\": %s is outside the work directory" % name)
        if f == (wd / "outline.md").resolve():
            raise BuildError("meta.json \"parts\" must not list outline.md: it is the joined result that build.py "
                             "writes. List the outline-*.md pieces instead")
        if not f.exists():
            warnings.append("missing part: %s (the page is built without it)" % name)
            continue
        text = read_text(f)
        chunks.append(text.rstrip("\r\n"))
        lines.extend((name, i, ln) for i, ln in enumerate(split_lines(text), 1))
    write_text(wd / "outline.md", "\n".join(chunks) + "\n")
    return lines


def build(workdir, no_paths=False):
    """Build the page for a work directory. Returns a BuildResult; raises BuildError."""
    wd = pathlib.Path(workdir).resolve()
    if not wd.is_dir():
        raise BuildError("not a directory: %s" % wd)
    meta = load_json(wd / "meta.json")
    if not isinstance(meta, dict):
        raise BuildError("meta.json must contain a JSON object")
    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        raise BuildError("meta.json needs a non-empty \"title\"")
    warnings = ["unknown meta.json field '%s' (ignored)" % k for k in sorted(set(meta) - META_FIELDS)]
    if "lang" not in meta:
        warnings.append("meta.json has no \"lang\", so the page interface is Chinese (the default); "
                        "set \"lang\": \"en\" or \"zh\" explicitly")

    i18n = load_i18n()
    lang = meta.get("lang", DEFAULT_LANG)
    if lang not in i18n:
        raise BuildError("unsupported \"lang\": %r (available: %s)" % (lang, ", ".join(sorted(i18n))))
    strings = i18n[lang]
    src_sep = "；" if lang == "zh" else "; "

    out_name = meta.get("out") or default_out_name(title)
    if not isinstance(out_name, str) or pathlib.PurePath(out_name).name != out_name or out_name in (".", ".."):
        raise BuildError("meta.json \"out\" must be a plain file name, not a path: %r" % (out_name,))
    out = wd / out_name
    stamp_js = out.with_suffix(".stamp.js")

    lines = collect_lines(wd, meta, warnings)
    root, parse_warnings = parse_outline(lines, src_sep)
    warnings.extend(parse_warnings)
    warnings.extend(check_nodes(root))
    nodes = list(walk(root))

    root_key = meta.get("root_key") or root["t"]
    if not isinstance(root_key, str):
        raise BuildError("meta.json \"root_key\" must be a string")
    now_title = meta.get("now", "")
    if not isinstance(now_title, str):
        raise BuildError("meta.json \"now\" must be a string")
    use = meta.get("use", "")
    if not isinstance(use, str):
        raise BuildError("meta.json \"use\" must be a string")
    use_key = normalize_use(use) if use.strip() else None
    if use.strip() and use_key is None:
        warnings.append("meta.json \"use\" is %r; the known values are learning, project tracking and decision "
                        "(it is shown as written)" % use)
    done_max = meta.get("done_max", 10)
    if isinstance(done_max, bool) or not isinstance(done_max, int) or done_max < 1:
        raise BuildError("meta.json \"done_max\" must be a whole number of at least 1")
    sections = meta.get("now_sections", {})
    if not isinstance(sections, dict) or not all(isinstance(v, str) for v in sections.values()):
        raise BuildError("meta.json \"now_sections\" must be an object that maps section kinds to titles, "
                         "for example {\"next\": \"Scheduled\"}")
    warnings.extend("meta.json \"now_sections\": unknown kind %r (use %s)" % (k, ", ".join(NOW_ROLE_KEYS))
                    for k in sorted(set(sections) - set(NOW_ROLE_KEYS)))
    moment = now_moment()
    stamp, stamp_full = moment.strftime("%Y-%m-%d %H:%M"), moment.strftime("%Y-%m-%d %H:%M:%S")
    keys = annotate(root, root_key)
    for token in ("{{updated}}", "{{更新}}"):
        root["t"] = root["t"].replace(token, strings["root_updated"].format(md=moment.strftime("%m-%d %H:%M")))
    if now_title and not any(c["t"] == now_title for c in root["c"]):
        warnings.append("meta.json \"now\" is %r, but the root has no first-level branch with that title" % now_title)
    # The checks below read the outline as written; the clock is local time (UTC under SOURCE_DATE_EPOCH, for tests).
    stale, open_outside, now_roles = None, [], None     # None = no "now" branch to check
    if now_title and any(c["t"] == now_title for c in root["c"]):
        stale = check_now(root, meta, moment.replace(tzinfo=None))
        open_outside = open_outside_now(root, meta)
        now_roles = now_roles_found(root, meta)
        branch = next(c for c in root["c"] if c["t"] == now_title)
        warnings.extend("meta.json \"now_sections\": %r is not the title of any section in the %r branch" % (named, now_title)
                        for named in sorted(set(sections.values()) - {c["t"] for c in branch["c"]}))

    replies = load_json(wd / "replies.json", default=[])
    if not isinstance(replies, list) or not all(isinstance(r, dict) and "id" in r for r in replies):
        raise BuildError("replies.json must be a list of reply objects (written by reply.py)")
    ask_nodes = {n["k"] for n, _, _ in nodes if "needs-you" in n["g"]}
    for i, r in enumerate(replies):
        r["rid"] = hashlib.sha1(("%s|%s|%d" % (r["id"], r.get("ts", ""), i)).encode("utf-8")).hexdigest()[:10]
        if r.get("status"):
            status = normalize_status(r["status"])
            if status is None:
                warnings.append("reply %s: status %r is not one of %s" % (r["id"], r["status"], ", ".join(STATUSES)))
            else:
                r["status"] = status
        resolved = []
        for spec in r.get("nodes") or []:
            path, why = resolve_node(str(spec), keys, root_key)
            if path:
                resolved.append(path)
            else:
                warnings.append("reply %s: node %r: %s" % (r["id"], spec, why))
        r["nodes"] = resolved
        if r.get("status") == "needs-you" and not (set(resolved) & ask_nodes):
            warnings.append("reply %s is marked needs-you but points at no node tagged [NEEDS-YOU]; use --node on the "
                            "matching item in the \"now\" branch, or add the tag in the outline first" % r["id"])

    fb = wd / "_fb"
    known_src = load_json(fb / "known.json", default=[])
    if not isinstance(known_src, list):
        raise BuildError("%s must contain a JSON list" % (fb / "known.json"))
    known = {}
    for item in known_src + load_jsonl(fb / "inbox.jsonl"):
        if isinstance(item, dict) and item.get("id"):
            known[item["id"]] = {k: item[k] for k in ("id", "ts", "text", "quotes", "ctx", "replaces") if item.get(k) is not None}
    for n, _, _ in nodes:   # full paths are only needed here; the page works them out itself
        n.pop("k", None)

    page_meta = {
        "id": str(meta.get("id") or title),
        "title": title,
        "lang": lang,
        "level": str(meta.get("level", "")),
        "desc": str(meta.get("desc", "")),
        "stamp": stamp,
        "stamp_full": stamp_full,
        "root_key": root_key,
        "now": now_title,
        "use": use_key or use.strip(),
        "statuses": STATUSES,
    }
    if "search_hint" in meta:
        page_meta["search_hint"] = str(meta["search_hint"])
    if not no_paths:
        py = "python" if os.name == "nt" else "python3"
        page_meta["file"] = str(out)
        page_meta["stamp_js"] = stamp_js.name
        page_meta["reply_cmd"] = '%s "%s" "%s" %s' % (py, SCRIPT_DIR / "reply.py", wd, strings["reply_args"])

    # One pass over the template: text that was substituted in is never scanned again, so an outline that
    # happens to contain "{{TITLE}}" or "/*META*/" cannot corrupt the page.
    subs = {
        "/*DATA*/": js(root), "/*META*/": js(page_meta), "/*REPLIES*/": js(replies), "/*KNOWN*/": js(known),
        "/*I18N*/": js(strings), "{{TITLE}}": esc(title), "{{HTMLLANG}}": esc(strings["html_lang"]),
        "{{CSP}}": esc(csp(not no_paths)),
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    html = re.sub("|".join(re.escape(k) for k in subs), lambda m: subs[m.group(0)], template)
    write_text(out, html)
    if not no_paths:
        write_text(stamp_js, "window.__MM_LATEST=" + js({"stamp_full": stamp_full}) + ";\n")
    depth = max(d for _, d, _ in nodes)
    tagged = {tag: sum(1 for n, _, _ in nodes if tag in n["g"]) for tag in ("needs-you", "doing", "waiting")}
    return BuildResult(out, len(nodes), depth, out.stat().st_size // 1024, len(replies), warnings, root, len(known), tagged,
                       stale, open_outside, now_roles)


def configure_streams():
    """Never crash on a console that cannot print some character (older Windows consoles)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def print_now_report(r, limit=12):
    """Tell the agent what is out of date in the "now" branch (stderr, like the other warnings) or that it looks current."""
    for w in r.stale or []:
        print('WARNING: "Now" branch is behind: ' + w, file=sys.stderr)
    missing = [name for role, name in (("ask", "Needs you"), ("next", "Next up"), ("done", "Recently done"))
               if r.now_roles is not None and role not in r.now_roles]
    if missing:
        print('  "Now" branch check: no section was recognized as %s, so that part was not checked (use the usual titles, or '
              'name them in "now_sections")' % ", ".join(missing))
    elif r.stale == []:
        print('  "Now" branch check passed: no passed time points, no relative dates, "Recently done" within limits')
    if r.open_outside:
        print('NOTE: %d node(s) outside the "Now" branch are still tagged [in progress] or [waiting]. On a big update check '
              'them, and tag the finished ones [done]:' % len(r.open_outside), file=sys.stderr)
        for path in r.open_outside[:limit]:
            print("  " + path, file=sys.stderr)
        if len(r.open_outside) > limit:
            print("  (and %d more)" % (len(r.open_outside) - limit), file=sys.stderr)


def main(argv=None):
    configure_streams()
    ap = argparse.ArgumentParser(description="Build a single-file HTML mind map from an outline work directory.")
    ap.add_argument("workdir", help="directory with meta.json and the outline files")
    ap.add_argument("--no-paths", action="store_true",
                    help="do not embed the local page path and reply command (for pages you share or publish)")
    args = ap.parse_args(argv)
    try:
        r = build(args.workdir, no_paths=args.no_paths)
    except BuildError as e:
        sys.exit("error: %s" % e)
    print("Wrote %s: %d nodes, deepest level %d, %d KB, %d replies" % (r.out, r.nodes, r.depth, r.kb, r.replies))
    print("  %d feedback item(s) already pulled back; tagged: %d needs-you, %d in progress, %d waiting"
          % (r.known, r.tagged["needs-you"], r.tagged["doing"], r.tagged["waiting"]))
    # one line per first-level branch: a node hung under the wrong parent shows up as a lopsided count
    for branch in r.root["c"]:
        print("  %s (%d nodes)" % (branch["t"] or "(empty title)", count_nodes(branch)))
    for w in r.warnings:
        print("WARNING: " + w, file=sys.stderr)
    print_now_report(r)


if __name__ == "__main__":
    main()
