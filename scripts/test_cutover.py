"""Named checks for the cutover preparation: the detach of the integration copy (integrare.py --detach), the public root
(PUBLIC_ROOT) and scripts/cutover_v2.py. Stdlib only.

    python3 scripts/test_cutover.py          # or: python3 -m unittest scripts/test_cutover.py -v

Every mutation runs on a temporary copy, or in a temporary repository: the repository's data, site/ and runs/ are only read.
The tests hold before and after the cutover: where they need the state before it (cutover_v2.is_applied is false), they
skip. No test applies the cutover to the real repository, and none runs the full `--rehearse` (it runs these tests).
"""
import contextlib
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import common  # noqa: E402
import cutover_v2  # noqa: E402
import taxonomy_v2  # noqa: E402
from test_taxonomy_v2 import OVERLAY, PACKAGE, REAL_OVERLAY, REAL_PACKAGE, Copy  # noqa: E402

ROOT = HERE.parent
RUNS = REAL_PACKAGE / "runs"
# PACKAGE and OVERLAY are the derived state of the integration copy (the real folders until the owner detaches it; see
# test_taxonomy_v2.py). The temporary repositories start from them, so these tests hold after the owner's edits too.
# Git must not read the user's configuration or ask for an identity.
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.org", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vcs(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=GIT_ENV, check=True).stdout.strip()


# ---- A temporary repository with the package ---------------------------------------------------------------------------

_base: tempfile.TemporaryDirectory | None = None


def setUpModule():
    """One repository with scripts/taxonomy_v2.py and data/taxonomy-v2/ (derived state, without the 16 MB run), committed once;
    each test copies it. It runs the current integrare.py."""
    global _base
    _base = tempfile.TemporaryDirectory()
    repo = Path(_base.name) / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(HERE / "taxonomy_v2.py", repo / "scripts" / "taxonomy_v2.py")
    shutil.copytree(PACKAGE, repo / "data" / "taxonomy-v2", ignore=shutil.ignore_patterns("runs", "__pycache__"))
    shutil.copy2(REAL_PACKAGE / "integrare.py", repo / "data" / "taxonomy-v2" / "integrare.py")
    vcs(repo, "init", "-q", "-b", "main")
    vcs(repo, "add", "-A")
    vcs(repo, "commit", "-q", "-m", "base")


def tearDownModule():
    _base.cleanup()


