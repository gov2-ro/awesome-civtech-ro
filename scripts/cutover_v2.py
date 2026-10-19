"""Move the public site from the v1 source (data/) to the taxonomy v2 integration copy. Stdlib only.

    python3 scripts/cutover_v2.py --plan              # the blockers and the steps; writes nothing
    python3 scripts/cutover_v2.py --apply             # edit the working tree; refuses while a blocker exists
    python3 scripts/cutover_v2.py --rehearse DIR      # --apply on a copy of the repository in DIR (outside it), with the
                                                      # blockers waived; then validate, build, smoke-test the scripts and run the tests

The cutover is one set of exact-text edits: PUBLIC_ROOT in scripts/common.py, the v2 browser code moved from site-v2/ into
site/ (app.js replaced, v2.css appended to style.css), the retired SITE_V2 copying in scripts/build.py, and the workflows
(the two Sheets workflows read the tab v2-intrari; Pages and PR validation use the publication gate). Each edit must match
exactly one place. When a file moved on, --apply and --rehearse stop and name the edit: update the edit in this file.
--apply never commits, pushes, deploys or calls Google. After it, run `python3 scripts/build.py` and commit.
The steps around it (the owner's decisions, the Sheet tab, the Form, the checks after deploy, the rollback) are in
docs/briefs/cutover-taxonomy-v2.md.

--rehearse keeps this script true: CI runs it on every change. The copy is a clone of the repository's history with the
working-tree files laid over it, so a detached overlay still finds its detach commit. The rehearsal waives the blockers and
the publication gate only inside the copy: it builds the copy's public site with the gate's check switched off.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import taxonomy_v2  # noqa: E402

OVERLAY = "data/taxonomy-v2/integrare"  # the integration copy that becomes the public root
APPLIED = 'PUBLIC_ROOT = DATA / "taxonomy-v2" / "integrare"'
MARK = ".cutover-rehearsal"  # in a rehearsal folder: it may be deleted and made again


@dataclass(frozen=True)
class Edit:
    path: str
    old: str
    new: str
    why: str  # one line for --plan


EDITS = [
    Edit("scripts/common.py", '''# The data root that feeds the public site, and the default --data-dir of every script. It is the v1 root until the
# cutover; scripts/cutover_v2.py then points it at the taxonomy v2 integration copy. Only this root may write site/.
PUBLIC_ROOT = DATA
''', '''# The data root that feeds the public site, and the default --data-dir of every script. Since the cutover it is the
# taxonomy v2 integration copy (before, the v1 root data/). Only this root may write site/.
PUBLIC_ROOT = DATA / "taxonomy-v2" / "integrare"
''', "PUBLIC_ROOT becomes the integration copy: every script reads it by default, and only it may write site/"),
    Edit("scripts/build.py", '''Before the cutover, a v2 preview copies the v2 browser code from site-v2/ over the template.
''', "", "build.py: the docstring drops the site-v2/ sentence"),
    Edit("scripts/build.py", '''SITE_V2 = ROOT / "site-v2"  # the v2 browser code; a v2 build copies it over the template in its --site-dir
''', "", "build.py: SITE_V2 is retired"),
    Edit("scripts/build.py", '''ASSET_LINKS = {"style.css": r'(href="style\\.css)(\\?v=[0-9a-f]+)?(")', "app.js": r'(src="app\\.js)(\\?v=[0-9a-f]+)?(")',
               "v2.css": r'(href="v2\\.css)(\\?v=[0-9a-f]+)?(")'}
''', '''ASSET_LINKS = {"style.css": r'(href="style\\.css)(\\?v=[0-9a-f]+)?(")', "app.js": r'(src="app\\.js)(\\?v=[0-9a-f]+)?(")'}
''', "build.py: v2.css is no separate asset"),
    Edit("scripts/build.py", "site-v2/app.js has its own switch.", "site/app.js has its own switch.",
         "build.py: the comment names site/app.js"),
    Edit("scripts/build.py", '''def prepare_site(site: Path, v2: bool):
    """Copy the template, assets and images of site/ into a separate output folder (and the v2 browser code over them),
    so that the build there never changes site/.''', '''def prepare_site(site: Path):
    """Copy the template, assets and images of site/ into a separate output folder,
    so that the build there never changes site/.''', "build.py: prepare_site copies site/ only"),
    Edit("scripts/build.py", '''    if v2:
        for src in SITE_V2.iterdir():
            shutil.copy2(src, site / src.name)
        index = site / "index.html"
        doc = index.read_text(encoding="utf-8")
        if 'href="v2.css' not in doc:
            link = re.search(r'<link rel="stylesheet" href="style\\.css[^"]*">', doc).group(0)
            index.write_text(doc.replace(link, link + '\\n<link rel="stylesheet" href="v2.css">'), encoding="utf-8")
''', "", "build.py: the copy of site-v2/ over the template is retired"),
    Edit("scripts/build.py", "        prepare_site(site, v2)\n", "        prepare_site(site)\n", "build.py: the call follows"),
    Edit(".github/workflows/pages.yml", '''          python3 scripts/validate.py
          python3 scripts/build.py
''', '''          python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare --publication
          python3 scripts/build.py --data-dir data/taxonomy-v2/integrare
''', "pages.yml: validate with the publication gate, build the integration copy"),
    Edit(".github/workflows/sheets-pull.yml", '''          uv run scripts/sheets.py diff > "$RUNNER_TEMP/diff.txt"''',
         '''          uv run scripts/sheets.py diff --data-dir data/taxonomy-v2/integrare --tabs v2-intrari > "$RUNNER_TEMP/diff.txt"''',
         "sheets-pull.yml: diff reads the tab v2-intrari"),
    Edit(".github/workflows/sheets-pull.yml", '''          uv run scripts/sheets.py pull || code=$?''',
         '''          uv run scripts/sheets.py pull --data-dir data/taxonomy-v2/integrare --tabs v2-intrari || code=$?''',
         "sheets-pull.yml: pull writes intrari.csv"),
    Edit(".github/workflows/sheets-pull.yml", "          if git diff --quiet -- data/proiecte.csv data/orgs.csv; then",
         "          if git diff --quiet -- data/taxonomy-v2/integrare/intrari.csv; then", "sheets-pull.yml: the changed file is intrari.csv"),
    Edit(".github/workflows/sheets-pull.yml", '''          GITHUB_ACTIONS=false python3 scripts/validate.py > "$RUNNER_TEMP/validate.txt" 2>&1''',
         '''          GITHUB_ACTIONS=false python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare --publication > "$RUNNER_TEMP/validate.txt" 2>&1''',
         "sheets-pull.yml: validate with the publication gate"),
    Edit(".github/workflows/sheets-pull.yml", '''          python3 scripts/build.py > "$RUNNER_TEMP/build.txt" 2>&1''',
         '''          python3 scripts/build.py --data-dir data/taxonomy-v2/integrare > "$RUNNER_TEMP/build.txt" 2>&1''',
         "sheets-pull.yml: build the integration copy"),
    Edit(".github/workflows/sheets-pull.yml", "          git add data/proiecte.csv data/orgs.csv\n", "          git add data/taxonomy-v2/integrare/intrari.csv\n",
         "sheets-pull.yml: the pull request carries intrari.csv"),
    Edit(".github/workflows/sheets-push.yml", "# Repo -> Google Sheet. After a push to main that changes proiecte.csv or orgs.csv, rewrites both tabs.",
         "# Repo -> Google Sheet. After a push to main that changes intrari.csv of the integration copy, rewrites the tab v2-intrari.",
         "sheets-push.yml: the comment"),
    Edit(".github/workflows/sheets-push.yml", '''    paths: ["data/proiecte.csv", "data/orgs.csv"]''', '''    paths: ["data/taxonomy-v2/integrare/intrari.csv"]''',
         "sheets-push.yml: the trigger is intrari.csv"),
    Edit(".github/workflows/sheets-push.yml", '''          uv run scripts/sheets.py push "${args[@]}"''',
         '''          uv run scripts/sheets.py push --data-dir data/taxonomy-v2/integrare --tabs v2-intrari "${args[@]}"''',
         "sheets-push.yml: push writes the tab v2-intrari"),
    Edit(".github/workflows/validate.yml", '''# v1 (data/) is the public source: its validation and build block. Taxonomy v2 is a preview until the cutover:
# its package checks, tests and preview build block too, but its publication gate only reports.
# The cutover rehearsal (scripts/cutover_v2.py --rehearse) blocks as well: it keeps the one-command cutover working.
''', '''# The public source is the taxonomy v2 integration copy: its publication gate, build, package checks and tests block.
''', "validate.yml: the header comment"),
    Edit(".github/workflows/validate.yml", '''      - name: Check proiecte.csv and orgs.csv (v1)
        run: python3 scripts/validate.py
      - name: Build site data (v1)
        run: python3 scripts/build.py
''', '''      - name: Check the public data root with the publication gate
        run: python3 scripts/validate.py --publication
      - name: Build the public site
        run: python3 scripts/build.py
''', "validate.yml: PR validation uses the publication gate on the public root"),
    Edit(".github/workflows/validate.yml", "          python3 data/taxonomy-v2/validate.py --baseline > /dev/null\n",
         "          python3 data/taxonomy-v2/validate.py > /dev/null\n",
         "validate.yml: the package baseline compares observatii/ with source/; live enrichment changes observatii/"),
    Edit(".github/workflows/validate.yml", '''      - name: Report the v2 publication gate (does not block)
        run: |
          set +e
          GITHUB_ACTIONS=false python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare --publication > "$RUNNER_TEMP/gate.txt" 2>&1
          code=$?
          {
            echo "### Taxonomy v2: publication gate (exit $code)"
            echo
            echo "The v2 source can replace v1 only when this gate passes. Open items:"
            echo
            echo '```'
            grep -c "publication:" "$RUNNER_TEMP/gate.txt" || true
            tail -n 1 "$RUNNER_TEMP/gate.txt"
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
          exit 0
''', "", "validate.yml: the report-only gate step goes (the public build blocks on the gate)"),
    Edit(".github/workflows/validate.yml", '''      - name: Rehearse the v2 cutover on a copy
        run: |
          bash <(curl -fsSL https://raw.githubusercontent.com/rhysd/actionlint/v1.7.12/scripts/download-actionlint.bash) 1.7.12
          ACTIONLINT="$PWD/actionlint" python3 scripts/cutover_v2.py --rehearse "$RUNNER_TEMP/rehearsal"
''', "", "validate.yml: the rehearsal step goes"),
    Edit(".github/workflows/validate.yml", "          node --check site-v2/app.js\n", "", "validate.yml: site-v2/ no longer exists"),
]


# --- State and blockers ------------------------------------------------------------------------------------------------------

def read(root: Path, rel: str) -> str:
    return (root / rel).read_bytes().decode("utf-8")


def is_applied(root: Path = ROOT) -> bool:
    return APPLIED in read(root, "scripts/common.py")


def touched(root: Path = ROOT) -> list[str]:
    """The files that --apply writes or deletes, relative to the repository."""
    paths = {e.path for e in EDITS} | {"site/app.js", "site/style.css"}
    site_v2 = root / "site-v2"
    paths |= {p.relative_to(root).as_posix() for p in site_v2.rglob("*") if p.is_file()} if site_v2.is_dir() else set()
    return sorted(paths)


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    return r.returncode, (r.stdout + r.stderr).strip()


def blockers(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """(blockers, notices) for the repository at `root`. A blocker stops --apply; a notice only informs the owner."""
    blocked, notes = [], []
    overlay = root / OVERLAY
    errors, summary = taxonomy_v2.check(overlay, publication=True)
    states = [e for e in errors if e.startswith("publication:") and "classification state" in e]
    items = [e for e in errors if e.startswith("publication:") and "open high-priority review item" in e]
    others = [e for e in errors if not e.startswith("publication:")]
    if states:
        counts = ", ".join(f"{n} {s}" for s, n in sorted(summary["classification_states"].items()))
        blocked.append(f"publication gate: {len(states)} of {summary['entries']} entries are not acceptat ({counts})")
    if items:
        ids = ", ".join(sorted(e.rsplit(" ", 1)[-1] for e in items))
        blocked.append(f"publication gate: {len(items)} open high-priority review items ({ids})")
    if others:
        blocked.append(f"{len(others)} structural errors in {OVERLAY}; first: {others[0]}")
    setari = json.loads((root / "data/taxonomy-v2/setari.json").read_text(encoding="utf-8"))
    if setari.get("site", {}).get("tabs", {}).get("intrari") is None:
        blocked.append("data/taxonomy-v2/setari.json: site.tabs.intrari is null (push the tab v2-intrari, then set its gid)")
    pachet = json.loads((root / OVERLAY / "pachet.json").read_text(encoding="utf-8"))
    if not pachet.get("detached"):
        blocked.append(f"{OVERLAY} is not detached (the owner runs `python3 data/taxonomy-v2/integrare.py --detach` and commits)")
    else:
        code, text = run([sys.executable, "data/taxonomy-v2/integrare.py"], root)
        if code:
            blocked.append(f"integrare.py: the detached overlay no longer proves its derivation: {text.splitlines()[-1] if text else code}")
    dirty = git_dirty(root)
    if dirty:
        blocked.append(f"uncommitted changes in files that the cutover edits: {', '.join(dirty)} (commit or restore them first, so that the repository can undo the cutover)")

    rows = taxonomy_v2.read_table(overlay / "intrari.csv")[1]
    bare = sum(not r["descriere_scurta"].strip() and not r["descriere"].strip() for r in rows)
    if bare:
        notes.append(f"{bare} of {len(rows)} entries have neither descriere_scurta nor descriere (the owner decides what the public page shows)")
    proposals = [r for r in taxonomy_v2.read_table(overlay / "propuneri-vocabular.csv")[1] if r["stare"] == "propus"]
    if proposals:
        notes.append(f"{len(proposals)} vocabulary proposals have the state propus ({', '.join(r['id'] for r in proposals)}); the owner accepts or rejects them")
    return blocked, notes


def git_dirty(root: Path) -> list[str]:
    """The files of touched() with uncommitted changes. [] outside a repository."""
    if not (root / ".git").exists():
        return []
    code, text = run(["git", "status", "--porcelain", "--", *touched(root)], root)
    return [line.split(None, 1)[1] for line in text.splitlines()] if code == 0 else []


# --- The edits ---------------------------------------------------------------------------------------------------------------

class Mismatch(Exception):
    """An edit does not match exactly one place. The tree is unchanged."""


def compute(root: Path) -> dict[str, bytes | None]:
    """The new content of every file that --apply changes (None: delete it). Raises Mismatch, and writes nothing."""
    texts: dict[str, str] = {}
    problems = []
    for e in EDITS:
        try:
            text = texts[e.path] if e.path in texts else read(root, e.path)
        except FileNotFoundError:
            problems.append(f"{e.path}: the file is missing")
            continue
        n = text.count(e.old)
        if n != 1:
            problems.append(f"{e.path}: the text to replace occurs {n} times, not once: {e.old.strip().splitlines()[0][:90]!r}")
        else:
            texts[e.path] = text.replace(e.old, e.new)
    app, css = root / "site-v2/app.js", root / "site-v2/v2.css"
    if not app.is_file() or not css.is_file():
        problems.append("site-v2/app.js or site-v2/v2.css is missing")
    changes: dict[str, bytes | None] = {path: text.encode("utf-8") for path, text in texts.items()}
    if not problems:
        style = read(root, "site/style.css")
        extra = css.read_bytes().decode("utf-8")
        head, _, rest = extra.partition("\n")
        if not head.startswith("/* Additions for the v2 browser code"):
            problems.append("site-v2/v2.css: the first line is not the expected comment")
        elif extra.strip() in style:
            problems.append("site/style.css already holds the rules of site-v2/v2.css")
        else:
            merged = "/* Taxonomy v2 additions (from site-v2/v2.css, merged at the cutover). The colours are style.css tokens. */\n" + rest
            changes["site/style.css"] = (style.rstrip("\n") + "\n\n" + merged).encode("utf-8")
            changes["site/app.js"] = app.read_bytes()
            for p in (root / "site-v2").rglob("*"):
                if p.is_file():
                    changes[p.relative_to(root).as_posix()] = None
    if problems:
        raise Mismatch("\n".join(problems))
    return changes


def write_changes(root: Path, changes: dict[str, bytes | None]):
    for rel, content in changes.items():
        path = root / rel
        if content is None:
            path.unlink()
        else:
            path.write_bytes(content)
    shutil.rmtree(root / "site-v2", ignore_errors=True)  # only empty folders are left


def apply(root: Path) -> list[str]:
    """Edit the tree at `root`; return the changed files. The caller has checked the blockers."""
    changes = compute(root)
    write_changes(root, changes)
    return sorted(changes)


# --- --plan, --apply -------------------------------------------------------------------------------------------------------------

def cmd_plan(root: Path = ROOT) -> int:
    if is_applied(root):
        print("The cutover is applied: PUBLIC_ROOT is the integration copy. Nothing to plan.")
        return 0
    blocked, notes = blockers(root)
    print("Cutover to taxonomy v2: the public site moves from data/ to data/taxonomy-v2/integrare.")
    print(f"\nBlockers ({len(blocked)}): --apply refuses while any exists." if blocked else "\nNo blockers: --apply can run.")
    for n, b in enumerate(blocked, 1):
        print(f"  {n}. {b}")
    if notes:
        print("\nNotices (they do not block):")
        for n in notes:
            print(f"  - {n}")
    print("\nSteps of --apply (it edits the working tree only; it never commits, pushes, deploys or calls Google):")
    seen = []
    for e in EDITS:
        seen.append(e.why)
        print(f"  {len(seen)}. {e.why}")
    print(f"  {len(seen) + 1}. site/app.js is replaced by site-v2/app.js")
    print(f"  {len(seen) + 2}. the rules of site-v2/v2.css are appended to site/style.css")
    print(f"  {len(seen) + 3}. site-v2/ is removed")
    print("\nAfter --apply: run `python3 scripts/build.py` (it needs the gate to pass and stamps site/index.html), then commit.")
    print("--apply does not edit the documentation. Update by hand: README.md, CONTRIBUTING.md, AGENTS.md, CLAUDE.md,")
    print("docs/DATA-SCHEMA.md, docs/ARCHITECTURE.md, docs/METODOLOGIE.md (paths of site-v2/), docs/specs/taxonomy-v2.md.")
    print("The full procedure is in docs/briefs/cutover-taxonomy-v2.md.")
    return 0


def cmd_apply(root: Path = ROOT) -> int:
    if is_applied(root):
        print("The cutover is already applied: PUBLIC_ROOT is the integration copy. Nothing was changed.", file=sys.stderr)
        return 1
    blocked, _ = blockers(root)
    if blocked:
        print(f"Refused: {len(blocked)} blockers. Nothing was changed.", file=sys.stderr)
        for b in blocked:
            print(f"  - {b}", file=sys.stderr)
        return 1
    try:
        changed = apply(root)
    except Mismatch as e:
        print(f"Refused: the files moved on since this script was written. Nothing was changed.\n{e}", file=sys.stderr)
        return 1
    print(f"Applied: {len(changed)} files changed or removed in the working tree.")
    print("Next: python3 scripts/build.py, then check `git status` and commit. Rollback: revert that commit.")
    return 0


# --- --rehearse --------------------------------------------------------------------------------------------------------------------

class Report:
    """The result lines of a rehearsal."""

    def __init__(self):
        self.failed = False

    def step(self, ok: bool | None, name: str, detail: str = ""):
        mark = {True: "ok  ", False: "FAIL", None: "skip"}[ok]
        self.failed |= ok is False
        print(f"{mark} {name}" + (f": {detail}" if detail else ""), flush=True)

    def output(self, text: str, lines: int = 12):
        for line in text.splitlines()[-lines:]:
            print(f"       {line}")


def copy_repository(dest: Path):
    """dest = a clone of the repository (its history, so that a detach commit resolves) with the tracked files of the working
    tree laid over it, including uncommitted edits. Needs a checkout with .git."""
    if not (ROOT / ".git").exists():
        raise SystemExit("--rehearse needs a repository checkout (.git)")
    code, text = run(["git", "clone", "--quiet", "--no-checkout", "--shared", str(ROOT), str(dest)], ROOT)
    if code:
        raise SystemExit(f"cannot clone the repository into {dest}: {text}")
    names = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode().split("\0")
    for name in filter(None, names):
        src = ROOT / name
        if src.is_file():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / name, follow_symlinks=False)
    run(["git", "reset", "--quiet"], dest)  # the index follows HEAD: `git status` in the copy lists what differs
    (dest / MARK).write_text("A rehearsal of scripts/cutover_v2.py. Safe to delete.\n", encoding="utf-8")


# The public build of the copy with the publication gate's check switched off. It runs the unchanged main() of build.py (the
# default root, the default site/), so only the gate differs from the real build.
WAIVED_BUILD = """
import sys
sys.path.insert(0, "scripts")
import taxonomy_v2, build
real = taxonomy_v2.check
taxonomy_v2.check = lambda root, **kw: real(root, **{**kw, "publication": False})
sys.argv = ["build.py"]
build.main()
"""

SHEETS_TABS = """
import sys
sys.path.insert(0, "scripts")
import common, sheets
print(" ".join(t.name for t in sheets.tabs_for(common.PUBLIC_ROOT)))
"""


def find_actionlint() -> tuple[Path | None, str]:
    wanted = os.environ.get("ACTIONLINT", "").strip()
    if wanted:
        path = Path(wanted).expanduser().resolve()
        return (path, "") if path.is_file() and os.access(path, os.X_OK) else (None, f"ACTIONLINT={wanted} is not an executable file")
    found = shutil.which("actionlint")
    return (Path(found), "") if found else (None, "actionlint is not installed (set ACTIONLINT to a binary)")


def rehearse(dest: Path) -> int:
    dest = dest.expanduser().resolve()
    if dest == ROOT or dest.is_relative_to(ROOT) or ROOT.is_relative_to(dest):
        print(f"{dest}: the rehearsal folder must be outside the repository", file=sys.stderr)
        return 1
    if dest.exists() and any(dest.iterdir()):
        if not (dest / MARK).exists():
            print(f"{dest} is not empty and is not a previous rehearsal: choose a new folder", file=sys.stderr)
            return 1
        shutil.rmtree(dest)
    if is_applied(ROOT):
        print("The cutover is applied; there is nothing to rehearse.")
        return 0
    report = Report()
    dest.parent.mkdir(parents=True, exist_ok=True)
    guarded = {p: (ROOT / p).read_bytes() for p in touched(ROOT) if (ROOT / p).is_file()}
    blocked, _ = blockers(ROOT)
    copy_repository(dest)
    report.step(True, "copy", f"{dest} (history of the repository and its tracked files)")
    if blocked:
        report.step(None, "blockers waived in the copy", f"{len(blocked)}: " + "; ".join(b.split(" (")[0] for b in blocked))
    py = sys.executable

    try:
        changed = apply(dest)
    except Mismatch as e:
        report.step(False, "apply", "an edit does not match the files")
        report.output(str(e), 30)
        return 1
    report.step(True, "apply", f"{len(EDITS)} text edits, site/app.js replaced, v2.css appended, site-v2/ removed; {len(changed)} files")
    again = subprocess.run([py, "scripts/cutover_v2.py", "--apply"], cwd=dest, capture_output=True, text=True)
    report.step(again.returncode != 0 and "already applied" in again.stderr, "apply twice is refused")
    snapshot_state(dest, report)

    code, text = run([py, "scripts/validate.py"], dest)
    report.step(code == 0, "validate.py (default root, draft rules)", text.splitlines()[-1] if text else "")
    if code:
        report.output(text)
    gate_code, gate_text = run([py, "scripts/validate.py", "--publication"], dest, {"GITHUB_ACTIONS": "false"})
    waived = gate_code != 0
    if waived:
        report.step(None, "validate.py --publication (the gate)", f"fails in the copy, as in the repository: {len(gate_text.splitlines()) - 1} messages; waived for the build")
    else:
        report.step(True, "validate.py --publication (the gate)", "passes")
    refused = run([py, "scripts/build.py", "--allow-draft"], dest)
    report.step(refused[0] != 0 and "cannot write the public site" in refused[1], "build.py --allow-draft cannot write site/")
    if waived:
        refused = run([py, "scripts/build.py"], dest)
        report.step(refused[0] != 0, "build.py with the gate refuses the proposals", "(as the public build does)")
        code, text = run([py, "-c", WAIVED_BUILD], dest)
    else:
        code, text = run([py, "scripts/build.py"], dest)
    report.step(code == 0, "build.py into the copy's site/" + (" (gate waived)" if waived else ""), text.splitlines()[0][:110] if text else "")
    if code:
        report.output(text)
    else:
        check_site(dest, report)

    slug = taxonomy_v2.read_table(dest / OVERLAY / "intrari.csv")[1][0]["slug"]
    for name, cmd in (("search.py --dry-run", [py, "scripts/search.py", "--dry-run", "--only", slug]),
                      ("review.py --dry-run", [py, "scripts/review.py", "--dry-run", "--only", slug]),
                      ("form.py (the plan)", [py, "scripts/form.py"])):
        code, text = run(cmd, dest)
        report.step(code == 0, f"{name} on the default root", "" if code == 0 else text.splitlines()[-1] if text else str(code))
        if code:
            report.output(text)
    code, text = run([py, "-c", SHEETS_TABS], dest)
    report.step(code == 0 and text.split() == ["v2-intrari"], "sheets.py tabs on the default root", text.splitlines()[-1] if text else "")
    if code:
        report.output(text)

    code, text = run([py, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py"], dest)
    tail = [line for line in text.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    report.step(code == 0, "unit tests in the copy", ", ".join(tail))
    if code:  # the names of the failing tests; their messages can be long
        report.output("\n".join(line[:160] for line in text.splitlines() if line.startswith(("FAIL:", "ERROR:"))) or text[-1500:], 30)

    ruby = shutil.which("ruby")
    if ruby:  # Ruby ships a YAML parser; the standard library of Python has none
        flows = sorted(str(p) for p in (dest / ".github/workflows").glob("*.yml"))
        code, text = run([ruby, "-ryaml", "-e", "ARGV.each { |f| YAML.load_file(f) }", *flows], dest)
        report.step(code == 0, "the changed workflows parse as YAML", f"{len(flows)} files" if code == 0 else text.splitlines()[0][:150])
    else:
        report.step(None, "the changed workflows parse as YAML", "ruby is not installed")
    lint = find_actionlint()
    if lint[0] is None:
        report.step(None, "actionlint on the changed workflows", lint[1])
    else:
        flows = sorted(str(p) for p in (dest / ".github/workflows").glob("*.yml"))
        code, text = run([str(lint[0]), *flows], dest)
        report.step(code == 0, "actionlint on the changed workflows", f"{len(flows)} files" if code == 0 else "")
        if code:
            report.output(text, 30)
    unchanged = all((ROOT / p).read_bytes() == data for p, data in guarded.items()) and (ROOT / "site-v2").is_dir()
    report.step(unchanged, "the repository itself is unchanged")
    print("\nThe rehearsal " + ("FAILED." if report.failed else f"passed. The copy is in {dest}."))
    return 1 if report.failed else 0


def snapshot_state(dest: Path, report: Report):
    """Static checks of the changed copy: the moved browser code, the retired paths, the workflows."""
    original = (ROOT / "site-v2/app.js").read_bytes()
    css = read(dest, "site/style.css")
    sheets = read(dest, ".github/workflows/sheets-pull.yml") + read(dest, ".github/workflows/sheets-push.yml") + read(dest, ".github/workflows/pages.yml")
    report.step((dest / "site/app.js").read_bytes() == original and not (dest / "site-v2").exists(), "site/app.js is the v2 browser code; site-v2/ is gone")
    report.step(css.count("{") == css.count("}") and "Taxonomy v2 additions" in css, "site/style.css holds the v2 rules with balanced braces")
    report.step("proiecte.csv" not in sheets and "data/orgs.csv" not in sheets and sheets.count("--data-dir data/taxonomy-v2/integrare") >= 6,
                "the Sheets and Pages workflows name the integration copy, not the v1 CSVs")
    node = shutil.which("node")
    if node:
        code, text = run([node, "--check", "site/app.js"], dest)
        report.step(code == 0, "node --check site/app.js", text.splitlines()[0] if text else "")
    else:
        report.step(None, "node --check site/app.js", "node is not installed")


def check_site(dest: Path, report: Report):
    """The built public site of the copy: the v2 payload, the entry pages, and the stamped asset links."""
    import hashlib
    data = json.loads((dest / "site/data.json").read_text(encoding="utf-8"))
    entries = len(taxonomy_v2.read_table(dest / OVERLAY / "intrari.csv")[1])
    pages = sum(1 for k in ("proiect", "organizatie", "resursa") for _ in (dest / "site" / k).glob("*/index.html"))
    report.step(str(data.get("schemaVersion", "")).startswith("2.") and len(data["items"]) == entries and pages == entries,
                "site/ holds the v2 payload and one page per entry", f"schemaVersion {data.get('schemaVersion')}, {len(data['items'])} items, {pages} pages")
    index = read(dest, "site/index.html")
    stamp = hashlib.sha1((dest / "site/app.js").read_bytes()).hexdigest()[:10]
    report.step(f'src="app.js?v={stamp}"' in index and "v2.css" not in index, "site/index.html is stamped with the hash of the new app.js")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--plan", action="store_true", help="print the blockers and the steps; write nothing")
    what.add_argument("--apply", action="store_true", help="edit the working tree (refused while a blocker exists)")
    what.add_argument("--rehearse", type=Path, metavar="DIR", help="apply on a copy of the repository in DIR, then check it")
    args = parser.parse_args()
    if args.plan:
        return cmd_plan()
    if args.apply:
        return cmd_apply()
    return rehearse(args.rehearse)


if __name__ == "__main__":
    sys.exit(main())
