#!/usr/bin/env python3
"""Pull the feedback a user wrote on a mind-atlas page straight out of the browser's local storage,
so they do not have to copy and paste it.

WHEN TO RUN IT: only when the user explicitly says "pull my feedback" (or the equivalent in their language).
Never on a timer, never from a scheduled task or heartbeat, never as a background service. It is a one-shot,
read-only tool: pull, reply to each item, rebuild the page, all in the same run.

How it works:
  The user opens the page from disk (a file:// page); the page keeps their feedback in the browser's
  localStorage under the key mm:<meta.json "id">:items. Chromium-based browsers store localStorage as a
  LevelDB database in <user data dir>/<Default or Profile N>/Local Storage/leveldb. This script never touches
  the live database: it copies the whole directory to a temporary folder (so a running browser, and its file
  locks, do not matter), reads it with a small pure-Python LevelDB reader (.log and .ldb files, with Snappy
  decompression), and deletes the copy. It looks through Chrome, Chromium, Edge, Brave and Ego Lite profiles
  and merges what it finds.
  Limit: browsers flush localStorage to disk with a delay, usually 2 to 5 seconds and up to about a minute
  after many reloads. An item the user added a moment ago may not be on disk yet. Every run prints when the
  newest item was written; if it looks stale, wait a little and run again.

Usage:
  python3 pull_feedback.py <workdir>                    pull; the new items are appended to _fb/inbox.jsonl and printed
  python3 pull_feedback.py <workdir> --all              print everything found, new or not (writes nothing)
  python3 pull_feedback.py <workdir> --compare FILE     compare with an existing JSON list of items (a check)
  python3 pull_feedback.py <workdir> --leveldb DIR ...  read these LevelDB directories instead of looking for browsers
  python3 pull_feedback.py <workdir> --browser NAME     only look at one browser (chrome, chromium, edge, brave, ego)
  python3 pull_feedback.py <workdir> --origin ORIGIN    the page's origin, file:// by default; for a page that is
                                                        served over http(s) pass e.g. https://example.org
The work directory is required.

An item counts as new when its id is neither in replies.json (already answered), nor in _fb/inbox.jsonl (pulled
before), nor in _fb/known.json. Items that were pulled before but not answered yet are listed again, so an
interrupted session does not lose them.

Then reply to each one:
  python3 reply.py <workdir> <id> "details" --summary "one-line conclusion" --status done --orig "the user's words"
and rebuild (reply.py does that). If no browser store can be found, ask the user to click "Copy for AI" instead.

Standard library only; Python 3.9 or newer.
"""
import argparse
import datetime
import glob
import json
import os
import pathlib
import shutil
import struct
import sys
import tempfile

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
LDB_MAGIC = bytes.fromhex("57fb808b247547db")


def browser_roots():
    """{name: user data directory} for the Chromium-based browsers on this platform."""
    home = pathlib.Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
        return {"chrome": base / "Google" / "Chrome", "chromium": base / "Chromium",
                "edge": base / "Microsoft Edge", "brave": base / "BraveSoftware" / "Brave-Browser",
                "ego": base / "Citro Labs" / "ego lite"}
    if sys.platform.startswith("win"):
        base = pathlib.Path(os.environ.get("LOCALAPPDATA") or (home / "AppData" / "Local"))
        return {"chrome": base / "Google" / "Chrome" / "User Data", "chromium": base / "Chromium" / "User Data",
                "edge": base / "Microsoft" / "Edge" / "User Data",
                "brave": base / "BraveSoftware" / "Brave-Browser" / "User Data"}
    base = home / ".config"
    return {"chrome": base / "google-chrome", "chromium": base / "chromium",
            "edge": base / "microsoft-edge", "brave": base / "BraveSoftware" / "Brave-Browser"}


# ---------- Snappy (raw format) ----------
def snappy_decompress(buf):
    """Decompress a raw Snappy block (the format LevelDB uses for compressed table blocks)."""
    pos, n, shift = 0, 0, 0
    while True:
        b = buf[pos]
        pos += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    out = bytearray()
    while pos < len(buf):
        tag = buf[pos]
        pos += 1
        kind = tag & 3
        if kind == 0:                       # literal
            ln = tag >> 2
            if ln < 60:
                ln += 1
            else:
                nb = ln - 59
                ln = int.from_bytes(buf[pos:pos + nb], "little") + 1
                pos += nb
            out += buf[pos:pos + ln]
            pos += ln
            continue
        if kind == 1:                       # copy, 1-byte offset
            ln = ((tag >> 2) & 7) + 4
            off = ((tag >> 5) << 8) | buf[pos]
            pos += 1
        elif kind == 2:                     # copy, 2-byte offset
            ln = (tag >> 2) + 1
            off = int.from_bytes(buf[pos:pos + 2], "little")
            pos += 2
        else:                               # copy, 4-byte offset
            ln = (tag >> 2) + 1
            off = int.from_bytes(buf[pos:pos + 4], "little")
            pos += 4
        if off <= 0 or off > len(out):
            raise ValueError("corrupt snappy data")
        start = len(out) - off
        if off >= ln:
            out += out[start:start + ln]
        else:                               # overlapping copy: repeat the pattern byte by byte
            for i in range(ln):
                out.append(out[start + i])
    if len(out) != n:
        raise ValueError("snappy length mismatch: %d != %d" % (len(out), n))
    return bytes(out)