class Repo:
    """A copy of the base repository in its own folder. The sealed run is linked in (read-only) and ignored by the repository."""

    def __init__(self, test: unittest.TestCase, own_run: bool = False):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(Path(_base.name) / "repo", self.root, symlinks=True)
        self.package = self.root / "data" / "taxonomy-v2"
        self.overlay = self.package / "integrare"
        if own_run:  # a writable copy, for the test that damages a sealed file
            shutil.copytree(RUNS, self.package / "runs")
        else:
            (self.package / "runs").symlink_to(RUNS, target_is_directory=True)
        with (self.root / ".git" / "info" / "exclude").open("a") as f:
            f.write("data/taxonomy-v2/runs\n")

    def script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.package / "integrare.py"), *args], cwd=self.root, capture_output=True, text=True, env=GIT_ENV)

    def commit(self, message: str = "change") -> str:
        vcs(self.root, "add", "-A")
        vcs(self.root, "commit", "-q", "-m", message)
        return vcs(self.root, "rev-parse", "HEAD")

    def pachet(self) -> dict:
        return json.loads((self.overlay / "pachet.json").read_text(encoding="utf-8"))

    def edit(self, name: str, fn):
        """Change the rows of one table of the overlay in place (fn returns nothing)."""
        header, rows = taxonomy_v2.read_table(self.overlay / name)
        fn(rows)
        with (self.overlay / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def edit_text(self, relative: str, fn):
        path = self.package / relative
        path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")


# ---- F1: detach the integration copy -----------------------------------------------------------------------------------------

class Detach(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self)

    def change_description(self):
        self.r.edit("intrari.csv", lambda rows: rows[0].update(descriere="Descriere scrisă de editor."))

    def detach(self) -> str:
        """Detach and commit the record. Returns the commit that the record names (HEAD before the detach)."""
        head = vcs(self.r.root, "rev-parse", "HEAD")
        done = self.r.script("--detach")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.r.commit("detach")
        return head

    def test_a_derived_copy_passes_and_an_edit_fails(self):
        self.assertEqual(self.r.script().returncode, 0)
        self.change_description()
        stale = self.r.script()
        self.assertEqual(stale.returncode, 1)
        self.assertIn("differs from a fresh assembly: intrari.csv", stale.stdout)

    def test_detach_records_head_and_the_date_and_changes_nothing_else(self):
        before = self.r.pachet()
        head = vcs(self.r.root, "rev-parse", "HEAD")
        self.assertEqual(self.r.script("--detach").returncode, 0)
        after = self.r.pachet()
        self.assertEqual(after["detached"]["commit"], head)
        self.assertRegex(after["detached"]["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertLessEqual(abs((date.fromisoformat(after["detached"]["date"]) - date.today()).days), 1)  # UTC date
        self.assertEqual({k: v for k, v in after.items() if k != "detached"}, before)
        self.assertEqual(list(after)[list(after).index("base") + 1], "detached")
        self.assertEqual((self.r.overlay / "pachet.json").read_text(encoding="utf-8")[-2:], "}\n")
        self.assertEqual(vcs(self.r.root, "status", "--porcelain", "--", "data/taxonomy-v2").split(), ["M", "data/taxonomy-v2/integrare/pachet.json"])

    def test_detach_refuses_uncommitted_changes(self):
        (self.r.overlay / "extra.txt").write_text("not committed\n", encoding="utf-8")
        done = self.r.script("--detach")
        self.assertEqual(done.returncode, 1)
        self.assertIn("uncommitted changes", done.stderr)
        self.assertNotIn("detached", self.r.pachet())

    def test_detach_refuses_an_overlay_that_is_not_a_fresh_assembly(self):
        self.change_description()
        self.r.commit()
        done = self.r.script("--detach")
        self.assertEqual(done.returncode, 1)
        self.assertIn("differs from a fresh assembly", done.stderr)
        self.assertNotIn("detached", self.r.pachet())

    def test_detach_twice_is_refused(self):
        self.detach()
        again = self.r.script("--detach")
        self.assertEqual(again.returncode, 1)
        self.assertIn("already detached", again.stderr)

    def test_the_check_ignores_editorial_edits_after_the_detach(self):
        commit = self.detach()
        self.change_description()
        self.r.edit("revizuire.csv", lambda rows: rows[0].update(stare="acceptat", decizie_editor="Decis de editor."))  # update() returns None
        self.r.commit("editorial edits")
        done = self.r.script()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn(f"detached since {commit[:7]}", done.stdout)
        self.assertIn("the seal of 2026-10-19-reasoned-evidence holds", done.stdout)
        self.assertIn("changed since: intrari.csv, revizuire.csv.", done.stdout)

    def test_the_check_reports_unchanged_files(self):
        self.detach()
        done = self.r.script()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("unchanged since", done.stdout)

    def test_the_check_fails_when_the_overlay_at_the_detach_commit_is_not_a_fresh_assembly(self):
        self.change_description()
        tampered = self.r.commit("an overlay edit before any detach")
        record = self.r.pachet()
        record["detached"] = {"commit": tampered, "date": "2026-10-20"}  # a hand-written record, as if --detach had accepted it
        (self.r.overlay / "pachet.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.r.commit("record")
        done = self.r.script()
        self.assertEqual(done.returncode, 1)
        self.assertIn("differ from a fresh assembly: intrari.csv", done.stdout)

    def test_the_check_names_a_commit_that_the_clone_does_not_have(self):
        record = self.r.pachet()
        record["detached"] = {"commit": "0123456789abcdef0123456789abcdef01234567", "date": "2026-10-20"}
        (self.r.overlay / "pachet.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        done = self.r.script()
        self.assertEqual(done.returncode, 1)
        self.assertIn("fetch the full history", done.stderr)

    def test_the_check_proves_the_seal_of_the_run(self):
        r = Repo(self, own_run=True)
        self.assertEqual(r.script("--detach").returncode, 0)
        r.commit("detach")
        response = next((r.package / "runs" / "2026-10-19-reasoned-evidence" / "responses").glob("*.json"))
        response.write_bytes(response.read_bytes() + b" ")
        done = r.script()
        self.assertEqual(done.returncode, 1)
        self.assertIn("sealed files changed", done.stderr)

    def test_write_is_refused_once_detached(self):
        self.detach()
        self.change_description()
        before = digest(self.r.overlay / "intrari.csv")
        done = self.r.script("--write")
        self.assertEqual(done.returncode, 1)
        self.assertIn("editorial", done.stderr)
        self.assertEqual(digest(self.r.overlay / "intrari.csv"), before)

    def test_write_and_detach_do_not_combine(self):
        self.assertEqual(self.r.script("--write", "--detach").returncode, 2)

    def test_the_baseline_does_not_apply_to_a_detached_overlay(self):
        """After the detach the editor may change the original text; --baseline compares with the initial snapshot only while derived."""
        c = Copy()
        self.addCleanup(c.close)
        c.edit("intrari.csv", lambda rows: rows[0].update(nume="Nume schimbat de editor"), c.overlay)
        self.assertTrue(any("original value differs in nume" in e for e in c.errors(c.overlay, baseline=True)))
        record = json.loads((c.overlay / "pachet.json").read_text(encoding="utf-8"))
        record["detached"] = {"commit": "0" * 40, "date": "2026-10-20"}
        (c.overlay / "pachet.json").write_text(json.dumps(record), encoding="utf-8")
        errors, summary = taxonomy_v2.check(c.overlay, baseline=True)
        self.assertEqual(errors, [])
        self.assertEqual(summary["detached"]["commit"], "0" * 40)

    def test_the_check_passes_on_the_real_overlay(self):
        """Derived (not yet detached): it matches a fresh assembly. Detached: the seal and the detach commit hold."""
        record = json.loads((REAL_OVERLAY / "pachet.json").read_text(encoding="utf-8")).get("detached")
        done = subprocess.run([sys.executable, str(REAL_PACKAGE / "integrare.py")], cwd=ROOT, capture_output=True, text=True)
        if record is None:
            self.assertIn("matches a fresh assembly", done.stdout)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


# ---- F2: one public root ---------------------------------------------------------------------------------------------------

class PublicRoot(unittest.TestCase):
    """build.py writes site/ only from PUBLIC_ROOT, and a v2 public root always passes the publication gate. The tests patch
    PUBLIC_ROOT and SITE inside the process; the repository's site/ is never the target."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name).resolve()
        self.site = self.dir / "site"
        shutil.copytree(ROOT / "site", self.site, ignore=shutil.ignore_patterns("proiect", "organizatie", "resursa", "data.json", "feed.xml", "llms.txt"))
        self.copy = Copy()
        self.addCleanup(self.copy.close)
        self.root = self.copy.root.resolve()

    def accept_everything(self):
        """The package root of the copy passes the publication gate: all accepted, no open high-priority item."""
        def accept(rows):
            for r in rows:
                r["clasificare_stare"] = "acceptat"

        def close(rows):
            for r in rows:
                if r["prioritate"] == "mare":
                    r.update(stare="amanat", decizie_editor="test")
        self.copy.edit("intrari.csv", accept)
        self.copy.edit("revizuire.csv", close)
        self.assertEqual(taxonomy_v2.check(self.root, publication=True)[0], [])

    def build(self, *args: str, public: Path | None = None) -> str:
        """build.main() with PUBLIC_ROOT and SITE patched. Returns the output; a refusal raises SystemExit."""
        out = io.StringIO()
        with mock.patch.object(build, "PUBLIC_ROOT", public if public is not None else self.root), mock.patch.object(build, "SITE", self.site), \
                mock.patch.object(sys, "argv", ["build.py", *args]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            build.main()
        return out.getvalue()

    def refused(self, *args: str, public: Path | None = None) -> str:
        with self.assertRaises(SystemExit) as raised:
            self.build(*args, public=public)
        return str(raised.exception)

    def site_digest(self) -> dict[str, str]:
        return {p.relative_to(self.site).as_posix(): digest(p) for p in self.site.rglob("*") if p.is_file()}

    def test_the_public_root_writes_the_public_site_with_the_gate(self):
        self.accept_everything()
        before = self.site_digest()
        self.build()
        data = json.loads((self.site / "data.json").read_text(encoding="utf-8"))
        self.assertTrue(data["schemaVersion"].startswith("2."))
        self.assertFalse(data["draft"])
        self.assertEqual(len(data["items"]), 122)
        self.assertNotEqual(self.site_digest(), before)

    def test_the_public_root_refuses_proposals_and_writes_nothing(self):
        before = self.site_digest()
        message = self.refused()
        self.assertIn("errors in", message)
        self.assertIn("--allow-draft", message)
        self.assertEqual(self.site_digest(), before)

    def test_an_open_high_priority_item_blocks_the_public_site(self):
        self.accept_everything()
        self.copy.edit("revizuire.csv", lambda rows: rows[0].update(stare="deschis", decizie_editor="", prioritate="mare"))  # update() returns None
        before = self.site_digest()
        self.assertIn("errors in", self.refused())
        self.assertEqual(self.site_digest(), before)

    def test_allow_draft_cannot_write_the_public_site(self):
        before = self.site_digest()
        for root_args in ((), ("--data-dir", str(self.root))):
            message = self.refused("--allow-draft", *root_args)
            self.assertIn("--allow-draft cannot write the public site", message)
        self.accept_everything()  # also not when the gate would pass
        self.assertIn("--allow-draft cannot write the public site", self.refused("--allow-draft"))
        self.assertEqual(self.site_digest(), before)

    def test_a_draft_preview_of_the_public_root_goes_to_another_folder(self):
        before = self.site_digest()
        out = self.dir / "preview"
        self.build("--allow-draft", "--site-dir", str(out))
        self.assertTrue(json.loads((out / "data.json").read_text(encoding="utf-8"))["draft"])
        self.assertEqual(self.site_digest(), before)

    def test_a_v2_root_that_is_not_the_public_root_cannot_write_site(self):
        other = Copy()
        self.addCleanup(other.close)
        before = self.site_digest()
        for public in (self.root, common.DATA):  # a v2 public root, and the v1 root that is the public root before the cutover
            for flags in ((), ("--allow-draft",)):
                message = self.refused("--data-dir", str(other.root.resolve()), *flags, public=public)
                self.assertIn("is not the public root", message)
                self.assertIn("separate --site-dir", message)
        self.assertEqual(self.site_digest(), before)

    def test_a_v1_root_cannot_write_site_once_the_public_root_is_v2(self):
        before = self.site_digest()
        message = self.refused("--data-dir", str(common.DATA))
        self.assertIn("is not the public root", message)
        self.assertEqual(self.site_digest(), before)

    def test_the_v1_public_root_builds_as_before(self):
        self.build(public=common.DATA)
        data = json.loads((self.site / "data.json").read_text(encoding="utf-8"))
        self.assertNotIn("schemaVersion", data)
        self.assertEqual(len(data["items"]), 122)
        self.assertIn("taxonomy", data)

    def test_every_script_defaults_to_the_public_root(self):
        for name in ("build", "validate", "profile", "search", "review", "sheets", "form"):
            lines = [l for l in (HERE / f"{name}.py").read_text(encoding="utf-8").splitlines() if 'add_argument("--data-dir"' in l]
            self.assertEqual(len(lines), 1, name)
            self.assertIn("default=PUBLIC_ROOT", lines[0], name)

    def test_the_loaders_default_to_the_public_root(self):
        self.assertEqual(common.load_catalogue.__defaults__, (common.PUBLIC_ROOT,))
        for fn in (common.data_schema, common.observation_paths, common.load_vocabulary, common.link_roles):
            self.assertEqual(fn.__defaults__, (common.PUBLIC_ROOT,), fn.__name__)


# ---- F3: scripts/cutover_v2.py ---------------------------------------------------------------------------------------------

class CutoverScript(unittest.TestCase):
    def mini(self) -> Path:
        """The files that the cutover reads, copied from the repository into a temporary tree."""
        if cutover_v2.is_applied(ROOT):
            self.skipTest("the cutover is applied in this repository")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel in cutover_v2.touched(ROOT):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, root / rel)
        return root

    def state(self, root: Path) -> dict[str, str]:
        return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}

    def test_the_edits_apply_to_the_repository_files(self):
        root = self.mini()
        changes = cutover_v2.compute(root)
        self.assertIn('PUBLIC_ROOT = DATA / "taxonomy-v2" / "integrare"', changes["scripts/common.py"].decode())
        self.assertEqual(changes["site/app.js"], (root / "site-v2/app.js").read_bytes())
        self.assertTrue(changes["site/style.css"].startswith((root / "site/style.css").read_bytes().rstrip(b"\n")))
        self.assertTrue(all(changes[p] is None for p in changes if p.startswith("site-v2/")))
        text = changes["scripts/build.py"].decode()
        self.assertNotIn("SITE_V2", text)
        self.assertNotIn("site-v2", text)
        compile(text, "build.py", "exec")
        compile(changes["scripts/common.py"].decode(), "common.py", "exec")
        flows = "".join(changes[f".github/workflows/{n}.yml"].decode() for n in ("pages", "sheets-pull", "sheets-push"))
        self.assertNotIn("proiecte.csv", flows)
        self.assertIn("--tabs v2-intrari", flows)
        validate = changes[".github/workflows/validate.yml"].decode()
        for gone in ("node --check site-v2/app.js", "cutover_v2", "Report the v2 publication gate"):
            self.assertNotIn(gone, validate)
        self.assertIn("validate.py --publication", validate)

    def test_apply_edits_the_tree_and_a_second_apply_is_refused(self):
        root = self.mini()
        changed = cutover_v2.apply(root)
        self.assertTrue(cutover_v2.is_applied(root))
        self.assertFalse((root / "site-v2").exists())
        self.assertEqual((root / "site/app.js").read_bytes(), (ROOT / "site-v2/app.js").read_bytes())
        self.assertIn("scripts/common.py", changed)
        before = self.state(root)
        with self.assertRaises(cutover_v2.Mismatch):
            cutover_v2.compute(root)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cutover_v2.cmd_apply(root), 1)
        self.assertIn("already applied", err.getvalue())
        self.assertEqual(self.state(root), before)

    def test_a_file_that_moved_on_stops_the_apply_and_names_the_edit(self):
        root = self.mini()
        pages = root / ".github/workflows/pages.yml"
        pages.write_text(pages.read_text(encoding="utf-8").replace("python3 scripts/validate.py", "python3 scripts/validate.py --other"), encoding="utf-8")
        before = self.state(root)
        with self.assertRaises(cutover_v2.Mismatch) as raised:
            cutover_v2.apply(root)
        self.assertIn(".github/workflows/pages.yml", str(raised.exception))
        self.assertEqual(self.state(root), before)  # nothing was written, also not the edits that matched

    def test_a_repeated_text_stops_the_apply(self):
        root = self.mini()
        pages = root / ".github/workflows/pages.yml"
        text = pages.read_text(encoding="utf-8")
        block = "          python3 scripts/validate.py\n          python3 scripts/build.py\n"
        self.assertEqual(text.count(block), 1)
        pages.write_text(text + block, encoding="utf-8")  # the text of an edit now occurs twice
        before = self.state(root)
        with self.assertRaises(cutover_v2.Mismatch) as raised:
            cutover_v2.apply(root)
        self.assertIn("occurs 2 times", str(raised.exception))
        self.assertEqual(self.state(root), before)

    def test_apply_on_the_real_repository_refuses_while_a_blocker_exists_and_changes_nothing(self):
        if cutover_v2.is_applied(ROOT):
            self.skipTest("the cutover is applied in this repository")
        blocked, _ = cutover_v2.blockers(ROOT)
        if not blocked:  # the real --apply would run: never from a test
            self.skipTest("no blocker is left, so --apply would change the repository")
        paths = cutover_v2.touched(ROOT)
        before = {p: digest(ROOT / p) for p in paths}
        done = subprocess.run([sys.executable, str(HERE / "cutover_v2.py"), "--apply"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("blockers", done.stderr)
        self.assertEqual({p: digest(ROOT / p) for p in paths}, before)
        self.assertTrue((ROOT / "site-v2" / "app.js").exists())
        self.assertNotIn(cutover_v2.APPLIED, (ROOT / "scripts/common.py").read_text(encoding="utf-8"))

    def test_plan_names_the_blockers_and_writes_nothing(self):
        if cutover_v2.is_applied(ROOT):
            self.skipTest("the cutover is applied in this repository")
        paths = cutover_v2.touched(ROOT)
        before = {p: digest(ROOT / p) for p in paths}
        done = subprocess.run([sys.executable, str(HERE / "cutover_v2.py"), "--plan"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Steps of --apply", done.stdout)
        self.assertEqual({p: digest(ROOT / p) for p in paths}, before)

    def test_the_blockers_follow_the_state_of_a_repository(self):
        """On a temporary repository: the four blockers of the gate, then each one resolved in turn."""
        r = Repo(self)
        kinds = ("entries are not acceptat", "open high-priority review items", "site.tabs.intrari is null", "is not detached")
        found, _ = cutover_v2.blockers(r.root)
        for kind in kinds:
            self.assertEqual(sum(kind in b for b in found), 1, (kind, found))
        self.assertEqual(len(found), 4, found)

        self.assertEqual(r.script("--detach").returncode, 0)
        r.commit("detach")
        found, _ = cutover_v2.blockers(r.root)
        self.assertFalse(any("detached" in b for b in found), found)

        def accept(rows):
            for row in rows:
                row["clasificare_stare"] = "acceptat"
                if row["slug"] == "incentru":  # the abstention needs a primary subject before it can be accepted
                    row["subiect_principal"], row["subiecte"] = "subiect:finante-publice", "subiect:finante-publice"
        r.edit("intrari.csv", accept)

        def close(rows):
            for row in rows:
                if row["prioritate"] == "mare" and row["stare"] == "deschis":
                    row.update(stare="amanat", decizie_editor="test")
        r.edit("revizuire.csv", close)
        found, _ = cutover_v2.blockers(r.root)
        self.assertEqual([b for b in found if "tabs.intrari" not in b], [], found)

        r.edit_text("setari.json", lambda text: text.replace('"intrari": null', '"intrari": 123456'))
        r.commit("editorial decisions")
        found, notes = cutover_v2.blockers(r.root)
        self.assertEqual(found, [])
        self.assertTrue(any("vocabulary proposals" in n for n in notes))

    def test_a_detached_overlay_that_no_longer_proves_its_derivation_is_a_blocker(self):
        r = Repo(self)
        self.assertEqual(r.script("--detach").returncode, 0)
        r.commit("detach")
        record = r.pachet()
        record["detached"]["commit"] = "0123456789abcdef0123456789abcdef01234567"
        (r.overlay / "pachet.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        found, _ = cutover_v2.blockers(r.root)
        self.assertTrue(any("no longer proves its derivation" in b for b in found), found)

    def test_rehearse_refuses_a_folder_inside_the_repository_or_a_folder_with_other_files(self):
        inside = ROOT / "docs" / "rehearsal-test"
        done = subprocess.run([sys.executable, str(HERE / "cutover_v2.py"), "--rehearse", str(inside)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("outside the repository", done.stderr)
        self.assertFalse(inside.exists())
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "keep.txt").write_text("mine\n", encoding="utf-8")
            done = subprocess.run([sys.executable, str(HERE / "cutover_v2.py"), "--rehearse", tmp], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(done.returncode, 1)
            self.assertIn("not a previous rehearsal", done.stderr)
            self.assertEqual((Path(tmp) / "keep.txt").read_text(encoding="utf-8"), "mine\n")

    def test_the_options_exclude_each_other(self):
        for args in ((), ("--plan", "--apply"), ("--apply", "--rehearse", "x")):
            done = subprocess.run([sys.executable, str(HERE / "cutover_v2.py"), *args], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(done.returncode, 2, args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
