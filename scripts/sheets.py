# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6.1", "google-auth>=2.30"]
# ///
"""Two-way sync between the Google Sheet and the CSVs of a data root.

    uv run scripts/sheets.py diff                   # what pull would write, what the repo has that the Sheet lacks, conflicts; no writes
    uv run scripts/sheets.py pull [--check]         # merge the Sheet's tabs into the CSVs (three-way); --check: then validate, exit 1 on errors
    uv run scripts/sheets.py push                   # write the CSVs to the Sheet, unless it holds edits not yet in the repo
    uv run scripts/sheets.py push --force           # no check: the Sheet becomes a copy of the CSVs
    uv run scripts/sheets.py diff|pull|push --since <ref>    # use the CSVs at <ref> as the base, not the sync marker
    uv run scripts/sheets.py push --data-dir data/taxonomy-v2/integrare   # a taxonomy v2 root: tab `v2-intrari` (--tabs v2-intrari,v2-revizuire)

Needs SHEET_ID and a service-account key: GOOGLE_SA_KEY (the JSON text) or GOOGLE_APPLICATION_CREDENTIALS (a path).
The repo is the source of truth. `diff` and `pull` read the Sheet; `push` overwrites it, so it checks first.

Data roots. The default root is data/ (v1): tabs `proiecte` and `orgs`. A taxonomy v2 root (--data-dir) uses new tabs only:
`v2-intrari` mirrors intrari.csv, `v2-revizuire` mirrors revizuire.csv; headers come from schema.json. A v2 root refuses
to touch the live v1 tabs, and a v1 root refuses the v2 tabs.

The sync marker is the tab `_sync` of the Sheet, one row per synced tab: tab, commit, SHA-256 of the CSV text pushed,
time. `push` writes it last, and only when the CSV it pushed equals the file at HEAD. It is the base of a three-way
comparison: `pull` takes a cell from the Sheet when only the Sheet changed it since the marker, keeps the repo's value
when only the repo changed it, and stops with exit 3 and the conflict list when both changed it differently.
`push` stops with exit 3 when the Sheet holds a cell that differs from the marker's and from the current CSV.
Without a marker the base is missing: `pull` copies the Sheet over the CSV (two-way, with a warning), and `push` compares
the Sheet with the current CSV. `--since <ref>` replaces the marker for one run. Delete a row of `_sync` to forget a tab.

Exit codes: 0 done, 1 error (or, with --check, validation errors after the CSVs were written), 3 the Sheet holds edits
not yet in the repo (`push`) or both sides changed a cell (`pull`); nothing was written.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from common import DATA, ORGS_COLS, PROIECTE_COLS, ROOT, data_schema, load_env, write_csv

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PENDING = 3  # exit code: the Sheet holds edits that are not in the repo, or both sides changed a cell
SYNC_TAB = "_sync"
SYNC_COLS = ["tab", "commit", "sha256", "time"]
V1_TABS = ("proiecte", "orgs")  # the live tabs of the v1 root
V2_TABS = ("v2-intrari", "v2-revizuire")  # the tabs of a v2 root; `push` may create them
SUGGEST_MAX = 40  # a drop-down that only suggests (a cell may hold several values) stays out when the list is longer


class SheetError(Exception):
    """The Sheet or a CSV does not have the expected shape."""


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short(commit: str) -> str:
    return commit[:7]


# ---- Tabs ------------------------------------------------------------------------------------------------------

@dataclass
class Tab:
    name: str  # the tab's title in the Sheet
    path: Path  # the CSV of the data root
    cols: list[str]  # row 1 of the tab, in this order
    key: str = "slug"  # the column that identifies a row
    label: str = "nume"  # the column shown next to a key in a diff
    table: str = ""  # v2: the table's name in schema.json (drop-downs); empty for v1


def display(path: Path) -> str:
    """A path as the messages show it: relative to the repo when it is inside."""
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def tabs_for(root: Path, names: list[str] | None = None) -> list[Tab]:
    """The tabs a data root may use. A v2 root never gets a v1 tab, and the other way round."""
    schema = data_schema(root)
    if schema == "v1":
        known = {"proiecte": Tab("proiecte", root / "proiecte.csv", list(PROIECTE_COLS)),
                 "orgs": Tab("orgs", root / "orgs.csv", list(ORGS_COLS))}
        default = list(V1_TABS)
    else:
        from taxonomy_v2 import Files
        files = Files(root)
        headers = json.loads(files.path("schema.json").read_text(encoding="utf-8"))["headers"]
        known = {"v2-intrari": Tab("v2-intrari", files.path("intrari.csv"), list(headers["intrari.csv"]), table="intrari.csv"),
                 "v2-revizuire": Tab("v2-revizuire", files.path("revizuire.csv"), list(headers["revizuire.csv"]), key="id",
                                     label="slug", table="revizuire.csv")}
        default = ["v2-intrari"]
    for name in names or []:
        if name not in known:
            other = V2_TABS if schema == "v1" else V1_TABS
            raise SheetError(f"tab '{name}' is refused: a {schema} data root uses only the tabs {', '.join(known)}"
                             + (f" (never {', '.join(other)})" if name in other or name in (SYNC_TAB, "propuneri") else ""))
    return [known[n] for n in dict.fromkeys(names or default)]


# ---- Sheet access ----------------------------------------------------------------------------------------------

def open_sheet():
    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id:
        sys.exit("SHEET_ID not set")
    try:  # imported here so that `import sheets` works with the standard library only
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        sys.exit("gspread and google-auth are not installed: run the script with `uv run scripts/sheets.py`")
    key, path = os.environ.get("GOOGLE_SA_KEY", "").strip(), os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    try:
        if key:
            info = json.loads(key)
        elif path:
            with open(path, encoding="utf-8") as f:
                info = json.load(f)
        else:
            sys.exit("no credentials: set GOOGLE_SA_KEY (JSON text) or GOOGLE_APPLICATION_CREDENTIALS (path)")
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    except (OSError, ValueError, KeyError, TypeError):  # the message could quote the key, so print none
        sys.exit("the service-account key is not readable or not valid JSON (GOOGLE_SA_KEY, GOOGLE_APPLICATION_CREDENTIALS)")
    return gspread.authorize(creds).open_by_key(sheet_id)


def find_ws(sh, name: str):
    """The worksheet with this title, or None. (gspread raises WorksheetNotFound; matched by name, so that the
    library stays an optional import.)"""
    try:
        return sh.worksheet(name)
    except Exception as e:
        if type(e).__name__ == "WorksheetNotFound":
            return None
        raise


def norm(cell: str) -> str:
    """The form of a cell in the CSV: no trailing spaces, no line-ending \\r."""
    return re.sub(r"\r+(?=\n|$)", "", cell).rstrip(" ")


def header_error(header: list[str], cols: list[str]) -> str:
    """Why row 1 differs from the column list; empty when it is equal."""
    header = list(header)
    while header and not header[-1]:
        header.pop()
    if header == cols:
        return ""
    missing, extra = [c for c in cols if c not in header], [c for c in header if c not in cols]
    out = []
    if missing:
        out.append("missing " + ", ".join(map(repr, missing)))
    if extra:
        out.append("unknown " + ", ".join(map(repr, extra)))
    if not out:
        out.append("same columns in another order or repeated; expected " + ", ".join(cols))
    return "; ".join(out)


def sheet_grid(ws) -> list[list[str]]:
    values = [list(r) for r in ws.get_all_values()]
    while values and not any(values[-1]):  # trailing empty rows; an empty tab comes back as one empty row
        values.pop()
    return values


def read_sheet(ws, cols: list[str]) -> list[dict]:
    """The data rows of a tab as dicts of strings (CSV form). [] when the tab has no data rows. Row 1 must equal `cols`."""
    values = sheet_grid(ws)
    if not values:
        return []
    if err := header_error(values[0], cols):
        raise SheetError(f"tab '{ws.title}': row 1 differs from the column list: {err}")
    rows = []
    for n, raw in enumerate(values[1:], start=2):
        cells = [norm(c) for c in raw]
        if not any(cells):
            continue
        if any(cells[len(cols):]):
            raise SheetError(f"tab '{ws.title}': row {n} has data to the right of column '{cols[-1]}'")
        rows.append(dict(zip(cols, cells + [""] * (len(cols) - len(cells)))))
    return rows


def read_sheet_lenient(ws, cols: list[str], ignore=()) -> tuple[list[dict], list[str]]:
    """The rows of a tab by column name, for the check before a push: a column that row 1 lacks reads as empty, and the
    order of the columns does not matter. Also the names of the columns that are not in `cols` (and not in `ignore`)
    and hold data: a push would erase them."""
    values = sheet_grid(ws)
    if not values:
        return [], []
    header = list(values[0])
    while header and not header[-1]:
        header.pop()
    repeated = sorted({h for h in header if header.count(h) > 1} | ({"(empty)"} if "" in header else set()))
    if repeated:
        raise SheetError(f"tab '{ws.title}': row 1 has repeated or empty column names: {', '.join(repeated)}")
    where = {h: i for i, h in enumerate(header)}
    rows, extras = [], {}
    for raw in values[1:]:
        cells = [norm(c) for c in raw]
        if not any(cells):
            continue
        rows.append({c: cells[where[c]] if c in where and where[c] < len(cells) else "" for c in cols})
        for h, i in where.items():
            if h not in cols and h not in ignore and i < len(cells) and cells[i]:
                extras[h] = True
        if any(cells[len(header):]):
            extras["(columns without a name)"] = True
    return rows, list(extras)


# ---- CSV and git access ----------------------------------------------------------------------------------------

def parse_csv(text: str, cols: list[str], label: str) -> list[dict]:
    """Rows as written in the file: not stripped, so that a pull can be compared byte for byte."""
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if err := header_error(reader.fieldnames or [], cols):
        raise SheetError(f"{label}: row 1 differs from the column list: {err}")
    return [{c: r.get(c) or "" for c in cols} for r in reader]


def parse_csv_lenient(text: str, cols: list[str]) -> tuple[list[str], list[dict]]:
    """Header and rows of a CSV that may have other columns than `cols` (an older version of the file): by column
    name, a missing column reads as empty."""
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows = [{c: r.get(c) or "" for c in cols} for r in reader]
    return list(reader.fieldnames or []), rows


def load_csv(tab: Tab) -> tuple[list[dict], bytes]:
    data = tab.path.read_bytes()
    return parse_csv(data.decode("utf-8-sig"), tab.cols, display(tab.path)), data


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Git:
    """The few git questions the sync asks. `root` is the repository (tests pass a temporary one)."""

    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True)

    def has(self, ref: str) -> bool:
        return self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0

    def rev(self, ref: str) -> str:
        r = self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        return r.stdout.decode().strip() if r.returncode == 0 else ""

    def head(self) -> str:
        return self.rev("HEAD")

    def rel(self, path: Path) -> str | None:
        path = Path(path).resolve()
        root = self.root.resolve()
        return path.relative_to(root).as_posix() if path.is_relative_to(root) else None

    def show(self, ref: str, path: Path) -> bytes | None:
        """The file at a commit, as bytes; None when the commit or the file is missing."""
        rel = self.rel(path)
        if rel is None:
            return None
        r = self.run("show", f"{ref}:{rel}")
        return r.stdout if r.returncode == 0 else None


@dataclass
class Context:
    sh: object  # a gspread Spreadsheet, or a test double with the same few methods
    root: Path
    tabs: list[Tab]
    git: Git = field(default_factory=Git)
    clock: Callable[[], str] = now_utc
    markers: dict = field(default_factory=dict)


# ---- Sync marker -----------------------------------------------------------------------------------------------

@dataclass
class Marker:
    tab: str
    commit: str
    sha256: str
    time: str


def read_markers(sh) -> dict[str, Marker]:
    """The rows of the tab `_sync` by tab name. {} when the tab does not exist."""
    ws = find_ws(sh, SYNC_TAB)
    values = sheet_grid(ws) if ws is not None else []
    if not values:
        return {}
    if err := header_error(values[0], SYNC_COLS):
        raise SheetError(f"tab '{SYNC_TAB}': row 1 differs from {', '.join(SYNC_COLS)}: {err}")
    out = {}
    for n, raw in enumerate(values[1:], start=2):
        cells = [norm(c) for c in raw][:len(SYNC_COLS)]
        cells += [""] * (len(SYNC_COLS) - len(cells))
        if not any(cells):
            continue
        m = Marker(*cells)
        if not (m.tab and m.commit and m.sha256):
            raise SheetError(f"tab '{SYNC_TAB}': row {n} is incomplete. Delete the row, then push.")
        if m.tab in out:
            raise SheetError(f"tab '{SYNC_TAB}': two rows for the tab '{m.tab}'. Delete one.")
        out[m.tab] = m
    return out


def write_markers(sh, new: dict[str, Marker]):
    """Add or replace the rows of `new` in the tab `_sync` (created when missing)."""
    merged = {**read_markers(sh), **new}
    ws = find_ws(sh, SYNC_TAB)
    if ws is None:
        ws = sh.add_worksheet(title=SYNC_TAB, rows=max(len(merged) + 1, 20), cols=len(SYNC_COLS))
    write_table(ws, SYNC_COLS, [vars(m) for m in merged.values()], {})


@dataclass
class Base:
    """The CSV rows the Sheet and the repo both started from. rows is None when there is no base."""
    rows: list[dict] | None = None
    header: list[str] = field(default_factory=list)
    how: str = "none"  # none | marker | since
    commit: str = ""

    def describe(self) -> str:
        return "no base (two-way)" if self.rows is None else f"{self.how} {short(self.commit)}"


def check_ref(ctx: Context, ref: str):
    if not ctx.git.has(ref):
        raise SheetError(f"git ref '{ref}' not found: fetch the history (fetch-depth: 0) or pass another --since")


def resolve_base(ctx: Context, tab: Tab, since: str = "") -> Base:
    """--since <ref>: the CSV at that commit. Else the sync marker: the CSV at the commit it names, if it hashes to the
    value in the marker. Else no base. An older file may have other columns; they are matched by name."""
    if since:
        data = ctx.git.show(since, tab.path)  # missing there: the file is new, so every row is
        header, rows = parse_csv_lenient(data.decode("utf-8-sig"), tab.cols) if data else ([], [])
        return Base(rows, header, "--since", ctx.git.rev(since))
    marker = ctx.markers.get(tab.name)
    if marker is None:
        return Base()
    data = ctx.git.show(marker.commit, tab.path)
    if data is None or sha256(data) != marker.sha256:
        raise SheetError(
            f"tab '{tab.name}': the sync marker names commit {short(marker.commit)}, but {display(tab.path)} at that commit "
            f"is not the file that was pushed. Either the commit is missing from this clone, or the push came from a file "
            f"that was not committed. Fetch the full history, pass --since <ref>, or run push --force from a clean checkout.")
    header, rows = parse_csv_lenient(data.decode("utf-8-sig"), tab.cols)
    return Base(rows, header, "marker", marker.commit)


# ---- Comparison ------------------------------------------------------------------------------------------------

def keyed(rows: list[dict], key: str = "slug") -> dict[str, dict]:
    """key column -> row with normalised cells. A repeated or empty key gets a name that tells it apart."""
    out: dict[str, dict] = {}
    for n, r in enumerate(rows, start=2):
        name = base = r[key].strip() or f"(row {n})"
        k = 2
        while name in out:
            name, k = f"{base}#{k}", k + 1
        out[name] = {c: norm(v) for c, v in r.items()}
    return out


def changes(old: dict, new: dict, cols: list[str]) -> list[tuple]:
    """Entries ("+", key, row), ("~", key, [(col, old, new)]), ("-", key, row), from the keys of two tables."""
    out = []
    for k, r in new.items():
        if k not in old:
            out.append(("+", k, r))
        elif old[k] != r:
            out.append(("~", k, [(c, old[k][c], r[c]) for c in cols if old[k][c] != r[c]]))
    return out + [("-", k, r) for k, r in old.items() if k not in new]


def reordered(old: dict, new: dict) -> bool:
    return [k for k in old if k in new] != [k for k in new if k in old]


def pending(base: dict, head: dict, sheet: dict, cols: list[str]) -> list[tuple]:
    """Sheet edits that the repo does not have: cells where the Sheet differs from `base` (the CSVs the Sheet was
    synced from) and also from `head` (the CSVs now). An edit that is in `head` already, for instance because a
    pull request carried it, is settled."""
    out = []
    for k, r in sheet.items():
        b, h = base.get(k), head.get(k)
        if r == b or r == h:
            continue
        cells = [(c, (h or b or {}).get(c, ""), r[c]) for c in cols if r[c] != (b or {}).get(c, "") and r[c] != (h or {}).get(c, "")]
        if cells:
            out.append(("+", k, r) if b is None and h is None else ("~", k, cells))
    out += [("-", k, base[k]) for k in base if k not in sheet and k in head]
    if reordered(base, sheet) and reordered(head, sheet):
        out.append(("order", "", None))
    return out


@dataclass
class Merge:
    rows: list[dict]  # the table after the merge, in file order
    conflicts: list[tuple] = field(default_factory=list)  # ("cell", key, col, base, repo, sheet) or ("row", key, why, ...)
    notes: list[str] = field(default_factory=list)
    sheet_changes: list = field(default_factory=list)  # changes() from the base to the Sheet
    repo_changes: list = field(default_factory=list)  # changes() from the base to the repo (none without a base)


def merge_order(base: list[str], head: list[str], sheet: list[str], wanted: set[str]) -> tuple[list[str], str]:
    """The row order of a merge. The side that did not move the rows it shares with the base gives the backbone; the
    other side's new rows go after their predecessor. When both moved rows, the repo order wins (and a note says so)."""
    in_base = set(base)

    def moved(keys: list[str]) -> bool:
        present = set(keys)
        return [k for k in keys if k in in_base] != [k for k in base if k in present]

    sheet_moved, head_moved = moved(sheet), moved(head)
    first, second = (sheet, head) if sheet_moved and not head_moved else (head, sheet)
    order = [k for k in first if k in wanted]
    for i, k in enumerate(second):
        if k in wanted and k not in order:
            prev = next((p for p in reversed(second[:i]) if p in order), None)
            order.insert(order.index(prev) + 1 if prev is not None else 0, k)
    return order, ("the Sheet and the repo both moved rows: the repo order is kept" if sheet_moved and head_moved else "")


