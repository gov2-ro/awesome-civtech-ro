"""Static entry pages and their JSON-LD (scripts/entry_page.py, build.entry_pages). Offline; one build of the public root."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import entry_page  # noqa: E402

ROOT = HERE.parent
TYPE = {"proiect": "WebApplication", "resursa": "CreativeWork", "publicatie": "Report"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.toc, self.current, self.h1, self.in_h1, self.desc, self.in_desc, self.ld, self.in_ld = [], [], "", False, "", False, [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and "toc-it" in (a.get("class") or "").split():
            self.toc.append(a["href"])
            if "aria-current" in a:
                self.current.append(a["href"])
        self.in_h1 |= tag == "h1"
        self.in_desc |= tag == "p" and "p-desc" in (a.get("class") or "")
        self.in_ld |= tag == "script" and a.get("type") == "application/ld+json"

    def handle_endtag(self, tag):
        self.in_h1 &= tag != "h1"
        self.in_desc &= tag != "p"
        self.in_ld &= tag != "script"

    def handle_data(self, data):
        if self.in_h1:
            self.h1 += data
        if self.in_desc:
            self.desc += data
        if self.in_ld:
            self.ld.append(data)


class EntryPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.site = Path(cls.tmp.name) / "site"
        subprocess.run([sys.executable, str(HERE / "build.py"), "--site-dir", str(cls.site)], check=True, capture_output=True, cwd=ROOT)
        cls.data = json.loads((cls.site / "data.json").read_text(encoding="utf-8"))
        cls.items = cls.data["items"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, i):
        text = (self.site / i["kind"] / i["slug"] / "index.html").read_text(encoding="utf-8")
        p = Links()
        p.feed(text)
        return text, p

    def test_one_entry_per_section(self):
        for kind in ("proiect", "organizatie", "resursa", "publicatie"):
            i = next(x for x in self.items if x["kind"] == kind and x["desc"] and x["primarySubject"])
            with self.subTest(kind=kind):
                text, p = self.page(i)
                self.assertEqual(p.h1.strip(), i["name"])
                self.assertIn(i["desc"][:40], p.desc)
                section = [x for x in self.items if x["kind"] == kind]
                self.assertEqual(sorted(p.toc), sorted(f"{kind}/{x['slug']}/" for x in section))
                self.assertEqual(p.current, [f"{kind}/{i['slug']}/"])
                self.assertIn('class="p-crumbs"', text)
                self.assertNotIn("<noscript><article", text)
                self.assertIn('data-slot="list" hidden', text)
                graph = json.loads("".join(p.ld))["@graph"]
                types = [g["@type"] for g in graph]
                entry = graph[-1]
                self.assertIn(entry["@type"], (TYPE.get(kind), "NGO", "Organization"))
                if kind != "organizatie":
                    self.assertEqual(entry["@type"], TYPE[kind])
                crumbs = next(g for g in graph if g["@type"] == "BreadcrumbList")["itemListElement"]
                self.assertEqual([c["position"] for c in crumbs], [1, 2, 3])
                self.assertEqual(crumbs[0]["name"], "CivTech România")
                self.assertEqual(types[:3], ["WebSite", "WebPage", "BreadcrumbList"])
                self.assertEqual(entry["name"], i["name"])

    def test_organisation_type_by_ngo(self):
        ngo = next(x for x in self.items if x["kind"] == "organizatie" and "organizatie:ong" in x["organisationTypes"])
        other = next(x for x in self.items if x["kind"] == "organizatie" and "organizatie:ong" not in x["organisationTypes"])
        self.assertEqual(json.loads("".join(self.page(ngo)[1].ld))["@graph"][-1]["@type"], "NGO")
        self.assertEqual(json.loads("".join(self.page(other)[1].ld))["@graph"][-1]["@type"], "Organization")

    def test_no_invented_fields(self):
        for i in self.items:
            entry = json.loads("".join(self.page(i)[1].ld))["@graph"][-1]
            self.assertFalse({"aggregateRating", "offers", "datePublished", "dateCreated"} & set(entry), i["slug"])
            self.assertTrue(all(v not in ("", [], None) for v in entry.values()), i["slug"])

    def test_every_entry_builds_with_valid_json_ld(self):
        for i in self.items:
            text, p = self.page(i)
            json.loads("".join(p.ld))
            self.assertEqual(p.current, [f"{i['kind']}/{i['slug']}/"], i["slug"])

    def test_home_has_a_website_with_a_publisher(self):
        text = (self.site / "index.html").read_text(encoding="utf-8")
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S).group(1))
        self.assertEqual(ld["@type"], "WebSite")
        self.assertEqual(ld["publisher"]["name"], "gov2.ro")

    def test_entry_with_no_description_and_no_image_builds(self):
        head = {"vocabulary": self.data["vocabulary"], "site": self.data["site"]}
        bare = {**next(x for x in self.items if x["kind"] == "resursa"), "slug": "gol", "name": "Gol", "desc": "", "tagline": "", "img": None, "icon": "",
                "url": "", "domain": "", "links": [], "code": "", "primarySubject": "", "subjects": [], "topics": [], "areas": [], "dataSources": [],
                "attributions": [], "since": "", "updated": "", "wayback": "", "contact": "", "maturity": "", "purposes": [], "capabilities": [], "formats": [],
                "technologies": [], "institutions": [], "organisationTypes": [], "dataRelation": "", "dataDetail": ""}
        bare.pop("repo", None)
        ctx = entry_page.Context([*self.items, bare], head, (ROOT / "site" / "app.js").read_text(encoding="utf-8"))
        view = entry_page.entry_view(bare, ctx)
        self.assertIn("<h1", view["sheet"])
        self.assertNotIn("p-desc", view["sheet"])
        entry = json.loads(re.search(r">(.*)</script>", entry_page.json_ld(bare, ctx)).group(1))["@graph"][-1]
        self.assertEqual(set(entry), {"@type", "@id", "name"})

    def test_network_logos_come_from_app_js(self):
        paths = entry_page.network_paths((ROOT / "site" / "app.js").read_text(encoding="utf-8"))
        self.assertTrue({"github", "gitlab", "facebook"} <= set(paths))


if __name__ == "__main__":
    unittest.main()
