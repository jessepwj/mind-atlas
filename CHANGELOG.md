# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/jessepwj/mind-atlas/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/jessepwj/mind-atlas/releases/tag/v1.0.0