def merge3(tab: Tab, base: list[dict] | None, head: list[dict], sheet: list[dict]) -> Merge:
    """Three-way merge of a tab, cell by cell. `base`: the rows both sides started from; None means the repo counts as
    unchanged, so the Sheet wins every difference (the old two-way pull). A cell that only one side changed takes that
    side's value; a cell that both changed differently is a conflict (the merged row keeps the repo's value then)."""
    cols = tab.cols
    H, S = keyed(head, tab.key), keyed(sheet, tab.key)
    B = keyed(base, tab.key) if base is not None else H
    blank = dict.fromkeys(cols, "")
    result: dict[str, dict] = {}
    conflicts: list[tuple] = []
    for k in dict.fromkeys([*S, *H, *B]):
        b, h, s = B.get(k), H.get(k), S.get(k)
        if s is None and h is None:
            continue  # gone on both sides
        if s is None:  # not in the Sheet
            if b is None:
                result[k] = h  # the repo added it; the Sheet does not have it yet
            elif h != b:
                conflicts.append(("row", k, "the Sheet deleted the row, the repo changed it", b, h, None))
                result[k] = h
            continue  # else: the Sheet deleted it, and the repo left it alone
        if h is None:  # not in the repo
            if b is None:
                result[k] = s  # the Sheet added it
            elif s != b:
                conflicts.append(("row", k, "the repo deleted the row, the Sheet changed it", b, None, s))
            continue  # else: the repo deleted it, and the Sheet left it alone
        row = {}
        for c in cols:
            bv, hv, sv = (b or blank)[c], h[c], s[c]
            if sv == hv or hv == bv:
                row[c] = sv
            elif sv == bv:
                row[c] = hv
            else:
                conflicts.append(("cell", k, c, bv, hv, sv))
                row[c] = hv
        result[k] = row
    order, note = merge_order(list(B), list(H), list(S), set(result))
    return Merge([result[k] for k in order], conflicts, [note] if note else [], changes(B, S, cols),
                 changes(B, H, cols) if base is not None else [])


