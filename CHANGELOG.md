# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-10-18

Every map says what it is for, and a map you track can no longer quietly go stale.

### Added

- **A use for every map.** `"use"` in `meta.json` takes `learning`, `project tracking` or `decision` (the Chinese
  spellings work too) and shows in the page header in the page's language. `SKILL.md` has a new section, "Decide the use
  first", with the first-level branches for each use. A learning map must end with **"What this means for us"** (what to
  borrow, whether to adopt it, how it would fit, the next step, every judgment marked `[proposal]`); a tracking map keeps
  the project's own notes as the source of truth and the map as a view of them. Another value is shown as written, with a warning.
- **A fixed "Now" branch for project tracking.** Seven sections in this order: Needs you, In progress, Waiting on others,
  Problems and risks, Next up (every title starts with a date), Later, and Recently done (the last two days, grouped by day,
  about ten items). Older groups move whole into the History branch under that day. "Update Now in the same step as the project
  notes" is now part of the instructions.
- **A stale-"Now" check in `build.py`.** For a map with `"now"`, every build reports: a time point that passed more than 30
  minutes ago; a time point whose title does not start with a date (`MM-DD HH:MM`, `MM-DD` or `YYYY-MM-DD`; a time under a dated
  group is fine); "today", "tomorrow", "yesterday", "tonight" and their Chinese counterparts in a title; "Recently done" with more
  than `done_max` items (default 10) or a day group from two days ago or earlier; an unfinished tag under "Recently done"; and an
  empty "Needs you". It also lists, as a note, the nodes outside "Now" still tagged `[in progress]` or `[waiting]` (a branch whose
  title contains "snapshot" is skipped). It only prints (to stderr, like the other warnings); the page is built either way.
  Sections are recognized by the words in their titles, in English and Chinese; `"now_sections"` in `meta.json` names them
  when a map uses other words (a title there that matches no section is a warning). When none of the "Needs you", "Next up" and
  "Recently done" sections is recognized the build says that part was not checked instead of claiming a pass. `build()` returns the
  findings as `BuildResult.stale` and `BuildResult.open_outside`, and the recognized section kinds as `BuildResult.now_roles`.
- **Moved nodes keep their quotes and replies.** When a node moves (say from "Recently done" into the History branch) and keeps its
  title, a reply's `--node` and the page's quotes and reply chips find it by the last part of the path, as long as exactly one
  node has that title.
- The console's nearest time point and its list also read `YYYY-MM-DD HH:MM` titles and a year on the parent group.
- Interface strings for the header (`meta_use` and the `uses` table) in both languages.
- A "What this means for us" branch in `examples/tool-library-en` and `examples/book-corner-zh`, which are now learning maps; the
  two `repair-cafe` examples are project-tracking maps with the full seven-section "Now" branch and a `"use"` each.
- Tests: the date and time reading, every stale-"Now" rule in both languages, the section recognition, the moved-node lookup in the
  build and in headless Chrome, the `use` field and its header, and the examples against the new rules (the clock is pinned for
  the dated ones).

### Changed

- Maps that stay open for days are now called project-tracking maps in the docs. The outline-format anchor
  `#long-running-maps-the-now-branch` is now `#project-tracking-maps-the-now-branch` (the zh-CN one follows).
- The two `repair-cafe` examples use the seven sections, with dated "Next up" entries and day groups under "Recently done".
- `BuildResult` has three more fields, `stale`, `open_outside` and `now_roles`, for anyone who imports `build.py`.
- The demo-site index labels each example by its `use` (project tracking, learning) instead of "long-running console" or "full map".

### Fixed

- The outline-format reference said "ten status tags" in the checklist for sub-agent reports; there are eleven.
- The list behind the console's time-point number showed the date twice ("11-05 11-05 18:00 ..."); it shows the title as written.
- "Quote this" now also appears when you select text inside the quote of a node that moved.

## [1.1.0] - 2026-10-17

A console for maps you keep open for days.

### Added

- **Console.** Five numbers under the page title (needs you, new replies, recently changed, in progress, waiting)
  that list their items and jump to the node, a "Show only" filter for each kind, and a "How to use" / "Legend" pair
  under the title. The numbers come from a first-level "Now" branch (`"now"` in `meta.json`).
- **`[needs-you]` status tag** (`【要你定】`, `[needs you]` also accepted): something the user must answer or do.
  Eleven status tags now.
- **Recently changed.** `build.py` gives every node a content fingerprint (title, status tags, note); the page compares
  it with the snapshot of what the user last saw and marks nodes New or Edited, and shows a dot beside `+N` when a
  collapsed branch holds changes.
- **`root_key` and `now` in `meta.json`.** `root_key` is the root's fixed name inside node paths, so the root title can
  carry the update time (`{{updated}}`, or `{{更新}}` in a Chinese outline) without breaking old quotes or snapshots.
  The "now" branch takes no color slot, starts expanded and shows its notes.
