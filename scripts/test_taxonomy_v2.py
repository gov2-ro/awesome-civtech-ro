"""Named checks for the taxonomy v2 package, the data-root selection and the isolated v2 build. Stdlib only.

    python3 scripts/test_taxonomy_v2.py          # or: python3 -m unittest scripts/test_taxonomy_v2.py -v

Every mutation runs on a temporary copy; the repository's data and site/ are only read.

PACKAGE and OVERLAY are the package and the integration copy in their derived state: the classifications of the sealed run
that these tests describe (counts, states, the baseline). While integrare/ is derived they are the real folders. After
`integrare.py --detach` the owner edits the real files, so they are the package as of the detach commit; REAL_PACKAGE and
REAL_OVERLAY stay the real folders.
"""
import atexit
import csv
import hashlib
import importlib.util
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
REAL_PACKAGE = ROOT / "data" / "taxonomy-v2"
REAL_OVERLAY = REAL_PACKAGE / "integrare"


def load_integrare():
    """data/taxonomy-v2/integrare.py as a module (it is a script, not a package member)."""
    spec = importlib.util.spec_from_file_location("integrare", REAL_PACKAGE / "integrare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derived_roots() -> tuple[Path, Path]:
    """(package, overlay) in the derived state; see the module docstring."""
    record = json.loads((REAL_OVERLAY / "pachet.json").read_text(encoding="utf-8")).get("detached")
    if not record:
        return REAL_PACKAGE, REAL_OVERLAY
    tmp = tempfile.TemporaryDirectory()
    atexit.register(tmp.cleanup)
    try:
        package = load_integrare().export_tree(record["commit"], Path(tmp.name).resolve())
    except SystemExit as e:  # export_tree names the problem, for instance a clone without the detach commit
        raise RuntimeError(f"the tests need the package as of the detach commit {record['commit']}: {e}") from e
    return package, package / "integrare"


PACKAGE, OVERLAY = derived_roots()


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, capture_output=True, text=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Copy:
    """A temporary copy of the package (without the 16 MB classification run), with small editing helpers."""

    def __init__(self, source: Path = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "taxonomy-v2"
        shutil.copytree(source or PACKAGE, self.root, ignore=shutil.ignore_patterns("runs", "__pycache__", "catalogue.json", "pagini", "surse"))
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


def with_hidden_code(rows: list[dict]):
    """Add the code `ascuns` to the list `clasificare_stare` of valori.csv. The derived package of these tests may predate it."""
    if not any(r["lista"] == "clasificare_stare" and r["cod"] == taxonomy_v2.HIDDEN for r in rows):
        rows.append({"lista": "clasificare_stare", "cod": taxonomy_v2.HIDDEN, "eticheta_ro": "Ascuns", "eticheta_en": "Hidden",
                     "definitie_ro": "Intrarea rămâne în date, dar nu apare în site-ul public.", "statut": "propus", "ordine": "3"})


def without_relation(rows: list[dict]):
    """Clear `relatie_date` in every row: a clean start for a test, whatever values the editors have written since."""
    for r in rows:
        r["relatie_date"] = ""


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
        result = run(REAL_PACKAGE / "integrare.py")  # the real overlay: derived (matches a fresh assembly) or detached (seal and commit hold)
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

    def test_default_root_is_the_public_root(self):
        """Before the cutover the public root is the v1 root data/; after it, the integration copy."""
        self.assertIn(common.PUBLIC_ROOT, (common.DATA, REAL_OVERLAY))
        self.assertEqual(common.data_schema(), common.data_schema(common.PUBLIC_ROOT))
        self.assertEqual(common.observation_paths(), common.observation_paths(common.PUBLIC_ROOT))
        self.assertEqual(common.data_schema(common.DATA), "v1")  # data/ stays a readable v1 root
        self.assertEqual(common.observation_paths(common.DATA)["profile"], common.DATA / "profil.csv")

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
        c = Copy()  # a copy that holds a proposal, whatever the state of the repository's data
        self.addCleanup(c.close)
        c.edit("intrari.csv", lambda rows: rows[0].update(clasificare_stare="propus"), c.overlay)
        gate = run("scripts/validate.py", "--data-dir", c.overlay, "--publication")
        self.assertEqual(gate.returncode, 1)
        self.assertIn(f"publication: {c.rows('intrari.csv', c.overlay)[1][0]['slug']}", gate.stdout + gate.stderr)

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

    def test_publication_gate_accepts_a_hidden_entry_and_ignores_its_review_items(self):
        c = Copy()
        self.addCleanup(c.close)
        c.edit("valori.csv", with_hidden_code)
        entries = {r["slug"]: r for r in c.rows("intrari.csv")[1]}
        queue = c.rows("revizuire.csv")[1]
        # An entry that has a subject and an open high-priority review item: hiding it must clear that item for the gate.
        slug = next(r["slug"] for r in queue if r["stare"] == "deschis" and r["prioritate"] == "mare"
                    and entries.get(r["slug"], {}).get("subiect_principal"))

        def settle(rows):
            for r in rows:
                r["clasificare_stare"] = taxonomy_v2.HIDDEN if r["slug"] == slug else "acceptat"

        def close_the_others(rows):
            for r in rows:
                if r["prioritate"] == "mare" and r["slug"] != slug:
                    r["stare"], r["decizie_editor"] = "amanat", "test"
        c.edit("intrari.csv", settle)
        self.assertNotEqual(c.errors(publication=True), [])  # the other open high-priority items still block
        c.edit("revizuire.csv", close_the_others)
        self.assertEqual(c.errors(publication=True), [])
        self.assertEqual(c.errors(), [])  # the plain checks accept the code too

    def test_publication_gate_still_refuses_a_proposal_next_to_a_hidden_entry(self):
        c = Copy()
        self.addCleanup(c.close)
        c.edit("valori.csv", with_hidden_code)

        def settle(rows):
            for n, r in enumerate(rows):
                r["clasificare_stare"] = "ascuns" if n == 0 else "propus" if n == 1 else "acceptat"
        c.edit("intrari.csv", settle)
        _, rows = c.rows("intrari.csv")
        errors = [e for e in c.errors(publication=True) if "classification state" in e]
        self.assertEqual(len(errors), 1)
        self.assertIn(f"publication: {rows[1]['slug']}", errors[0])
        self.assertIn("not acceptat or ascuns", errors[0])

    def test_an_unknown_classification_state_is_refused_without_the_hidden_code(self):
        """The code list decides: `ascuns` is valid only where valori.csv lists it."""
        c = Copy()
        self.addCleanup(c.close)
        c.edit("valori.csv", lambda rows: [rows.remove(r) for r in list(rows)
                                           if r["lista"] == "clasificare_stare" and r["cod"] == taxonomy_v2.HIDDEN])
        c.edit("intrari.csv", lambda rows: rows[0].update(clasificare_stare=taxonomy_v2.HIDDEN))
        self.assertTrue(any("clasificare_stare" in e for e in c.errors()))


class RelationToData(unittest.TestCase):
    """The column `relatie_date`: how an entry relates to data. These tests use a copy of the real package (the current
    state), not the derived one that the other classes use: the derived package is the state at the detach commit and has no column."""

    def setUp(self):
        self.c = Copy(REAL_PACKAGE)
        self.addCleanup(self.c.close)
        self.c.edit("intrari.csv", without_relation, self.c.overlay)

    def entry(self, test) -> str:
        return next(r["slug"] for r in self.c.rows("intrari.csv", self.c.overlay)[1] if test(r))

    def set_relation(self, slug: str, code: str, **more):
        def edit(rows):
            row = next(r for r in rows if r["slug"] == slug)
            row["relatie_date"] = code
            row.update(more)
        self.c.edit("intrari.csv", edit, self.c.overlay)

    def errors(self, **kw) -> list[str]:
        return self.c.errors(self.c.overlay, **kw)

    def test_the_column_follows_dovada_detaliere_and_the_list_has_four_codes_in_order(self):
        header = self.c.rows("intrari.csv", self.c.overlay)[0]
        self.assertEqual(header[header.index("dovada_detaliere") + 1], "relatie_date")
        self.assertEqual(self.c.rows("intrari.csv")[0], header)  # the base package has the same header
        pkg = taxonomy_v2.load(self.c.overlay)
        self.assertEqual(list(pkg.codes["relatie_date"]), ["date-publice", "date-proprii", "calcul", "fara-date"])
        self.assertEqual(pkg.label("relatie_date", "fara-date"), "Fără date")
        rule = pkg.rules("intrari.csv")["relatie_date"]
        self.assertEqual((rule["kind"], rule["list"], rule.get("required", False)), ("code", "relatie_date", False))
        self.assertEqual(self.errors(), [])

    def test_an_empty_value_passes_the_checks_and_the_publication_gate(self):
        self.assertIn("relatie_date", self.c.rows("intrari.csv", self.c.overlay)[0])
        self.assertTrue(all(r["relatie_date"] == "" for r in self.c.rows("intrari.csv", self.c.overlay)[1]))
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.errors(publication=True), [])

    def test_each_code_passes_on_a_project_and_on_a_resource(self):
        for kind in ("proiect", "resursa"):
            slug = self.entry(lambda r: r["tip_entitate"] == kind and not r["detaliere_date"])
            for code in ("date-publice", "date-proprii", "calcul", "fara-date"):
                with self.subTest(kind=kind, code=code):
                    self.set_relation(slug, code)
                    self.assertEqual(self.errors(publication=True), [])

    def test_an_unknown_code_is_refused(self):
        slug = self.entry(lambda r: r["tip_entitate"] == "proiect")
        self.set_relation(slug, "altceva")
        errors = self.errors()
        self.assertTrue(any(f"intrari.csv {slug}: unknown relatie_date code 'altceva'" in e for e in errors), errors)

    def test_a_list_of_two_codes_is_refused(self):
        slug = self.entry(lambda r: r["tip_entitate"] == "proiect")
        self.set_relation(slug, "date-publice|calcul")
        self.assertTrue(any(f"intrari.csv {slug}: unknown relatie_date code" in e for e in self.errors()))

    def test_fara_date_with_a_data_breakdown_is_refused(self):
        slug = self.entry(lambda r: r["tip_entitate"] != "organizatie" and r["detaliere_date"])
        self.set_relation(slug, "date-publice")
        self.assertEqual(self.errors(), [])  # another code goes with a breakdown
        self.set_relation(slug, "fara-date")
        errors = self.errors()
        self.assertEqual([e for e in errors if slug in e], [f"intrari.csv {slug}: relatie_date fara-date excludes detaliere_date"])

    def test_a_code_on_an_organisation_is_refused(self):
        slug = self.entry(lambda r: r["tip_entitate"] == "organizatie")
        for code in ("date-publice", "fara-date"):
            with self.subTest(code=code):
                self.set_relation(slug, code)
                errors = self.errors()
                self.assertTrue(any(f"intrari.csv {slug}: relatie_date on an organisation" in e for e in errors), errors)
        self.set_relation(slug, "")
        self.assertEqual(self.errors(), [])  # an organisation stays empty

    def run_validate(self):
        return run("scripts/validate.py", "--data-dir", self.c.overlay)

    def test_validate_warns_when_a_fara_date_entry_has_extracted_fields_and_does_not_fail(self):
        fields = {r["slug"]: int(r["campuri_din_surse"] or 0) for r in taxonomy_v2.read_table(self.c.root / "observatii/inventare/rezumat.csv")[1]}
        with_fields = self.entry(lambda r: r["tip_entitate"] != "organizatie" and not r["detaliere_date"] and fields.get(r["slug"], 0) > 0)
        without = self.entry(lambda r: r["tip_entitate"] != "organizatie" and not r["detaliere_date"] and fields.get(r["slug"], 0) == 0)
        clean = self.run_validate()
        self.assertEqual((clean.returncode, "fara-date" in clean.stdout), (0, False), clean.stdout + clean.stderr)
        self.set_relation(without, "fara-date")
        self.set_relation(with_fields, "date-publice")
        quiet = self.run_validate()  # no field contradicts these two
        self.assertEqual((quiet.returncode, "fara-date" in quiet.stdout), (0, False), quiet.stdout + quiet.stderr)
        self.set_relation(with_fields, "fara-date")
        loud = self.run_validate()
        self.assertEqual(loud.returncode, 0, loud.stdout + loud.stderr)  # a warning, not an error
        lines = [l for l in loud.stdout.splitlines() if "fara-date" in l]
        self.assertEqual(len(lines), 1, loud.stdout)
        self.assertIn("warning", lines[0])
        self.assertIn(f"{with_fields}: relatie_date is fara-date, but the inventory has {fields[with_fields]} extracted fields", lines[0])
        self.assertNotIn(without, " ".join(lines))
        self.assertIn("1 avertismente", loud.stderr)

    def test_the_build_writes_data_relation_on_each_item_and_the_code_list_and_nothing_else_changes(self):
        sys.path.insert(0, str(HERE))
        import build
        slug = self.entry(lambda r: r["tip_entitate"] == "proiect" and r["clasificare_stare"] == "acceptat")
        site = Path(self.c.tmp.name) / "site"
        before, head = build.items_v2(self.c.overlay, site)
        self.assertTrue(before and all(i["dataRelation"] == "" for i in before))  # the empty column changes nothing
        self.assertEqual([c["key"] for c in head["vocabulary"]["dataRelations"]], ["date-publice", "date-proprii", "calcul", "fara-date"])
        self.assertEqual({c["key"]: c["label"] for c in head["vocabulary"]["dataRelations"]}["calcul"], "Calculator sau formular")
        self.set_relation(slug, "calcul")
        after, _ = build.items_v2(self.c.overlay, site)
        self.assertEqual({i["slug"]: i["dataRelation"] for i in after if i["dataRelation"]}, {slug: "calcul"})
        strip = lambda items: [{k: v for k, v in i.items() if k != "dataRelation"} for i in items]
        self.assertEqual(strip(before), strip(after))

    def test_the_build_writes_the_two_data_groups_that_the_explorer_reads_and_they_agree_with_the_scope_rule(self):
        sys.path.insert(0, str(HERE))
        import build
        from common import inventory_exclusion
        _, head = build.items_v2(self.c.overlay, Path(self.c.tmp.name) / "site")
        vocabulary = head["vocabulary"]
        groups = {g["key"]: g for g in vocabulary["dataGroups"]}
        self.assertEqual([g["key"] for g in vocabulary["dataGroups"]], ["cu-date", "fara-date"])
        self.assertEqual({k: g["label"] for k, g in groups.items()}, {"cu-date": "Lucrează cu date", "fara-date": "Fără date"})
        self.assertEqual(groups["cu-date"]["codes"], ["date-publice", "date-proprii", "calcul"])
        self.assertEqual(groups["fara-date"]["codes"], ["fara-date", ""], "the empty value is without data")
        for code in [c["key"] for c in vocabulary["dataRelations"]] + [""]:
            homes = [k for k, g in groups.items() if code in g["codes"]]
            self.assertEqual(len(homes), 1, f"{code!r} belongs to one group")
            in_scope = inventory_exclusion("proiect", "activ", code) == ""
            self.assertEqual(homes[0] == "cu-date", in_scope, f"{code!r}: the group cu-date is the scope of /date/")


# What a recommendation must not be: the empty or placeholder proposals of the generated queue.
GENERIC_PROPOSALS = {"", "verificare manuală", "verificare cu dovezi primare", "dovadă primară pentru format"}


class ReviewReconciliation(unittest.TestCase):
    """Slice D: the technical closure `tehnic`, the reconciliation of the review queue, and the recommendations."""

    @classmethod
    def setUpClass(cls):
        cls.base = taxonomy_v2.read_table(PACKAGE / "revizuire.csv")[1]
        cls.queue = taxonomy_v2.read_table(OVERLAY / "revizuire.csv")[1]
        cls.recon = taxonomy_v2.read_table(OVERLAY / "reconciliere.csv")[1]
        cls.integrare = load_integrare()

    def setUp(self):
        self.c = Copy()
        self.addCleanup(self.c.close)

    # --- the code `tehnic` and its rule ---------------------------------------------------------------------------------

    def test_tehnic_is_a_code_of_the_review_states(self):
        self.assertIn("tehnic", taxonomy_v2.load(PACKAGE).codes["revizuire_stare"])

    def test_technical_closure_needs_a_reason(self):
        def close(rows):
            rows[0].update(stare="tehnic", motiv="  ", decizie_editor="")
        self.c.edit("revizuire.csv", close, self.c.overlay)
        self.assertTrue(any("a technical closure needs a reason" in e for e in self.c.errors(self.c.overlay)))

    def test_technical_closure_refuses_an_editor_decision(self):
        def close(rows):
            rows[0].update(stare="tehnic", motiv="Premisa nu se aplică.", decizie_editor="acceptat de test")
        self.c.edit("revizuire.csv", close, self.c.overlay)
        self.assertTrue(any("no editor decision" in e for e in self.c.errors(self.c.overlay)))

    def test_technical_closure_with_a_reason_passes(self):
        def close(rows):
            rows[0].update(stare="tehnic", motiv="Premisa nu se aplică.", decizie_editor="")
        self.c.edit("revizuire.csv", close, self.c.overlay)
        self.assertEqual(self.c.errors(self.c.overlay), [])

    def test_gate_ignores_technical_closures(self):
        def accept(rows):
            for r in rows:
                r["clasificare_stare"] = "acceptat"

        def close(rows):
            for r in rows:
                if r["prioritate"] == "mare":
                    r.update(stare="tehnic", motiv="Închis tehnic de test.", decizie_editor="")
        self.c.edit("intrari.csv", accept)
        self.assertNotEqual(self.c.errors(publication=True), [])  # open high-priority items still block
        self.c.edit("revizuire.csv", close)
        self.assertEqual(self.c.errors(publication=True), [])

    def test_gate_counts_only_open_high_priority_items(self):
        errors = taxonomy_v2.check(OVERLAY, publication=True)[0]
        blocking = {r["id"] for r in self.queue if r["stare"] == "deschis" and r["prioritate"] == "mare"}
        listed = {e.rsplit(" ", 1)[-1] for e in errors if "review item" in e}
        self.assertEqual(listed, blocking)

    def test_a_duplicate_closure_never_lowers_the_priority(self):
        """A closed duplicate points to an open item of the same or a higher priority, so the gate loses nothing."""
        rank = {"mare": 0, "medie": 1, "mica": 2}
        items = {r["id"]: r for r in self.queue}
        for r in self.queue:
            if r["stare"] == "tehnic" and r["motiv"].startswith("Dublură a "):
                kept = items[r["motiv"].split()[2].rstrip(":")]
                self.assertEqual(kept["stare"], "deschis", r["id"])
                self.assertLessEqual(rank[kept["prioritate"]], rank[r["prioritate"]], r["id"])

    # --- the reconciliation table ----------------------------------------------------------------------------------------

    def test_every_r_item_has_a_reconciliation_row(self):
        r_ids = [r["id"] for r in self.base]
        self.assertEqual(r_ids, [f"R{n:03d}" for n in range(1, 67)])
        recon_ids = [r["id"] for r in self.recon]
        self.assertEqual(len(recon_ids), len(set(recon_ids)))
        self.assertLessEqual(set(r_ids), set(recon_ids))
        self.assertLessEqual(set(recon_ids), {r["id"] for r in self.queue})  # no row for an item that does not exist

    def test_reconciliation_keeps_priorities_and_takes_no_decision(self):
        old = {r["id"]: r for r in self.base}
        for r in self.queue:
            if r["id"] in old:
                self.assertEqual(r["prioritate"], old[r["id"]]["prioritate"], r["id"])
            self.assertIn(r["stare"], ("deschis", "tehnic"), r["id"])  # nothing is accepted, rejected or deferred
            self.assertEqual(r["decizie_editor"], "", r["id"])
        self.assertEqual({r["stare"] for r in self.base}, {"deschis"})  # the base queue is unchanged

    def test_every_technical_closure_says_why_and_cites_evidence(self):
        recon = {r["id"]: r for r in self.recon}
        closed = [r for r in self.queue if r["stare"] == "tehnic"]
        self.assertTrue(closed)
        for r in closed:
            self.assertEqual(recon[r["id"]]["rezultat"], "tehnic", r["id"])
            self.assertGreater(len(r["motiv"].split()), 12, r["id"])
            self.assertIn("Dovadă:", r["motiv"], r["id"])

    def test_every_open_item_has_a_concrete_recommendation(self):
        opened = [r for r in self.queue if r["stare"] == "deschis"]
        self.assertTrue(opened)
        for r in opened:
            self.assertNotIn(r["propunere"].strip(), GENERIC_PROPOSALS, r["id"])
            self.assertTrue(r["propunere"].startswith("Recomandare: "), f"{r['id']}: {r['propunere'][:60]}")
            self.assertGreaterEqual(len(r["propunere"].split()), 5, r["id"])  # a verb and a named value, not a label
            self.assertGreater(len(r["motiv"].split()), 12, r["id"])
            self.assertIn("Dovadă:", r["motiv"], r["id"])

    def test_moldova_recommendation_uses_the_iso_style_id(self):
        carrying = [r["id"] for r in self.queue if r["stare"] == "deschis" and "tara:MD" in r["propunere"] and "cod_iso_3166_1=MD" in r["propunere"]]
        self.assertTrue(carrying, "no open item recommends tara:MD with cod_iso_3166_1=MD")
        areas = taxonomy_v2.load(PACKAGE).areas
        self.assertNotIn("tara:MD", areas)  # the recommendation does not add the area
        self.assertNotIn("tara:republica-moldova", areas)
        self.assertEqual(areas["tara:RO"]["cod_iso_3166_1"], "RO")  # the style that the recommendation follows

    def test_reconciliation_table_has_the_expected_header(self):
        header = taxonomy_v2.read_table(OVERLAY / "reconciliere.csv")[0]
        self.assertEqual(header, ["id", "rezultat", "camp", "valoare_originala", "propunere", "motiv", "dovada"])
        self.assertTrue({r["rezultat"] for r in self.recon} <= {"pastrat", "rescris", "tehnic"})

    # --- the evidence of every row must exist -------------------------------------------------------------------------------

    def test_every_citation_in_the_table_resolves(self):
        generated = {}
        for r in self.recon:
            tokens = r["dovada"].split("|") if r["dovada"] else []
            self.assertTrue(tokens, r["id"])
            for token in tokens:
                self.assertTrue(self.integrare.citation_exists(token, generated, PACKAGE), f"{r['id']}: {token}")

    def test_invented_evidence_is_refused(self):
        exists = lambda token, generated: self.integrare.citation_exists(token, generated, PACKAGE)
        slug = "7-ani-de-acasa"
        self.assertTrue(exists(f"clasificare-input.csv:{slug}:descriere", {}))  # an empty cell proves an absent description
        self.assertTrue(exists(f"runs/2026-10-19-reasoned-evidence/responses/{slug}.json:justifications[subiect_principal]", {}))
        self.assertTrue(exists(f"runs/2026-10-19-reasoned-evidence/responses/{slug}.json:excluded_legacy_tags[tip=educativ]", {}))
        for token in (f"clasificare-input.csv:{slug}:nu_exista",                      # unknown column
                      "clasificare-input.csv:slug-inventat:descriere",                 # unknown row
                      f"runs/2026-10-19-reasoned-evidence/responses/{slug}.json:justifications[teme=subiect:inventat]",  # unknown value
                      f"runs/2026-10-19-reasoned-evidence/responses/{slug}.json:cheie_inventata",  # unknown key
                      "runs/2026-10-19-reasoned-evidence/responses/slug-inventat.json:uncertainties",  # unknown file
                      "../scripts/common.py:x:y",                                      # outside the package
                      "/etc/hosts:x:y", "concepte.csv", "", f" clasificare-input.csv:{slug}:descriere"):
            self.assertFalse(exists(token, {}), token)

    def test_reconcile_rejects_bad_tables(self):
        reconcile = self.integrare.reconcile
        columns = taxonomy_v2.read_table(OVERLAY / "intrari.csv")[0]
        good = {"id": "R001", "rezultat": "rescris", "camp": "clasificare", "valoare_originala": "x", "propunere": "Recomandare: păstrați x.",
                "motiv": "Motiv.", "dovada": "clasificare-input.csv:7-ani-de-acasa:descriere"}

        def queue():
            return [{"id": "R001", "slug": "7-ani-de-acasa", "camp": "clasificare", "valoare_originala": "descriere absentă",
                     "propunere": "verificare manuală", "motiv": "Motiv vechi.", "prioritate": "mare", "stare": "deschis", "decizie_editor": ""}]

        def fails(*rows, items=None):
            with self.assertRaises(SystemExit):
                reconcile(items or queue(), list(rows), columns, {})

        items = queue()
        reconcile(items, [good], columns, {})  # the good row is applied
        self.assertEqual((items[0]["propunere"], items[0]["stare"]), ("Recomandare: păstrați x.", "deschis"))
        self.assertTrue(items[0]["motiv"].endswith("Dovadă: clasificare-input.csv:7-ani-de-acasa:descriere"))
        items = queue()
        reconcile(items, [dict(good, rezultat="tehnic")], columns, {})
        self.assertEqual(items[0]["stare"], "tehnic")
        fails()                                                                    # an R item without a row
        fails(good, dict(good))                                                    # duplicate id
        fails(good, dict(good, id="R999"))                                         # row for an item that does not exist
        fails(dict(good, rezultat="inchis"))                                       # unknown result
        fails(dict(good, camp="localitati_acoperite"))                             # not a column
        fails(dict(good, rezultat="tehnic", dovada=""))                            # a closure without evidence
        fails(dict(good, rezultat="tehnic", motiv=" "))                            # a closure without a reason
        fails(dict(good, dovada="clasificare-input.csv:7-ani-de-acasa:inventat"))  # invented evidence
        fails(dict(good, rezultat="pastrat"))                                      # pastrat must keep the text and carry no evidence
        keep = {"id": "R001", "rezultat": "pastrat", "camp": "clasificare", "valoare_originala": "descriere absentă",
                "propunere": "verificare manuală", "motiv": "Motiv vechi.", "dovada": ""}
        items = queue()
        reconcile(items, [keep], columns, {})
        self.assertEqual(items[0]["stare"], "deschis")
        self.assertEqual(items[0]["motiv"], "Motiv vechi.")


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
        """A v2 root that is not the public root never writes site/, whatever the public root is (PACKAGE never is)."""
        result = run("scripts/build.py", "--data-dir", PACKAGE, "--allow-draft")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("separate --site-dir", result.stderr)

    def test_v2_build_needs_allow_draft_for_proposals(self):
        c = Copy()  # a copy that holds proposals, whatever the state of the repository's data
        self.addCleanup(c.close)
        c.edit("intrari.csv", lambda rows: rows[0].update(clasificare_stare="propus"), c.overlay)
        result = run("scripts/build.py", "--data-dir", c.overlay, "--site-dir", Path(self.tmp.name) / "refused")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((Path(self.tmp.name) / "refused").exists())

    def test_build_leaves_out_a_hidden_entry(self):
        """A hidden entry stays in the data. No public file shows it: data.json, the entry page, the feed, llms.txt."""
        c = Copy()
        self.addCleanup(c.close)
        c.edit("valori.csv", with_hidden_code)
        slug = "465"
        row = next(r for r in c.rows("intrari.csv", c.overlay)[1] if r["slug"] == slug)

        def settle(rows):
            for r in rows:
                r["clasificare_stare"] = taxonomy_v2.HIDDEN if r["slug"] == slug else "acceptat"
                if not r["subiect_principal"]:  # the abstention has no subject, and `acceptat` needs one
                    r["subiect_principal"] = r["subiecte"] = "subiect:guvernare-democratie"

        def close(rows):
            for r in rows:
                if r["prioritate"] == "mare":
                    r["stare"], r["decizie_editor"] = "amanat", "test"
        c.edit("intrari.csv", settle, c.overlay)
        c.edit("revizuire.csv", close, c.overlay)
        out = Path(self.tmp.name) / "hidden"
        result = run("scripts/build.py", "--data-dir", c.overlay, "--site-dir", out)  # no --allow-draft: the gate passes
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((out / "data.json").read_text())
        slugs = [i["slug"] for i in data["items"]]
        self.assertEqual(len(slugs), len(c.rows("intrari.csv", c.overlay)[1]) - 1)
        self.assertNotIn(slug, slugs)
        self.assertEqual(sorted(i["id"] for i in data["items"]), list(range(1, len(slugs) + 1)))  # no gap where the entry was
        self.assertFalse(data["draft"])
        page = f"{row['sectiune_url']}/{slug}/"
        self.assertFalse((out / row["sectiune_url"] / slug).exists())
        for name in ("feed.xml", "llms.txt", "data.json"):
            self.assertNotIn(page, (out / name).read_text(), name)
        self.assertNotIn(row["nume"], (out / row["sectiune_url"] / "index.html").read_text())

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
        index = (self.out / "index.html").read_text()
        if (ROOT / "site-v2").is_dir():  # before the cutover a v2 preview links the extra stylesheet
            self.assertIn('href="v2.css?v=', index)
        else:  # after it, style.css holds those rules
            self.assertNotIn("v2.css", index)

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