def excerpt(s: str, other: str) -> str:
    """`s` around the first character where it differs from `other`, on one line."""
    same = next((i for i, (a, b) in enumerate(zip(s, other)) if a != b), min(len(s), len(other)))
    start = max(0, same - 20)
    text = s[start:start + 80].replace("\n", "\\n")
    return f"'{'...' if start else ''}{text}{'...' if start + 80 < len(s) else ''}'"


def render(name: str, entries: list[tuple], extra: str = "", label: str = "nume") -> list[str]:
    counts = {k: sum(1 for e in entries if e[0] == k) for k in "+-~"}
    head = f"{name}: +{counts['+']} -{counts['-']} ~{counts['~']}" if entries else f"{name}: no differences"
    lines = [head + (f" ({extra})" if extra else "")]
    for kind, key, data in entries:
        if kind == "~":
            lines.append(f"~ {key}")
            lines += [f"    {c}: {excerpt(a, b)} -> {excerpt(b, a)}" for c, a, b in data]
        elif kind == "order":
            lines.append("~ the rows are in a different order")
        elif kind == "col":
            lines.append(f"! column '{key}' of the Sheet holds data and is not in the column list")
        else:
            lines.append(f"{kind} {key}: {data.get(label, '')}")
    return lines


def render_conflicts(name: str, conflicts: list[tuple]) -> list[str]:
    lines = [f"{name}: {len(conflicts)} conflict(s): the Sheet and the repo both changed these since the base"]
    for kind, key, what, b, h, s in conflicts:
        if kind == "row":
            lines.append(f"! {key}: {what}")
        else:
            lines += [f"! {key} / {what}", f"    base:  {excerpt(b, h)}", f"    repo:  {excerpt(h, s)}", f"    Sheet: {excerpt(s, h)}"]
    return lines


