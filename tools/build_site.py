#!/usr/bin/env python3
"""Build every example into one folder of ready-to-publish demo pages (used for the GitHub Pages demo).

Usage:
    python3 tools/build_site.py <output-dir>

Each example under examples/ is built with --no-paths (no local paths or .stamp.js inside the page) and written to
<output-dir>/<the example's "out" name>; an index.html links them. Standard library only.
"""
import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "mind-atlas" / "scripts"))
import build  # noqa: E402

REPO_URL = "https://github.com/jessepwj/mind-atlas"
INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>mind-atlas demos</title>
<style>
body{font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;max-width:640px;margin:48px auto;padding:0 20px;color:#1f2328}
h1{font-size:28px;margin-bottom:4px} p.sub{color:#57606a;margin-top:0}
li{margin:10px 0} a{color:#0969da} small{color:#57606a}
</style>
</head>
<body>
<h1>mind-atlas</h1>
<p class="sub">Interactive, multi-level HTML mind maps made by your AI agent. Live demos of the examples in the repository.<br>让 AI 智能体生成的多级交互式 HTML 思维导图。下面是仓库里示例的在线演示。</p>
<ul>
%(items)s
</ul>
<p><a href="%(repo)s">Source, install instructions and docs / 源码与说明</a></p>
</body>
</html>
"""


def build_site(out_dir):
    """Build all examples into out_dir. Returns the list of page file names written."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items, written = [], []
    for src in sorted((ROOT / "examples").iterdir()):
        if not (src / "meta.json").exists():
            continue
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-site-"))
        try:
            work = pathlib.Path(shutil.copytree(str(src), str(tmp / "work")))
            result = build.build(work, no_paths=True)
            if result.warnings:
                raise SystemExit("example %s has warnings: %s" % (src.name, result.warnings))
            meta = json.loads((work / "meta.json").read_text(encoding="utf-8"))
            shutil.copyfile(str(result.out), str(out_dir / result.out.name))
        finally:
            shutil.rmtree(str(tmp), ignore_errors=True)
        language = "English" if meta.get("lang") == "en" else "中文"
        kind = {"tracking": "project tracking / 跟进项目", "learning": "learning / 学习理解",
                "decision": "decision / 做决定"}.get(build.normalize_use(meta.get("use", "")), "map / 导图")
        items.append('<li><a href="%s">%s</a> <small>%s, %s, %d nodes</small></li>'
                     % (result.out.name, build.esc(meta["title"]), language, kind, result.nodes))
        written.append(result.out.name)
    build.write_text(out_dir / "index.html", INDEX % {"items": "\n".join(items), "repo": REPO_URL})
    build.write_text(out_dir / ".nojekyll", "")
    return written


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.exit(__doc__)
    build.configure_streams()
    for name in build_site(argv[0]):
        print("wrote", name)
    print("wrote index.html")


if __name__ == "__main__":
    main()
