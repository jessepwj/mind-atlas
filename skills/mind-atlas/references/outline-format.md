# Outline format

`scripts/build.py` reads an indented Markdown nested list and builds the page. The syntax below is everything it understands; do not invent more. You can copy from the complete examples in the repository's `examples/` folder.

## What is in a work folder

| File | Written by | Purpose |
|---|---|---|
| `meta.json` | you | Page title, language, level, description, which pieces to join |
| `outline-*.md` | you | Outline pieces, joined in the order of `parts` |
| `outline.md` | `build.py` | The joined outline, only for inspection; never edit it (it is overwritten) |
| `A-xxx.md` etc. | sub-agents | Research reports. Raw material; never joined into the page |
| `replies.json` | `reply.py` | Replies to the user's feedback; optional |
| `_fb/` | `pull_feedback.py` | Feedback already pulled back from the browser (`inbox.jsonl`); embedded in the page; optional |
| `<title>.html` or `out` | `build.py` | The result: one file that opens with a double-click |
| `<title>.stamp.js` | `build.py` | Just the build time, so a page left open can offer a refresh (not written with `--no-paths`) |

Put the folder at `mindmaps/<topic>/` in the project, or wherever the user prefers.

## The outline

```
# Root title | Root note
- First-level branch [active] | Note text [src: where it came from]
  - Second-level node
    - Third-level node [issue] | Note text
      A line indented deeper that does not start with "- " continues the note above.
```

- **Two spaces per level**, spaces only, no tabs. A child is indented exactly 2 spaces more than its parent; skipping a level is an error.
- The whole outline has **exactly one `# Root`** line, first in the file. A second `# Title` line (for example at the top of a later piece) is an error. Other lines that begin with `#`, such as `## Heading` copied from a report, are not nodes: they are merged into the note above with a warning, so turn them into hyphen-list nodes.
- Children of the root (first-level branches) have no indent: `- Title`.
- Separate the title from the note with ` | ` (a pipe with one space on each side). Everything before the first separator is the title; everything after is the note. A pipe without spaces on both sides, such as `a|b`, is not a separator. If a title must contain ` | `, rewrite it without the spaces or use another character.
- Put sources in `[src: ...]`, anywhere in the line, usually at the end. A node can have several; the page joins them.
- Put status tags in square brackets (`[active]`, see the table below), usually right after the title and before ` | `. A node can have several.
- Blank lines and `<!-- comments -->` are ignored, and a comment may span several lines.
- Pieces are joined as plain text, and **only indentation counts**. So you can write a branch head in the trunk piece and put its children in another piece, indented 2 more spaces, directly after it (this is how `outline-A-inventory.md` in the English example attaches under the last node of the trunk).
- Lines starting with `*` or `+` are not nodes (only `-` starts one). They are treated as note text and `build.py` warns about them.
- A note line (a continuation line) belongs entirely to the note of the node above it. It may contain tags and sources, but not a title separator.

### Chinese spellings work too

The syntax is the same in every language; both spellings are always understood, whatever `lang` is, and can be mixed in one file.

| Element | ASCII spelling | Chinese spelling |
|---|---|---|
| Title / note separator | ` \| ` (pipe, one space each side) | ` ｜ ` (full-width bar, one space each side) |
| Source | `[src: ...]` or `[source: ...]` | `〔...〕` |
| Status tag | `[active]` | `【在用】` |

A tag word is a tag wherever it appears in the line, even inside a note, so a sentence about tags loses the word. To keep a bracketed word literally, put a backslash in front: `\[todo]` shows as the text `[todo]` and is not a tag. The Chinese `【】` tags cannot be escaped; to write about them, put other quotation marks around the word. Only the exact tag words and `[src:` or `[source:` are special; other brackets such as `a[0]` or `[maybe]` are ordinary text.

