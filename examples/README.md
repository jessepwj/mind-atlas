# Examples

Four small, made-up maps. They exist to show the outline format and the page; none of the content is real.

| Folder | Language | Map | Nodes |
|---|---|---|---|
| [`tool-library-en`](tool-library-en) | English | A neighborhood tool library run by five volunteers | 60 |
| [`book-corner-zh`](book-corner-zh) | 中文 | 小区旧书漂流角（志愿者维护的一组书架） | 60 |
| [`repair-cafe-en`](repair-cafe-en) | English | A monthly repair cafe, as a long-running map with a "Now" branch | 38 |
| [`repair-cafe-zh`](repair-cafe-zh) | 中文 | 旧物维修咖啡馆，带「现在」分支的长期使用的图 | 38 |

Each folder holds source files only:

| File | What it is |
|---|---|
| `meta.json` | Title, `lang`, a stable `id`, level, description, and the order of the pieces |
| `outline-trunk.md` | The trunk: purpose and rules, who does what. Written by the mapper |
| `outline-A-*.md`, `outline-B-*.md` | Branches that sub-agents would research. Piece A is attached under the last trunk node by indenting it two more spaces; piece B starts with its own branch head |
| `outline-T-*.md` | The cross-cutting branches: timeline, where the data lives |
| `outline-Z-*.md` | Problems and next steps, with the mapper's own judgment marked `[proposal]` |
| `outline-about.md` | About this map |

The first two maps each use all ten of the original status tags. The English one uses the ASCII
spellings (`[active]`, ` | `, `[src: ...]`); the Chinese one uses the Chinese spellings (`【在用】`, ` ｜ `, `〔...〕`).

The two `repair-cafe` maps are the same small map in both languages. They show a long-running map: a first-level
"Now" branch (set with `"now"` in `meta.json`) with items that need the user (`[needs-you]`), are in progress or are
waiting, dated entries under "Next up", a root title that carries the update time (`{{updated}}`) with a fixed `root_key`,
and a single `outline-main.md`. Open the page and look at the five numbers under the title.

## Build one

```bash
python3 skills/mind-atlas/scripts/build.py examples/tool-library-en
```

This writes `tool-library.html` and `outline.md` into the folder. Both are git-ignored; do not commit them.
The live demos are built by CI (`tools/build_site.py`) and published with GitHub Pages.
