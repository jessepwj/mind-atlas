---
name: mind-atlas
description: "Turn a project, system, topic or pile of material into a multi-level, interactive HTML mind map. Pick a level (L1 overview to L4 panorama), optionally fan out read-only sub-agents to research the branches, write an outline, and build a single-file page that opens with a double-click; the user reads it, writes feedback in the page, and copies it back to you. Use when the user asks to map out, outline or get the whole picture of something: 'mind map this', 'map out the whole project', 'give me the big picture', 'draw the structure of X', 'make a panorama of Y'. Chinese triggers: 梳理一下全貌, 理一下, 做成思维导图, 全景梳理, 画个脑图, 把这件事的结构理出来. Also use when the user pastes feedback that starts with [Mind map feedback] or 【导图反馈】: that is the reply step of a map made earlier. Not for a plain explanation, a summary, or a one- or two-level list."
---

# mind-atlas: turn something into a multi-level HTML mind map

The goal is to let a person (the user, or someone they share it with) see the whole of a thing at a glance, give feedback right on the map, and follow the questions down to a decision. The method comes from a real panoramic mapping run: 700+ nodes, 16 first-level branches, and 7 read-only research sub-agents working in parallel. The page design and the feedback loop were kept because they worked there.

## Setup

- `<skill_dir>` is the folder that contains this `SKILL.md` (for example `~/.claude/skills/mind-atlas` or `~/.codex/skills/mind-atlas`).
- `<workdir>` is the map's working folder. Default to `mindmaps/<topic>/` inside the current project, or use any folder the user prefers. It holds source files and generated output; tell the user so they can decide whether to commit it.
- Commands are `python3 <skill_dir>/scripts/build.py <workdir>`. On Windows the interpreter is usually `python` or `py`. Python 3.9 or newer, standard library only.
- `<workdir>/meta.json` describes the map. A minimal one:

  ```json
  {
    "title": "Payments service overview",
    "id": "payments-overview",
    "lang": "en",
    "level": "L2 Standard",
    "desc": "Built from the repository and the design docs; statuses checked against the latest changelog.",
    "parts": ["outline-trunk.md", "outline-A-ledger.md", "outline-Z-problems.md"]
  }
  ```

  `title` is required. `parts` lists the outline pieces in order (leave it out only if you write a single `outline.md` yourself). End `desc` with a full stop, because the page puts the next sentence right after it. Choose `id` once: a short ASCII name that is **unique among the user's maps** and never changes (feedback is stored in the browser under it).
- **Always set `"lang"`** to the language the user works in: `"en"` or `"zh"`. It switches the whole page (buttons, hints, the text of the feedback the user copies back). The default is `"zh"`, so an English map without `"lang": "en"` gets a Chinese interface (`build.py` warns). Write the outline in that same language.
- When the user writes in Chinese, read the `.zh-CN.md` version of each reference file; the two versions say the same thing.

## Not everything needs full detail: choose a level first

| Level | Purpose | Depth / nodes | Sub-agents |
|---|---|---|---|
| L1 Overview | Get a first impression, or explain it to someone | 2-3 levels, about 30-80 | None (at most 1 to gather material) |
| L2 Standard | Understand a project or topic, spot obvious problems | 3 levels, about 80-200 | 1-3 for the branches you do not know |
| L3 Detailed | Decide something, or rework one part | 4 levels, about 200-450 | 3-5, split by module |
| L4 Panorama | Optimize everything, set the blueprint | 4-5 levels, about 500-1000 | 6-8, one per line or module, plus cross-cutting ones |

Choose by **purpose** (what will the user do with the map next), **scope** (how many lines, files, modules) and **the user's own words**: "everything", "in full", "completely", 全部, 完全, 详细 point to L4; "roughly", "a quick look", 大概, 看个轮廓 point to L1 or L2. The trigger phrases themselves ("map this out", "the big picture", 梳理一下全貌) do not mean L4 on their own; without a stronger signal, choose by purpose and scope. For L1 or L2, or when purpose and scope are clear, decide yourself and say so in your first reply: "Doing this as L2 because ...; tell me if you want it finer or coarser." For L3 or L4 with an unclear purpose, ask one question and give a recommendation. Never run more than 10 sub-agents at once.

The full comparison, how to cut branches, what each level looks like, and how to spot-check reports: [references/levels.md](references/levels.md) (中文: [references/levels.zh-CN.md](references/levels.zh-CN.md)).

## Workflow

