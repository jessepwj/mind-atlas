#!/usr/bin/env python3
"""Regenerate the README screenshots (docs/assets/screenshot-en.png, screenshot-zh.png, screenshot-console-en.png
and screenshot-console-zh.png).

Usage:
    python3 tools/make_screenshots.py [output-dir]

Builds four examples, opens each in headless Chrome/Chromium with made-up feedback and AI replies already
in the right panel (and, for the console shots, the list behind "Needs you" open) and saves a screenshot of each. Needs Chrome, Chromium or
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

# One entry per screenshot: which example, the made-up feedback items (what the user wrote) and replies (what the agent
# answered) that the page already holds, and the clicks to make before the picture is taken.
#   items:   id, ts, text, path (titles under the root; [] = no quote), sent
#   replies: id, ts, text, plus the optional summary, status, nodes, ask
#   edited / new: titles of nodes shown as Edited / New (the "what you last saw" snapshot is faked from them)
CLASSIC_STEPS = """
  click(document.querySelector('[data-lv="3"]')); await sleep(100);
  const q = $('q'); q.value = %(search)s; q.dispatchEvent(new Event('input', {bubbles: true})); await sleep(600);
  q.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); await sleep(600);
  const hit = [...document.querySelectorAll('.node')].find(n => n.textContent.includes(%(node)s));
  click(hit); await sleep(600);
  click($('zo')); await sleep(500); click($('zo')); await sleep(500); click($('zo')); await sleep(500);
"""
CONSOLE_STEPS = """
  const chip = document.querySelector('#cons .chip[data-k="ask"]'); click(chip); await sleep(600);
"""

SHOTS = [
    {
        "example": "tool-library-en", "file": "screenshot-en.png", "steps": CLASSIC_STEPS,
        "search": "damp wall", "node": "Damp wall may rust",
        "items": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:15:00", "sent": "2026-10-16 10:16:00",
                   "text": "How damp is it really? A humidity logger for a month would tell us before we spend money.",
                   "path": ["Problems and next steps", "1. Protect the tools", "Damp wall may rust the steel tools"]}],
        "replies": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:40:00", "status": "done",
                     "summary": "Added a node: borrow a logger and measure for four weeks before buying anything.",
                     "text": "Good point. I added a node under this risk: borrow a logger and read it for four weeks before "
                             "buying dehumidifiers. The proposal is marked as not decided yet.",
                     "nodes": ["Damp wall may rust the steel tools"]}],
    },
    {
        "example": "book-corner-zh", "file": "screenshot-zh.png", "steps": CLASSIC_STEPS,
        "search": "梅雨季书会", "node": "梅雨季书会发霉",
        "items": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:15:00", "sent": "2026-10-16 10:16:00",
                   "text": "到底有多潮？先放一个湿度计观察一个月，再决定要不要花钱买除湿盒。",
                   "path": ["问题与下一步", "一、先保书", "梅雨季书会发霉"]}],
        "replies": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:40:00", "status": "已做",
                     "summary": "已加一个节点：先借湿度计测四周，再决定买不买除湿盒。",
                     "text": "有道理。我在这条风险下加了一个节点：先借一个湿度计，观察四周再决定买不买除湿盒。这条建议还没有定。",
                     "nodes": ["梅雨季书会发霉"]}],
    },
    {
        "example": "repair-cafe-en", "file": "screenshot-console-en.png", "steps": CONSOLE_STEPS,
        "edited": "Print the new sign-up sheet", "new": "Flyers delivered to 40 mailboxes",
        "items": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:15:00", "sent": "2026-10-16 10:16:00",
                   "text": "Can we also fix kettles and toasters?", "path": ["Purpose and rules", "Fix what neighbors bring, for free"]},
                  {"id": "F1016-102500-cd", "ts": "2026-10-16 10:25:00", "sent": "2026-10-16 10:26:00",
                   "text": "What is holding up the autumn session?", "path": ["Now", "Needs your decision", "Pick the date of the autumn session"]}],
        "replies": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:20:00", "status": "done",
                     "summary": "Yes: kettles and toasters are fine as long as no mains rewiring is needed.",
                     "text": "Small appliances with a plug are in scope. I added them to the rule and to the sign-in sheet draft.",
                     "nodes": ["Purpose and rules › Fix what neighbors bring, for free"]},
                    {"id": "F1016-102500-cd", "ts": "2026-10-16 10:30:00", "status": "needs-you",
                     "summary": "Only the date: the hall is free on 12 Nov and 19 Nov.",
                     "ask": "Which date do you pick for the autumn session?",
                     "text": "Everything else is ready. The hall is free on both dates; the volunteers lean towards the 19th.",
                     "nodes": ["Pick the date of the autumn session"]}],
    },
    {
        "example": "repair-cafe-zh", "file": "screenshot-console-zh.png", "steps": CONSOLE_STEPS,
        "edited": "印新的签到表", "new": "传单已投进 40 个信箱",
        "items": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:15:00", "sent": "2026-10-16 10:16:00",
                   "text": "水壶和烤面包机也能修吗？", "path": ["目的与规矩", "免费帮邻居修他们带来的东西"]},
                  {"id": "F1016-102500-cd", "ts": "2026-10-16 10:25:00", "sent": "2026-10-16 10:26:00",
                   "text": "秋季场现在卡在哪？", "path": ["现在", "等你拍板", "选定秋季场的日期"]}],
        "replies": [{"id": "F1016-101500-ab", "ts": "2026-10-16 10:20:00", "status": "已做",
                     "summary": "能修：水壶和烤面包机都行，只要不用改市电布线。",
                     "text": "带插头的小家电都在范围内。我已把它们写进规矩，也加进了签到表草稿。",
                     "nodes": ["目的与规矩 › 免费帮邻居修他们带来的东西"]},
                    {"id": "F1016-102500-cd", "ts": "2026-10-16 10:30:00", "status": "要你定",
                     "summary": "只差日期：礼堂 11 月 12 日和 19 日都空着。",
                     "ask": "秋季场选哪一天？",
                     "text": "别的都准备好了。礼堂这两天都空着，志愿者倾向 19 日。",
                     "nodes": ["选定秋季场的日期"]}],
    },
]


def walk(node, root_key, path=None):
    """Yield (full path, node) for the built page's data tree (the root is named root_key)."""
    here = (path or []) + [root_key if path is None else node["t"]]
    yield " \u203a ".join(here), node
    for child in node["c"]:
        for item in walk(child, root_key, here):
            yield item