- **Structured replies.** `reply.py` takes `--summary`, `--status` (`done`, `doing`, `planned`, `dropped`, `needs-you`,
  Chinese spellings accepted), `--node` (repeatable) and `--ask`, plus `--no-build`. A reply shows as a one-line conclusion,
  a status label, folded details and related-node chips. `build.py` resolves the nodes and warns about unknown statuses,
  nodes it cannot find and `needs-you` replies that point at no `[needs-you]` node. Old replies still show.
- **Right panel in four groups**: needs you, new replies, waiting for the AI, handled (folded by date). A reply counts
  as read after two seconds in view; node badges carry a count and a red dot while something is unread.
- **`scripts/pull_feedback.py`.** When the user says "pull my feedback", reads their feedback out of a copy of the
  browser's local storage (Chrome, Chromium, Edge, Brave, Ego Lite; a small pure-Python LevelDB and Snappy reader),
  lists the new items and records them in `_fb/inbox.jsonl`. Manual only: no timer, no service. `build.py` embeds
  `_fb/` in the page so another browser still shows the user's words and the replies.
- **`<page>.stamp.js`.** A page left open reads it when the user returns to the tab and offers a refresh when there is
  a newer build (local pages only; not written with `--no-paths`).
- The page keeps expansion, filter, selection and zoom in `sessionStorage`, so refreshing the same tab keeps the place.
- Two small examples that show the console, with live demos: `examples/repair-cafe-en` and `examples/repair-cafe-zh`.
  Two new screenshots.
- Tests: the new tag and `meta.json` fields, fingerprints and node resolution, every `reply.py` option and its checks,
  embedded feedback, the stamp file and content-security policy, the LevelDB and Snappy readers and `pull_feedback.py`
  end to end (also against a LevelDB written by a real Chrome), and headless-browser tests of the five numbers, their
  lists, the filters, the New/Edited marks and the stale-page notice, in both languages.

### Changed

- "Back to root" is now "Back to Now" (the top left of the map); the zoom buttons float at the bottom left of the map.
- "Copy for AI" copies the feedback that has no reply yet and was not copied before; it is described as the fallback to
  "pull my feedback".
- A page built without `--no-paths` allows the sibling `.stamp.js` through its content-security policy
  (`script-src 'unsafe-inline' file:`); pages built with `--no-paths` keep the stricter policy.
- New interface strings are in `i18n.json` in both languages; the `tags` table gained `needs-you` and a `statuses` table
  was added.

## [1.0.0] - 2026-10-16

### Added

- `mind-atlas` skill: choose a level (L1 overview to L4 panorama), research branches with read-only
  sub-agents, write an outline, build a single-file HTML mind map, and run a feedback loop with the user.
- `scripts/build.py`: builds the page from an outline work folder. Checks the structure (tabs, odd or skipped
  indentation, a second root, an empty outline) with file and line numbers, and warns about ellipsis
  truncation, empty titles, duplicate sibling titles, missing pieces, unknown `meta.json` fields, a missing
  `lang`, and lines that look like list items or headings but are not nodes. It prints one line per first-level
  branch with its node count, which makes a node hung under the wrong parent easy to spot. `--no-paths` leaves local paths out of pages that will be shared.
- `scripts/reply.py`: records a reply to a piece of page feedback and rebuilds the page.
- `scripts/template.html`: the page. A horizontal tree with drag, pan and zoom, search, an outline view, a
  details panel, and a feedback panel that stores feedback in the browser. Single file, no network
  (enforced with a content security policy), no server.
- English and Chinese interface, selected with `"lang"` in `meta.json`; every UI string lives in
  `scripts/i18n.json`, so another language is one more block there.
- Outline syntax in two spellings that can be mixed: `[active]`, ` | `, `[src: ...]` and
  `【在用】`, ` ｜ `, `〔...〕`.
- Three reference documents in English and Chinese: levels and sub-agents, a dispatch brief template, and the
  outline format.
- Two examples with source files only: `examples/tool-library-en` and `examples/book-corner-zh`.
- Unit tests (standard library `unittest`) for parsing, building, replies, the examples, the string tables and
  repository hygiene, plus an opt-in headless-browser test.
- CI on Ubuntu and Windows with Python 3.9 to 3.13, markdown lint, a browser smoke test, and a GitHub Pages
  workflow that publishes the examples as live demos.
- Claude Code plugin manifest and marketplace entry, Codex `agents/openai.yaml`.
- Bilingual README, contribution guide, code of conduct, security policy, and issue and pull request
  templates.

[Unreleased]: https://github.com/jessepwj/mind-atlas/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/jessepwj/mind-atlas/releases/tag/v1.2.0
[1.1.0]: https://github.com/jessepwj/mind-atlas/releases/tag/v1.1.0
[1.0.0]: https://github.com/jessepwj/mind-atlas/releases/tag/v1.0.0