1. **Settle the purpose.** Who will read the map, and what should they do after reading it? Pick the level and say so in your first sentence.
2. **Read the core documents yourself to get the trunk**: purpose, principles, blueprint, history, overall architecture, who does what. The trunk and the purpose must be understood by you, the main agent. Do not outsource them.
3. **Create the work folder, cut the branches, dispatch sub-agents** (L1 normally uses none). Write `meta.json`. Dispatch with the [brief template](references/brief-template.md) ([中文](references/brief-template.zh-CN.md)), one sub-agent per branch, each told to write its report to `<workdir>/A-branch-name.md` (then `B-...`). Name the model explicitly in every dispatch: in Claude Code use the Agent tool with `model: haiku`; in Codex or any other agent use its sub-agent mechanism with the cheapest model that can follow the brief. The sub-agent type must be allowed to write that one file (in Claude Code use `general-purpose`, not a read-only type such as `Explore`); if it cannot write, have it return the report as text and save it yourself. Send all dispatches in one message so they run in parallel, then write the trunk outline `outline-trunk.md` yourself while they work. If your platform has no sub-agents, do the branches yourself one at a time and drop a level.
4. **Collect the reports and check them against the sources.** Open the source files and verify key facts, especially statuses such as fixed or not fixed, verified or not verified, in use or stopped, against the latest progress. Sub-agents often read stale documents; their claim of success is not evidence.
5. **Rewrite each report as an outline piece `outline-*.md`** in the format of [references/outline-format.md](references/outline-format.md) ([中文](references/outline-format.zh-CN.md)). Add the cross-cutting branches (timeline, where the data lives, current status) and, by level, "Problems and next steps" and "About this map". Keep the reports as raw material; do not paste them into the page.
6. **Build**: `python3 <skill_dir>/scripts/build.py <workdir>`. Check that the node count and depth match the level, and read every warning (ellipsis truncation, empty titles, duplicate sibling titles, a missing piece). The build also prints one line per first-level branch with its node count: compare it with what you meant. A wrong indent does not always fail, it hangs a node under the wrong parent, which shows up as a lopsided count. Then read the joined `outline.md`, or open the page, and look through each first-level branch.
7. **Verify the page** (next section).
8. **Hand it over.** Give the user the html file (attach it if your environment can, otherwise give the absolute path). In your reply give the three to five most important findings, not the contents of the map, and say which level you did and how far you verified. If the project keeps notes, add a short entry: the map exists, where it is, what it found, what is waiting for the user's decision.
9. **Run the feedback loop** (below).
10. **The page is static. Do not start a long-running server** (see "Why a static page").

## Verify the page

**Option A: headless Chrome, simulating a double-click open.** This is closest to how the user will open it:

```
<chrome> --headless=new --disable-gpu --no-first-run --user-data-dir=<temp profile dir> --virtual-time-budget=4000 --dump-dom "file://<absolute path of the html>" > dom.html
grep -o 'class="node' dom.html | wc -l
grep -o 'id="conn"[^>]*>[^<]*' dom.html
```

- The node count must equal the count `build.py` printed. The text after `id="conn"` must be "Saved in this browser" (zh: 存在这个浏览器里). "Can't save in this window" means the browser cannot keep local data; use another browser to open the file.
- The commands above are for macOS and Linux (on Windows use PowerShell equivalents). If no Chrome, Chromium or Edge is installed, skip this check and say in your reply that you built the page but could not open it.
- New headless Chrome may keep running after it prints the DOM. Limit it with a timeout (`timeout 60` on Linux; macOS has none, use `perl -e 'alarm 60; exec @ARGV' ...`, where exit code 142 means the alarm ended it, which is normal once the DOM is printed). Delete the temp profile afterwards and confirm no browser process of yours is left (`pgrep -fl <profile dir name>`). Only touch processes you started.

**Option B: a temporary local server**, only to look at it: `python3 -m http.server <free port> --bind 127.0.0.1 --directory <workdir>` (the folder may hold raw sub-agent reports, so keep it off the network). Stop it as soon as you have looked. Never leave a port occupied.

## What the page looks like

The layout and interaction live in `scripts/template.html`; think before changing them and retest after.

- **Horizontal tree**: root on the left, growing right. Each first-level branch has its own color (18 colors in rotation). Status tags are colored badges; ⓘ means the node has notes or sources; `+N` is the number of collapsed nodes below. Clicking a node selects it (and expands it if collapsed); clicking the selected node again collapses it.
- **Viewing**: drag to pan, two-finger swipe on a trackpad, pinch or hold Ctrl/⌘ and scroll to zoom. "Fit to window" and "Back to root" buttons.
- **Controls**: expand to level 1, 2, 3, 4 or all; show notes; outline view (a collapsible list); search (Enter jumps to the next hit, Shift+Enter to the previous).
- **Right panel**: details of the selected node (breadcrumb, notes, sources, next level, click to jump) above the feedback area (records and an input box). The panel folds away and can be resized.
- One file, all data embedded, no network, no dependency on any service.

## Feedback loop

The user says what they think wherever they are looking; they do not need to work out how to refer to things first.

1. The user writes feedback in the right panel. To address one node, hover over it and click the orange 💬 at its top-right corner to quote the whole node, or select text in the details or the outline view and click "Quote this" to quote one sentence. Quoting is optional.
2. The user clicks "Copy for AI". That turns the feedback not yet copied into one block of text and puts it on the clipboard; the user pastes it into the chat. If automatic copy fails, the page shows a box with the text selected.
3. You receive a block that starts with **`[Mind map feedback]`** (`【导图反馈】` on a Chinese page). It holds the page file path, an id per item (such as `F1016-162301-ab`), the quoted node path and sentence, and the user's words. Handle each item (an item marked `(revises F...)` replaces the earlier item with that id: answer the new one and say what changed), then record the reply:

