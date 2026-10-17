"""pull_feedback.py: read the feedback out of a browser's LevelDB local storage (pure functions and the command)."""
import json
import os
import pathlib
import struct
import tempfile
import shutil
import unittest

from helpers import WorkdirCase, load_script, run_script, text

pull = load_script("pull_feedback")


# ---- tiny writers for the formats the script reads (the test must not depend on a real browser) ----
def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def snappy_literal(data):
    n = len(data) - 1
    if n < 60:
        return bytes([n << 2]) + data
    return bytes([60 << 2, n]) + data           # one length byte covers up to 256 bytes


def snappy_copy2(length, offset):
    return bytes([((length - 1) << 2) | 2]) + struct.pack("<H", offset)


def snappy_copy1(length, offset):
    return bytes([((offset >> 8) << 5) | ((length - 4) << 2) | 1, offset & 0xFF])


def snappy_block(uncompressed_len, ops):
    return varint(uncompressed_len) + b"".join(ops)


def ls_key(name, origin="file://"):
    return ("_" + origin).encode() + b"\x00\x01" + name.encode("latin-1")


def ls_value(text_, wide=None):
    """Chromium stores a string as Latin-1 (first byte 1) when it can, otherwise as UTF-16 (first byte 0)."""
    if wide is None:
        wide = any(ord(c) > 255 for c in text_)
    return b"\x00" + text_.encode("utf-16-le") if wide else b"\x01" + text_.encode("latin-1")


def write_batch(entries, seq=1):
    """entries: [(key, value or None)]; None is a delete."""
    out = struct.pack("<QI", seq, len(entries))
    for key, value in entries:
        if value is None:
            out += b"\x00" + varint(len(key)) + key
        else:
            out += b"\x01" + varint(len(key)) + key + varint(len(value)) + value
    return out


def log_file(path, batches):
    """A .log file: each batch is one full record in the 32 KB block format (records never cross a block here)."""
    data = bytearray()
    for b in batches:
        if 32768 - len(data) % 32768 < 7 + len(b):
            data += bytes(32768 - len(data) % 32768)
        data += b"\x00\x00\x00\x00" + struct.pack("<H", len(b)) + b"\x01" + b
    pathlib.Path(path).write_bytes(bytes(data))


def table_block(entries, compress=False):
    """entries: [(key, value)] already sorted; one restart point per block."""
    body = b"".join(varint(0) + varint(len(k)) + varint(len(v)) + k + v for k, v in entries)
    body += struct.pack("<I", 0) + struct.pack("<I", 1)
    if compress:
        return snappy_block(len(body), [snappy_literal(body)]), 1
    return body, 0


def ldb_file(path, entries, compress=False):
    """A .ldb file with one data block. entries: [(user key, sequence, type, value)]."""
    internal = [(k + struct.pack("<Q", (seq << 8) | typ), v) for k, seq, typ, v in sorted(entries)]
    data_block, kind = table_block(internal, compress)
    data = data_block + bytes([kind]) + b"\0\0\0\0"
    handle = varint(0) + varint(len(data_block))
    index_block, ikind = table_block([(internal[-1][0], handle)])
    index_off = len(data)
    data += index_block + bytes([ikind]) + b"\0\0\0\0"
    footer = varint(0) + varint(0) + varint(index_off) + varint(len(index_block))
    footer += bytes(40 - len(footer)) + pull.LDB_MAGIC
    pathlib.Path(path).write_bytes(data + footer)


