"""Repository-level checks: no leaked personal details, links resolve, versions agree, files are in place."""
import json
import re
import subprocess
import unittest

from helpers import CJK, ROOT, build

TEXT_SUFFIXES = {".md", ".py", ".json", ".yml", ".yaml", ".html", ".svg", ".txt", ".cfg", ".toml", ".gitignore",
                 ".gitattributes", ".editorconfig"}
SKIP_DIRS = {".git", "__pycache__", "_site", "node_modules"}


def repo_files():
    """Files git would track (tracked plus new, minus ignored); falls back to walking the tree."""
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=str(ROOT),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        names = [n for n in out.decode("utf-8").split("\0") if n]
        found = [ROOT / n for n in names]
    except (OSError, subprocess.CalledProcessError):
        found = [p for p in ROOT.rglob("*") if p.is_file()]
    return sorted(p for p in found if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS))


def text_files():
    return [p for p in repo_files() if p.suffix.lower() in TEXT_SUFFIXES or p.name.startswith(".")]


class HygieneTests(unittest.TestCase):
    # Patterns are assembled from pieces so that this file does not match itself.
    FORBIDDEN = {
        "home folder on macOS": "/Us" + "ers/",
        "home folder on Windows": r"[A-Za-z]:\\Us" + "ers",
        "a personal user name": "pan" + "wejie",
        "a personal name in Chinese": "潘" + "文杰",
        "a private vault name": "codex-knowledge" + "-vault",
        "a private drive name": "EXTERNAL" + "USB",
        "a private scratch folder": r"\.scra" + "tch",
        "a private tool name": "phone" + "-lab",
        "a private tool name (file delivery)": "SendUser" + "File",
        "a local dev port": r"127\.0\.0\.1:8" + "7",
        "a private-network address": r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "the first-person owner word": "本" + "人",
        "a private notes path": "skills/" + "save",
        "a private wiki path": r"\bwik" + r"i/",
        "a mainland phone number": r"(?<!\d)1[3-9]\d{9}(?!\d)",
        "an API key": r"\bsk-[A-Za-z0-9]{20,}",
        "a GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{20,}",
        "an AWS key": r"\bAKIA[0-9A-Z]{16}\b",
        "a Slack token": r"\bxox[abp]-[A-Za-z0-9-]{10,}",
        "a private key block": "BEGIN (RSA |EC |OPENSSH )?PRIVATE" + " KEY",
    }
    EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
    EMAIL_OK = ("users.noreply.github.com",)

    def test_no_personal_or_machine_details(self):
        problems = []
        for path in text_files():
            body = path.read_text(encoding="utf-8", errors="replace")
            for what, pattern in self.FORBIDDEN.items():
                m = re.search(pattern, body)
                if m:
                    problems.append("%s: %s (%r)" % (path.relative_to(ROOT), what, m.group(0)))
            for m in self.EMAIL.finditer(body):
                if not m.group(0).endswith(self.EMAIL_OK):
                    problems.append("%s: an e-mail address (%r)" % (path.relative_to(ROOT), m.group(0)))
        self.assertEqual(problems, [])

    def test_the_scan_sees_the_files_it_should(self):
        names = {p.relative_to(ROOT).as_posix() for p in text_files()}
        for expected in ("README.md", "skills/mind-atlas/SKILL.md", "skills/mind-atlas/scripts/build.py",
                         "examples/tool-library-en/meta.json", ".github/workflows/ci.yml"):
            self.assertIn(expected, names)

    def test_no_generated_files_are_in_the_tree(self):
        generated = [p.relative_to(ROOT).as_posix() for p in repo_files()
                     if "examples" in p.relative_to(ROOT).parts[:1]
                     and (p.suffix == ".html" or p.name in ("outline.md", "replies.json"))]
        self.assertEqual(generated, [], "generated files in examples/ should be git-ignored (see .gitignore)")


class LinkTests(unittest.TestCase):
    LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)")

    def test_relative_links_and_images_resolve(self):
        problems = []
        for path in repo_files():
            if path.suffix != ".md":
                continue
            body = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
            for m in self.LINK.finditer(body):
                target = (m.group(1) or m.group(2)).split("#")[0]
                if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target):
                    continue
                if not (path.parent / target).resolve().exists():
                    problems.append("%s -> %s" % (path.relative_to(ROOT), target))
        self.assertEqual(problems, [])

    def test_the_two_readmes_link_to_each_other_and_share_the_same_images(self):
        en = (ROOT / "README.md").read_text(encoding="utf-8")
        zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        self.assertIn("(README.zh-CN.md)", en)
        self.assertIn("(README.md)", zh)
        img = re.compile(r"\]\((docs/assets/[^)]+)\)|src=\"(docs/assets/[^\"]+)\"")
        for body in (en, zh):
            for m in img.finditer(body):
                self.assertTrue((ROOT / (m.group(1) or m.group(2))).exists())

    def test_every_reference_has_both_languages(self):
        refs = ROOT / "skills" / "mind-atlas" / "references"
        english = sorted(p.stem for p in refs.glob("*.md") if not p.name.endswith(".zh-CN.md"))
        self.assertEqual(english, ["brief-template", "levels", "outline-format"])
        for stem in english:
            twin = refs / (stem + ".zh-CN.md")
            self.assertTrue(twin.exists(), twin)
            self.assertIsNotNone(CJK.search(twin.read_text(encoding="utf-8")))
            self.assertIsNone(CJK.search(re.sub(r"【[^】]*】|〔|〕| ｜ ", "", (refs / (stem + ".md")).read_text(encoding="utf-8"))
                                         .replace("中文", "").replace("简体中文", "")), stem)

    def test_docs_come_in_pairs(self):
        for en in (ROOT / "docs").glob("*.md"):
            if not en.name.endswith(".zh-CN.md"):
                self.assertTrue(en.with_name(en.stem + ".zh-CN.md").exists(), en)
        self.assertTrue((ROOT / "CONTRIBUTING.zh-CN.md").exists())


