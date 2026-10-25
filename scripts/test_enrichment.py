"""Named checks for the enrichment stages on explicit data roots: profile merge, search plan from relations, review on a
v2 root, label invalidation and coverage, and the dated last activity. Stdlib only; no network, no API key.

    python3 scripts/test_enrichment.py          # or: python3 -m unittest scripts/test_enrichment.py -v

Every mutation runs on a temporary copy. The repository's data and site/ are only read; tearDownModule proves it.
profile.py clashes with the stdlib module `profile`, so the three scripts load by path (importlib).
"""
import asyncio
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import common  # noqa: E402

ROOT = HERE.parent
DATA = ROOT / "data"
PACKAGE = DATA / "taxonomy-v2"
OVERLAY = PACKAGE / "integrare"
THIRD_PARTY = ("httpx", "selectolax", "PIL", "anthropic", "playwright")

# Runs a script with the third-party libraries blocked, as plain `python3` has them: the dry runs and the imports must work.
BLOCKED_RUN = """
import importlib.abc, json, runpy, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split('.')[0] in %r:
            raise ImportError('blocked ' + name)
script, name, args = json.loads(sys.argv[1])
sys.meta_path.insert(0, Block())
sys.path.insert(0, %r)
sys.argv = [script, *args]
runpy.run_path(script, run_name=name)
""" % (THIRD_PARTY, str(HERE))


def run_blocked(script: str, *args, name: str = "__main__") -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    return subprocess.run([sys.executable, "-I", "-c", BLOCKED_RUN, json.dumps([str(HERE / script), name, [str(a) for a in args]])],
                          cwd=ROOT, capture_output=True, text=True, env=env)