## `meta.json`

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | Page title, and the html file name unless `out` is set |
| `lang` | strongly recommended | `"en"` or `"zh"`; the language of the page interface. **Default `"zh"`.** Set it explicitly |
| `id` | recommended | A stable identity for the page. The user's feedback is stored in the browser under it. If missing, `title` is used, and changing `title` later orphans earlier feedback. Pick a short ASCII name that no other map of yours uses (the browser shares local storage between local files, so equal ids mix their feedback), and never change it |
| `use` | recommended | What the map is for: `learning`, `project tracking` or `decision` (the Chinese spellings, listed in the zh-CN version of this file, work too). Shown in the page header in the page's language; another value is shown as written, with a warning. See "Decide the use first" in `SKILL.md` |
| `level` | recommended | The mapping level, such as `L4 Panorama`, shown in the page header |
| `desc` | recommended | One line for the header: how it was made, how far it was verified |
| `root_key` | recommended for project-tracking maps | The root's fixed name inside node paths. The root title may change (for example it carries `{{updated}}`); old quotes and the "what you last saw" snapshot keep working because paths use this name. Default: the root title as written |
| `now` | project-tracking maps | Title of the first-level branch that holds what is going on right now; must match the outline exactly (the build warns otherwise). It takes no color slot, starts expanded and shows its notes, and its `[in progress]`, `[waiting]` and `[needs-you]` nodes feed the numbers at the top of the page. With `now` set, the build also checks that the branch has not gone stale (see below) |
| `done_max` | no | Most items "Recently done" may hold; default 10. More than that and the build reports it |
| `now_sections` | no | Tells the build which section is which when the titles of the "now" sections do not use the usual words: `{"ask": ..., "doing": ..., "waiting": ..., "issues": ..., "next": ..., "later": ..., "done": ...}`, each value the exact title. Only the build's checks use it: the page's nearest-time number still looks for a group whose title starts with Next, Upcoming or Coming up |
| `search_hint` | no | Placeholder of the search box; give a few words that are really in this map |
| `parts` | no | Ordered list of the outline pieces to join. If absent, `outline.md` in the folder is read |
| `out` | no | Output file name (a plain name, not a path). Default `<title>.html` |

Unknown fields are ignored with a warning, so a typo does not go unnoticed.

## Status tags (eleven, no others)

| Tag | Chinese | Use it for |
|---|---|---|
| `[needs-you]` | 【要你定】 | Something the user must answer or do before things can move. Only in the "now" branch of a project-tracking map; leave it out when there is nothing. After the user has answered and the AI has replied, change it to `[decided]` or `[todo]` and move it out of "now" |
| `[active]` | 【在用】 | Something running now: a feature, a scheduled job, a rule |
| `[stopped]` | 【已停】 | Used before; stopped, retired or replaced |
| `[in progress]` | 【进行中】 | Being worked on and not finished |
| `[todo]` | 【待做】 | Decided to do, or clearly should be done, not started |
| `[issue]` | 【问题】 | A confirmed fault, gap or contradiction |
| `[done]` | 【已完成】 | Finished; common in history and in the steps of a blueprint |
| `[decided]` | 【已定】 | A decision, principle or boundary that the user or owner settled; no more discussion |
| `[waiting]` | 【等别人】 | Blocked on someone else: the user, another session, a third party |
| `[risk]` | 【风险】 | Nothing has gone wrong yet, but it could |
| `[proposal]` | 【建议】 | The mapper's own judgment, not decided; needs the user's review before action |

Tag words are not case sensitive (`[Active]` works, and so does `[NEEDS-YOU]`; `[needs you]` is accepted too).

**Keep to the rule for `[proposal]`:** anything the mapper puts forward on their own (a way of doing it, a ranking, a trade-off) is marked `[proposal]`, so the reader can tell fact from judgment at a glance. Change it to `[decided]` or `[todo]` only after the user agrees.

How much to use at each level: L1 hardly at all; L2 on problems and key facts; L3 and L4 widely (in the reference 700-node map about a fifth of the nodes carried a tag). **Not every node needs a tag; when there is no status to state, leave it out.**

## Project-tracking maps: the "now" branch

