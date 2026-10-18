"""tools/build_site.py: the demo site built for GitHub Pages."""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

from helpers import ROOT, page_json


class SiteTests(unittest.TestCase):
    def test_site_contains_every_example_without_local_paths(self):
        spec = importlib.util.spec_from_file_location("mind_atlas_site", str(ROOT / "tools" / "build_site.py"))
        site = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(site)
        out = pathlib.Path(tempfile.mkdtemp(prefix="mind-atlas-site-test-"))
        self.addCleanup(shutil.rmtree, str(out), True)
        written = site.build_site(out)
        self.assertEqual(sorted(written), ["book-corner.html", "repair-cafe-zh.html", "repair-cafe.html", "tool-library.html"])
        index = (out / "index.html").read_text(encoding="utf-8")
        for name in written:
            self.assertIn('href="%s"' % name, index)
            meta = page_json((out / name).read_text(encoding="utf-8"), "meta")
            self.assertNotIn("file", meta)
            self.assertNotIn("reply_cmd", meta)
        self.assertEqual(index.count("project tracking / 跟进项目"), 2)       # the kind comes from the example's "use"
        self.assertEqual(index.count("learning / 学习理解"), 2)
        self.assertTrue((out / ".nojekyll").exists())
        self.assertEqual(sorted(p.name for p in out.iterdir()), [".nojekyll", "book-corner.html", "index.html", "repair-cafe-zh.html", "repair-cafe.html", "tool-library.html"])


if __name__ == "__main__":
    unittest.main()