# ---- Reading a tab for diff and pull ---------------------------------------------------------------------------

@dataclass
class Plan:
    tab: Tab
    head: list[dict]
    sheet: list[dict]
    base: Base
    merge: Merge


def plan_tab(ctx: Context, tab: Tab, since: str, must_have_rows: bool) -> Plan | None:
    ws = find_ws(ctx.sh, tab.name)
    if ws is None:
        raise SheetError(f"tab '{tab.name}' is not in the Sheet" + (" (push creates it)" if tab.name in V2_TABS else ""))
    sheet = read_sheet(ws, tab.cols)
    head, _ = load_csv(tab)
    if not sheet:
        if must_have_rows:
            raise SheetError(f"tab '{tab.name}' has no data rows: pull would empty {display(tab.path)}")
        print(f"{tab.name}: the Sheet tab has no data rows (the CSV has {len(head)})")
        return None
    base = resolve_base(ctx, tab, since)
    return Plan(tab, head, sheet, base, merge3(tab, base.rows, head, sheet))


def render_csv(cols: list[str], rows: list[dict]) -> str:
    out = io.StringIO(newline="")
    w = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def run_checks(root: Path) -> tuple[int, str]:
    """validate.py on the root (v1: the file checks; v2: the package checks with per-token ID and scheme checks)."""
    r = subprocess.run([sys.executable, str(Path(__file__).with_name("validate.py")), "--data-dir", str(root)], cwd=ROOT,
                       capture_output=True, text=True, env={**os.environ, "GITHUB_ACTIONS": "false"})
    return r.returncode, (r.stdout + r.stderr).strip()


