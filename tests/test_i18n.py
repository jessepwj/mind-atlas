"""The page's UI strings: both languages complete, consistent and actually used."""
import json
import re
import unittest

from helpers import CJK, SCRIPTS, build

I18N = json.loads((SCRIPTS / "i18n.json").read_text(encoding="utf-8"))
TEMPLATE = (SCRIPTS / "template.html").read_text(encoding="utf-8")
BUILD_PY = (SCRIPTS / "build.py").read_text(encoding="utf-8")
VARS = re.compile(r"\{(\w+)\}")


def variants(value):
    return list(value.values()) if isinstance(value, dict) else [value]


def used_vars(value):
    found = set()
    for v in variants(value):
        found |= set(VARS.findall(v))
    return found


class StringTableTests(unittest.TestCase):
    def test_languages(self):
        self.assertEqual(sorted(I18N), ["en", "zh"])

    def test_same_keys_in_every_language(self):
        zh, en = set(I18N["zh"]), set(I18N["en"])
        self.assertEqual(zh - en, set(), "missing in en")
        self.assertEqual(en - zh, set(), "missing in zh")

    def test_same_placeholders_in_every_language(self):
        for key, zh_value in I18N["zh"].items():
            if key == "tags":
                continue
            with self.subTest(key=key):
                # a language may use fewer placeholders (a plural form can drop {n}), never different ones
                self.assertLessEqual(used_vars(I18N["en"][key]), used_vars(zh_value) | {"n"})
                self.assertLessEqual(used_vars(zh_value), used_vars(I18N["en"][key]) | {"n"})

    def test_plural_entries_have_exactly_one_and_other(self):
        for lang, table in I18N.items():
            for key, value in table.items():
                if isinstance(value, dict) and key != "tags":
                    with self.subTest(lang=lang, key=key):
                        self.assertEqual(sorted(value), ["one", "other"])

    def test_values_are_strings_and_not_blank(self):
        for lang, table in I18N.items():
            for key, value in table.items():
                if key == "tags":
                    continue
                for v in variants(value):
                    with self.subTest(lang=lang, key=key):
                        self.assertIsInstance(v, str)
                        self.assertTrue(v.strip())

    def test_english_has_no_chinese_characters(self):
        self.assertIsNone(CJK.search(json.dumps(I18N["en"], ensure_ascii=False)))

    def test_chinese_strings_are_chinese(self):
        for key, value in I18N["zh"].items():
            if key in ("html_lang", "tags"):
                continue
            if key in ("quote_text", "export_quote_text"):   # just quotation marks around {x}
                continue
            with self.subTest(key=key):
                self.assertIsNotNone(CJK.search(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)))

    def test_status_labels_cover_every_status_key(self):
        keys = set(build.TAGS_ZH.values())
        self.assertEqual(keys, set(build.TAGS_EN.values()))
        for lang in I18N:
            self.assertEqual(set(I18N[lang]["tags"]), keys)
        legend = re.search(r"const TAGS = \[(.*?)\];", TEMPLATE).group(1)
        self.assertEqual(set(re.findall(r'"(\w+)"', legend)), keys)

    def test_chinese_labels_are_the_written_spellings(self):
        spelled = {v: k for k, v in build.TAGS_ZH.items()}
        for key, label in I18N["zh"]["tags"].items():
            self.assertEqual(spelled[key], label)

    def test_template_has_no_hard_coded_chinese(self):
        self.assertIsNone(CJK.search(TEMPLATE))

    def test_every_key_the_template_asks_for_exists(self):
        asked = set(re.findall(r"\bt\('(\w+)'", TEMPLATE))
        asked |= set(re.findall(r'data-i18n(?:-title|-ph)?="(\w+)"', TEMPLATE))
        self.assertTrue(asked)
        for lang, table in I18N.items():
            self.assertEqual(asked - set(table), set(), lang)

    def test_every_key_is_used_somewhere(self):
        asked = set(re.findall(r"\bt\('(\w+)'", TEMPLATE))
        asked |= set(re.findall(r'data-i18n(?:-title|-ph)?="(\w+)"', TEMPLATE))
        asked |= {"tags"} | set(re.findall(r'strings\["(\w+)"\]', BUILD_PY))
        self.assertEqual(set(I18N["zh"]) - asked, set())

    def test_every_language_builds_a_page(self):
        import tempfile, shutil, pathlib
        for lang in I18N:
            with self.subTest(lang=lang):
                tmp = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-i18n-"))
                self.addCleanup(shutil.rmtree, str(tmp), True)
                (tmp / "meta.json").write_text(json.dumps({"title": "T", "lang": lang}), encoding="utf-8")
                (tmp / "outline.md").write_text("# R\n- A\n", encoding="utf-8")
                self.assertEqual(build.build(tmp).nodes, 2)


if __name__ == "__main__":
    unittest.main()
