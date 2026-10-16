# The feedback loop

**English** · [简体中文](feedback-loop.zh-CN.md)

A map is only half the work. The other half is what you think when you read it. mind-atlas lets you say that
on the map itself and hand it to the agent without any server in between.

```text
page (your browser)                              agent (your chat)
───────────────────                              ─────────────────
write feedback, quote nodes
  │ saved in localStorage
  ▼
"Copy for AI"  ── one block of text ──────────▶  reads the block, handles each item
                                                   │
                                                   ├─ edits outline-*.md if a change was asked for
                                                   └─ reply.py <workdir> <id> "reply" --orig "..."
                                                        │ appends to replies.json, runs build.py
refresh the page  ◀── rebuilt page with replies ───────┘
```

## What you do

1. **Write** in the right panel. Quote a node (hover over it and click the orange 💬, or use *Quote this node* in the details) or one
   sentence (select it in the details or the outline view, then click *Quote this*), or do not quote at all.
2. **Add** the item (the *Add* button, or ⌘/Ctrl + Enter). It now shows in the feedback list with the note
   "Not copied for AI yet; saved only in this browser".
3. **Copy for AI** puts every item you have not copied yet on the clipboard as one block of text. The items
   are marked "Copied for AI". *Copy everything again* sends all of them once more.
4. **Paste** the block into the chat with your agent.
5. When the agent has answered, **refresh the page**. Each reply appears under the item it answers.

You can **Edit** an item (it returns to the input box; if you had already copied it, the new version is
marked as a revision of the earlier one) or **Delete** it (only from your browser).

## The block the agent receives

```text
[Mind map feedback] Neighborhood Tool Library (example), 2 items
Page file: /home/you/mindmaps/tool-library/tool-library.html
Write replies back to the page: python3 "/home/you/.claude/skills/mind-atlas/scripts/reply.py" "/home/you/mindmaps/tool-library" <id> "reply"

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
   python3 <skill_dir>/scripts/reply.py <workdir> F1016-123456-ab "Added a node under this risk ..." --orig "How damp is it really? ..."
   ```

   This appends to `replies.json` and rebuilds the page. `--orig` carries your original words, so if you
   open the page in a different browser (where your own feedback is not stored) the page can still show your
   question next to the reply. An id can be answered more than once; replies are listed in time order.
4. Tell you in the chat what it did.
5. If the exchange settled a decision, record it where the project keeps decisions, and change the matching
   `[proposal]` on the map to `[decided]` or `[todo]`.

## Where things are stored

| What | Where | Notes |
|---|---|---|
| Your feedback items | The browser's `localStorage`, key `mm:<id>:items` | `<id>` is `id` from `meta.json` (or `title`). Never uploaded |
| Your unsent draft, panel width, folded state | `localStorage`, keys `mm:<id>:draft`, `:w`, `:fold` | |
| The agent's replies | `<workdir>/replies.json` | A JSON list of `{"id", "ts", "text", "orig"}`; embedded in the page at build time |

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
cost is one manual step (paste the block into the chat). For a map that a person reads in a sitting and
answers in batches, that is a good trade. See the "Why a static page" section of the
[README](../README.md#why-a-static-page-and-not-a-server).