# ---- Subcommands -----------------------------------------------------------------------------------------------

def cmd_diff(ctx: Context, since: str = ""):
    if since:
        check_ref(ctx, since)
    ctx.markers = read_markers(ctx.sh)
    for tab in ctx.tabs:
        plan = plan_tab(ctx, tab, since, must_have_rows=False)
        if plan is None:
            continue
        head, sheet, merged = keyed(plan.head, tab.key), keyed(plan.sheet, tab.key), keyed(plan.merge.rows, tab.key)
        entries = changes(head, merged, tab.cols) + ([("order", "", None)] if reordered(head, merged) else [])
        extra = f"CSV {len(head)} rows, Sheet {len(sheet)}; base {plan.base.describe()}"
        print("\n".join(render(tab.name, entries, extra, tab.label)))
        if plan.base.rows is not None:  # the repo changed these since the base; the Sheet does not have them yet
            repo_only = changes(sheet, merged, tab.cols)
            if repo_only:
                print("\n".join(render(f"{tab.name} (in the repo, not in the Sheet yet)", repo_only, "", tab.label)))
        if plan.merge.conflicts:
            print("\n".join(render_conflicts(tab.name, plan.merge.conflicts)))
        for note in plan.merge.notes:
            print(f"{tab.name}: {note}")
        if not entries and not plan.merge.conflicts and tab.path.read_bytes().decode("utf-8-sig") != render_csv(tab.cols, plan.merge.rows):
            # same cells, but pull would still write other bytes (trailing spaces, line endings)
            print(f"{tab.name}: only the file format differs (trailing spaces or line endings); pull rewrites {display(tab.path)}")