class SnappyTests(unittest.TestCase):
    def test_literal_only(self):
        self.assertEqual(pull.snappy_decompress(snappy_block(5, [snappy_literal(b"hello")])), b"hello")

    def test_a_literal_longer_than_sixty_bytes(self):
        data = bytes(range(100))
        self.assertEqual(pull.snappy_decompress(snappy_block(100, [snappy_literal(data)])), data)

    def test_copy_with_two_byte_offset(self):
        self.assertEqual(pull.snappy_decompress(snappy_block(9, [snappy_literal(b"abcd"), snappy_copy2(5, 4)])), b"abcdabcda")

    def test_copy_with_one_byte_offset(self):
        self.assertEqual(pull.snappy_decompress(snappy_block(8, [snappy_literal(b"abcd"), snappy_copy1(4, 4)])), b"abcdabcd")

    def test_an_overlapping_copy_repeats_the_pattern(self):
        self.assertEqual(pull.snappy_decompress(snappy_block(8, [snappy_literal(b"ab"), snappy_copy2(6, 2)])), b"abababab")

    def test_a_multi_byte_length_prefix(self):
        data = b"x" * 300
        block = snappy_block(300, [snappy_literal(b"x"), snappy_copy2(64, 1)] * 4 + [snappy_copy2(40, 1)])
        self.assertEqual(pull.snappy_decompress(block), data[:300])

    def test_an_offset_beyond_the_output_is_corrupt(self):
        with self.assertRaises(ValueError):
            pull.snappy_decompress(snappy_block(6, [snappy_literal(b"ab"), snappy_copy2(4, 9)]))

    def test_a_wrong_length_prefix_is_corrupt(self):
        with self.assertRaises(ValueError):
            pull.snappy_decompress(snappy_block(7, [snappy_literal(b"hello")]))

    def test_empty_payload(self):
        self.assertEqual(pull.snappy_decompress(b"\x00"), b"")


class SmallFunctionTests(unittest.TestCase):
    def test_varint(self):
        for n in (0, 1, 127, 128, 300, 16383, 16384, 2 ** 31):
            self.assertEqual(pull.varint(varint(n) + b"tail", 0), (n, len(varint(n))))

    def test_varint_from_an_offset(self):
        self.assertEqual(pull.varint(b"xx" + varint(300), 2), (300, 4))

    def test_decode_str(self):
        self.assertEqual(pull.decode_str(b""), "")
        self.assertEqual(pull.decode_str(b"\x01hello"), "hello")
        self.assertEqual(pull.decode_str(b"\x00" + "中文 ok".encode("utf-16-le")), "中文 ok")
        self.assertEqual(pull.decode_str(b"\x01caf\xe9"), "café")

    def test_plural_and_fmt(self):
        self.assertEqual(pull.plural({"one": "a", "other": "b"}, 1), "a")
        self.assertEqual(pull.plural({"one": "a", "other": "b"}, 2), "b")
        self.assertEqual(pull.plural("same", 5), "same")
        self.assertEqual(pull.fmt("{a} and {b}", a=1, b="x"), "1 and x")

    def test_browser_roots_name_the_usual_browsers(self):
        roots = pull.browser_roots()
        for name in ("chrome", "chromium", "edge", "brave"):
            self.assertIn(name, roots)
            self.assertTrue(str(roots[name]))


class BatchAndLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-ldb-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)

    def collect(self, reader, path):
        seen = []
        reader(path, lambda key, seq, typ, val: seen.append((key, seq, typ, val)))
        return seen

    def test_a_batch_yields_puts_and_deletes_with_consecutive_sequences(self):
        seen = []
        pull.read_batch(write_batch([(b"k1", b"v1"), (b"k2", None), (b"k3", b"v3")], seq=10),
                        lambda key, seq, typ, val: seen.append((key, seq, typ, val)))
        self.assertEqual(seen, [(b"k1", 10, 1, b"v1"), (b"k2", 11, 0, b""), (b"k3", 12, 1, b"v3")])

    def test_a_truncated_batch_does_not_crash(self):
        seen = []
        pull.read_batch(write_batch([(b"k1", b"value")], seq=1)[:-3], lambda *a: seen.append(a))
        self.assertEqual(seen, [])
        pull.read_batch(b"short", lambda *a: seen.append(a))

    def test_log_file_records(self):
        path = self.tmp / "000003.log"
        log_file(path, [write_batch([(b"a", b"1")], seq=1), write_batch([(b"b", b"2")], seq=2)])
        self.assertEqual([(k, v) for k, _, _, v in self.collect(pull.read_log, path)], [(b"a", b"1"), (b"b", b"2")])

    def test_a_record_that_was_not_finished_is_ignored(self):
        path = self.tmp / "000003.log"
        log_file(path, [write_batch([(b"a", b"1")], seq=1), write_batch([(b"b", b"2")], seq=2)])
        path.write_bytes(path.read_bytes()[:-2])
        self.assertEqual([k for k, _, _, _ in self.collect(pull.read_log, path)], [b"a"])

    def test_fragmented_records_are_joined(self):
        batch = write_batch([(b"big", b"v" * 100)], seq=5)
        first, middle, last = batch[:40], batch[40:80], batch[80:]

        def rec(kind, payload):
            return b"\x00\x00\x00\x00" + struct.pack("<H", len(payload)) + bytes([kind]) + payload

        path = self.tmp / "000004.log"
        path.write_bytes(rec(2, first) + rec(3, middle) + rec(4, last))
        seen = self.collect(pull.read_log, path)
        self.assertEqual([(k, len(v)) for k, _, _, v in seen], [(b"big", 100)])

    def test_ldb_table_plain_and_snappy(self):
        entries = [(b"a", 1, 1, b"alpha"), (b"b", 2, 1, b"beta"), (b"c", 3, 0, b"")]
        for compress in (False, True):
            with self.subTest(compress=compress):
                path = self.tmp / ("000005-%s.ldb" % compress)
                ldb_file(path, entries, compress)
                self.assertEqual(sorted(self.collect(pull.read_ldb, path)), sorted(entries))

    def test_not_a_table_is_an_error(self):
        path = self.tmp / "bad.ldb"
        path.write_bytes(b"x" * 100)
        with self.assertRaises(ValueError):
            pull.read_ldb(path, lambda *a: None)

    def test_directory_keeps_the_newest_value_and_drops_deleted_and_foreign_keys(self):
        name = ls_key("mm:one:items")
        gone = ls_key("mm:one:gone")
        other = ls_key("mm:one:other", "https://example.org")
        ldb_file(self.tmp / "000005.ldb", [(name, 1, 1, ls_value("old")), (gone, 2, 1, ls_value("x")), (other, 3, 1, ls_value("y"))])
        log_file(self.tmp / "000006.log", [write_batch([(name, ls_value("new")), (gone, None)], seq=10)])
        kv, bad = pull.read_leveldb_dir(str(self.tmp))
        self.assertEqual(bad, [])
        self.assertEqual(kv, {name: ls_value("new")})
        kv2, _ = pull.read_leveldb_dir(str(self.tmp), "https://example.org")
        self.assertEqual(kv2, {other: ls_value("y")})

    def test_one_broken_file_does_not_hide_the_others(self):
        (self.tmp / "000001.ldb").write_bytes(b"garbage")
        log_file(self.tmp / "000002.log", [write_batch([(ls_key("mm:a:items"), ls_value("[]"))], seq=1)])
        kv, bad = pull.read_leveldb_dir(str(self.tmp))
        self.assertEqual(len(kv), 1)
        self.assertEqual(len(bad), 1)
        self.assertIn("000001.ldb", bad[0])

    def test_local_storage_decodes_origin_key_and_both_string_encodings(self):
        log_file(self.tmp / "000002.log", [write_batch([(ls_key("mm:a:items"), ls_value("[1]")),
                                                        (ls_key("mm:a:wide"), ls_value("中文", wide=True))], seq=1)])
        (self.tmp / "LOCK").write_text("", encoding="utf-8")
        storage, bad = pull.local_storage(str(self.tmp))
        self.assertEqual(bad, [])
        self.assertEqual(storage, {("file://", "mm:a:items"): "[1]", ("file://", "mm:a:wide"): "中文"})

    def test_local_storage_leaves_the_original_directory_alone(self):
        log_file(self.tmp / "000002.log", [write_batch([(ls_key("mm:a:items"), ls_value("[1]"))], seq=1)])
        before = sorted(p.name for p in self.tmp.iterdir())
        pull.local_storage(str(self.tmp))
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), before)


