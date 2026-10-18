"""Drive a built mind-atlas page in headless Chrome (or another Chromium) and read back what it did.

The page is copied with two scripts injected: one before the page script (stubs the clipboard
and confirm(), fixes the clock and Math.random, records errors and CSP violations) and one after
it (clicks through a fixed scenario and writes the visible text after each step into the DOM).
`chrome --dump-dom` then prints the final DOM, and the result is decoded from it.

Used by test_browser.py. Chrome is optional: find_chrome() returns None when none is installed.
"""
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

PRE_JS = r"""
(function(){
  window.__clips = []; window.__errors = []; window.__violations = []; window.__clipFail = false;
  window.addEventListener('error', function(e){ window.__errors.push(String(e.message)); });
  document.addEventListener('securitypolicyviolation', function(e){ window.__violations.push(e.violatedDirective + ' ' + e.blockedURI); });
  Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
    writeText: function(t){ if (window.__clipFail) return Promise.reject(new Error('stub')); window.__clips.push(t); return Promise.resolve(); }
  }});
  window.confirm = function(){ return true; };
  var RealDate = Date, tick = 0, BASE = new RealDate(2026, 9, 16, 12, 34, 56).getTime();
  window.Date = class extends RealDate {
    constructor(...a){ if (a.length) super(...a); else super(BASE + 1000 * (tick++)); }
    static now(){ return BASE + 1000 * tick; }
  };
  Math.random = function(){ return 0.5; };
  /*SEED*/
})();
"""

SCENARIO_JS = r"""
(async function(){
  const SEARCH = /*SEARCH*/;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const log = [];
  function texts(){
    const out = [];
    (function walk(el){
      if (el.nodeType === 3){ const t = el.textContent.trim(); if (t) out.push(t); return; }
      if (el.nodeType !== 1 || /^(SCRIPT|STYLE)$/.test(el.tagName) || el.id === '__result') return;
      ['title', 'placeholder'].forEach(a => { const v = el.getAttribute(a); if (v) out.push('@' + a + '=' + v); });
      el.childNodes.forEach(walk);
    })(document.body);
    return out;
  }
  const snap = label => log.push({label, texts: texts(), values: {fbt: $('fbt').value, cpt: $('cpt').value, q: $('q').value}});
  const click = el => { if (!el) throw new Error('missing element for click'); el.click(); };
  const type = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); };
  try {
    snap('initial');
    click(document.querySelector('.d1 > .node'));
    snap('select-branch');
    click(document.querySelector('[data-lv="99"]'));
    const withNotes = Array.from(document.querySelectorAll('.node')).filter(n => n.querySelector('.ni')).pop();
    click(withNotes);
    snap('select-leaf');
    type($('q'), SEARCH); await sleep(400); snap('search-hit');
    $('q').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); snap('search-next');
    type($('q'), 'qzxqzxqzx'); await sleep(400); snap('search-none');
    $('q').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    click($('bo')); snap('outline-view');
    click(document.querySelector('#outline .oq')); snap('outline-quote');
    click($('bo'));
    click($('bn')); snap('notes-on'); click($('bn'));
    // feedback flow
    click($('fbs')); snap('submit-empty');
    click(document.querySelector('#n2 .qbtn')); click($('fbs')); snap('submit-quote-only');
    type($('fbt'), 'First feedback\nsecond line'); click($('fbs')); snap('item-1');
    click(withNotes); type($('fbt'), 'Second, without a quote'); click($('fbs')); snap('item-2');
    click($('fbn')); await sleep(50); snap('copied');
    click($('fbn')); await sleep(50); snap('copied-again');
    click(document.querySelector('[data-act="edit"]')); snap('editing');
    type($('fbt'), $('fbt').value + ' (revised)'); click($('fbs')); snap('item-revised');
    click($('fbn')); await sleep(50);
    click($('fba')); await sleep(50); snap('copy-all');
    const pn = document.querySelector('#pc .pn') || document.querySelector('#pc h2');
    const rng = document.createRange(); rng.selectNodeContents(pn);
    const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rng);
    document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); await sleep(20);
    snap('selection-popup');
    click($('selq')); type($('fbt'), 'About a sentence'); click($('fbs')); snap('item-sentence');
    window.__clipFail = true; click($('fbn')); await sleep(50); snap('copy-failed-modal'); click($('cpok')); window.__clipFail = false;
    click(document.querySelector('[data-act="del"]')); snap('deleted');
    click($('ffold')); snap('folded'); click($('fv'));
    click($('zf')); click($('zh')); click($('zi')); click($('zo')); click($('zr'));
    snap('final');
  } catch (e) { window.__errors.push('scenario: ' + e.message); }
  const result = {
    lang: document.documentElement.lang, title: document.title,
    nodes: document.querySelectorAll('.node').length,
    conn: ($('conn') || {}).textContent, connClass: ($('conn') || {}).className,
    suspicious: document.body.querySelectorAll('img,iframe,object,embed,svg,video,audio,form,[onerror],[onload],[onclick],[onmouseover]').length,
    pwned: window.__pwned === undefined ? null : window.__pwned,
    errors: window.__errors, violations: window.__violations, clips: window.__clips, log: log
  };
  const div = document.createElement('div'); div.id = '__result';
  div.setAttribute('data-b64', btoa(unescape(encodeURIComponent(JSON.stringify(result)))));
  document.body.appendChild(div);
})();
"""