def shoot(shot, out_dir, chrome):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mmtest-shot-"))
    try:
        work = pathlib.Path(shutil.copytree(str(ROOT / "examples" / shot["example"]), str(tmp / "work")))
        (work / "replies.json").write_text(json.dumps(shot["replies"], ensure_ascii=False), encoding="utf-8")
        result = build.build(work, no_paths=True)
        html = result.out.read_text(encoding="utf-8")
        meta = json.loads(html.split('<script id="meta" type="application/json">')[1].split("</script>")[0])
        data = json.loads(html.split('<script id="data" type="application/json">')[1].split("</script>")[0])
        root = meta.get("root_key") or data["t"]
        items = [{"id": it["id"], "ts": it["ts"], "text": it["text"], "ctx": None, "sent": it["sent"], "replaces": None,
                  "quotes": [{"p": [root] + it["path"], "x": ""}] if it["path"] else []} for it in shot["items"]]
        storage = {"mm:%s:items" % meta["id"]: items}
        if shot.get("edited") or shot.get("new"):       # fake the snapshot of what the user last saw
            snap = {}
            for key, node in walk(data, root):
                if node["t"] == shot.get("edited"):
                    snap[bh.fnv_key(key)] = "00000000"
                elif node["t"] != shot.get("new"):
                    snap[bh.fnv_key(key)] = node["f"]
            storage["mm:%s:snap" % meta["id"]] = snap
            storage["mm:%s:snapTs" % meta["id"]] = "2026-10-15 09:00:00"
        seed = "".join("localStorage.setItem(%s, %s);" % (json.dumps(k), json.dumps(json.dumps(v))) for k, v in storage.items())
        pre = "<script>" + bh.PRE_JS.replace("/*SEED*/", seed) + "</script>\n"
        steps = shot["steps"] % {"search": json.dumps(shot.get("search", "")), "node": json.dumps(shot.get("node", ""))}
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