Most maps are read once. A map that stays open for days, that the user answers again and again and the AI keeps updating (a project's control map, say), works better with a "now" branch and the console on top of the page. Its danger is falling behind: a "Now" that is out of date is worse than no map. The source of truth is the project's own notes; the map is a view of them, and where the two disagree the notes win.

1. **Put a first-level branch "Now" first.** Write `"now": "Now"` in `meta.json`; the title must match exactly. It always has the same seven sections, in this order:

   | Section | What it holds | How to write it |
   |---|---|---|
   | Needs you | What the user must answer or do before things can move | Tag `[needs-you]`. If there is nothing, write one node "Nothing needs you right now"; do not leave it empty or pad it |
   | In progress | Who is doing what, and when there will be a result | Tag `[in progress]`; the console counts them. If nothing is running, say in the note when you last looked and what comes next |
   | Waiting on others | Blocked on someone other than the user: another session, a third party | Tag `[waiting]`; write whom, for what, and the expected day |
   | Problems and risks | Known faults and hazards that are not settled | Tag `[issue]` or `[risk]`; write who owns it. When settled, move it to "Recently done" |
   | Next up | Things with a date | Sort by time. **Start every title with the date**: `10-19 05:00 Switch the proxy back`, `10-20 Pay the invoice` or `2026-11-05 18:00 Meeting`. Do not make "today" or "tomorrow" groups. If nothing is dated, leave the section without items |
   | Later | Decided to do, no date yet | Tag `[todo]`; say why there is no date |
   | Recently done | What finished in the last two days, newest first | Group by day (`10-18`, `10-17 evening`), about ten items in all. Older groups move whole into the History branch under that day |

2. **The numbers at the top count what is tagged inside "Now"**:

   | Number | Counts |
   |---|---|
   | Needs you | Nodes tagged `[needs-you]` anywhere in the map, plus the AI's open questions (a reply with the status `needs-you`) |
   | New replies | Replies the user has not seen yet; a reply counts as seen after two seconds in the right panel |
   | Recently changed | Nodes whose title, status or note changed, or that are new, since the user last looked at this map |
   | In progress | The lowest `[in progress]` nodes in "Now" |
   | Waiting | The lowest `[waiting]` nodes in "Now" |

   Beside them the page shows the nearest upcoming time point. A node in a group of "Now" titled "Next up", "Upcoming" or "Coming up" (a Chinese outline uses the Chinese word for "next"; the zh-CN version of this file spells it out) counts as a time point when its title starts with `HH:MM`, optionally preceded by `MM-DD` (otherwise the date is read from a parent title such as `11-05`). That group and a group titled "Recently done" start collapsed.
3. **Use `[needs-you]` sparingly**: only for what truly needs the user. When a reply to the user's feedback sets the status `needs-you`, point it (`--node`) at the matching `[needs-you]` item, and keep the two in step. After the user has answered, change it to `[decided]` or `[todo]` and move it out of "Needs you".
4. **Fix two names in `meta.json`**: `id` (where feedback lives in the browser) and `root_key`. The root title may then carry the update time: write `{{updated}}` in it, and the build turns it into "updated MM-DD HH:MM" (a Chinese page says it the Chinese way). Paths use `root_key`, so the changing title breaks nothing.
5. **Edit only what must change.** The build gives every node a fingerprint of its title, tags and note; the page marks nodes whose fingerprint differs from what the user last saw as New or Edited. Rewriting text for no reason makes the whole map light up.
6. **Update "Now" in the same step as the project notes.** Whenever something is decided, finished or scheduled, update the "Now" piece and the detail branches that say the same thing, and rebuild. A heartbeat or scheduled check that finishes something does the same.
7. **Move nodes without renaming them.** When an item moves from "Recently done" into the History branch, or from "Next up" to "Recently done", keep its title exactly. Quotes and replies store a node's path. When the path no longer matches, the page and the build look the node up by the last part of the path, its title, and accept it only if exactly one node has that title. A node whose title changed cannot be found; change its note instead.

### What the build checks in "Now"

For a map with `"now"` the build reports what has gone stale. Everything is printed (to stderr, like the other warnings) and nothing stops the build:

- A time point under "Next up" that passed more than 30 minutes ago. Done ones move to "Recently done"; the others get a new date or a note saying what they wait for. A title with a date but no time falls due at the end of that day.
- A time point whose title does not start with a date (`MM-DD HH:MM`, `MM-DD` or `YYYY-MM-DD`, the time optional; a full-width colon in the time is fine). A date without a year means the nearest such date to today, so write the year for anything more than a few months away. A time such as `18:00` is accepted when a parent group has the date (`11-05`). Details under a dated point are not time points. Undated items belong under "Later".
- A title in "Now" with "today", "tomorrow", "yesterday", "tonight", "this morning" and the like (and their Chinese counterparts). It is wrong a day later; write the date. Only titles are read; a note may say "today".
- "Recently done" with more than `done_max` items (10 by default; items inside day groups are counted, not the groups), or with a day group from two days ago or earlier.
- An item under "Recently done" that carries an unfinished tag: `[needs-you]`, `[in progress]`, `[todo]`, `[issue]`, `[risk]`, `[waiting]` or `[proposal]`. It belongs in the section for problems, in progress or waiting.
- An empty "Needs you" section.
- As a reminder, the nodes outside "Now" that are still tagged `[in progress]` or `[waiting]`. A branch whose title contains "snapshot" (or the Chinese word for it) is skipped, because it keeps an old state on purpose. Detail branches are the easiest place to forget an update; on a big update go through the list and tag the finished ones `[done]`.

The checks use the clock of the machine that builds. The sections are recognized by the words in their titles, in English and in Chinese: needs you or to decide; a title starting with next, upcoming or coming up (as the page does); later or backlog; done, finished or completed; problems, issues or risks; in progress, under way or doing; waiting, blocked or on others. If your titles use other words, set `now_sections`.

## Writing a node

1. **Make the title a short complete sentence or noun phrase** that reads in one line on the map. Put details after ` | ` in the note, not a whole paragraph in the title.
2. **No ellipsis truncation** (neither the single character nor three dots). If it does not fit, write a shorter complete sentence or split it into child nodes. `build.py` warns when it finds one.
3. **Do not only report a count; say what they are.** Bad: "12 scripts". Good: "12 scripts: collection, transcription, publishing; 5 of them for collection".
4. **One node, one meaning.** If the note enumerates "first, second", make child nodes.
5. **Sibling titles must be different.** A feedback quote finds its node by the path "parent title › child title". Duplicates cannot be told apart, and a renamed node loses old quotes (the page says the node is no longer in the map). `build.py` warns about duplicates.
6. **Write concrete dates**: `10-16`, not "yesterday" or "recently". People open the map much later.
7. **Usually no more than 9 children under one parent**; above that, add a grouping level.
8. **Sources go after the node**: file paths, page names, session names, dates. Key facts must have one; the rest may not.
9. **No private content, passwords or keys on the map.** Write which file holds them and with what permissions.
10. **Facts in the note, judgment in a separate node marked `[proposal]`.** Do not mix them in one sentence.

## Fixed branches

- **Purpose and blueprint** (L2 and up): what is wanted in the end, in how many steps, the state of each step, what is explicitly out, and the boundaries that always hold. Quote the user's own words and the date where you can, and mark `[decided]`.
- **Now** (project-tracking maps): the seven sections above, first among the first-level branches.
- **History**: by date, one node per day, with what got done under it, marked `[done]`. When one day has more than nine items, add a level for the part of the day (early, morning, afternoon, evening). Groups that move over from "Now › Recently done" keep their titles.
- **What this means for us** (learning maps): what to borrow, whether to adopt it, how it would fit what we do, and the next step. Every judgment is marked `[proposal]`. Put it before "About this map".
- **Timeline**: gathers scattered schedules and dates into one chronological list. It is a cross-cutting branch, written by the main agent.
- **Where the data lives**: the folder structure and one sentence for each kind of data. Locations only; never copy contents.
- **Problems and improvements**: first group by priority (one, two, three), the problems under each group, and `[proposal]` nodes under the problems. Group titles state the purpose: "protect the data first", "consolidate the documents", "tidy the code".
- **About this map** (L4): how it was made, what was corrected, how to give feedback, how to update it.

## Turning a sub-agent report into an outline piece

A report is a Markdown nested list whose indentation is already close to an outline, but it needs these changes:

1. Sources in brackets become `[src: source]` at the end of the node.
2. Keep only the eleven status tags in the table; rewrite anything else.
3. Split over-long titles into "title | note".
4. Correct statuses against the latest progress and the source files (fixed or not, verified or not); fix whatever is out of date.
5. Merge duplicates. For contradictions, take one according to the source and write down why.
6. Adjust the whole piece's indentation to where it sits in the map (2 more spaces when it attaches under a branch head in the trunk).
7. Save it as `outline-<id>.md` and put it in order in the `parts` list of `meta.json`.

## Building and checking

```
python3 <skill_dir>/scripts/build.py <workdir>
```

It prints the node count, deepest level, file size and number of replies, a line with the number of feedback items already pulled back and of `[needs-you]`, `[in progress]` and `[waiting]` nodes, then one line per first-level branch with its node count (a branch whose count looks far too small or too large often has nodes hung under the wrong parent), and it checks:

- Structure mistakes stop the build with the file and line: tab indentation, an indent that is not a multiple of 2, an indent that skips a level, a second `# Root` line, text or a node before the root, an empty outline, an unsupported `lang`.
- Warnings (printed to stderr, the page is still built): ellipsis truncation, empty titles, duplicate sibling titles, a missing piece (`missing part: file`; the page is built without that block, so fix it), unknown `meta.json` fields, a line starting with `*` or `+`, a line starting with `#`, a continuation line not indented deeper than its node, a `meta.json` without `lang`, a `now` that matches no first-level branch, a `use` that is none of the known values, an unknown kind in `now_sections`, and replies in `replies.json` that are wrong: a status that is not one of the five, a `--node` that is not found or ambiguous, or a `needs-you` reply that points at no `[needs-you]` node.

For a map with `"now"` the build then prints either `"Now" branch check passed` or one `WARNING: "Now" branch is behind:` line per finding, followed by a `NOTE:` listing the open nodes outside "Now". Fix them and rebuild before you hand the map over.

Compare the numbers with the level's target (see [levels](levels.md)): an L2 with 30 nodes, or an L4 with 200, has probably missed things. A wrong indent can still parse and hang a node under the wrong parent, so after building, look through each first-level branch on the page and check what is under it.

`build.py <workdir> --no-paths` leaves the absolute path of the page and the reply command out of the page. Use it for a page that goes to other people or onto a website.
