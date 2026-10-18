# The feedback loop

**English** · [简体中文](feedback-loop.zh-CN.md)

A map is only half the work. The other half is what you think when you read it. mind-atlas lets you say that
on the map itself and hand it to the agent without any server in between. There are two ways to hand it over:
paste a block of text ("Copy for AI", works everywhere), or tell the agent to pull the feedback out of your
browser itself ("pull my feedback", one command, nothing to paste).

```text
page (your browser)                              agent (your chat)
───────────────────                              ─────────────────
write feedback, quote nodes
  │ saved in localStorage
  ▼
"Copy for AI"  ── one block of text ──────────▶  reads the block, handles each item
   or you say "pull my feedback"  ───────────────▶  (pull_feedback.py reads it from the browser)
                                                   │
                                                   ├─ edits outline-*.md if a change was asked for
                                                   └─ reply.py <workdir> <id> "details" --summary "..." --status done --orig "..."
                                                        │ appends to replies.json, runs build.py
refresh the page  ◀── rebuilt page with replies ───────┘
```

## What you do

1. **Write** in the right panel. Quote a node (hover over it and click the orange 💬, or use *Quote this node* in the details) or one
   sentence (select it in the details or the outline view, then click *Quote this*), or do not quote at all.
2. **Add** the item (the *Add* button, or ⌘/Ctrl + Enter). It now shows in the feedback list with the note
   "Not copied for AI yet; saved only in this browser".
3. **Hand it over**, one of two ways:
   - **Copy for AI** puts every item that has no reply yet and was not copied before on the clipboard as one block of text; paste it
     into the chat with your agent. The items are marked "Copied for AI". *Copy everything again* sends all of them once more.
   - **Say "pull my feedback"** in the chat. The agent runs `pull_feedback.py`, which reads your items out of the browser's
     local storage (see below). Nothing to copy. Use "Copy for AI" instead if you switched browsers or the agent cannot find the data.
4. When the agent has answered, **refresh the page**. Each reply appears under the item it answers.

You can **Edit** an item (it returns to the input box; if you had already copied it, the new version is
marked as a revision of the earlier one) or **Delete** it (only from your browser).

## The block the agent receives

```text
[Mind map feedback] Neighborhood Tool Library (example), 2 items
Page file: /home/you/mindmaps/tool-library/tool-library.html
Write replies back to the page: python3 "/home/you/.claude/skills/mind-atlas/scripts/reply.py" "/home/you/mindmaps/tool-library" <id> "details" --summary "one-line conclusion" --status done --orig "the user's words"

1. [F1016-123456-ab] 10-16 12:34
   Quote: Problems and next steps › 1. Protect the tools › Damp wall may rust the steel tools (whole node)
   Says: How damp is it really? A humidity logger for a month would tell us before we spend money.

2. [F1016-123458-cd] 10-16 12:35
   Quote: Purpose and rules › Goal: let neighbors borrow tools instead of buying them
         “Success means a well-stocked shed, not a long member list.”
   Says: Do we have any numbers on how many people borrow in a month?
```

- The first line starts with `[Mind map feedback]` on an English page and `【导图反馈】` on a Chinese page.
- The id in square brackets (`F` + month and day + time + two random characters) is what the agent passes
  to `reply.py`.
- A quote shows the node's title path (the root is left out) and, when you quoted one sentence, the sentence
  itself. An item with no quote and a node selected at the time says which node was selected.
- A page built with `--no-paths` has neither the `Page file` nor the `Write replies back` line, so there is
  nothing for the agent to run; use that only for pages you share. If you answer feedback on such a page, pass
  `--no-paths` to `reply.py` too, because the rebuild would otherwise put the paths back in.

## What the agent does

For each item:

1. Understand it, and check the source if it is a question about a fact.
2. If you asked for a change, edit the right `outline-*.md` (add a node, fix a status, correct a fact) and
   run `build.py`. Renaming a node breaks old quotes of it, so the agent renames only when it must.
3. Record the reply:

   ```bash
   python3 <skill_dir>/scripts/reply.py <workdir> F1016-123456-ab "Added a node under this risk: borrow a logger and read it for four weeks." \
       --summary "Added a node: measure the damp for four weeks first." --status done \
       --node "Problems and next steps › 1. Protect the tools › Damp wall may rust the steel tools" \
       --orig "How damp is it really? A humidity logger for a month would tell us before we spend money."
   ```

   This appends to `replies.json` and rebuilds the page. `--orig` carries your original words, so if you
   open the page in a different browser (where your own feedback is not stored) the page can still show your
   question next to the reply. An id can be answered more than once; replies are listed in time order.
   On the page a reply is one bold conclusion line, a coloured status label, details that fold open, and chips for the
   related nodes (see "Structured replies").
4. Tell you in the chat what it did.
5. If the exchange settled a decision, record it where the project keeps decisions, and change the matching
   `[proposal]` on the map to `[decided]` or `[todo]`.

## Pulling feedback without copy and paste

`pull_feedback.py` is for the moment you tell the agent "pull my feedback". It is **manual only**: no timer, no
scheduled task, no background service. It does one thing and exits:

```bash
python3 <skill_dir>/scripts/pull_feedback.py <workdir>
```

- It reads your items from the browser's local storage. Chromium-based browsers (Chrome, Chromium, Edge, Brave, Ego Lite)
  keep it as a LevelDB database under the profile folder. The script first **copies** that folder to a temporary
  directory (so a running browser and its file locks do not matter), reads the copy with a small pure-Python reader (including Snappy
  decompression), and deletes the copy. The live database is never written to. Standard library only.
- It prints the items it has not seen before, in the same format as the "Copy for AI" block, and appends them to
  `<workdir>/_fb/inbox.jsonl`. Items that were pulled earlier but are not answered yet are listed again, so an interrupted
  session loses nothing. `build.py` embeds `_fb/` in the page, so another browser still shows your words, quotes and replies.
- Browsers write local storage to disk with a delay, usually 2 to 5 seconds and up to about a minute after many reloads.
  The script prints when the newest item was written; if you have just typed something that is not in the list, wait a
  little and ask again.
- It looks in the default profiles of Chrome, Chromium, Edge, Brave and Ego Lite. Use `--leveldb <dir>` to name a
  directory, `--browser <name>` to look at one browser, and `--origin https://example.org` for a page that is served over
  http(s) instead of opened from disk. If nothing is found, use "Copy for AI".

## Structured replies

A reply carries more than a paragraph, so you can see where things stand without reading it:

| Part | `reply.py` option | On the page |
|---|---|---|
| The details | the text argument | Folded under "Details" |
| One-line conclusion | `--summary` | Shown in bold; the first sentence of the details if missing |
| Status | `--status done`, `doing`, `planned`, `dropped` or `needs-you` | A coloured label: Done, In progress, Planned, Dropped, Needs you |
| Related nodes | `--node "path"` (repeatable) | Chips; click one to jump to the node |
| A question for you | `--ask "..."` | Shown under the label when the status is `needs-you` |

Chinese spellings of the statuses (已做, 在做, 定了待做, 不做, 要你定) are accepted too. A reply with the status
`needs-you` must point (`--node`) at an item tagged `[needs-you]` in the map; the build warns when it does not. When one id has several
replies, the last one's status counts: answering a question with a later reply of another status closes it.
Every part is optional, and replies written by version 1.0 still show.

## The console for project-tracking maps

For a map that stays open for days, the top of the page has five numbers: **Needs you**, **New replies**,
**Recently changed**, **In progress** and **Waiting**. Click one to list its items, click an item to jump to the node. The right
panel is ordered the same way: questions for you first, then new replies, then items waiting for the agent, then the handled
ones folded by date. A reply counts as read once it has stayed in view for two seconds. The setup (a "Now" branch,
`root_key`, the `[needs-you]` tag) is in the [outline format](../skills/mind-atlas/references/outline-format.md#project-tracking-maps-the-now-branch).
Since version 1.2 the build also checks that the "Now" branch has not gone stale and prints what to fix, so the agent keeps the numbers true.

## Where things are stored

| What | Where | Notes |
|---|---|---|
| Your feedback items | The browser's `localStorage`, key `mm:<id>:items` | `<id>` is `id` from `meta.json` (or `title`). Never uploaded |
| Your unsent draft, panel width, folded state | `localStorage`, keys `mm:<id>:draft`, `:w`, `:fold` | |
| Which replies you have read, which questions you marked handled | `localStorage`, keys `mm:<id>:read`, `:answered`, `:ansnode`, `:del` | Per browser |
| What you last looked at (for "Recently changed") | `localStorage`, keys `mm:<id>:snap`, `:snapTs` | A short hash of every node's path with its content fingerprint |
| Your place in the map (expansion, filter, selection, zoom) | `sessionStorage`, key `mmv:<id>` | Survives a refresh of the same tab only |
| The agent's replies | `<workdir>/replies.json` | A JSON list of `{"id", "ts", "text", "orig"}` plus the optional `summary`, `status`, `nodes`, `ask`; embedded in the page at build time |
| Feedback already pulled back | `<workdir>/_fb/inbox.jsonl` (written by `pull_feedback.py`) and the optional `_fb/known.json` | Embedded in the page, so another browser shows it |
| The build time | `<page name>.stamp.js` beside the page (not written with `--no-paths`) | A page left open reads it when you return to the tab and offers a refresh |

Because feedback is stored per browser and per `id`:

- Opening the same file in another browser shows replies (with your original words if `--orig` was given)
  but not your own items.
- Changing the `id` (or the `title` when there is no `id`) makes the page forget everything you wrote. Pick
  the `id` once.
- Browsers share local storage between all the files you open from disk, so two maps with the same `id` would
  show each other's feedback. Give every map its own `id`.
- Clearing site data for local files removes your items. Copy to the agent before you clean up.

## Why this design

There is no server to forget about, nothing to authenticate, and the page works from a USB stick. The
cost is one manual step (paste the block into the chat, or say "pull my feedback"). For a map that a person reads in a sitting and
answers in batches, that is a good trade. See the "Why a static page" section of the
[README](../README.md#why-a-static-page-and-not-a-server).
