# 参与贡献 mind-atlas

[English](CONTRIBUTING.md) · **简体中文**

感谢你考虑参与。mind-atlas 有两半：一半是 **skill**（指导智能体行为的文字），一半是一小套**工具链**
（`build.py`、`reply.py` 和页面模板，把大纲变成页面）。两半都欢迎你来改。

## 可以怎么参与

- **拿真实的活试一试，告诉我们哪里不对。** 最有价值的贡献是一个 issue：「我梳理了 X，智能体或页面做了 Y」。
  私人内容请先去掉。
- **改进 skill 文字。** 说得更清楚的指令、更好的等级建议、更利落的派单模板。
- **增加或改进一种语言。** 页面上的文字都在 `skills/mind-atlas/scripts/i18n.json` 里。
- **改进页面。** 布局、无障碍、键盘操作、大图的性能。
- **加一个示例。** 在 `examples/` 里放一份小而虚构的导图，什么语言都行。
- **修文档。** README、`CONTRIBUTING`、`docs/feedback-loop` 和各份参考文档都有中英文两个版本，要保持同步。

## 基本规矩

这些规矩让项目保持它现在的样子。要改动其中一条，请在 pull request 里说明理由。

1. **页面是静态的单文件。** 不联网、不起服务、不引用外部脚本、字体或图片。页面里带有内容安全策略来保证这一点。
2. **Python 脚本只用标准库**，在 macOS、Linux、Windows 上都要能跑，Python 3.9 或更高版本。文件一律按
   UTF-8、LF 换行写出，不要依赖控制台的编码。
3. **任何地方都不能出现个人或本机信息**：真实用户名、用户目录路径、内部项目名、令牌。用 `<skill_dir>`、
   `<workdir>` 这样的占位符。测试会扫描仓库里常见的泄露。
4. **事实和判断分开。** skill 要求智能体把自己的判断标成 `[proposal]`（中文写法【建议】），示例也要守这个规矩。
5. **两种语言平等。** 页面上的每条文字在 `i18n.json` 的每种语言里都要有（测试会核对键和占位符）；改了英文的 README、`CONTRIBUTING`、`docs/feedback-loop`
   或参考文档，要在同一个 pull request 里改它的 `zh-CN` 对应版本，或在 pull request 里说明翻译还没做。

## 开发环境

只需要 Python 3.9 或更高版本，没有任何东西要安装。

```bash
python -m unittest discover -s tests -v        # 全部测试
python skills/mind-atlas/scripts/build.py examples/book-corner-zh    # 生成一个示例
```

macOS 和 Linux 上解释器一般叫 `python3`，Windows 上是 `python` 或 `py`。`examples/` 里生成的 `*.html` 和
`outline.md` 已被 git 忽略。

驱动真实页面的测试需要 Chrome、Chromium 或 Edge，所以要自己打开：

```bash
MIND_ATLAS_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  python -m unittest discover -s tests -p "test_browser.py" -v
```

（Windows PowerShell 里先设置 `$env:MIND_ATLAS_CHROME`。）改了页面或示例之后，用 `python tools/make_screenshots.py`
重新生成 README 里的截图。

### 目录说明

| 路径 | 内容 |
|---|---|
| `skills/mind-atlas/SKILL.md` | skill 本体。文件开头 frontmatter 里的 `name` 必须和文件夹同名 |
| `skills/mind-atlas/references/` | 给智能体看的参考文档，每份都有 `.zh-CN.md` 对应版本 |
| `skills/mind-atlas/scripts/` | `build.py`、`reply.py`、`template.html`、`i18n.json` |
| `examples/` | 示例的源文件。不要提交生成的 html |
| `tests/` | `unittest` 测试 |
| `tools/` | 维护者工具：演示站点生成器、截图生成器 |
| `docs/` | 给人看的文档和截图 |

### 增加一种语言

1. 把 `skills/mind-atlas/scripts/i18n.json` 里的 `en` 块复制成新的键（比如 `"fr"`），把每一条都翻译。
   `{占位符}` 要原样保留。带 `one` 和 `other` 的是单复数条目（`n` 为 1 时用 `one`）。`html_lang` 和 `tags` 的标签也要填。
2. 文字要短。页面上的地方不大，最长的几条要在浏览器里看一下。
3. 运行测试。`tests/test_i18n.py` 会检查每种语言里的键和占位符是否齐全。
4. 大纲的写法（`[active]`、`【在用】`、` | `、` ｜ `）是和语言无关的关键字，不变：新增一种语言只翻译界面。
5. 在 pull request 里说明你怎么检查的措辞。母语者的审阅帮助很大。

## Pull request

1. fork 后从 `main` 拉分支（`feat/...`、`fix/...`、`docs/...`）。
2. 一个 pull request 只做一件事：一个修复、一个功能、一种语言。
3. 补充或更新测试，并在你手头最老的 Python 上跑一遍。
4. 在 `CHANGELOG.md` 的 `[Unreleased]` 下记一笔。
5. 说清改了什么、为什么。关联相关 issue。

## 提交信息

用 [Conventional Commits](https://www.conventionalcommits.org/)：`feat:`、`fix:`、`docs:`、`refactor:`、`test:`、`chore:`。

## 行为准则

参与即表示你同意遵守[行为准则](CODE_OF_CONDUCT.md)。
