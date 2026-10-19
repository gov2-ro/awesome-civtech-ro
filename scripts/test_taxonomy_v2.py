"""Named checks for the taxonomy v2 package, the data-root selection and the isolated v2 build. Stdlib only.

    python3 scripts/test_taxonomy_v2.py          # or: python3 -m unittest scripts/test_taxonomy_v2.py -v

Every mutation runs on a temporary copy; the repository's data and site/ are only read.
"""
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
import taxonomy_v2  # noqa: E402

ROOT = HERE.parent
PACKAGE = ROOT / "data" / "taxonomy-v2"
OVERLAY = PACKAGE / "integrare"


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, capture_output=True, text=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Copy:
    """A temporary copy of the package (without the 16 MB classification run), with small editing helpers."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "taxonomy-v2"
        shutil.copytree(PACKAGE, self.root, ignore=shutil.ignore_patterns("runs", "__pycache__", "catalogue.json"))
        self.overlay = self.root / "integrare"

    def rows(self, name: str, root: Path = None) -> tuple[list[str], list[dict]]:
        return taxonomy_v2.read_table((root or self.root) / name)

    def write(self, name: str, header: list[str], rows: list[dict], root: Path = None):
        with ((root or self.root) / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def edit(self, name: str, fn, root: Path = None):
        header, rows = self.rows(name, root)
        rows = fn(rows) or rows
        self.write(name, header, rows, root)

    def json(self, name: str, fn):
        path = self.root / name
        data = json.loads(path.read_text(encoding="utf-8"))
        fn(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def errors(self, root: Path = None, **kw) -> list[str]:
        return taxonomy_v2.check(root or self.root, **kw)[0]

    def close(self):
        self.tmp.cleanup()


class PackageChecks(unittest.TestCase):
    """Slice 1: the draft.2 package, its code lists and its negative checks."""

    def setUp(self):
        self.c = Copy()
        self.addCleanup(self.c.close)

    def assertError(self, fragment: str, errors: list[str]):
        self.assertTrue(any(fragment in e for e in errors), f"no error with {fragment!r} in {errors[:5]}")

    def test_package_baseline_passes(self):
        errors, summary = taxonomy_v2.check(PACKAGE, baseline=True)
        self.assertEqual(errors, [])
        self.assertEqual((summary["schema_version"], summary["entries"], summary["concepts"], summary["code_lists"]),
                         ("2.0.0-draft.2", 122, 128, 16))

    def test_integration_overlay_baseline_passes(self):
        errors, summary = taxonomy_v2.check(OVERLAY, baseline=True)
        self.assertEqual(errors, [])
        self.assertEqual(summary["classification_states"], {"propus": 121, "de-revizuit": 1})
        self.assertEqual(summary["without_primary_subject"], 1)

    def test_maturity_rejects_two_values(self):
        def two(rows):
            rows[0]["maturitate"] = "maturitate:prototip|maturitate:pilot"
        self.c.edit("intrari.csv", two)
        self.assertError("maturitate allows one value", self.c.errors())

    def test_unknown_code_rejected(self):
        def bad(rows):
            rows[0]["tip_entitate"] = "aplicatie"
        self.c.edit("intrari.csv", bad)
        self.assertError("unknown tip_entitate code 'aplicatie'", self.c.errors())

    def test_duplicate_code_rejected(self):
        self.c.edit("valori.csv", lambda rows: rows + [dict(rows[0], ordine="99")])
        self.assertError("missing or duplicate lista+cod", self.c.errors())

    def test_blank_code_row_rejected(self):
        self.c.edit("valori.csv", lambda rows: rows + [dict(rows[0], cod="", ordine="98")])
        self.assertError("missing or duplicate lista+cod", self.c.errors())

    def test_retired_code_rejected(self):
        def retire(rows):
            for r in rows:
                if (r["lista"], r["cod"]) == ("nivel_acoperire", "national"):
                    r["statut"] = "retras"
        self.c.edit("valori.csv", retire)
        self.assertError("uses the retired code 'national'", self.c.errors())

    def test_unreferenced_code_list_rejected(self):
        self.c.edit("valori.csv", lambda rows: rows + [dict(rows[0], lista="tipuri_vechi", cod="x", ordine="0")])
        self.assertError("code list `tipuri_vechi` is not referenced", self.c.errors())

    def test_missing_code_list_rejected(self):
        self.c.edit("valori.csv", lambda rows: [r for r in rows if r["lista"] != "incredere"])
        self.assertError("missing code list `incredere`", self.c.errors())

    def test_host_with_unknown_role_rejected(self):
        self.c.edit("gazde-linkuri.csv", lambda rows: rows + [{"gazda": "vimeo.com", "rol": "video"}])
        self.assertError("unknown link role 'video'", self.c.errors())

    def test_duplicate_host_rejected(self):
        self.c.edit("gazde-linkuri.csv", lambda rows: rows + [{"gazda": "github.com", "rol": "cod"}])
        self.assertError("missing or duplicate gazda", self.c.errors())

    def test_host_with_scheme_or_wildcard_rejected(self):
        self.c.edit("gazde-linkuri.csv", lambda rows: rows + [{"gazda": "*.substack.com", "rol": "web"}])
        self.assertError("not a plain lowercase host", self.c.errors())

    def test_link_token_with_unknown_role_rejected(self):
        def token(rows):
            rows[0]["linkuri"] = "video:https://vimeo.com/x"
        self.c.edit("intrari.csv", token)
        self.assertError("unknown link role 'video'", self.c.errors())

    def test_sections_in_settings_rejected(self):
        self.c.json("setari.json", lambda d: d.update(sectiuni=[{"key": "proiect", "label": "Proiecte"}]))
        self.assertError("`sectiuni` duplicates valori.csv", self.c.errors())

    def test_roles_in_settings_rejected(self):
        self.c.json("setari.json", lambda d: d.update(roluri_linkuri=[]))
        self.assertError("`roluri_linkuri` duplicates roluri-linkuri.csv", self.c.errors())

    def test_enums_in_schema_rejected(self):
        self.c.json("schema.json", lambda d: d.update(enums={"incredere": ["mica"]}))
        self.assertError("`enums` duplicates valori.csv", self.c.errors())

    def test_retired_concept_assignment_rejected(self):
        def retire(rows):
            for r in rows:
                if r["id"] == "format:harta":
                    r["statut"] = "retras"
        self.c.edit("concepte.csv", retire)
        self.assertError("retired concept: format:harta", self.c.errors())

    def test_topic_without_its_root_rejected(self):
        def orphan(rows):
            r = next(r for r in rows if r["slug"] == "ce-cumpara-primaria")
            r["teme"] = "subiect:achizitii-publice|subiect:alegeri"
        self.c.edit("intrari.csv", orphan)
        self.assertError("topic root missing from subiecte: subiect:alegeri", self.c.errors())

    def test_empty_primary_subject_only_while_incomplete(self):
        self.assertEqual(self.c.errors(self.c.overlay), [])

        def accept(rows):
            next(r for r in rows if r["slug"] == "incentru")["clasificare_stare"] = "acceptat"
        self.c.edit("intrari.csv", accept, self.c.overlay)
        self.assertError("subiect_principal is required", self.c.errors(self.c.overlay))

    def test_source_snapshot_change_detected(self):
        path = self.c.root / "source" / "orgs.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        self.assertError("immutable source snapshot changed", self.c.errors())

    def test_baseline_detects_a_changed_override(self):
        def change(rows):
            next(r for r in rows if r["stare"] == "arhivat")["stare"] = "offline"
        self.c.edit("intrari.csv", change, self.c.overlay)
        self.assertError("original value differs in stare", self.c.errors(self.c.overlay, baseline=True))

    def test_extracted_roles_keep_the_v1_lookup(self):
        pkg = taxonomy_v2.load(PACKAGE)
        v1 = json.loads((PACKAGE / "source" / "taxonomy.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg.link_roles(), [{k: r[k] for k in ("key", "label", "hosts")} for r in v1["linkuri"]["roluri"]])
        self.assertEqual(pkg.sections(), v1["kinds"])

    def test_export_has_scalar_maturity(self):
        data = taxonomy_v2.export(OVERLAY)
        self.assertTrue(all(e["maturitate"] is None or isinstance(e["maturitate"], str) for e in data["entries"]))
        self.assertTrue(all(isinstance(e["subiecte"], list) for e in data["entries"]))
        self.assertNotIn("sectiuni", json.loads((PACKAGE / "setari.json").read_text()))
        self.assertEqual([s["key"] for s in data["settings"]["sectiuni"]], ["proiect", "organizatie", "resursa"])

    def test_integration_copy_is_reproducible(self):
        result = run(PACKAGE / "integrare.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_technology_claims_have_evidence(self):
        """No technology without a justification of its own that cites more than the legacy tags."""
        run_dir = PACKAGE / "runs" / "2026-10-19-reasoned-evidence"
        for row in taxonomy_v2.read_table(OVERLAY / "intrari.csv")[1]:
            for tech in taxonomy_v2.values(row["tehnologii"]):
                response = json.loads((run_dir / "responses" / f"{row['slug']}.json").read_text(encoding="utf-8"))
                just = [j for j in response["justifications"] if j["field"] == "tehnologii" and j["value"] == tech]
                self.assertTrue(just, f"{row['slug']}: {tech} has no justification")
                sources = {e["source_id"].split(":")[-1] for j in just for e in j["evidence"]}
                self.assertTrue(sources - {"cuvinte_original", "tip_original", "domeniu_original"}, f"{row['slug']}: {tech} cites only legacy tags")


class RootSelection(unittest.TestCase):
    """Slice 2: explicit data roots, v1 by default; observations and snapshots stay where they belong."""

    def test_default_root_is_v1(self):
        self.assertEqual(common.data_schema(), "v1")
        self.assertEqual(common.observation_paths()["profile"], common.DATA / "profil.csv")

    def test_v2_roots_are_detected(self):
        self.assertEqual(common.data_schema(PACKAGE), "v2")
        self.assertEqual(common.data_schema(OVERLAY), "v2")
        self.assertEqual(common.data_schema(PACKAGE / "source"), "v1")

    def test_unknown_root_is_refused(self):
        with self.assertRaises(SystemExit):
            common.data_schema(ROOT / "docs")

    def test_overlay_takes_vocabulary_and_observations_from_its_base(self):
        files = taxonomy_v2.Files(OVERLAY)
        self.assertEqual(files.path("intrari.csv"), OVERLAY / "intrari.csv")
        self.assertEqual(files.path("concepte.csv"), PACKAGE / "concepte.csv")
        self.assertEqual(common.observation_paths(OVERLAY)["mentions"], PACKAGE / "observatii" / "mentiuni.csv")
        self.assertNotIn("source", common.observation_paths(OVERLAY)["profile"].parts)

    def test_overlay_missing_local_file_is_reported(self):
        c = Copy()
        self.addCleanup(c.close)
        (c.overlay / "revizuire.csv").unlink()
        self.assertIn("revizuire.csv: missing file", c.errors(c.overlay))

    def test_catalogue_v2_shape(self):
        entries = {e["slug"]: e for e in common.load_catalogue(OVERLAY)}
        self.assertEqual(len(entries), 122)
        self.assertIsNone(entries["incentru"]["primary_subject"])
        self.assertIsInstance(entries["presspay"]["maturity"], str)
        self.assertEqual(entries["7-ani-de-acasa"]["legacy"]["domeniu"], "civic")
        self.assertFalse({"nota", "nota_clasificare", "sursa_rand", "incredere"} & set(entries["465"]))
        self.assertEqual(entries["465"]["row"], 2)

    def test_validate_cli_selects_the_root(self):
        self.assertEqual(run("scripts/validate.py").returncode, 0)
        self.assertEqual(run("scripts/validate.py", "--data-dir", OVERLAY).returncode, 0)
        gate = run("scripts/validate.py", "--data-dir", OVERLAY, "--publication")
        self.assertEqual(gate.returncode, 1)
        self.assertIn("publication: incentru", gate.stdout + gate.stderr)

    def test_publication_gate_passes_when_everything_is_accepted(self):
        c = Copy()
        self.addCleanup(c.close)

        def accept(rows):
            for r in rows:
                r["clasificare_stare"] = "acceptat"
        c.edit("intrari.csv", accept)
        self.assertNotEqual(c.errors(publication=True), [])  # open high-priority review items remain

        def close(rows):
            for r in rows:
                if r["prioritate"] == "mare":
                    r["stare"], r["decizie_editor"] = "amanat", "test"
        c.edit("revizuire.csv", close)
        self.assertEqual(c.errors(publication=True), [])


class Build(unittest.TestCase):
    """Slice 3: the v2 build writes only to its own folder and publishes no private data."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "v2"
        cls.site_before = {p: digest(p) for p in (ROOT / "site").rglob("*") if p.is_file() and "img" not in p.parts}
        cls.result = run("scripts/build.py", "--data-dir", OVERLAY, "--site-dir", cls.out, "--allow-draft")
        cls.data = json.loads((cls.out / "data.json").read_text()) if (cls.out / "data.json").exists() else {}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_v2_build_needs_a_separate_site_dir(self):
        result = run("scripts/build.py", "--data-dir", OVERLAY, "--allow-draft")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate --site-dir", result.stderr)

    def test_v2_build_needs_allow_draft_for_proposals(self):
        result = run("scripts/build.py", "--data-dir", OVERLAY, "--site-dir", Path(self.tmp.name) / "refused")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((Path(self.tmp.name) / "refused").exists())

    def test_build_refuses_a_folder_inside_the_repository(self):
        result = run("scripts/build.py", "--site-dir", ROOT / "docs" / "preview")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((ROOT / "docs" / "preview").exists())

    def test_preview_writes_only_its_folder(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        after = {p: digest(p) for p in (ROOT / "site").rglob("*") if p.is_file() and "img" not in p.parts}
        self.assertEqual(after, self.site_before)
        pages = [p for k in ("proiect", "organizatie", "resursa") for p in (self.out / k).glob("*/index.html")]
        self.assertEqual(len(pages), 122)
        self.assertTrue(all((self.out / k / "index.html").exists() for k in ("proiect", "organizatie", "resursa")))
        self.assertIn('href="v2.css?v=', (self.out / "index.html").read_text())

    def test_payload_contract(self):
        d = self.data
        self.assertTrue(d["schemaVersion"].startswith("2."))
        self.assertTrue(d["draft"])
        for it in d["items"]:
            self.assertTrue(it["maturity"] is None or isinstance(it["maturity"], str))
            self.assertIn(it["kind"], ("proiect", "organizatie", "resursa"))
        used = {c for it in d["items"] for f in ("subjects", "topics", "purposes", "capabilities", "formats", "technologies",
                                                "institutions", "organisationTypes") for c in it[f]}
        known = {c["id"] for c in d["vocabulary"]["concepts"]}
        self.assertLessEqual(used, known)
        self.assertLess(len(known), 128)  # unused concepts stay out of the public filters

    def test_payload_has_no_private_fields(self):
        raw = (self.out / "data.json").read_text()
        for key in ("nota_clasificare", "sursa_rand", "sursa_fisier", "incredere", "decizie_editor", "justifications", "clasificare_stare"):
            self.assertNotIn(key, raw)
        notes = [r["nota"] for r in taxonomy_v2.read_table(OVERLAY / "intrari.csv")[1] if r["nota"]]
        self.assertTrue(notes)
        self.assertFalse([n for n in notes if n in raw])

    def test_score_does_not_grow_with_assigned_concepts(self):
        sys.path.insert(0, str(HERE))
        import build
        c = Copy()
        self.addCleanup(c.close)
        site = Path(self.tmp.name) / "score"
        before = {i["slug"]: i["score"] for i in build.items_v2(c.overlay, site)[0]}

        def more(rows):
            r = next(r for r in rows if r["slug"] == "465")
            r["scopuri"] = "scop:transparenta|scop:participare|scop:informare|scop:responsabilizare"
            r["functionalitati"] = "functie:cautare|functie:comparare"
        c.edit("intrari.csv", more, c.overlay)
        after = {i["slug"]: i["score"] for i in build.items_v2(c.overlay, site)[0]}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