def load_script(name: str):
    """scripts/<name>.py as a module under another name (profile.py would clash with the stdlib `profile`)."""
    spec = importlib.util.spec_from_file_location(f"civtech_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected() -> dict[Path, str]:
    """Files that no test may change: the v1 data, the v2 package (source/, reference/, runs/ included) and site/."""
    files = [p for p in DATA.glob("*") if p.is_file()] + [p for p in PACKAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [p for p in (ROOT / "site").rglob("*") if p.is_file()]
    return {p: digest(p) for p in files}


_before: dict[Path, str] = {}


def setUpModule():
    _before.update(protected())


def tearDownModule():
    after = protected()
    changed = sorted(str(p.relative_to(ROOT)) for p in after.keys() | _before.keys() if after.get(p) != _before.get(p))
    assert not changed, f"the tests changed protected files: {changed[:5]}"


class Copy:
    """A temporary copy of the v2 package (without the 16 MB classification run), and of the v1 data on request."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.root = self.dir / "taxonomy-v2"
        shutil.copytree(PACKAGE, self.root, ignore=shutil.ignore_patterns("runs", "__pycache__", "catalogue.json"))
        self.overlay = self.root / "integrare"

    def v1(self) -> Path:
        out = self.dir / "data"
        out.mkdir()
        for name in ("proiecte.csv", "orgs.csv", "profil.csv", "mentiuni.csv", "taxonomy.json", "site.json"):
            shutil.copy2(DATA / name, out / name)
        return out

    def close(self):
        self.tmp.cleanup()


def rows_of(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# --- Item 2: profile preservation -------------------------------------------------------------------------------------------


class ProfileMerge(unittest.TestCase):
    OLD = {"url": "https://a.ro/", "status": "activ", "mentions": "7", "mention_hosts": "x.ro y.ro", "search_social": {"x": "https://x.com/a"},
           "opr": "3.5", "cert_first": "2019-04-01", "wiki_refs": "4", "archive_months": "40", "first_seen": "2015-01-02",
           "last_capture": "2026-09-01", "updated": "2026-08-01", "updated_src": "feed", "repo": "o/r", "repo_created": "2018-01-01",
           "stars": "9", "forks": "2", "commits": "100", "license": "MIT", "icon": "img/icon/a.webp", "sitemap_urls": "30"}

    def test_columns_of_other_stages_survive(self):
        fresh = {"url": "https://a.ro/", "status": "activ", "title": "A", "fetched_at": "2026-10-19T10:00:00+00:00"}
        out = common.merge_profile(self.OLD, fresh)
        for col in ("mentions", "mention_hosts", "search_social", "opr"):
            self.assertEqual(out[col], self.OLD[col], col)
        self.assertEqual(out["title"], "A")

    def test_extra_signals_survive_when_the_fetch_found_nothing(self):
        # A 502 from crt.sh gives "", a failed Wikipedia call gives no key, GitHub gave nothing, every date source failed.
        fresh = {"url": "https://a.ro/", "status": "activ", "cert_first": "", "updated": "", "updated_src": ""}
        out = common.merge_profile(self.OLD, fresh)
        for col in ("cert_first", "wiki_refs", "archive_months", "first_seen", "last_capture", "updated", "updated_src", "repo",
                    "stars", "forks", "commits", "license", "icon", "sitemap_urls"):
            self.assertEqual(out[col], self.OLD[col], col)

    def test_fresh_values_win_and_zero_is_a_value(self):
        fresh = {"url": "https://a.ro/", "cert_first": "2020-01-01", "wiki_refs": 0, "archive_months": 0, "first_seen": "", "last_capture": "",
                 "updated": "2026-10-01", "updated_src": "sitemap", "sitemap_urls": 0}
        out = common.merge_profile(self.OLD, fresh)
        self.assertEqual((out["cert_first"], out["wiki_refs"], out["archive_months"], out["first_seen"], out["sitemap_urls"]),
                         ("2020-01-01", 0, 0, "", 0))
        self.assertEqual((out["updated"], out["updated_src"]), ("2026-10-01", "sitemap"))  # a new date takes its source with it

    def test_same_repository_fills_the_stats_that_failed(self):
        fresh = {"url": "https://a.ro/", "repo": "o/r", "repo_archived": False, "stars": 11, "forks": 3}  # github_stats failed
        out = common.merge_profile(self.OLD, fresh)
        self.assertEqual((out["stars"], out["forks"], out["commits"], out["license"], out["repo_archived"]), (11, 3, "100", "MIT", False))

    def test_another_repository_replaces_the_whole_group(self):
        fresh = {"url": "https://a.ro/", "repo": "o/other", "stars": 1}
        out = common.merge_profile(self.OLD, fresh)
        self.assertEqual((out["repo"], out["stars"]), ("o/other", 1))
        for col in ("forks", "commits", "license", "repo_created"):
            self.assertNotIn(col, out)

    def test_a_new_address_keeps_only_the_search_columns(self):
        out = common.merge_profile(self.OLD, {"url": "https://b.ro/", "status": "activ"})
        self.assertEqual((out["mentions"], out["mention_hosts"]), ("7", "x.ro y.ro"))
        for col in ("opr", "cert_first", "wiki_refs", "repo", "first_seen", "icon"):
            self.assertNotIn(col, out)

    def test_inputs_stay_as_they_are(self):
        old, fresh = json.loads(json.dumps(self.OLD)), {"url": "https://a.ro/", "cert_first": ""}
        before = json.loads(json.dumps(fresh))
        common.merge_profile(old, fresh)
        self.assertEqual((old, fresh), (self.OLD, before))
        self.assertEqual(common.merge_profile(None, fresh), fresh)

    def test_a_forced_refresh_keeps_the_columns_through_the_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profil.csv"
            common.save_profile({"a": dict(self.OLD)}, path)
            stored = common.load_profile(path)["a"]
            fresh = {"url": "https://a.ro/", "status": "activ", "http_status": 200, "social": {}, "repos": [], "cert_first": ""}
            common.save_profile({"a": common.merge_profile(stored, fresh)}, path)
            row = rows_of(path)[0]
        for col in ("mentions", "mention_hosts", "opr", "cert_first", "wiki_refs", "repo", "stars"):
            self.assertEqual(row[col], str(self.OLD[col]), col)
        self.assertEqual(json.loads(row["search_social"]), self.OLD["search_social"])

    def test_wikipedia_failure_is_unknown_not_zero(self):
        profile = load_script("profile")

        class Client:
            def __init__(self, behaviour):
                self.behaviour = behaviour

            async def get(self, url, **kw):
                return self.behaviour(url)

        ok = lambda url: types.SimpleNamespace(json=lambda: {"query": {"exturlusage": [{"title": "A"}, {"title": "B"}]}})
        broken = lambda url: types.SimpleNamespace(json=lambda: {"error": {"code": "ratelimited"}})

        def boom(url):
            raise RuntimeError("network")

        run = lambda behaviour: asyncio.run(profile.wiki_refs(Client(behaviour), "a.ro"))
        self.assertEqual(run(ok), 4)  # two languages, two articles each
        self.assertIsNone(run(broken))
        self.assertIsNone(run(boom))
        self.assertIsNone(run(lambda url: ok(url) if "//ro." in url else boom(url)))  # half a count is no count

    def test_profile_main_reads_and_writes_the_root_it_is_given(self):
        profile = load_script("profile")

        class Httpx:  # enough of httpx for an --extra run that has no entry to fetch
            class Timeout:
                def __init__(self, *a, **k):
                    pass

            class AsyncClient:
                def __init__(self, **k):
                    pass

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *a):
                    return False

        c = Copy()
        self.addCleanup(c.close)
        path = c.root / "observatii" / "profil.csv"
        rows = rows_of(path)
        with open(path, "w", encoding="utf-8", newline="") as f:  # reversed: save_profile sorts by slug, so a rewrite shows
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(reversed(rows))
        written = path.read_bytes()
        with mock.patch.multiple(profile, httpx=Httpx, Image=object(), ImageOps=object(), HTMLParser=object()), \
                mock.patch.object(sys, "argv", ["profile.py", "--data-dir", str(c.overlay), "--extra", "--only", "none-such"]):
            asyncio.run(profile.main())
        self.assertNotEqual(path.read_bytes(), written)
        self.assertEqual([r["slug"] for r in rows_of(path)], sorted(r["slug"] for r in rows))
        self.assertEqual({r["slug"]: r["mentions"] for r in rows_of(path)}, {r["slug"]: r["mentions"] for r in rows})


# --- Item 1: the scripts import without their libraries, and a root selects the files ------------------------------------------


class ScriptsImportAndRoots(unittest.TestCase):
    def test_scripts_import_without_third_party_libraries(self):
        for script in ("profile.py", "search.py", "review.py"):
            result = run_blocked(script, name="civtech_import")
            self.assertEqual(result.returncode, 0, f"{script}: {result.stderr[-400:]}")

    def test_observation_paths_for_each_root(self):
        self.assertEqual(common.observation_paths(DATA)["review"], DATA / "review")
        self.assertEqual(common.observation_paths()["review"], common.observation_paths(common.PUBLIC_ROOT)["review"])  # the default root
        self.assertEqual(common.observation_paths(OVERLAY)["review"], PACKAGE / "observatii" / "review")
        self.assertEqual(common.observation_paths(PACKAGE)["profile"], PACKAGE / "observatii" / "profil.csv")

    def test_search_prune_only_touches_only_the_given_root(self):
        c = Copy()
        self.addCleanup(c.close)
        obs = c.root / "observatii"
        rows = rows_of(obs / "mentiuni.csv")
        rows[0]["regula"] = "zzz"  # a rule that does not exist: prune-only must recompute it
        with open(obs / "mentiuni.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        profile_rows = rows_of(obs / "profil.csv")
        profile_rows[0]["mentions"] = "999"
        with open(obs / "profil.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(profile_rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(profile_rows)
        result = run_blocked("search.py", "--data-dir", c.overlay, "--prune-only")
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertNotEqual(rows_of(obs / "mentiuni.csv")[0]["regula"], "zzz")
        self.assertNotEqual(next(r for r in rows_of(obs / "profil.csv") if r["slug"] == profile_rows[0]["slug"])["mentions"], "999")
        self.assertFalse((c.root / "integrare" / "observatii").exists())  # the overlay owns no observation files


# --- Item 3: search from relations ----------------------------------------------------------------------------------------------


class SearchFromRelations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search = load_script("search")
        cls.v2 = {e["slug"]: e for e in common.load_catalogue(OVERLAY)}
        cls.v1 = {e["slug"]: e for e in common.load_catalogue(DATA)}
        cls.both = {"serper", "brave"}

    def queries(self, entry):
        return [q for _, q, _ in self.search.plan(entry, self.both)]

    def test_a_target_entry_gives_its_name_not_its_slug(self):
        self.assertIn('"7 ani de acasă" Funky Citizens', [q.replace("brave: ", "") for q in self.queries(self.v2["7-ani-de-acasa"])])
        self.assertIn('"7 ani de acasă" funky-citizens', self.queries(self.v1["7-ani-de-acasa"]))  # the v1 cell holds the slug

    def test_the_first_relation_is_the_first_author(self):
        self.assertTrue(any(q.endswith("Alex Ifrimenco") for q in self.queries(self.v2["bucuresti-verde"])))
        self.assertTrue(any(q.endswith("Alex Ifrimenco") for q in self.queries(self.v1["bucuresti-verde"])))

    def test_the_original_text_is_the_fallback(self):
        entry = {**self.v2["bucuresti-verde"], "attributions": [], "autor": "Ana Pop (voluntar) / Dan Ion"}
        self.assertTrue(any(q.endswith("Ana Pop") for q in self.queries(entry)))

    def test_a_funder_is_not_an_author(self):
        entry = {**self.v2["465"], "attributions": [{"predicate": "finantat_de", "state": "propus", "slug": "", "literal": "Fundatia X", "name": "Fundatia X"}],
                 "autor": ""}
        self.assertFalse(any("Fundatia X" in q for q in self.queries(entry)))

    def test_v1_plans_do_not_change(self):
        # Pinned from the v1 entry that has two authors and one that has a bracketed note.
        entry = {"slug": "x", "kind": "proiect", "nume": "Nume X", "url": "https://x.ro/", "autor": "A B (nota) / C D", "linkuri": ""}
        self.assertEqual(self.search.plan(entry, self.both), [("serper", "x.ro -site:x.ro", 2), ("serper", "Nume X A B", 1), ("brave", '"Nume X" A B', 1)])

    def entry(self, **kw):
        return {"slug": "x", "nume": "X", "url": "https://x.ro/", "linkuri": "", "autor": "", "attributions": [], **kw}

    def rel(self, slug="", literal="", predicate="atribuit_in_sursa"):
        return {"predicate": predicate, "state": "rol_neconfirmat", "slug": slug, "literal": literal, "name": literal or slug}

    def test_only_an_organisation_entry_gives_an_authors_site(self):
        orgs = {"funky-citizens": "https://funky.ong/"}  # main() builds this from the entries of type organizatie only
        own = self.search.own_sites(self.entry(attributions=[self.rel("funky-citizens")]), {}, orgs)
        self.assertIn("funky.ong", own)
        # A project as target: main() leaves it out of `orgs`, so its URL never counts.
        self.assertNotIn("funky.ong", self.search.own_sites(self.entry(attributions=[self.rel("a-project")]), {}, orgs))

    def test_a_literal_never_matches_an_organisation_by_name(self):
        orgs = {"acme": "https://acme.org/", "acme-ong": "https://acme.org/"}  # a slug, and the flat name that v1 would look up
        own = self.search.own_sites(self.entry(attributions=[self.rel(literal="Acme")]), {}, orgs)
        self.assertEqual(own, {"x.ro"})
        # The fixed list of known authors is a deliberate name match.
        self.assertIn("code4.ro", self.search.own_sites(self.entry(attributions=[self.rel(literal="Code for Romania")]), {}, orgs))
        # The original text, without relations, does not look organisations up either (a v2 `orgs` is keyed by slug).
        self.assertEqual(self.search.own_sites(self.entry(autor="Acme"), {}, orgs), {"x.ro"})

    def test_organisation_urls_come_from_organisation_entries_only(self):
        v2 = self.search.organisation_urls({e["slug"]: e for e in self.v2.values()}, True)
        self.assertIn("funky-citizens", v2)
        self.assertFalse({"465", "factual", "7-ani-de-acasa"} & set(v2))
        self.assertTrue(all(self.v2[s]["entity_type"] == "organizatie" for s in v2))
        v1 = self.search.organisation_urls({e["slug"]: e for e in self.v1.values()}, False)
        self.assertEqual(v1["funkycitizens"], self.v1["funky-citizens"]["url"])

    def test_dry_run_on_a_v2_root_queries_with_the_relation_names(self):
        c = Copy()
        self.addCleanup(c.close)
        result = run_blocked("search.py", "--data-dir", c.overlay, "--dry-run", "--force", "--only", "7-ani-de-acasa,bucuresti-verde")
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertIn("Funky Citizens", result.stderr)
        self.assertIn("Alex Ifrimenco", result.stderr)
        self.assertNotIn("funky-citizens", result.stderr.replace("7-ani-de-acasa", ""))  # the slug of the author is not a query


# --- Item 4: review on a v2 root ------------------------------------------------------------------------------------------------


def blank_answer(**kw) -> dict:
    return {"stare": "activ", "stare_motiv": "", "descriere_scurta": "", "descriere": "", "subiect_principal": "", "subiecte": [], "teme": [],
            "scopuri": [], "functionalitati": [], "formate": [], "tehnologii": [], "institutii_vizate": [], "atribuiri": [], "linkuri": [],
            "propuneri_vocabular": [], "probleme": [], "incredere": "medie", "mentiuni": [], "atentie": "", **kw}


class ReviewV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = load_script("review")
        cls.entries = common.load_catalogue(OVERLAY)
        cls.by = {e["slug"]: e for e in cls.entries}
        cls.vocab = cls.review.Vocab2(common.load_vocabulary(OVERLAY)["package"], cls.entries)
        cls.page = {"url_final": "https://example.ro/", "text": "Platforma folosește inteligență artificială pentru a rezuma legile. Echipa Funky Citizens.",
                    "linkuri_externe": [], "pagini_interne": []}
        cls.pool = cls.review.evidence_pool(cls.page, [])

    def src(self, quote, url="https://example.ro/"):
        return {"url": url, "citat": quote}

    def test_the_request_lists_every_facet_with_qualified_ids_and_definitions(self):
        block = json.loads(self.vocab.block())
        prefix = {"subiecte": "subiect:", "teme": "subiect:", "scopuri": "scop:", "functionalitati": "functie:", "formate": "format:",
                  "tehnologii": "tehnologie:", "institutii_vizate": "institutie:"}
        for facet, prefixed in prefix.items():
            items = block["vocabular"][facet]
            self.assertTrue(items, facet)
            self.assertTrue(all(i["id"].startswith(prefixed) and i["definitie"] for i in items), facet)
        self.assertTrue(all("mai_larg" not in i for i in block["vocabular"]["subiecte"]))  # the roots have no parent
        self.assertTrue(all("mai_larg" in i for i in block["vocabular"]["teme"]))
        self.assertEqual({r["id"] for r in block["roluri_atribuire"]}, set(self.review.TYPED_ROLES))
        self.assertIn("funky-citizens", {o["slug"] for o in block["organizatii_catalogate"]})

    def test_the_answer_schema_has_one_array_per_facet(self):
        schema = self.vocab.schema()
        self.assertEqual(set(schema["required"]), set(blank_answer()))
        for facet in self.review.FACETS:
            self.assertEqual(schema["properties"][facet]["type"], "array", facet)
        enum = schema["properties"]["scopuri"]["items"]["enum"]
        self.assertTrue(enum and all(i.startswith("scop:") for i in enum))
        self.assertTrue(all(i.startswith("subiect:") for i in schema["properties"]["subiecte"]["items"]["enum"]))
        self.assertTrue(all(i.startswith("tehnologie:") for i in schema["properties"]["tehnologii"]["items"]["properties"]["id"]["enum"]))
        self.assertEqual(schema["properties"]["atribuiri"]["items"]["properties"]["rol"]["enum"], list(self.review.TYPED_ROLES))

    def test_a_technology_needs_a_quote_from_the_supplied_text(self):
        good = {"id": "tehnologie:ai", "sursa": self.src("folosește inteligență artificială pentru a rezuma")}
        invented = {"id": "tehnologie:mcp", "sursa": self.src("oferă un server MCP pentru agenți")}
        wrong_url = {"id": "tehnologie:ai", "sursa": self.src("folosește inteligență artificială pentru a rezuma", "https://elsewhere.ro/")}
        short = {"id": "tehnologie:ai", "sursa": self.src("AI")}
        out, dropped = self.vocab.check(blank_answer(tehnologii=[good, invented, wrong_url, short]), self.pool)
        self.assertEqual([t["id"] for t in out["tehnologii"]], ["tehnologie:ai"])
        self.assertEqual(len(dropped), 1)  # the repeat of an id is skipped; only the invented claim is dropped
        out, dropped = self.vocab.check(blank_answer(tehnologii=[good]), {})  # the page could not be fetched
        self.assertEqual((out["tehnologii"], len(dropped)), ([], 1))

    def test_a_typed_role_needs_a_source_and_a_known_organisation(self):
        quote = self.src("Echipa Funky Citizens")
        ok = {"nume": "Funky Citizens", "rol": "creat_de", "obiect_slug": "funky-citizens", "sursa": quote}
        no_quote = {**ok, "rol": "mentinut_de", "sursa": self.src("Echipa Altcineva")}
        unknown = {**ok, "rol": "publicat_de", "obiect_slug": "not-an-entry"}
        literal = {"nume": "Ana Pop", "rol": "finantat_de", "obiect_slug": "", "sursa": quote}
        out, dropped = self.vocab.check(blank_answer(atribuiri=[ok, no_quote, unknown, literal]), self.pool)
        self.assertEqual([(a["rol"], a["obiect_slug"] or a["nume"]) for a in out["atribuiri"]],
                         [("creat_de", "funky-citizens"), ("finantat_de", "Ana Pop")])
        self.assertEqual(len(dropped), 2)

    def test_an_id_outside_its_facet_never_enters_the_answer(self):
        out, dropped = self.vocab.check(blank_answer(scopuri=["scop:transparenta", "functie:cautare", "scop:inventat"], formate=["format:ghid"],
                                                     subiecte=["subiect:alegeri"]), self.pool)
        self.assertEqual((out["scopuri"], out["formate"]), (["scop:transparenta"], ["format:ghid"]))
        self.assertEqual(out["subiecte"], [])  # a topic is no top-level subject
        self.assertEqual({d["valoare"] for d in dropped}, {"functie:cautare", "scop:inventat", "subiect:alegeri"})

    def test_roots_of_the_chosen_topics_and_the_main_subject_join_the_subjects(self):
        out, _ = self.vocab.check(blank_answer(subiect_principal="subiect:media-informare", subiecte=[], teme=["subiect:alegeri"]), self.pool)
        self.assertEqual(out["subiect_principal"], "subiect:media-informare")
        self.assertEqual(out["subiecte"], ["subiect:media-informare", "subiect:guvernare-democratie"])

    def test_an_unknown_term_goes_to_the_proposals_and_a_known_one_does_not(self):
        new = {"schema": "scop", "eticheta_ro": "Verificare independentă a datelor", "definitie_ro": "d", "motiv": "m", "sursa": self.src("x" * 12)}
        known = {**new, "eticheta_ro": "transparență"}  # exists as scop:transparenta, any case
        out, dropped = self.vocab.check(blank_answer(propuneri_vocabular=[new, known]), self.pool)
        self.assertEqual([p["eticheta_ro"] for p in out["propuneri_vocabular"]], ["Verificare independentă a datelor"])
        self.assertIn("exists as scop:transparenta", dropped[0]["motiv"])
        rows = self.review.proposal_rows("465", out)
        self.assertEqual((rows[0]["slug"], rows[0]["schema"]), ("465", "scop"))
        self.assertEqual(out["scopuri"], [])  # never an id

    def test_suggestion_rows_carry_the_source_and_leave_the_catalogue_alone(self):
        e = self.by["465"]
        answer = blank_answer(subiect_principal=e["primary_subject"], scopuri=["scop:transparenta", "scop:responsabilizare"],
                              tehnologii=[{"id": "tehnologie:ai", "sursa": self.src("folosește inteligență artificială pentru a rezuma")}],
                              atribuiri=[{"nume": "Funky Citizens", "rol": "creat_de", "obiect_slug": "funky-citizens", "sursa": self.src("Echipa Funky Citizens")}])
        before = json.dumps(e, sort_keys=True)
        rows = self.review.diff_rows_v2(e, answer)
        by = {r["camp"]: r for r in rows}
        self.assertEqual(by["scopuri"]["propus"], "scop:transparenta|scop:responsabilizare")
        self.assertIn("scop:responsabilizare", by["scopuri"]["motiv"])
        self.assertIn("«folosește inteligență artificială", by["tehnologii"]["sursa"])
        self.assertTrue(by["relatii"]["propus"].startswith("creat_de: funky-citizens"))
        self.assertNotIn("subiect_principal", by)  # unchanged
        self.assertEqual(before, json.dumps(e, sort_keys=True))
        self.assertEqual(self.review.diff_rows_v2(e, blank_answer()), [])  # an empty answer proposes nothing

    def test_dry_run_on_a_v2_root_needs_no_key_no_library_and_writes_nothing(self):
        c = Copy()
        self.addCleanup(c.close)
        tables = {p: digest(p) for group in (c.root.glob("*.csv"), c.overlay.glob("*.csv")) for p in group}
        result = run_blocked("review.py", "--data-dir", c.overlay, "--dry-run", "--only", "465")
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        out = result.stdout
        for needle in ("scop:transparenta", "functie:cautare", "tehnologie:ai", "subiect:guvernare-democratie", "format:ghid",
                       "institutie:parlament", "propuneri_vocabular", "----- user: 465", "dry run: the homepage is not downloaded"):
            self.assertIn(needle, out)
        self.assertIn("Instituții publice, reprezentare politică", out)  # a definition, not only an id
        self.assertEqual({p: digest(p) for p in tables}, tables)  # no table of the package changed, intrari.csv included
        self.assertFalse((c.root / "observatii" / "review").exists())
        self.assertIn("labels 0/", result.stderr)  # the coverage line

    def test_v1_dry_run_is_still_the_v1_request(self):
        c = Copy()
        self.addCleanup(c.close)
        result = run_blocked("review.py", "--data-dir", c.v1(), "--dry-run", "--only", "factual")
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertIn('"domeniu"', result.stdout)
        self.assertNotIn("subiect:", result.stdout)

    def test_the_v2_record_stores_hashes_and_the_dropped_claims(self):
        e = self.by["465"]

        class Messages:
            def create(self, **kw):
                self.kw = kw
                answer = blank_answer(tehnologii=[{"id": "tehnologie:ai", "sursa": {"url": "https://x.ro/", "citat": "nu apare în text"}}],
                                      scopuri=["scop:transparenta"], incredere="mare")
                usage = types.SimpleNamespace(input_tokens=100, output_tokens=20, cache_creation_input_tokens=0, cache_read_input_tokens=0)
                return types.SimpleNamespace(usage=usage, stop_reason="end_turn", content=[types.SimpleNamespace(type="text", text=json.dumps(answer))])

        client = types.SimpleNamespace(messages=Messages())
        hashes = self.review.input_hashes(self.review.SYSTEM_V2, self.vocab.schema(), self.vocab.data(), self.review.entry_row_v2(e), [])
        record = self.review.review(client, [], e, "user", [], self.vocab.schema(), hashes, lambda a: self.vocab.check(a, self.pool))
        self.assertEqual(record["inputs"], hashes)
        self.assertEqual(record["review"]["tehnologii"], [])
        self.assertEqual([d["valoare"] for d in record["respinse"]], ["tehnologie:ai"])
        self.assertEqual(client.messages.kw["output_config"]["format"]["schema"], self.vocab.schema())

    def test_a_review_run_writes_only_the_review_files_and_asks_again_after_a_change(self):
        quote = "Platforma folosește inteligență artificială pentru a rezuma legile"
        page = {"http_status": 200, "url_final": "https://465.ro/", "text": f"{quote}. Echipa Funky Citizens.", "linkuri_externe": [], "pagini_interne": []}
        asked = []
        c = Copy()
        self.addCleanup(c.close)
        obs = c.root / "observatii"
        kept_rows = common.kept_by_slug(common.load_mentions(obs / "mentiuni.csv"))
        slug = next(s for s, rows in kept_rows.items() if len(rows) >= 2)

        class Messages:
            def create(self, **kw):
                user = json.loads(kw["messages"][0]["content"])
                asked.append(user["rand_actual"]["slug"])
                answer = blank_answer(scopuri=["scop:transparenta"], subiect_principal="subiect:guvernare-democratie", incredere="mare",
                                      tehnologii=[{"id": "tehnologie:ai", "sursa": {"url": "https://465.ro/", "citat": quote}},
                                                  {"id": "tehnologie:mcp", "sursa": {"url": "https://465.ro/", "citat": "un server MCP care nu apare în text"}}],
                                      propuneri_vocabular=[{"schema": "scop", "eticheta_ro": "Verificare independentă a datelor", "definitie_ro": "d",
                                                            "motiv": "m", "sursa": {"url": "", "citat": ""}}],
                                      mentiuni=[{"id": m["id"], "despre_proiect": True, "tip_sursa": "stire", "independent": True}
                                                for m in user.get("mentiuni", [])])
                usage = types.SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0)
                return types.SimpleNamespace(usage=usage, stop_reason="end_turn", content=[types.SimpleNamespace(type="text", text=json.dumps(answer))])

        fake = types.SimpleNamespace(Anthropic=lambda: types.SimpleNamespace(messages=Messages()))
        tables = {p: digest(p) for group in (c.root.glob("*.csv"), c.overlay.glob("*.csv")) for p in group}

        def run(*args):
            with mock.patch.multiple(self.review, anthropic=fake, httpx=object(), HTMLParser=object(), homepage=lambda url: page), \
                    mock.patch.object(sys, "argv", ["review.py", "--data-dir", str(c.overlay), "--workers", "1", *args]), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.review.main()

        run("--only", slug)
        self.assertEqual(asked, [slug])
        record = json.loads((obs / "review" / "raw.jsonl").read_text().splitlines()[0])
        self.assertEqual(set(record["inputs"]), {"entry", "urls", "vocabulary", "prompt", "model"})
        self.assertEqual([t["id"] for t in record["review"]["tehnologii"]], ["tehnologie:ai"])
        self.assertEqual([d["valoare"] for d in record["respinse"]], ["tehnologie:mcp"])
        suggestions = rows_of(obs / "review" / "sugestii.csv")
        self.assertEqual(list(suggestions[0]), ["slug", "camp", "actual", "propus", "motiv", "sursa", "incredere"])
        self.assertIn("tehnologii", {r["camp"] for r in suggestions})
        self.assertEqual([r["eticheta_ro"] for r in rows_of(obs / "review" / "propuneri-vocabular.csv")], ["Verificare independentă a datelor"])
        labels = rows_of(obs / "mentiuni_etichete.csv")
        self.assertEqual({r["slug"] for r in labels}, {slug})
        self.assertEqual({r["url"] for r in labels}, {r["url"] for r in kept_rows[slug]})
        self.assertEqual({p: digest(p) for p in tables}, tables)  # intrari.csv and every other table are untouched

        asked.clear()
        run()  # the reviewed entry is current: everything else is asked, it is not
        self.assertNotIn(slug, asked)
        self.assertEqual(len(asked), len(common.read_csv(c.overlay / "intrari.csv")) - 1)

        asked.clear()
        run()  # now every answer is current
        self.assertEqual(asked, [])

        rows = rows_of(obs / "mentiuni.csv")
        dropped = next(r for r in rows if r["slug"] == slug and common.is_kept(r))
        dropped["editor"] = "0"  # the editor drops one kept result: the set of URLs sent moves
        common.write_csv(obs / "mentiuni.csv", common.MENTIUNI_COLS, rows)
        run()
        self.assertEqual(asked, [slug])
        self.assertNotIn(dropped["url"], {r["url"] for r in rows_of(obs / "mentiuni_etichete.csv") if r["slug"] == slug})
        self.assertEqual({p: digest(p) for p in tables}, tables)


# --- Item 5: label invalidation and coverage ----------------------------------------------------------------------------------


def mention(slug, url, rank=1, host=None, editor="", regula="", date_=""):
    return {"slug": slug, "provider": "serper", "query": "q", "rank": str(rank), "url": url, "host": host or url.split("/")[2], "title": "t",
            "snippet": "s", "date": date_, "regula": regula, "editor": editor, "fetched_at": "2026-10-19"}


def label(slug, url, about="1", indep="1", kind="stire"):
    return {"slug": slug, "url": url, "despre_proiect": about, "tip_sursa": kind, "independent": indep, "model": "m", "labelled_at": "t"}


class LabelInvalidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = load_script("review")
        cls.entries = common.load_catalogue(OVERLAY)
        cls.vocab = cls.review.Vocab2(common.load_vocabulary(OVERLAY)["package"], cls.entries)
        cls.e = next(e for e in cls.entries if e["slug"] == "465")
        cls.results = [{"id": 1, "url": "https://a.ro/1", "titlu": "t", "fragment": "f", "data": ""}]

    def hashes(self, e=None, results=None, instructions=None, vocabulary=None, schema=None):
        return self.review.input_hashes(instructions or self.review.SYSTEM_V2, schema or self.vocab.schema(), vocabulary or self.vocab.data(),
                                        self.review.entry_row_v2(e or self.e), self.results if results is None else results)

    def test_an_answer_with_equal_hashes_is_current(self):
        h = self.hashes()
        self.assertEqual(self.review.due_reason({"review": {}, "inputs": h}, self.hashes()), "")

    def test_each_input_makes_the_entry_due_again(self):
        h = self.hashes()
        stored = {"review": {}, "inputs": h}
        due = lambda new: self.review.due_reason(stored, new)
        self.assertEqual(due(self.hashes(e={**self.e, "descriere": self.e["descriere"] + " nou"})), "changed: entry")
        self.assertEqual(due(self.hashes(results=[*self.results, {**self.results[0], "id": 2, "url": "https://b.ro/2"}])), "changed: urls")
        self.assertEqual(due(self.hashes(instructions=self.review.SYSTEM_V2 + " more")), "changed: prompt")
        self.assertEqual(due(self.hashes(vocabulary={**self.vocab.data(), "versiune_vocabular": "2.0.0-draft.3"})), "changed: vocabulary")
        with mock.patch.object(self.review, "MODEL", "another-model"):
            self.assertEqual(due(self.hashes()), "changed: model")

    def test_the_current_classification_is_part_of_the_entry_text(self):
        changed = {**self.e, "scopuri": [], "purposes": ["scop:informare"]}
        self.assertNotEqual(self.hashes()["entry"], self.hashes(e=changed)["entry"])

    def test_an_earlier_format_and_a_missing_answer_are_due(self):
        h = self.hashes()
        self.assertEqual(self.review.due_reason(None, h), "new")
        self.assertTrue(self.review.due_reason({"review": {}, "mentiuni_map": {}}, h).startswith("no input hashes"))

    def test_a_kept_url_beyond_the_cap_does_not_reach_the_hash(self):
        rows = [mention("s", f"https://h{i}.ro/p", rank=i) for i in range(1, 46)]
        sent = self.review.kept_results(rows)
        self.assertEqual(len(sent), self.review.MAX_MENTIONS)
        rows[44]["url"] = "https://changed.ro/p"  # rank 45: never sent
        self.assertEqual(self.hashes(results=sent), self.hashes(results=self.review.kept_results(rows)))
        rows[2]["editor"] = "0"  # the editor drops a sent URL: the set of sent URLs moves
        self.assertNotEqual(self.hashes(results=sent)["urls"], self.hashes(results=self.review.kept_results(rows))["urls"])

    def test_v1_hashes_ignore_the_keyword_counts_but_not_the_keywords(self):
        entries = common.load_catalogue(DATA)
        tax = json.loads((DATA / "taxonomy.json").read_text())
        fp = lambda es: (lambda d: {**d, "vocabular_cuvinte": sorted(d["vocabular_cuvinte"])})(self.review.taxonomy_data(es, tax))
        more = [dict(e, cuvinte=e["cuvinte"] + ", " + e["cuvinte"].split(",")[0]) if e["cuvinte"] and i == 0 else e for i, e in enumerate(entries)]
        self.assertEqual(self.review.digest(fp(entries)), self.review.digest(fp(more)))  # a repeated keyword only moves a count
        new_word = [dict(entries[0], cuvinte=entries[0]["cuvinte"] + ", cuvant-nou-in-vocabular"), *entries[1:]]
        self.assertNotEqual(self.review.digest(fp(entries)), self.review.digest(fp(new_word)))

    def test_labels_are_written_per_root_and_replace_a_redone_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mentiuni_etichete.csv"
            common.write_csv(path, common.ETICHETE_COLS, [label("a", "https://a.ro/old"), label("b", "https://b.ro/1")])
            fresh = {"slug": "a", "model": "m", "mentiuni_map": {"1": "https://a.ro/1"},
                     "review": {"mentiuni": [{"id": 1, "despre_proiect": True, "tip_sursa": "stire", "independent": False}]}}
            self.review.write_labels([fresh], path)
            rows = {(r["slug"], r["url"]): r for r in rows_of(path)}
        self.assertEqual(set(rows), {("a", "https://a.ro/1"), ("b", "https://b.ro/1")})
        self.assertEqual(rows[("a", "https://a.ro/1")]["independent"], "0")


class Coverage(unittest.TestCase):
    MENTIONS = [mention("full", "https://a.ro/1"), mention("full", "https://b.ro/1"),
                mention("part", "https://c.ro/1"), mention("part", "https://d.ro/1"), mention("part", "https://e.ro/1", editor="0"),
                mention("none", "https://f.ro/1"), mention("dropped", "https://g.ro/1", regula="social")]
    LABELS = [label("full", "https://a.ro/1"), label("full", "https://b.ro/1", indep="0"),
              label("part", "https://c.ro/1"), label("part", "https://e.ro/1"),  # e.ro is not kept: its label counts for nothing
              label("none", "https://stale.ro/1")]  # a URL that the search no longer returns

    def test_coverage_counts_labelled_kept_rows(self):
        cov = common.label_coverage(self.MENTIONS, self.LABELS)
        self.assertEqual((cov["kept"], cov["labelled"]), (5, 3))
        self.assertAlmostEqual(cov["ratio"], 0.6)
        self.assertEqual((cov["slugs"], cov["full"], cov["partial"], cov["none"]), (3, 1, 1, 1))
        self.assertIn("labels 3/5 kept rows (60%)", common.coverage_line(cov))

    def test_nothing_kept_is_full_coverage(self):
        self.assertEqual(common.label_coverage([], [])["ratio"], 1.0)

    def test_without_labels_the_kept_hosts_stand_in(self):
        reach = build.reach_features(self.MENTIONS, [])
        self.assertEqual(reach["full"], {"indep": 2, "stiri": 0, "cercetare": 0, "guvern": 0, "ultima": ""})  # the shape the v1 build has today
        self.assertNotIn("dropped", reach)

    def test_a_fully_labelled_entry_counts_labelled_hosts_only(self):
        reach = build.reach_features(self.MENTIONS, self.LABELS)["full"]
        self.assertEqual((reach["indep"], reach["stiri"]), (1, 1))
        self.assertNotIn("provisional", reach)

    def test_a_partly_labelled_entry_adds_the_unlabelled_hosts_and_is_provisional(self):
        reach = build.reach_features(self.MENTIONS, self.LABELS)["part"]
        self.assertEqual(reach["indep"], 2)  # c.ro labelled and independent, d.ro unlabelled and kept; e.ro is dropped
        self.assertEqual((reach["stiri"], reach["cercetare"]), (1, 0))
        self.assertIs(reach["provisional"], True)

    def test_stale_labels_alone_fall_back_to_the_kept_hosts(self):
        reach = build.reach_features(self.MENTIONS, self.LABELS)["none"]
        self.assertEqual((reach["indep"], reach["stiri"]), (1, 0))
        self.assertNotIn("provisional", reach)

    def test_a_label_for_a_dropped_url_does_not_count_after_the_editor_changes_the_row(self):
        mentions = [mention("m", "https://a.ro/1"), mention("m", "https://b.ro/1")]
        labels = [label("m", "https://a.ro/1"), label("m", "https://b.ro/1")]
        self.assertNotIn("provisional", build.reach_features(mentions, labels)["m"])
        mentions[1]["editor"] = "0"
        self.assertEqual(build.reach_features(mentions, labels)["m"]["indep"], 1)
        mentions.append(mention("m", "https://c.ro/1"))  # a new kept URL without a label
        reach = build.reach_features(mentions, labels)["m"]
        self.assertEqual((reach["indep"], reach["provisional"]), (2, True))

    def test_hosts_count_once(self):
        mentions = [mention("m", "https://a.ro/1", host="a.ro"), mention("m", "https://a.ro/2", host="a.ro"), mention("m", "https://a.ro/3", host="a.ro")]
        reach = build.reach_features(mentions, [label("m", "https://a.ro/1")])["m"]
        self.assertEqual(reach["indep"], 1)  # one host, labelled and unlabelled rows together

    def test_the_build_reports_coverage_and_marks_provisional_entries(self):
        c = Copy()
        self.addCleanup(c.close)
        root = c.v1()
        kept = common.kept_by_slug(common.load_mentions(root / "mentiuni.csv"))
        slug, rows = next((s, r) for s, r in kept.items() if len(r) >= 3)
        common.write_csv(root / "mentiuni_etichete.csv", common.ETICHETE_COLS,
                         [label(slug, rows[0]["url"], kind="cercetare"), label(slug, "https://gone.example/")])
        out = c.dir / "out"
        result = subprocess.run([sys.executable, str(HERE / "build.py"), "--data-dir", str(root), "--site-dir", str(out)], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        total = sum(len(r) for r in kept.values())
        self.assertIn(f"labels 1/{total} kept rows", result.stdout)
        item = next(i for i in json.loads((out / "data.json").read_text())["items"] if i["slug"] == slug)
        self.assertIs(item["reach"]["provisional"], True)
        self.assertEqual(item["reach"]["cercetare"], 1)
        others = [i for i in json.loads((out / "data.json").read_text())["items"] if i["slug"] != slug]
        self.assertTrue(all("provisional" not in i["reach"] for i in others))


# --- since: entries whose domain had an earlier use ------------------------------------------------------------


class SinceOfEarlierDomainUse(unittest.TestCase):
    PROFILE = {"first_seen": "2011-05-19", "repo_created": "2024-05-04", "cert_first": "2024-04-18"}

    def test_the_first_capture_still_wins_for_an_ordinary_entry(self):
        self.assertEqual(build.since(self.PROFILE), ("2011-05-19", "arhiva"))

    def test_a_listed_entry_takes_the_repository_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profil.csv"
            common.save_profile({"lista-firme": dict(self.PROFILE), "other": dict(self.PROFILE)}, path)
            profile = build.site_profile(path)
        self.assertEqual(build.since(profile["lista-firme"]), ("2024-05-04", "cod"))
        self.assertEqual(build.since(profile["other"]), ("2011-05-19", "arhiva"))


# --- Item 6: last activity ----------------------------------------------------------------------------------------------------


class LastActivity(unittest.TestCase):
    TODAY = date(2026, 10, 19)

    def test_a_dated_update_wins_over_the_copyright_year(self):
        self.assertEqual(build.last_activity({"updated": "2023-05-01", "copyright_year": "2026"}, self.TODAY), "2023-05-01")
        self.assertEqual(build.last_activity({"updated": "2019-01-01", "copyright_year": "2024"}, self.TODAY), "2019-01-01")

    def test_the_copyright_year_is_a_fallback_from_the_first_of_january(self):
        self.assertEqual(build.last_activity({"copyright_year": "2024"}, self.TODAY), "2024-01-01")
        self.assertEqual(build.last_activity({"copyright_year": "2026"}, self.TODAY), "2026-01-01")

    def test_the_copyright_date_is_never_after_today(self):
        self.assertEqual(build.last_activity({"copyright_year": "2027"}, self.TODAY), "")
        self.assertEqual(build.last_activity({"copyright_year": "2026"}, date(2025, 12, 31)), "")
        self.assertEqual(build.last_activity({"copyright_year": "2026"}, date(2026, 1, 1)), "2026-01-01")
        year = date.today().year
        self.assertLessEqual(build.last_activity({"copyright_year": str(year)}), date.today().isoformat())
        self.assertEqual(build.last_activity({"copyright_year": str(year + 1)}), "")

    def test_no_evidence_gives_no_date(self):
        self.assertEqual(build.last_activity({}, self.TODAY), "")
        self.assertEqual(build.last_activity({"copyright_year": ""}, self.TODAY), "")

    def test_a_current_year_footer_is_not_a_date_in_the_future(self):
        # The audit case: a 2026 footer gave 2026-12-31 in October, so the entry looked active until the end of the year.
        self.assertLess(build.last_activity({"copyright_year": "2026"}, self.TODAY), "2026-12-31")
        self.assertLessEqual(build.last_activity({"copyright_year": "2026"}, self.TODAY), self.TODAY.isoformat())


if __name__ == "__main__":
    unittest.main(verbosity=2)
