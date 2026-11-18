"""scripts/indexnow.py and the data-finder pages in the sitemap (offline, stdlib).

    python3 scripts/test_indexnow.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402
import indexnow  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
S = indexnow.SITE_URL


def make_site(tmp: Path, pages: dict[str, str], key: str = "abc12345abc12345") -> Path:
    """A site folder with a sitemap of `pages` (path -> HTML; "" is the home page) and a key file."""
    for path, html in pages.items():
        (tmp / path).mkdir(parents=True, exist_ok=True)
        (tmp / path / "index.html").write_text(html, encoding="utf-8")
    locs = "".join(f"<url><loc>{S}{p + '/' if p else ''}</loc></url>" for p in pages)
    (tmp / "sitemap.xml").write_text(f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')
    (tmp / f"{key}.txt").write_text(key)
    return tmp


class Manifest(unittest.TestCase):
    def test_a_new_asset_hash_does_not_count_as_a_change(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), {"": '<link href="style.css?v=aaaa11">x', "proiect/a": "a"})
            before = indexnow.manifest(site)
            (site / "index.html").write_text('<link href="style.css?v=bbbb22">x')
            self.assertEqual(indexnow.manifest(site), before)
            (site / "index.html").write_text('<link href="style.css?v=bbbb22">y')
            self.assertNotEqual(indexnow.manifest(site)[S], before[S])

    def test_an_address_with_no_page_stops_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), {"proiect/a": "a"})
            (site / "proiect/a/index.html").unlink()
            with self.assertRaises(SystemExit):
                indexnow.manifest(site)


class Changed(unittest.TestCase):
    def test_new_and_changed_addresses_go_and_unchanged_and_removed_ones_do_not(self):
        old = {S + "a/": "1", S + "b/": "2", S + "gone/": "3"}
        new = {S + "a/": "1", S + "b/": "9", S + "c/": "4"}
        self.assertEqual(indexnow.changed(new, old), [S + "b/", S + "c/"])

    def test_with_no_earlier_manifest_every_address_goes(self):
        new = {S + "a/": "1", S + "b/": "2"}
        self.assertEqual(indexnow.changed(new, None), list(new))


class Plan(unittest.TestCase):
    def test_plan_writes_the_manifest_into_the_site_and_the_list_outside_it(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as o:
            site = make_site(Path(d), {"": "home", "proiect/a": "a"})
            out = Path(o) / "urls.txt"
            urls = indexnow.plan(site, out, live=None)
            self.assertEqual(urls, [S, S + "proiect/a/"])
            self.assertEqual(out.read_text().split(), urls)
            self.assertEqual(set(json.loads((site / indexnow.MANIFEST).read_text())), set(urls))

    def test_a_site_without_exactly_one_key_file_stops(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), {"": "home"})
            (site / "zzzz9999zzzz9999.txt").write_text("zzzz9999zzzz9999")
            with self.assertRaises(SystemExit):
                indexnow.key_file(site)
            (site / "zzzz9999zzzz9999.txt").write_text("not the key")  # a .txt whose content is not its name is no key
            self.assertEqual(indexnow.key_file(site).stem, "abc12345abc12345")


class Submit(unittest.TestCase):
    def test_the_payload_names_the_host_the_key_and_its_location(self):
        p = indexnow.payload([S + "a/"], "abc12345abc12345")
        self.assertEqual(p, {"host": "civtech.gov2.ro", "key": "abc12345abc12345",
                             "keyLocation": S + "abc12345abc12345.txt", "urlList": [S + "a/"]})

    def test_an_empty_list_sends_nothing(self):
        self.assertEqual(indexnow.submit([], "abc12345abc12345", endpoint="http://127.0.0.1:9/never"), 0)

    def test_an_unreachable_endpoint_warns_and_does_not_raise(self):
        self.assertEqual(indexnow.submit([S], "abc12345abc12345", endpoint="http://127.0.0.1:9/indexnow", timeout=2), 0)


class TrackedFiles(unittest.TestCase):
    def test_the_site_holds_one_key_file_whose_content_is_its_name(self):
        key = indexnow.key_file(ROOT / "site")
        self.assertRegex(key.stem, indexnow.KEY_RX)

    def test_the_data_finder_templates_allow_indexing_and_the_entity_page_does_not(self):
        for name in ("inventory.html", "inventory-list.html", "inventory-vars.html"):
            self.assertNotIn("noindex", (ROOT / "scripts/templates" / name).read_text(), name)
        self.assertIn("noindex", (ROOT / "scripts/templates/entities.html").read_text())


class DataPages(unittest.TestCase):
    def test_each_finder_page_gets_its_canonical_address_once_and_joins_the_sitemap(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            for path in ("date", "date/lista", "date/sicap-ai"):
                (site / path).mkdir(parents=True)
                (site / path / "index.html").write_text("<html><head><title>x</title></head><body></body></html>")
            urls = build.data_pages(site)
            self.assertEqual(urls, [S + "date/", S + "date/lista/", S + "date/sicap-ai/"])
            doc = (site / "date/lista/index.html").read_text()
            self.assertIn(f'<link rel="canonical" href="{S}date/lista/">', doc)
            build.data_pages(site)
            self.assertEqual((site / "date/lista/index.html").read_text().count('rel="canonical"'), 1)
            self.assertIn(f"<loc>{S}date/sicap-ai/</loc>", build.sitemap([], site))

    def test_a_build_without_the_finder_lists_no_finder_page(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(build.data_pages(Path(d)), [])


if __name__ == "__main__":
    unittest.main()