def cmd_pull(ctx: Context, since: str = "", check: bool = False):
    if since:
        check_ref(ctx, since)
    ctx.markers = read_markers(ctx.sh)
    plans = [plan_tab(ctx, tab, since, must_have_rows=True) for tab in ctx.tabs]
    conflicts = [line for p in plans if p.merge.conflicts for line in render_conflicts(p.tab.name, p.merge.conflicts)]
    if conflicts:
        print("\n".join(conflicts))
        log("Both the Sheet and the repo changed these cells. Nothing was written. Make the two values equal "
            "(edit the Sheet or the CSV), or run pull --since <ref> to let the Sheet win.")
        sys.exit(PENDING)
    for p in plans:
        if p.base.rows is None:
            log(f"{p.tab.name}: no sync marker, so the Sheet is copied over the CSV (two-way). Run push once to set the marker.")
        before = p.tab.path.read_bytes()
        write_csv(p.tab.path, p.tab.cols, p.merge.rows)
        print(f"{p.tab.name}: {len(p.merge.rows)} rows written to {display(p.tab.path)} "
              f"({'changed' if p.tab.path.read_bytes() != before else 'unchanged'}); base {p.base.describe()}"
              + (f"; since then the Sheet changed {len(p.merge.sheet_changes)} row(s), the repo {len(p.merge.repo_changes)}"
                 if p.base.rows is not None else ""))
        if p.base.rows is not None:  # the cells of each side, as the three-way merge saw them
            for who, entries in (("Sheet", p.merge.sheet_changes), ("repo", p.merge.repo_changes)):
                if entries:
                    print("\n".join(render(f"{p.tab.name} ({who} changes since the base)", entries, "", p.tab.label)))
        for note in p.merge.notes:
            print(f"{p.tab.name}: {note}")
    if check:
        code, text = run_checks(ctx.root)
        print(f"validate.py --data-dir {display(ctx.root)}: exit {code}" + (f"\n{text}" if text else ""))
        if code:
            sys.exit(1)