CONSOLE_JS = r"""
(async function(){
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const out = {errors: window.__errors, violations: window.__violations};
  try {
    const chips = () => Array.from(document.querySelectorAll('#cons .chip')).map(c => ({
      k: c.dataset.k, label: c.querySelector('.lb').textContent, n: c.querySelector('b').textContent,
      cls: c.className, title: c.title, shown: c.style.display !== 'none', sub: (c.querySelector('.sub') || {}).textContent || ''}));
    out.chips = chips();
    out.age = $('age').textContent;
    out.sections = Array.from(document.querySelectorAll('#fbl .sec > .sh')).map(e => e.childNodes[0].textContent);
    out.sectionCounts = Array.from(document.querySelectorAll('#fbl .sec > .sh .c')).map(e => e.textContent);
    out.cards = Array.from(document.querySelectorAll('#fbl .th > summary')).map(e => e.textContent);
    out.marks = Array.from(document.querySelectorAll('.node .mk.on')).map(e => e.closest('.node').querySelector('.t').textContent + ':' + e.textContent);
    out.pills = Array.from(document.querySelectorAll('#fbl .st')).map(e => e.textContent);
    out.flt = Array.from(document.querySelectorAll('.flt button')).map(e => e.textContent);
    out.home = $('zh').textContent;
    out.legend = $('legend').textContent;
    out.hmeta = $('hmeta').textContent;
    out.nodeBadges = Array.from(document.querySelectorAll('.node .fbn')).filter(e => e.textContent).map(e => e.closest('.node').querySelector('.t').textContent + ':' + e.textContent + (e.classList.contains('hot') ? ':hot' : ''));
    out.nowExpanded = Array.from(document.querySelectorAll('.nowb')).length;
    out.pops = {};
    for (const k of ['ask', 'new', 'chg', 'doing', 'wait', 'next']) {
      const c = document.querySelector('#cons .chip[data-k="' + k + '"]');
      c.click(); await sleep(60);
      const p = $('pop');
      out.pops[k] = {open: p.classList.contains('open'), head: p.querySelector('.ph b').textContent, hint: p.querySelector('.ph .hint').textContent,
                     items: Array.from(p.querySelectorAll('.ci, .none')).map(e => e.textContent)};
      c.click(); await sleep(30);
    }
    out.filters = {};
    for (const f of ['ask', 'doing', 'wait', 'prob', 'chg']) {
      document.querySelector('[data-f="' + f + '"]').click(); await sleep(60);
      out.filters[f] = {banner: $('fbanner').textContent, visible: Array.from(document.querySelectorAll('.node')).filter(n => !n.closest('.fhide')).length};
    }
    document.querySelector('[data-f=""]').click(); await sleep(60);
    out.allVisible = Array.from(document.querySelectorAll('.node')).filter(n => !n.closest('.fhide')).length;
    out.nodes = document.querySelectorAll('.node').length;
    // jump from a console item to its node
    document.querySelector('#cons .chip[data-k="ask"]').click(); await sleep(60);
    const first = document.querySelector('#pop .ci[data-nid]');
    if (first){ first.click(); await sleep(100); out.jumped = document.querySelector('.node.sel .t').textContent; }
    document.querySelector('#cons .chip[data-k="ask"]').click(); await sleep(30);
    // "mark all as read" in the right panel clears the new-reply number but not the open questions
    const readall = document.querySelector('#fbl .sa[data-act="readall"]');
    if (readall){ readall.click(); await sleep(100); }
    out.after = chips();
    out.countsAfter = Array.from(document.querySelectorAll('#fbl .sec > .sh .c')).map(e => e.textContent);
    await sleep(2500);       // the page looks for a newer build 1.5 s after it opens
    out.newverShown = $('newver').classList.contains('on');
    out.mm = window.__mm ? {read: Object.keys(window.__mm.state().read).length} : null;
  } catch (e) { window.__errors.push('scenario: ' + e.message); }
  out.errors = window.__errors; out.violations = window.__violations;
  const div = document.createElement('div'); div.id = '__result';
  div.setAttribute('data-b64', btoa(unescape(encodeURIComponent(JSON.stringify(out)))));
  document.body.appendChild(div);
})();
"""


