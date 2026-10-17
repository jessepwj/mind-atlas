"""Shared helpers for the test suite (standard library only)."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "mind-atlas" / "scripts"
EXAMPLES = ROOT / "examples"
CJK = re.compile("[㐀-鿿]")


def load_script(name):
    """Import skills/mind-atlas/scripts/<name>.py under a private module name."""
    spec = importlib.util.spec_from_file_location("mind_atlas_" + name, str(SCRIPTS / (name + ".py")))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_script("build")


def page_json(html, script_id):
    """Decode one of the JSON blocks (data, meta, replies, i18n) embedded in a built page."""
    m = re.search(r'<script id="%s" type="application/json">(.*?)</script>' % script_id, html, re.S)
    if not m:
        raise AssertionError("no %s block in the page" % script_id)
    return json.loads(m.group(1))


def run_script(name, *args, **kwargs):
    """Run a script as a subprocess; returns CompletedProcess with text output (UTF-8)."""
    env = dict(os.environ)
    env.update(kwargs.pop("env", {}))
    env.setdefault("PYTHONUTF8", "1")
    return subprocess.run([sys.executable, str(SCRIPTS / (name + ".py"))] + [str(a) for a in args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, **kwargs,
                          universal_newlines=False)


def text(proc):
    """Decoded (stdout, stderr) with Windows line endings turned into newlines."""
    return (proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"),
            proc.stderr.decode("utf-8", "replace").replace("\r\n", "\n"))


class WorkdirCase(unittest.TestCase):
    """Gives each test an empty temporary work directory."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-test-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.wd = self.tmp / "work"
        self.wd.mkdir()

    def write(self, name, content, binary=False):
        path = self.wd / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if binary:
            path.write_bytes(content)
        else:
            build.write_text(path, content)
        return path

    def write_meta(self, **fields):
        meta = {"title": "Test map", "id": "test-map", "lang": "en"}
        meta.update(fields)
        return self.write("meta.json", json.dumps(meta, ensure_ascii=False))

    def build(self, outline=None, no_paths=False, **meta):
        """Write meta.json (and outline.md when given) and build; returns the BuildResult."""
        self.write_meta(**meta)
        if outline is not None:
            self.write("outline.md", outline)
        return build.build(self.wd, no_paths=no_paths)

    def html(self, result):
        return result.out.read_text(encoding="utf-8")


@contextlib.contextmanager
def quiet():
    """Swallow stdout/stderr of in-process calls."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err