def varint(buf, pos):
    """Read a base-128 varint at pos. Returns (value, new position)."""
    result, shift = 0, 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


# ---------- LevelDB reading ----------
def read_log(path, sink):
    """A .log file: the write-ahead log. 32 KB blocks of fragmented records; each record is a WriteBatch."""
    data = pathlib.Path(path).read_bytes()
    pos, frag = 0, bytearray()
    while pos < len(data):
        remaining = 32768 - (pos % 32768)
        if remaining < 7:
            pos += remaining
            continue
        if pos + 7 > len(data):
            break
        ln = struct.unpack_from("<H", data, pos + 4)[0]
        kind = data[pos + 6]
        payload = data[pos + 7:pos + 7 + ln]
        if len(payload) < ln:               # the last record was not finished
            break
        pos += 7 + ln
        if kind == 1:                       # full
            frag = bytearray()
            read_batch(bytes(payload), sink)
        elif kind == 2:                     # first
            frag = bytearray(payload)
        elif kind == 3:                     # middle
            frag += payload
        elif kind == 4:                     # last
            frag += payload
            read_batch(bytes(frag), sink)
            frag = bytearray()
        # kind 0 is padding


def read_batch(b, sink):
    """Decode one WriteBatch and pass each put/delete to sink(key, sequence, type, value)."""
    if len(b) < 12:
        return
    seq = struct.unpack_from("<Q", b, 0)[0]
    count = struct.unpack_from("<I", b, 8)[0]
    pos = 12
    for i in range(count):
        try:
            tag = b[pos]
            pos += 1
            klen, pos = varint(b, pos)
            key = b[pos:pos + klen]
            pos += klen
            if pos > len(b):                # cut off in the middle of a key
                return
            if tag == 1:
                vlen, pos = varint(b, pos)
                value = b[pos:pos + vlen]
                pos += vlen
                if pos > len(b):            # cut off in the middle of a value
                    return
                sink(key, seq + i, 1, value)
            else:
                sink(key, seq + i, 0, b"")
        except IndexError:
            return


def block_contents(data, off, size):
    raw = data[off:off + size]
    kind = data[off + size]
    if kind == 0:
        return raw
    if kind == 1:
        return snappy_decompress(raw)
    raise ValueError("unknown block compression type %d" % kind)


def block_entries(block):
    """Yield (key, value) from a table block (prefix-compressed entries followed by the restart array)."""
    restarts = struct.unpack_from("<I", block, len(block) - 4)[0]
    end = len(block) - 4 - 4 * restarts
    pos, key = 0, b""
    while pos < end:
        shared, pos = varint(block, pos)
        non_shared, pos = varint(block, pos)
        vlen, pos = varint(block, pos)
        key = key[:shared] + block[pos:pos + non_shared]
        pos += non_shared
        yield key, block[pos:pos + vlen]
        pos += vlen


def read_ldb(path, sink):
    """A .ldb file: a sorted table. The last 48 bytes are the footer, which locates the index block."""
    data = pathlib.Path(path).read_bytes()
    if len(data) < 48 or data[-8:] != LDB_MAGIC:
        raise ValueError("not a leveldb table file")
    pos = len(data) - 48
    _, pos = varint(data, pos)              # metaindex offset
    _, pos = varint(data, pos)              # metaindex size
    index_off, pos = varint(data, pos)
    index_size, pos = varint(data, pos)
    for _key, handle in block_entries(block_contents(data, index_off, index_size)):
        off, p = varint(handle, 0)
        size, _ = varint(handle, p)
        for ikey, value in block_entries(block_contents(data, off, size)):
            if len(ikey) < 8:
                continue
            tail = struct.unpack("<Q", ikey[-8:])[0]
            sink(ikey[:-8], tail >> 8, tail & 0xFF, value)


