# Contributing to mind-atlas

**English** · [简体中文](CONTRIBUTING.zh-CN.md)

Thanks for considering a contribution. mind-atlas has two halves: a **skill**, which is prose that guides an
agent, and a small **toolchain** (`build.py`, `reply.py`, a page template) that turns an outline into a page.
Both matter, and both are welcome here.

## Ways to contribute

- **Try it on real work and tell us what broke.** The most valuable contribution is an issue that says "I
  mapped X, and the agent or the page did Y". Redact anything private.
- **Improve the skill text.** Clearer instructions, better level guidance, a sharper brief template.
- **Add or improve a language.** The page's strings live in `skills/mind-atlas/scripts/i18n.json`.
- **Improve the page.** Layout, accessibility, keyboard use, performance on large maps.
- **Add an example.** A small, made-up map in `examples/`, in any language.
- **Fix docs.** The READMEs, `CONTRIBUTING`, `docs/feedback-loop` and the references exist in English and Chinese; keep each pair in sync.

## Ground rules

These keep the project what it is. A change that bends one of them needs a good reason in the pull request.

1. **The page is a static single file.** No network access, no server, no external script, font or image.
   The page carries a content security policy that enforces this.
2. **Python scripts use the standard library only** and must run on Python 3.9 or newer, on macOS, Linux and
   Windows. Write files as UTF-8 with LF line endings; do not rely on the console encoding.
3. **No personal or machine-specific details anywhere**: no real user names, home-folder paths, internal
   project names, tokens. Use placeholders such as `<skill_dir>` and `<workdir>`. A test scans the repository
   for common leaks.
4. **Fact and judgment stay apart.** The skill tells the agent to mark its own judgments `[proposal]`; keep
   that discipline in the examples too.
5. **Both languages stay equal.** A UI string exists in every language of `i18n.json` (a test checks the
   keys and the placeholders), and a change to an English README, `CONTRIBUTING`, `docs/feedback-loop` or reference is made in its
   `zh-CN` twin in the same pull request, or you say in the pull request that a translation is still needed.

## Development setup

You only need Python 3.9 or newer. There is nothing to install.

```bash
python -m unittest discover -s tests -v        # the whole suite
python skills/mind-atlas/scripts/build.py examples/tool-library-en   # build an example
```

On macOS and Linux the interpreter is usually `python3`, on Windows `python` or `py`. The generated
`*.html` and `outline.md` files in `examples/` are git-ignored.

The tests that drive a real page need Chrome, Chromium or Edge, so they are opt-in:

```bash
MIND_ATLAS_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  python -m unittest discover -s tests -p "test_browser.py" -v
```

(On Windows PowerShell set `$env:MIND_ATLAS_CHROME` first.) To regenerate the README screenshots after
changing the page or the examples, run `python tools/make_screenshots.py`.

### Where things are

| Path | What |
|---|---|
| `skills/mind-atlas/SKILL.md` | The skill. Keep the front matter `name` equal to the folder name |
| `skills/mind-atlas/references/` | Agent-facing reference docs, each with a `.zh-CN.md` twin |
| `skills/mind-atlas/scripts/` | `build.py`, `reply.py`, `template.html`, `i18n.json` |
| `examples/` | Source files of the examples. Never commit the generated html |
| `tests/` | `unittest` tests |
| `tools/` | Maintainer tools: the demo-site builder and the screenshot maker |
| `docs/` | Human-facing docs and screenshots |

### Adding a language

1. Copy the `en` block in `skills/mind-atlas/scripts/i18n.json` to a new key, for example `"fr"`, and
   translate every value. Keep the `{placeholders}` exactly. Entries with `one` and `other` are plurals
   (`one` is used when `n` is 1). Set `html_lang` and the `tags` labels too.
2. Keep strings short. The page has little room, so test the longest ones in the browser.
3. Run the tests. `tests/test_i18n.py` checks that every key and placeholder exists in every language.
4. Outline spellings (`[active]`, `【在用】`, ` | `, ` ｜ `) are language-neutral keywords and do not change:
   a new language only translates the interface.
5. Say in the pull request how you checked the wording. A native speaker's review helps a lot.

## Pull requests

1. Fork and branch from `main` (`feat/...`, `fix/...`, `docs/...`).
2. Keep pull requests focused: one fix, one feature, one language.
3. Add or update tests, and run the suite on the oldest Python you have.
4. Update `CHANGELOG.md` under `[Unreleased]`.
5. Describe what changed and why. Link any issue.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `refactor:`,
`test:`, `chore:`.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