class DocExampleTests(unittest.TestCase):
    def fenced_after(self, path, heading):
        body = (ROOT / path).read_text(encoding="utf-8")
        section = body.split(heading, 1)[1]
        return re.search(r"```text\n(.*?)```", section, re.S).group(1)

    def test_the_outline_sample_in_each_readme_is_valid(self):
        for path, heading in (("README.md", "## The outline format at a glance"), ("README.zh-CN.md", "## 大纲写法速览")):
            with self.subTest(readme=path):
                sample = self.fenced_after(path, heading)
                lines = [("README", i, ln) for i, ln in enumerate(sample.splitlines(), 1)]
                root, warnings = build.parse_outline(lines)
                self.assertEqual(warnings, [])
                self.assertEqual(build.check_nodes(root), [])
                problems = [n for n in root["c"] if n["t"].startswith(("Problems", "问题"))][0]
                self.assertEqual(problems["g"], [], "the note must not contain a status word")
                tags = {g for n, _, _ in build.walk(root) for g in n["g"]}
                self.assertTrue({"decided", "active", "risk", "proposal"} <= tags, tags)

    def test_the_outline_sample_in_the_skill_references_is_valid(self):
        for name in ("outline-format.md", "outline-format.zh-CN.md"):
            with self.subTest(file=name):
                body = (ROOT / "skills" / "mind-atlas" / "references" / name).read_text(encoding="utf-8")
                sample = re.search(r"```\n(# .*?)```", body, re.S).group(1)
                lines = [(name, i, ln) for i, ln in enumerate(sample.splitlines(), 1)]
                root, _ = build.parse_outline(lines)
                self.assertTrue(root["c"])


class MetadataTests(unittest.TestCase):
    def load(self, rel):
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))

    def test_versions_agree(self):
        plugin = self.load(".claude-plugin/plugin.json")
        market = self.load(".claude-plugin/marketplace.json")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        latest = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M).group(1)
        self.assertEqual(plugin["version"], latest)
        self.assertEqual(market["metadata"]["version"], latest)
        self.assertEqual(market["plugins"][0]["version"], latest)
        self.assertEqual(market["plugins"][0]["name"], plugin["name"])
        self.assertIn("[%s]: https://github.com/jessepwj/mind-atlas/releases/tag/v%s" % (latest, latest), changelog)

    def test_plugin_and_marketplace_fields(self):
        plugin = self.load(".claude-plugin/plugin.json")
        self.assertEqual(plugin["name"], "mind-atlas")
        self.assertEqual(plugin["license"], "MIT")
        self.assertEqual(plugin["repository"], "https://github.com/jessepwj/mind-atlas")
        market = self.load(".claude-plugin/marketplace.json")
        self.assertEqual(market["plugins"][0]["source"]["repo"], "jessepwj/mind-atlas")

    def test_skill_front_matter(self):
        body = (ROOT / "skills" / "mind-atlas" / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"---\nname: (\S+)\ndescription: \"(.+?)\"\n---\n", body, re.S)
        self.assertIsNotNone(m, "front matter with name and a quoted description")
        self.assertEqual(m.group(1), "mind-atlas")
        self.assertLess(len(m.group(2)), 1024)
        for trigger in ("mind map", "梳理一下全貌", "做成思维导图"):
            self.assertIn(trigger, m.group(2))
        self.assertTrue(body.split("---\n", 2)[2].lstrip().startswith("# mind-atlas"))

    def test_license(self):
        body = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(body.startswith("MIT License"))
        self.assertIn("Copyright (c) 2026 Pan Wenjie", body)

    def test_expected_community_files(self):
        for rel in ("README.md", "README.zh-CN.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
                    "SECURITY.md", ".editorconfig", ".gitattributes", ".gitignore", ".markdownlint.json",
                    ".github/workflows/ci.yml", ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/bug_report.yml",
                    ".github/ISSUE_TEMPLATE/feature_request.yml", ".github/ISSUE_TEMPLATE/config.yml",
                    "skills/mind-atlas/agents/openai.yaml", "docs/assets/screenshot-en.png", "docs/assets/screenshot-zh.png"):
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_workflows_cover_windows_and_the_python_range(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("windows-latest", ci)
        for v in ("3.9", "3.10", "3.11", "3.12", "3.13"):
            self.assertIn('"%s"' % v, ci)


if __name__ == "__main__":
    unittest.main()