def read_leveldb_dir(directory, origin="file://"):
    """Read a (copied) LevelDB directory. Returns ({user key: newest value}, [files that could not be read]).

    Deleted keys are left out, and only keys of the given origin are kept.
    """
    prefix = ("_" + origin).encode("utf-8")
    best = {}

    def sink(key, seq, kind, value):
        if not key.startswith(prefix):
            return
        old = best.get(key)
        if old is None or seq >= old[0]:
            best[key] = (seq, kind, value)

    files = sorted(glob.glob(os.path.join(directory, "*.ldb")) + glob.glob(os.path.join(directory, "*.sst"))
                   + glob.glob(os.path.join(directory, "*.log")))
    bad = []
    for f in files:
        try:
            (read_log if f.endswith(".log") else read_ldb)(f, sink)
        except Exception as e:              # one unreadable file must not hide the others
            bad.append("%s: %s" % (os.path.basename(f), e))
    return {k: v[2] for k, v in best.items() if v[1] == 1}, bad


def decode_str(b):
    """A Chromium localStorage string: first byte 0 = UTF-16LE follows, 1 = Latin-1 follows."""
    if not b:
        return ""
    if b[0] == 0:
        return b[1:].decode("utf-16-le", "replace")
    return b[1:].decode("latin-1")


def local_storage(directory, origin="file://"):
    """Copy the directory to a temporary folder and read it. Returns ({(origin, key): value}, bad files)."""
    tmp = tempfile.mkdtemp(prefix="mm-ls-")
    try:
        dst = os.path.join(tmp, "leveldb")
        shutil.copytree(directory, dst, ignore=shutil.ignore_patterns("LOCK"))
        kv, bad = read_leveldb_dir(dst, origin)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = {}
    for k, v in kv.items():
        i = k.find(b"\x00")
        if i < 0:
            continue
        out[(k[1:i].decode("latin-1"), decode_str(k[i + 1:]))] = decode_str(v)
    return out, bad


def find_dirs(which):
    """[(browser name, LevelDB directory)] for every profile of the requested browser(s)."""
    dirs = []
    for name, base in browser_roots().items():
        if which not in ("all", name):
            continue
        for p in sorted(glob.glob(str(base / "*" / "Local Storage" / "leveldb"))):
            dirs.append((name, p))
    return dirs


# ---------- output ----------
def load_jsonl(path):
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def plural(value, n):
    """An i18n entry is a string or {"one": ..., "other": ...}."""
    if isinstance(value, dict):
        value = value["one"] if n == 1 else value["other"]
    return value


def fmt(template, **kw):
    for k, v in kw.items():
        template = template.replace("{%s}" % k, str(v))
    return template


def ts_label(strings, ts):
    ts = ts or ""
    if not ts:
        return ""
    return fmt(strings["ts_format"], M=ts[5:7], D=ts[8:10], hm=ts[11:16])