ITEMS = [
    {"id": "F1017-101500-ab", "ts": "2026-10-17 10:15:00", "text": "what about ladders?\nsecond line",
     "quotes": [{"p": ["Atlas", "Rules", "No ladders"], "x": "ladders"}], "ctx": None, "sent": None, "replaces": None},
    {"id": "F1017-101600-cd", "ts": "2026-10-17 10:16:00", "text": "中文也行", "quotes": [], "ctx": ["Atlas", "Now"], "sent": None, "replaces": "F1016-000000-zz"},
]


class CommandTests(WorkdirCase):
    def setUp(self):
        super().setUp()
        self.write_meta(id="test-map", lang="en", title="Test map")
        self.write("outline.md", "# Atlas\n- A\n")
        self.ldb = self.tmp / "leveldb"
        self.ldb.mkdir()
        self.put(ITEMS)

    def put(self, items, name="mm:test-map:items", origin="file://", seq=1, wide=None):
        log_file(self.ldb / "000003.log", [write_batch([(ls_key(name, origin), ls_value(json.dumps(items, ensure_ascii=False), wide=wide))], seq=seq)])

    def pull(self, *args, workdir=True):
        base = [self.wd] if workdir else []
        return run_script("pull_feedback", *(base + ["--leveldb", self.ldb] + list(args)))

    def inbox(self):
        path = self.wd / "_fb" / "inbox.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def test_help_says_when_to_run_it(self):
        proc = run_script("pull_feedback", "--help")
        self.assertEqual(proc.returncode, 0)
        out = text(proc)[0]
        self.assertIn("Pull the feedback", out)
        self.assertIn("--leveldb", out)
        self.assertIn("--origin", out)
        self.assertIn("explicitly", out)

    def test_the_module_docstring_states_the_manual_only_rule(self):
        doc = pull.__doc__
        self.assertIn("pull my feedback", doc)
        self.assertIn("Never on a timer", doc)
        self.assertIn("never as a background service", doc)

    def test_first_run_prints_the_new_items_and_records_them(self):
        proc = self.pull()
        out, err = text(proc)
        self.assertEqual(proc.returncode, 0, err)
        self.assertIn("Found 2 item(s) in the browser; 0 already answered; 2 new; 0 pulled earlier", out)
        self.assertIn("[Mind map feedback] Test map, 2 items (from given, pulled ", out)
        self.assertIn("1. [F1017-101500-ab] 10-17 10:15", out)
        self.assertIn("   Quote: Rules › No ladders\n         “ladders”", out)
        self.assertIn("   Says: what about ladders?\n      second line", out)
        self.assertIn("2. [F1017-101600-cd] 10-17 10:16 (revises F1016-000000-zz)", out)
        self.assertIn("   (no quote; the node selected when written: Now)", out)
        self.assertIn("   Says: 中文也行", out)
        self.assertIn("Reply to each:", out)
        self.assertIn("reply.py", out)
        self.assertEqual([r["id"] for r in self.inbox()], ["F1017-101500-ab", "F1017-101600-cd"])
        self.assertEqual(self.inbox()[0]["source"], "given")
        self.assertRegex(self.inbox()[0]["pulled_at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_second_run_lists_unanswered_items_again_but_records_nothing_new(self):
        self.pull()
        out = text(self.pull())[0]
        self.assertIn("0 new; 2 pulled earlier but not answered yet", out)
        self.assertIn("2 items", out)
        self.assertEqual(len(self.inbox()), 2)

    def test_answered_items_drop_out(self):
        self.pull()
        self.write("replies.json", json.dumps([{"id": "F1017-101500-ab", "ts": "2026-10-17 11:00:00", "text": "done"}]))
        out = text(self.pull())[0]
        self.assertIn("1 already answered", out)
        self.assertIn("[Mind map feedback] Test map, 1 item (", out)
        self.assertNotIn("[F1017-101500-ab]", out.split("Reply to each")[0].split("\n\n", 1)[1])

    def test_everything_answered_says_so(self):
        self.write("replies.json", json.dumps([{"id": i["id"], "ts": "t", "text": "x"} for i in ITEMS]))
        self.assertIn("Nothing to answer.", text(self.pull())[0])

    def test_known_json_counts_as_pulled_before(self):
        self.write("_fb/known.json", json.dumps([ITEMS[0]]))
        out = text(self.pull())[0]
        self.assertIn("1 new", out)
        self.assertEqual([r["id"] for r in self.inbox()], ["F1017-101600-cd"])

    def test_all_prints_everything_and_writes_nothing(self):
        out = text(self.pull("--all"))[0]
        self.assertIn("2 items", out)
        self.assertFalse((self.wd / "_fb").exists())

    def test_the_block_follows_the_language_of_the_map(self):
        self.write_meta(id="test-map", lang="zh", title="测试图")
        out = text(self.pull())[0]
        self.assertIn("【导图反馈】测试图，2 条（given，", out)
        self.assertIn("   引用：Rules › No ladders\n         「ladders」", out)
        self.assertIn("   说：中文也行", out)
        self.assertIn("2. [F1017-101600-cd] 10月17日 10:16（改写了之前的 F1016-000000-zz）", out)
        self.assertIn('--status 已做', out)

    def test_wide_strings_are_read_too(self):
        self.put(ITEMS, wide=True)
        self.assertIn("2 new", text(self.pull())[0])

    def test_another_page_in_the_same_browser_is_not_confused(self):
        self.put(ITEMS, name="mm:other-map:items")
        proc = self.pull()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no feedback found", text(proc)[1])

    def test_a_hosted_page_is_found_through_origin(self):
        self.put(ITEMS, origin="https://example.org")
        self.assertNotEqual(self.pull().returncode, 0)
        proc = self.pull("--origin", "https://example.org")
        self.assertEqual(proc.returncode, 0, text(proc)[1])
        self.assertIn("2 new", text(proc)[0])

    def test_compare_exits_zero_when_identical(self):
        ref = self.tmp / "ref.json"
        ref.write_text(json.dumps(ITEMS), encoding="utf-8")
        proc = self.pull("--compare", ref)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("identical 2", text(proc)[0])

    def test_compare_reports_differences_and_missing_items(self):
        changed = [dict(ITEMS[0], text="edited"), {"id": "F-missing", "text": "x"}]
        ref = self.tmp / "ref.json"
        ref.write_text(json.dumps(changed), encoding="utf-8")
        proc = self.pull("--compare", ref)
        out = text(proc)[0]
        self.assertEqual(proc.returncode, 1)
        self.assertIn("differs: F1017-101500-ab", out)
        self.assertIn("missing: F-missing", out)

    def test_missing_work_directory_is_an_error(self):
        proc = self.pull(workdir=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("work directory", text(proc)[1])

    def test_a_directory_without_meta_json_is_an_error(self):
        proc = run_script("pull_feedback", self.tmp / "nowhere", "--leveldb", self.ldb)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("meta.json", text(proc)[1])

    def test_no_browser_found_points_at_the_copy_button(self):
        home = self.tmp / "emptyhome"
        home.mkdir()
        env = {"HOME": str(home), "USERPROFILE": str(home), "LOCALAPPDATA": str(home / "Local"), "XDG_CONFIG_HOME": str(home / ".config")}
        proc = run_script("pull_feedback", self.wd, env=env)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Copy for AI", text(proc)[1])


if __name__ == "__main__":
    unittest.main()