def dropdowns(root: Path, tab: Tab) -> dict[str, tuple[list[str], bool]]:
    """column -> (allowed values, strict). A cell that takes a list (`tip` in v1; the `|` cells of v2) gets a drop-down
    that only suggests: a strict one would reject the valid multi-value cells."""
    if not tab.table:  # v1: the lists of taxonomy.json
        tax = json.loads((root / "taxonomy.json").read_text(encoding="utf-8"))
        return {"fel": ([f["key"] for f in tax["fel"]], True), "domeniu": ([d["key"] for d in tax["domenii"]], True),
                "tip": ([t["key"] for t in tax["tipuri"]], False), "acoperire": ([a["key"] for a in tax["acoperire"]], True),
                "stare": (["arhivat", "offline"], True), "civictech": (["0", "1"], True)}
    from taxonomy_v2 import load
    pkg = load(root)
    out = {}
    for col, rule in pkg.rules(tab.table).items():
        if col not in tab.cols:
            continue
        kind, strict = rule.get("kind"), True
        if kind == "code":
            values = [c for c, r in pkg.codes.get(rule["list"], {}).items() if r["statut"] != "retras"]
        elif kind == "concept":
            level = rule.get("level")
            values = [i for i, r in pkg.concepts.items() if r["schema"] == rule.get("scheme") and r["statut"] != "retras"
                      and (level is None or bool(r["mai_larg"]) == (level == "narrower"))]
            strict = rule.get("max_items") == 1
        elif kind == "area":
            values, strict = list(pkg.areas), False
        else:
            continue
        if values and (strict or len(values) <= SUGGEST_MAX):
            out[col] = (values, strict)
    return out


def format_requests(ws, cols: list[str], rules: dict[str, tuple[list[str], bool]]) -> list[dict]:
    """Freeze and bold row 1, make every cell of the table plain text, add the drop-downs."""
    sid = ws.id

    def area(row0, row1=None, col0=0, col1=len(cols)):
        return {"sheetId": sid, "startRowIndex": row0, **({"endRowIndex": row1} if row1 else {}),
                "startColumnIndex": col0, "endColumnIndex": col1}

    reqs = [
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": area(0), "cell": {"userEnteredFormat": {"numberFormat": {"type": "TEXT"}}},
                        "fields": "userEnteredFormat.numberFormat"}},
        {"repeatCell": {"range": area(0, 1), "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}},
    ]
    for col, (values, strict) in rules.items():
        if col in cols:
            i = cols.index(col)
            reqs.append({"setDataValidation": {"range": area(1, col0=i, col1=i + 1), "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in values]},
                "strict": strict, "showCustomUi": True}}})
    return reqs


def a1(row: int, col: int) -> str:
    """Cell notation, 1-based: (1, 1) is A1, (3, 27) is AA3."""
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def write_table(ws, cols: list[str], rows: list[dict], rules: dict):
    """Write header + rows, format, and clear what is left below and to the right of the table."""
    need = len(rows) + 1
    if ws.row_count < need or ws.col_count < len(cols):
        ws.resize(rows=max(ws.row_count, need), cols=max(ws.col_count, len(cols)))
    ws.update(values=[cols] + [[r[c] for c in cols] for r in rows], range_name="A1", raw=True)
    ws.spreadsheet.batch_update({"requests": format_requests(ws, cols, rules)})  # after the values: a raw update resets the cell format
    clear = []
    if ws.row_count > need:
        clear.append(f"A{need + 1}:{a1(ws.row_count, ws.col_count)}")
    if ws.col_count > len(cols):  # a column that left the list would stay in the Sheet and fail the next read
        clear.append(f"{a1(1, len(cols) + 1)}:{a1(need, ws.col_count)}")
    if clear:
        ws.batch_clear(clear)