def render(items, title, source, reply_hint, strings, now=None):
    """The block the page's "Copy for AI" would have produced, in the page's language, plus a pull note."""
    now = now or datetime.datetime.now()
    key = lambda p: " › ".join(p)
    n = len(items)
    head = fmt(plural(strings["export_head"], n), title=title, n=n)
    lines = [head + fmt(strings["pull_suffix"], src=source, time=now.strftime("%m-%d %H:%M")), ""]
    for i, it in enumerate(items, 1):
        line = "%d. [%s] %s" % (i, it["id"], ts_label(strings, it.get("ts")))
        if it.get("replaces"):
            line += fmt(strings["export_revises"], id=it["replaces"])
        lines.append(line)
        for q in it.get("quotes") or []:
            path = key(q["p"][1:]) or q["p"][0]
            tail = ("\n         " + fmt(strings["export_quote_text"], x=q["x"])) if q.get("x") else strings["export_quote_whole"]
            lines.append("   " + fmt(strings["export_quote"], path=path) + tail)
        ctx = it.get("ctx")
        if not it.get("quotes") and ctx and len(ctx) > 1:
            lines.append("   " + fmt(strings["export_noquote"], path=key(ctx[1:])))
        lines.append("   " + strings["export_says"] + it["text"].replace("\n", "\n      "))
        lines.append("")
    lines.append(reply_hint)
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Pull the feedback a user wrote on a mind-atlas page from their browser (read-only). "
                    "Run it only when the user explicitly asks you to pull their feedback.")
    ap.add_argument("workdir", nargs="?", help="the work directory (required)")
    ap.add_argument("--leveldb", action="append", default=[], help="a LevelDB directory to read; may be repeated")
    ap.add_argument("--browser", default="all", choices=["all"] + sorted(browser_roots()),
                    help="only look at this browser (default: all)")
    ap.add_argument("--origin", default="file://", help="origin of the page (default: file://)")
    ap.add_argument("--all", action="store_true", help="print everything found; write nothing")
    ap.add_argument("--compare", help="compare with a JSON list of feedback items")
    a = ap.parse_args(argv)

    if not a.workdir:
        sys.exit("error: give the work directory: python3 pull_feedback.py <workdir>")
    wd = pathlib.Path(a.workdir).resolve()
    try:
        meta = json.loads((wd / "meta.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        sys.exit("error: cannot read %s: %s" % (wd / "meta.json", e))
    i18n = json.loads((SCRIPT_DIR / "i18n.json").read_text(encoding="utf-8"))
    strings = i18n.get(meta.get("lang", "zh"), i18n["zh"])
    namespace = "mm:" + (meta.get("id") or meta["title"]) + ":"
    sources = [("given", p) for p in a.leveldb] or find_dirs(a.browser)
    if not sources:
        sys.exit("error: no browser local-storage directory found. Pass one with --leveldb, "
                 "or ask the user to click \"Copy for AI\" on the page instead.")

    found, notes, misses = {}, [], []       # id -> item; read problems; browsers without this page
    for name, directory in sources:
        try:
            storage, bad = local_storage(directory, a.origin)
        except Exception as e:
            notes.append("could not read %s: %s" % (directory, e))
            continue
        for b in bad:
            notes.append("%s: a file could not be read: %s" % (directory, b))
        value = storage.get((a.origin, namespace + "items"))
        if value is None:
            misses.append("%s (%s) has no %sitems" % (name, directory, namespace))
            continue
        try:
            items = json.loads(value)
        except ValueError as e:
            notes.append("%s: items is not valid JSON: %s" % (name, e))
            continue
        for it in items:
            if isinstance(it, dict) and it.get("id"):
                it = dict(it)
                it["_src"] = name
                found.setdefault(it["id"], it)
    for n in notes + (misses if not found else []):   # another browser lacking this page is normal
        print("NOTE:", n, file=sys.stderr)
    if not found:
        sys.exit("error: no feedback found (the page has no saved feedback yet, or it was opened in another "
                 "browser or profile).")
    items = sorted(found.values(), key=lambda x: x.get("ts", ""))
    source = ", ".join(sorted({i["_src"] for i in items}))

    if a.compare:
        ref = json.loads(pathlib.Path(a.compare).read_text(encoding="utf-8"))
        ref_by_id = {x["id"]: x for x in ref}
        same = diff = 0
        for rid, r in ref_by_id.items():
            g = found.get(rid)
            if g is None:
                print("missing:", rid)
                diff += 1
                continue
            gg = {k: v for k, v in g.items() if k != "_src"}
            if gg == r:
                same += 1
            else:
                diff += 1
                print("differs:", rid, {k: (r.get(k), gg.get(k)) for k in set(r) | set(gg) if r.get(k) != gg.get(k)})
        extra = [i["id"] for i in items if i["id"] not in ref_by_id]
        print("compared %d: identical %d, different or missing %d; found but not in the file: %d %s"
              % (len(ref_by_id), same, diff, len(extra), extra))
        sys.exit(0 if diff == 0 else 1)

    py = "python" if os.name == "nt" else "python3"
    reply_hint = ('Reply to each: %s "%s" "%s" %s   (--status: done|doing|planned|dropped|needs-you; '
                  'also --node "node path", --ask "question for the user")'
                  % (py, SCRIPT_DIR / "reply.py", wd, strings["reply_args"]))
    if a.all:
        print(render(items, meta["title"], source, reply_hint, strings))
        return

    fb = wd / "_fb"
    fb.mkdir(exist_ok=True)
    inbox = fb / "inbox.jsonl"
    replies_file = wd / "replies.json"
    replied = {r["id"] for r in json.loads(replies_file.read_text(encoding="utf-8-sig"))} if replies_file.exists() else set()
    inbox_ids = {x["id"] for x in load_jsonl(inbox) if "id" in x}
    known_file = fb / "known.json"
    known_ids = {x["id"] for x in json.loads(known_file.read_text(encoding="utf-8-sig"))} if known_file.exists() else set()
    new = [i for i in items if i["id"] not in replied and i["id"] not in inbox_ids and i["id"] not in known_ids]
    pending = [i for i in items if i["id"] not in replied and i["id"] in inbox_ids]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if new:
        with inbox.open("a", encoding="utf-8", newline="\n") as f:
            for i in new:
                rec = {k: v for k, v in i.items() if k != "_src"}
                rec["pulled_at"] = now
                rec["source"] = i["_src"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("Found %d item(s) in the browser; %d already answered; %d new; %d pulled earlier but not answered yet."
          % (len(items), len([i for i in items if i["id"] in replied]), len(new), len(pending)))
    print("The newest item was written at %s (now %s). Browsers flush to disk with a delay of up to about a minute: "
          "if the user has just written something, wait a little and run again."
          % (items[-1].get("ts"), datetime.datetime.now().strftime("%H:%M:%S")))
    todo = new + pending
    if todo:
        print()
        print(render(todo, meta["title"], source, reply_hint, strings))
        if new:
            print("(the %d new item(s) were recorded in %s)" % (len(new), inbox))
    else:
        print("Nothing to answer.")


if __name__ == "__main__":
    main()