TRACKING_JS = r"""
(async function(){
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const out = {errors: window.__errors, violations: window.__violations};
  try {
    out.hmeta = $('hmeta').textContent;
    out.quotes = [];
    for (const qb of Array.from(document.querySelectorAll('#fbl .qb'))) {
      $('toast').style.display = 'none';
      document.querySelectorAll('.node.sel').forEach(n => n.classList.remove('sel'));
      qb.click(); await sleep(150);
      const sel = document.querySelector('.node.sel .t');
      out.quotes.push({key: qb.dataset.key, selected: sel ? sel.textContent : null,
                       toast: $('toast').style.display === 'block' ? $('toast').textContent : ''});
    }
    out.chips = [];
    for (const nc of Array.from(document.querySelectorAll('#fbl .nc'))) {
      document.querySelectorAll('.node.sel').forEach(n => n.classList.remove('sel'));
      nc.click(); await sleep(150);
      const sel = document.querySelector('.node.sel .t');
      out.chips.push({text: nc.textContent, selected: sel ? sel.textContent : null});
    }
    const nxt = document.querySelector('#cons .chip[data-k="next"]');
    out.next = {shown: nxt.style.display !== 'none', tm: nxt.querySelector('.tm').textContent, lb: nxt.querySelector('.lb').textContent};
    nxt.click(); await sleep(80);
    out.nextItems = Array.from(document.querySelectorAll('#pop .ci')).map(e => e.querySelector('.ct').textContent);
    nxt.click(); await sleep(30);
    out.badges = Array.from(document.querySelectorAll('.node .fbn')).filter(e => e.textContent).map(e => e.closest('.node').querySelector('.t').textContent);
    out.nodes = document.querySelectorAll('.node').length;
  } catch (e) { window.__errors.push('scenario: ' + e.message); }
  out.errors = window.__errors; out.violations = window.__violations;
  const div = document.createElement('div'); div.id = '__result';
  div.setAttribute('data-b64', btoa(unescape(encodeURIComponent(JSON.stringify(out)))));
  document.body.appendChild(div);
})();
"""


def fnv_key(text):
    """The page's short hash of a node path (FNV-1a, base 36); the snapshot of what the user last saw uses it."""
    h = 0x811c9dc5
    for ch in text:
        h = ((h ^ ord(ch)) * 0x01000193) & 0xffffffff
    digits, out = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while h:
        h, r = divmod(h, 36)
        out = digits[r] + out
    return out or "0"


def find_chrome():
    """Path of a Chromium-based browser, or None. MIND_ATLAS_CHROME overrides the search."""
    env = os.environ.get("MIND_ATLAS_CHROME")
    if env:
        return env if (os.path.exists(env) or shutil.which(env)) else None
    candidates = []
    if sys.platform == "darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                      "/Applications/Chromium.app/Contents/MacOS/Chromium",
                      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    elif sys.platform.startswith("win"):
        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                candidates += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                               os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")]
    for c in candidates:
        if os.path.exists(c):
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _kill_tree(proc):
    """Kill the browser and every process it started (it is its own process group on POSIX)."""
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ValueError):
        pass


