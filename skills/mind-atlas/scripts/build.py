#!/usr/bin/env python3
"""Build a single-file, double-click-to-open HTML mind map from an outline.

Usage:
    python3 build.py <workdir> [--no-paths]

The work directory holds:
    meta.json      {"title": ..., "id": ..., "lang": "zh" | "en", "level": ..., "desc": ...,
                    "search_hint": ..., "parts": [outline files, joined in order], "out": ...,
                    "root_key": the root's fixed name inside node paths, "now": title of the "now" branch}
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
META_FIELDS = {"title", "id", "lang", "level", "desc", "search_hint", "parts", "out", "root_key", "now"}

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

BuildResult = collections.namedtuple("BuildResult", "out nodes depth kb replies warnings root known tagged")


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
    moment = now_moment()
    stamp, stamp_full = moment.strftime("%Y-%m-%d %H:%M"), moment.strftime("%Y-%m-%d %H:%M:%S")
    keys = annotate(root, root_key)
    for token in ("{{updated}}", "{{更新}}"):
        root["t"] = root["t"].replace(token, strings["root_updated"].format(md=moment.strftime("%m-%d %H:%M")))
    if now_title and not any(c["t"] == now_title for c in root["c"]):
        warnings.append("meta.json \"now\" is %r, but the root has no first-level branch with that title" % now_title)

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
    return BuildResult(out, len(nodes), depth, out.stat().st_size // 1024, len(replies), warnings, root, len(known), tagged)


def configure_streams():
    """Never crash on a console that cannot print some character (older Windows consoles)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


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


if __name__ == "__main__":
    main()
