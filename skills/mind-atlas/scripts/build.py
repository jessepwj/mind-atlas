#!/usr/bin/env python3
"""Build a single-file, double-click-to-open HTML mind map from an outline.

Usage:
    python3 build.py <workdir> [--no-paths]

The work directory holds:
    meta.json      {"title": ..., "id": ..., "lang": "zh" | "en", "level": ..., "desc": ...,
                    "search_hint": ..., "parts": [outline files, joined in order], "out": ...}
    outline-*.md   outline pieces (or a single outline.md when "parts" is not given)
    replies.json   replies to the user's feedback (written by reply.py; optional)
Output: <workdir>/<title>.html (or meta "out"). When "parts" is used, the joined
outline is also written to <workdir>/outline.md for inspection (never list outline.md in "parts").
The node count of every first-level branch is printed, so a node hung under the wrong parent stands out.

Outline syntax (two spaces per level, spaces only):
    # Root title | root note
    - Node title [active] | Note text [src: where it came from]
      - Child node
        A deeper-indented line that does not start with "- " continues the note above.

    Chinese spelling works too:  - 标题 【在用】 ｜ 说明 〔来源〕
    Status tags (both spellings): active/在用  stopped/已停  in progress/进行中  todo/待做
    issue/问题  done/已完成  decided/已定  waiting/等别人  risk/风险  proposal/建议

--no-paths leaves the local page path and reply command out of the page, for pages
that will be shared or published.

Standard library only; Python 3.9 or newer.
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import re
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATE = SCRIPT_DIR / "template.html"
I18N_FILE = SCRIPT_DIR / "i18n.json"

DEFAULT_LANG = "zh"
META_FIELDS = {"title", "id", "lang", "level", "desc", "search_hint", "parts", "out"}

# Status tags: spelling -> canonical key (the key is what the page stores and styles).
TAGS_ZH = {
    "在用": "active", "已停": "stopped", "进行中": "doing", "待做": "todo", "问题": "issue",
    "已完成": "done", "已定": "decided", "等别人": "waiting", "风险": "risk", "建议": "proposal",
}
TAGS_EN = {
    "active": "active", "stopped": "stopped", "in progress": "doing", "todo": "todo", "issue": "issue",
    "done": "done", "decided": "decided", "waiting": "waiting", "risk": "risk", "proposal": "proposal",
}
_TAG_ZH_ALT = "|".join(map(re.escape, TAGS_ZH))
_TAG_EN_ALT = "|".join(map(re.escape, TAGS_EN))
TAG_RE = re.compile("【(" + _TAG_ZH_ALT + ")】|(?<!\\\\)\\[(" + _TAG_EN_ALT + ")\\]", re.IGNORECASE)
SRC_RE = re.compile("〔([^〕]*)〕|(?<!\\\\)\\[(?:src|source):\\s*([^\\]]*)\\]", re.IGNORECASE)
ESCAPED_RE = re.compile("\\\\(\\[(?:" + _TAG_EN_ALT + "|src:|source:))", re.IGNORECASE)
SEP_RE = re.compile(" ｜ | \\| ")
BAD_FILENAME_CHARS = re.compile('[\\\\/:*?"<>|\\x00-\\x1f]')

BuildResult = collections.namedtuple("BuildResult", "out nodes depth kb replies warnings root")


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


def now_stamp():
    """Local time, or UTC from SOURCE_DATE_EPOCH (reproducible builds)."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "")
    if epoch.isdigit():
        moment = datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
    else:
        moment = datetime.datetime.now()
    return moment.strftime("%Y-%m-%d %H:%M")


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

    lines = collect_lines(wd, meta, warnings)
    root, parse_warnings = parse_outline(lines, src_sep)
    warnings.extend(parse_warnings)
    warnings.extend(check_nodes(root))
    nodes = list(walk(root))

    replies = load_json(wd / "replies.json", default=[])
    if not isinstance(replies, list) or not all(isinstance(r, dict) and "id" in r for r in replies):
        raise BuildError("replies.json must be a list of reply objects (written by reply.py)")

    page_meta = {
        "id": str(meta.get("id") or title),
        "title": title,
        "lang": lang,
        "level": str(meta.get("level", "")),
        "desc": str(meta.get("desc", "")),
        "stamp": now_stamp(),
    }
    if "search_hint" in meta:
        page_meta["search_hint"] = str(meta["search_hint"])
    if not no_paths:
        py = "python" if os.name == "nt" else "python3"
        page_meta["file"] = str(out)
        page_meta["reply_cmd"] = '%s "%s" "%s" %s' % (py, SCRIPT_DIR / "reply.py", wd, strings["reply_args"])

    # One pass over the template: text that was substituted in is never scanned again, so an outline that
    # happens to contain "{{TITLE}}" or "/*META*/" cannot corrupt the page.
    subs = {
        "/*DATA*/": js(root), "/*META*/": js(page_meta), "/*REPLIES*/": js(replies), "/*I18N*/": js(strings),
        "{{TITLE}}": esc(title), "{{HTMLLANG}}": esc(strings["html_lang"]),
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    html = re.sub("|".join(re.escape(k) for k in subs), lambda m: subs[m.group(0)], template)
    write_text(out, html)
    depth = max(d for _, d, _ in nodes)
    return BuildResult(out, len(nodes), depth, out.stat().st_size // 1024, len(replies), warnings, root)


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
    # one line per first-level branch: a node hung under the wrong parent shows up as a lopsided count
    for branch in r.root["c"]:
        print("  %s (%d nodes)" % (branch["t"] or "(empty title)", count_nodes(branch)))
    for w in r.warnings:
        print("WARNING: " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