def run_chrome(chrome, url, extra_args=(), timeout=90, budget_ms=15000, window=None, done=None, profile=None):
    """Open `url` headless and return what Chrome printed to stdout (the DOM with --dump-dom).

    Chrome's new headless mode may keep running after it has printed the DOM, so instead of waiting for
    the process to exit this polls the output until it looks complete (`done(text)` is true, by default
    when it ends with </html>), then kills the browser and everything it started. `profile` is a user-data
    directory to keep (the caller owns it); by default a throwaway one is used and removed.
    """
    done = done or (lambda text: text.rstrip().endswith("</html>"))
    keep_profile = profile is not None
    profile = profile or tempfile.mkdtemp(prefix="mmtest-")
    args = [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--user-data-dir=" + profile, "--virtual-time-budget=%d" % budget_ms]
    if window:
        args.append("--window-size=%d,%d" % window)
    if sys.platform.startswith("linux") and os.environ.get("CI"):
        args.append("--no-sandbox")
    args += list(extra_args) + [url]
    kwargs = {"stdout": None, "stderr": subprocess.DEVNULL}
    if os.name != "nt":
        kwargs["start_new_session"] = True
    out_path = os.path.join(profile + "-stdout.txt")
    text, proc = "", None
    try:
        with open(out_path, "wb") as sink:
            kwargs["stdout"] = sink
            proc = subprocess.Popen(args, **kwargs)
            deadline = time.time() + timeout
            while time.time() < deadline:
                time.sleep(0.25)
                with open(out_path, "rb") as f:
                    text = f.read().decode("utf-8", errors="replace")
                if done(text) or proc.poll() is not None:
                    break
            else:
                _kill_tree(proc)
                raise subprocess.TimeoutExpired(args, timeout)
        with open(out_path, "rb") as f:
            text = f.read().decode("utf-8", errors="replace")
    finally:
        if proc is not None:
            _kill_tree(proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        if not keep_profile:
            shutil.rmtree(profile, ignore_errors=True)
        try:
            os.remove(out_path)
        except OSError:
            pass
    return text


def instrument(html, search_term="a", seed=None, scenario=None, extra_storage=None):
    """Return the page with the test scripts injected. `seed` = (page id, list of feedback items);
    `extra_storage` = {localStorage key: JSON-able value} written before the page script runs."""
    seed_js = ""
    if seed:
        page_id, items = seed
        seed_js = "localStorage.setItem(%s, %s);" % (
            json.dumps("mm:%s:items" % page_id), json.dumps(json.dumps(items)))
    for key, value in (extra_storage or {}).items():
        seed_js += "localStorage.setItem(%s, %s);" % (json.dumps(key), json.dumps(json.dumps(value)))
    pre = "<script>" + PRE_JS.replace("/*SEED*/", seed_js) + "</script>\n"
    post = "<script>" + (scenario or SCENARIO_JS).replace("/*SEARCH*/", json.dumps(search_term)) + "</script>\n"
    marker = '<script id="data"'
    if marker not in html or "</body>" not in html:
        raise ValueError("not a mind-atlas page")
    html = html.replace(marker, pre + marker, 1)
    return html.replace("</body>", post + "</body>", 1)


def run_scenario(html_path, search_term="a", seed=None, chrome=None, timeout=90, scenario=None, extra_storage=None):
    """Run a scripted scenario (the default click-through, or `scenario`) against a built page; returns the
    decoded result dict."""
    chrome = chrome or find_chrome()
    if not chrome:
        raise RuntimeError("no Chrome/Chromium found (set MIND_ATLAS_CHROME)")
    src = pathlib.Path(html_path)
    html = src.read_text(encoding="utf-8")
    tmpdir = tempfile.mkdtemp(prefix="mmtest-page-")
    try:
        page = pathlib.Path(tmpdir) / src.name
        page.write_text(instrument(html, search_term, seed, scenario, extra_storage), encoding="utf-8")
        stamp = src.with_suffix(".stamp.js")
        if stamp.exists():                       # a local page checks the .stamp.js beside it for a newer build
            shutil.copyfile(str(stamp), str(pathlib.Path(tmpdir) / stamp.name))
        dom = run_chrome(chrome, page.as_uri(), ["--dump-dom"], timeout=timeout)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    m = re.search(r'id="__result"[^>]*data-b64="([^"]+)"', dom) or re.search(r'data-b64="([^"]+)"[^>]*id="__result"', dom)
    if not m:
        raise RuntimeError("the scenario produced no result; DOM head: " + dom[:300])
    return json.loads(base64.b64decode(m.group(1)).decode("utf-8"))


def dump_dom(html_path, chrome=None, timeout=60):
    """Plain `--dump-dom` of a page as a user would open it (no instrumentation)."""
    chrome = chrome or find_chrome()
    return run_chrome(chrome, pathlib.Path(html_path).resolve().as_uri(), ["--dump-dom"], timeout=timeout, budget_ms=4000)