```
python3 <skill_dir>/scripts/reply.py <workdir> <id> "your reply" --orig "the user's original words"
```

   This appends to `replies.json` and rebuilds the page. Always pass `--orig`: if the user switched browsers, the page cannot find their own item, and `--orig` lets it show their words with your reply. One item can be answered more than once. If the page was built with `--no-paths`, add `--no-paths` to this command too, or the rebuild puts the paths back.
4. If the feedback asks for a change (add a node, fix a status, correct a fact), edit the `outline-*.md` first, run `build.py`, and say in the reply what changed. Renaming a node makes old quotes say the node is no longer in the map, so rename only when you must.
5. Tell the user in the chat what you did. When they refresh the page, your reply shows under their item.
6. If a decision came out of it (what to do first, a suggestion rejected), note it where the project keeps decisions, and change the matching `[proposal]` on the map to `[decided]` or `[todo]`.

Feedback is stored in the user's browser (localStorage), keyed by the `id` in `meta.json` (the `title` if there is no `id`). A different browser does not show what they wrote, but replies carry the original words. Therefore: **choose an `id` once, a short stable ASCII name that no other map of the user's uses, and never change it** (Chrome gives all local files one shared storage, so two maps with the same `id` would mix their feedback).

## Why a static page, not a local server

An early version ran a local server that saved feedback to disk and could call the agent. It was dropped for three reasons: people forget to stop servers and they sit in the background; a chat session can end within the hour, and the server and the page die with it; and the page has to work by double-clicking the file, with no backend.

So feedback stays in the browser, goes out through "Copy for AI", and replies come back by regenerating the page. **Do not add a resident service for convenience.** A temporary server for looking at the page is fine; stop it when you are done.

## File map

| Path | Purpose |
|---|---|
| `scripts/build.py` | Builds the single-file html from a work folder; checks structure and prints warnings |
| `scripts/template.html` | The page: all styles and interaction |
| `scripts/i18n.json` | Every UI string, per language (`zh`, `en`); add a language here |
| `scripts/reply.py` | Appends a reply to `replies.json` and rebuilds |
| `references/levels.md` | The four levels, how to choose, sub-agent counts, how to spot-check |
| `references/brief-template.md` | Template for dispatching a branch-research sub-agent |
| `references/outline-format.md` | Outline syntax, `meta.json` fields, status tags, how to write nodes |

Each reference also has a `.zh-CN.md` twin. Two complete example folders live in the repository's `examples/` directory (not inside the skill folder): `tool-library-en` and `book-corner-zh`. Build one with `python3 <skill_dir>/scripts/build.py <that folder>` to see the output; do not commit the generated `.html` and `outline.md`.

## Rules to keep

- Do not end a sentence with an ellipsis; write short, complete sentences. Do not report only a count; say what the things are.
- Sub-agents are read-only. Every dispatch names its model. No more than 10 at once. Use cheap models for research; merging, status checking and acceptance are your own work (if you want a reviewer, use a mid-range model, not the cheapest).
- Anything that is your own judgment, ranking or trade-off is marked `[proposal]` (`【建议】` in a Chinese outline). It is not a fact until the user agrees.
- Secrets, passwords and private message contents never go on the map: write which file holds them and with what permissions. If a sub-agent printed or carried out a secret, delete its temporary files at once and tell the user in your reply.
- When `meta.json` lists `parts`, `outline.md` in the work folder is produced by `build.py` from the pieces: never edit it by hand and never list it in `parts`; edit the `outline-*.md` pieces and rebuild. (Without `parts`, `outline.md` is simply the outline you write.)
- **Check your own work before handing it over**: sensible node count, no warnings, the page opens, key statuses verified against the sources. Say what you checked.
- The built page embeds the absolute path of the page file and the reply command, so the AI can answer. Before sharing a page with other people, build it with `--no-paths` to leave those out.

## Common pitfalls

- Sub-agents read outdated documents and report things as unfixed that are fixed, unverified that are verified, or in conflict that are fine. Correcting statuses is the main agent's job.
- A second `# Root` line in a later piece is an error: only the first piece has one. Headings from a sub-agent report (`## Branch`) are not nodes and only earn a warning; turn them into hyphen-list nodes.
- Indentation must be a multiple of 2 spaces, no tabs, and a child sits exactly one level (2 spaces) under its parent. `build.py` reports violations with file and line.
- A status word in brackets is a tag wherever it sits in a line, even inside a note. To write about tags in prose, escape it (`\[todo]`) or avoid the bracket form; in a Chinese outline rewrite with other quotes (“建议”), because 【】 cannot be escaped.
- Changing `title` without an `id` orphans earlier feedback.
- The reply command and page path in the page are the absolute paths from build time. If the work folder or the skill folder moved, build again.
- The "Generated" time in the header changes on every build. Feedback is unaffected because it lives in the browser.
