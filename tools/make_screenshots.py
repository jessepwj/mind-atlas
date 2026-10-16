#!/usr/bin/env python3
"""Regenerate the README screenshots (docs/assets/screenshot-en.png and screenshot-zh.png).

Usage:
    python3 tools/make_screenshots.py [output-dir]

Builds both examples, opens each in headless Chrome/Chromium with a made-up piece of feedback and an AI
reply already in the right panel, selects one node and saves a screenshot. Needs Chrome, Chromium or
Edge (set MIND_ATLAS_CHROME to choose one). Standard library only.
"""
import datetime
import json
import os
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "mind-atlas" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import browser_harness as bh  # noqa: E402
import build  # noqa: E402

STAMP = int(datetime.datetime(2026, 10, 16, 10, 45, tzinfo=datetime.timezone.utc).timestamp())

# One entry per screenshot: which example, what to search for to bring the node into view,
# and the made-up feedback and reply that the right panel shows.
SHOTS = [
    {
        "example": "tool-library-en", "file": "screenshot-en.png", "search": "damp wall", "node": "Damp wall may rust",
        "path": ["Problems and next steps", "1. Protect the tools", "Damp wall may rust the steel tools"],
        "feedback": "How damp is it really? A humidity logger for a month would tell us before we spend money.",
        "reply": "Good point. I added a node under this risk: borrow a logger and read it for four weeks before "
                 "buying dehumidifiers. The proposal is marked as not decided yet.",
    },
    {
        "example": "book-corner-zh", "file": "screenshot-zh.png", "search": "梅雨季书会", "node": "梅雨季书会发霉",
        "path": ["问题与下一步", "一、先保书", "梅雨季书会发霉"],
        "feedback": "到底有多潮？先放一个湿度计观察一个月，再决定要不要花钱买除湿盒。",
        "reply": "有道理。我在这条风险下加了一个节点：先借一个湿度计，观察四周再决定买不买除湿盒。这条建议还没有定。",
    },
]

STEPS = """
  click(document.querySelector('[data-lv="3"]')); await sleep(100);
  const q = $('q'); q.value = %(search)s; q.dispatchEvent(new Event('input', {bubbles: true})); await sleep(600);
  q.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); await sleep(600);
  const hit = [...document.querySelectorAll('.node')].find(n => n.textContent.includes(%(node)s));
  click(hit); await sleep(600);
  click($('zo')); await sleep(500); click($('zo')); await sleep(500); click($('zo')); await sleep(500);
"""


def shoot(shot, out_dir, chrome):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mmtest-shot-"))
    try:
        work = pathlib.Path(shutil.copytree(str(ROOT / "examples" / shot["example"]), str(tmp / "work")))
        reply_id = "F1016-101500-ab"
        (work / "replies.json").write_text(json.dumps(
            [{"id": reply_id, "ts": "2026-10-16 10:40:00", "text": shot["reply"], "orig": ""}], ensure_ascii=False), encoding="utf-8")
        result = build.build(work, no_paths=True)
        html = result.out.read_text(encoding="utf-8")
        meta = json.loads(html.split('<script id="meta" type="application/json">')[1].split("</script>")[0])
        data = json.loads(html.split('<script id="data" type="application/json">')[1].split("</script>")[0])
        item = {"id": reply_id, "ts": "2026-10-16 10:15:00", "text": shot["feedback"], "ctx": None,
                "quotes": [{"p": [data["t"]] + shot["path"], "x": ""}], "sent": "2026-10-16 10:16:00", "replaces": None}
        seed = "localStorage.setItem(%s, %s);" % (json.dumps("mm:%s:items" % meta["id"]), json.dumps(json.dumps([item])))
        pre = "<script>" + bh.PRE_JS.replace("/*SEED*/", seed) + "</script>\n"
        steps = STEPS % {"search": json.dumps(shot["search"]), "node": json.dumps(shot["node"])}
        post = ("<script>(async function(){const sleep=ms=>new Promise(r=>setTimeout(r,ms));"
                "const $=id=>document.getElementById(id);const click=e=>e.click();" + steps + "})();</script></body>")
        page = tmp / "page.html"
        page.write_text(html.replace('<script id="data"', pre + '<script id="data"', 1).replace("</body>", post, 1), encoding="utf-8")
        png = pathlib.Path(out_dir) / shot["file"]
        png.parent.mkdir(parents=True, exist_ok=True)
        if png.exists():
            png.unlink()
        bh.run_chrome(chrome, page.as_uri(), ["--screenshot=" + str(png), "--hide-scrollbars", "--force-device-scale-factor=2"],
                      window=(1440, 900), budget_ms=8000, timeout=120,
                      done=lambda _t: png.exists() and png.stat().st_size > 1000)
        return png
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out_dir = argv[0] if argv else str(ROOT / "docs" / "assets")
    chrome = bh.find_chrome()
    if not chrome:
        sys.exit("error: no Chrome/Chromium/Edge found; set MIND_ATLAS_CHROME")
    os.environ["SOURCE_DATE_EPOCH"] = str(STAMP)     # a fixed "Generated ..." time in the header
    for shot in SHOTS:
        print("wrote", shoot(shot, out_dir, chrome))


if __name__ == "__main__":
    main()
