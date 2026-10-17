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
| `level` | recommended | The mapping level, such as `L4 Panorama`, shown in the page header |
| `desc` | recommended | One line for the header: how it was made, how far it was verified |
| `root_key` | recommended for long-running maps | The root's fixed name inside node paths. The root title may change (for example it carries `{{updated}}`); old quotes and the "what you last saw" snapshot keep working because paths use this name. Default: the root title as written |
| `now` | long-running maps | Title of the first-level branch that holds what is going on right now; must match the outline exactly (the build warns otherwise). It takes no color slot, starts expanded and shows its notes, and its `[in progress]`, `[waiting]` and `[needs-you]` nodes feed the numbers at the top of the page |
| `search_hint` | no | Placeholder of the search box; give a few words that are really in this map |
| `parts` | no | Ordered list of the outline pieces to join. If absent, `outline.md` in the folder is read |
| `out` | no | Output file name (a plain name, not a path). Default `<title>.html` |

Unknown fields are ignored with a warning, so a typo does not go unnoticed.

## Status tags (eleven, no others)

| Tag | Chinese | Use it for |
|---|---|---|
| `[needs-you]` | 【要你定】 | Something the user must answer or do before things can move. Only in the "now" branch of a long-running map; leave it out when there is nothing. After the user has answered and the AI has replied, change it to `[decided]` or `[todo]` and move it out of "now" |
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

## Long-running maps: the "now" branch

Most maps are read once. A map that stays open for days, that the user answers again and again and the AI keeps updating (a project's control map, say), works better with a "now" branch and the console on top of the page.

1. **Put a first-level branch "Now" first.** Write `"now": "Now"` in `meta.json`; the title must match exactly. Group it into: what needs the user's decision, what is in progress, what is waiting on others, the next points in time, what was recently finished. The other branches hold the detail; "Now" and the detail must agree.
2. **The numbers at the top count what is tagged inside "Now"**:

   | Number | Counts |
   |---|---|
   | Needs you | Nodes tagged `[needs-you]` anywhere in the map, plus the AI's open questions (a reply with the status `needs-you`) |
   | New replies | Replies the user has not seen yet; a reply counts as seen after two seconds in the right panel |
   | Recently changed | Nodes whose title, status or note changed, or that are new, since the user last looked at this map |
   | In progress | The lowest `[in progress]` nodes in "Now" |
   | Waiting | The lowest `[waiting]` nodes in "Now" |

   Beside them the page shows the nearest upcoming time point. A node in a group of "Now" titled "Next up", "Upcoming" or "Coming up" (a Chinese outline uses the Chinese word for "next"; the zh-CN version of this file spells it out) counts as a time point when its title starts with `HH:MM`, optionally preceded by `MM-DD` (otherwise the date is read from a parent title such as `11-05`). That group and a group titled "Recently done" start collapsed.
3. **Use `[needs-you]` sparingly**: only for what truly needs the user. If there is nothing, write that there is nothing; do not invent items. When a reply to the user's feedback sets the status `needs-you`, point it (`--node`) at the matching `[needs-you]` item, and keep the two in step.
4. **Fix two names in `meta.json`**: `id` (where feedback lives in the browser) and `root_key`. The root title may then carry the update time: write `{{updated}}` in it, and the build turns it into "updated MM-DD HH:MM" (a Chinese page says it the Chinese way). Paths use `root_key`, so the changing title breaks nothing.
5. **Edit only what must change.** The build gives every node a fingerprint of its title, tags and note; the page marks nodes whose fingerprint differs from what the user last saw as New or Edited. Rewriting text for no reason makes the whole map light up.
6. **Keep "Now" current.** Whenever something is decided, finished or scheduled, update the "Now" piece, update the detail branches to match, and rebuild.

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
- **History**: by date, one node per day, with what got done under it, marked `[done]`.
- **Timeline**: gathers scattered schedules and dates into one chronological list. It is a cross-cutting branch, written by the main agent.
- **Where the data lives**: the folder structure and one sentence for each kind of data. Locations only; never copy contents.
- **Problems and improvements**: first group by priority (one, two, three), the problems under each group, and `[proposal]` nodes under the problems. Group titles state the purpose: "protect the data first", "consolidate the documents", "tidy the code".
- **About this map** (L4): how it was made, what was corrected, how to give feedback, how to update it.

## Turning a sub-agent report into an outline piece

A report is a Markdown nested list whose indentation is already close to an outline, but it needs these changes:

1. Sources in brackets become `[src: source]` at the end of the node.
2. Keep only the ten status tags in the table; rewrite anything else.
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
- Warnings (printed to stderr, the page is still built): ellipsis truncation, empty titles, duplicate sibling titles, a missing piece (`missing part: file`; the page is built without that block, so fix it), unknown `meta.json` fields, a line starting with `*` or `+`, a line starting with `#`, a continuation line not indented deeper than its node, a `meta.json` without `lang`, a `now` that matches no first-level branch, and replies in `replies.json` that are wrong: a status that is not one of the five, a `--node` that is not found or ambiguous, or a `needs-you` reply that points at no `[needs-you]` node.

Compare the numbers with the level's target (see [levels](levels.md)): an L2 with 30 nodes, or an L4 with 200, has probably missed things. A wrong indent can still parse and hang a node under the wrong parent, so after building, look through each first-level branch on the page and check what is under it.

`build.py <workdir> --no-paths` leaves the absolute path of the page and the reply command out of the page. Use it for a page that goes to other people or onto a website.