def cmd_push(ctx: Context, since: str = "", force: bool = False):
    if since:
        check_ref(ctx, since)
    ctx.markers = {} if force else read_markers(ctx.sh)
    jobs, found = [], []
    for tab in ctx.tabs:
        head, data = load_csv(tab)
        ws = find_ws(ctx.sh, tab.name)
        if ws is None and tab.name not in V2_TABS:
            raise SheetError(f"tab '{tab.name}' is not in the Sheet")
        jobs.append((tab, ws, head, data))
        if force or ws is None:
            continue
        base = resolve_base(ctx, tab, since)
        sheet, extra_cols = read_sheet_lenient(ws, tab.cols, ignore=base.header)
        if not sheet:  # an empty tab holds no edits
            continue
        if base.rows is not None:
            entries = pending(keyed(base.rows, tab.key), keyed(head, tab.key), keyed(sheet, tab.key), tab.cols)
        else:
            entries = (changes(keyed(head, tab.key), keyed(sheet, tab.key), tab.cols)
                       + ([("order", "", None)] if reordered(keyed(head, tab.key), keyed(sheet, tab.key)) else []))
        entries += [("col", name, None) for name in extra_cols]
        if entries:
            found += render(tab.name, entries, f"base {base.describe()}", tab.label)
    if found:
        print("\n".join(found))
        log("The Sheet has changes that are not in the repo. Nothing was written."
            + ("" if since or ctx.markers else " There is no sync marker: compare with --since <ref>, run pull, or use --force to overwrite the Sheet."))
        sys.exit(PENDING)
    marks = {}
    for tab, ws, head, data in jobs:
        if ws is None:
            ws = ctx.sh.add_worksheet(title=tab.name, rows=max(len(head) + 1, 100), cols=len(tab.cols))
        write_table(ws, tab.cols, head, dropdowns(ctx.root, tab))
        print(f"{tab.name}: {len(head)} rows written to the Sheet")
        commit = ctx.git.head()
        if commit and ctx.git.show(commit, tab.path) == data:
            marks[tab.name] = Marker(tab.name, commit, sha256(data), ctx.clock())
        else:  # the marker names a commit, so it must name one that holds exactly what was pushed
            log(f"{tab.name}: the sync marker is not updated: {display(tab.path)} differs from HEAD. Commit it, then push again.")
    if marks:
        write_markers(ctx.sh, marks)  # last: a failed push leaves the old marker, which still describes the old base
        print(f"sync marker: {', '.join(marks)} at {short(next(iter(marks.values())).commit)}")


def google_error(e: Exception) -> str | None:
    """A short message for the errors of the Google libraries; None for any other exception."""
    if type(e).__module__.split(".")[0] != "gspread":
        return None
    name = type(e).__name__
    if name == "SpreadsheetNotFound":
        return "spreadsheet not found: check SHEET_ID and that the service account has access"
    if name == "WorksheetNotFound":
        return f"tab not found: {e}"
    if name == "APIError":
        return f"Google API error: {e}"
    return None


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--data-dir", type=Path, default=DATA, help="data root (default: data/, the v1 tabs)")
    shared.add_argument("--tabs", default="", help="comma-separated tabs of the root (v2: v2-intrari, v2-revizuire)")
    shared.add_argument("--since", default="", metavar="REF", help="commit whose CSVs are the base, instead of the sync marker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("diff", parents=[shared], help="what pull would write, and the conflicts; no writes")
    pull = sub.add_parser("pull", parents=[shared], help="merge the Sheet's tabs into the CSVs")
    pull.add_argument("--check", action="store_true", help="validate the root after writing; exit 1 on errors")
    push = sub.add_parser("push", parents=[shared], help="write the CSVs to the Sheet")
    push.add_argument("--force", action="store_true", help="overwrite the Sheet without the check")
    args = ap.parse_args()

    try:
        root = args.data_dir.resolve()
        tabs = tabs_for(root, [t.strip() for t in args.tabs.split(",") if t.strip()])
        ctx = Context(open_sheet(), root, tabs)
        if args.cmd == "diff":
            cmd_diff(ctx, args.since)
        elif args.cmd == "pull":
            cmd_pull(ctx, args.since, args.check)
        else:
            cmd_push(ctx, args.since, args.force)
    except SheetError as e:
        sys.exit(str(e))
    except Exception as e:
        if (message := google_error(e)) is None:
            raise
        sys.exit(message)


if __name__ == "__main__":
    main()
