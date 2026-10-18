# /// script
# requires-python = ">=3.11"
# dependencies = ["gspread>=6.1", "google-auth>=2.30"]
# ///
"""Two-way sync between the Google Sheet (tabs `proiecte` and `orgs`) and data/proiecte.csv, data/orgs.csv.

    uv run scripts/sheets.py diff                   # Sheet vs the CSVs: rows added / removed / changed; no writes
    uv run scripts/sheets.py pull                   # write the Sheet's tabs to the CSVs
    uv run scripts/sheets.py push --since <ref>     # write the CSVs to the Sheet, unless it holds edits not yet in the repo
    uv run scripts/sheets.py push                   # same, but compare with the current CSVs (--force: no check)

Needs SHEET_ID and a service-account key: GOOGLE_SA_KEY (the JSON text) or GOOGLE_APPLICATION_CREDENTIALS (a path).
The repo is the source of truth. `diff` and `pull` read the Sheet; `push` overwrites it, so it checks first.
`--since <ref>` names the commit the Sheet was last synced from (in CI: the push's `before`). A Sheet change counts
as pending when it is neither in the CSVs at <ref> nor in the current CSVs. Exit codes: 0 done, 1 error,
3 the Sheet holds edits not yet in the repo (nothing written).
"""
import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys

import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

from common import load_env, DATA, ORGS_COLS, PROIECTE_COLS, ROOT, write_csv

TABS = {"proiecte": ("proiecte.csv", PROIECTE_COLS), "orgs": ("orgs.csv", ORGS_COLS)}
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PENDING = 3  # exit code: the Sheet holds edits that are not in the repo


class SheetError(Exception):
    """The Sheet or a CSV does not have the expected shape."""


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---- Sheet access ----------------------------------------------------------------------------------------------

def open_sheet() -> gspread.Spreadsheet:
    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id:
        sys.exit("SHEET_ID not set")
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


def read_sheet(ws: gspread.Worksheet, cols: list[str]) -> list[dict]:
    """The data rows of a tab as dicts of strings (CSV form). [] when the tab has no data rows."""
    values = ws.get_all_values()
    while values and not any(values[-1]):  # trailing empty rows; an empty tab comes back as one empty row
        values.pop()
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


# ---- CSV access ------------------------------------------------------------------------------------------------

def parse_csv(text: str, cols: list[str], label: str) -> list[dict]:
    """Rows as written in the file: not stripped, so that a pull can be compared byte for byte."""
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if err := header_error(reader.fieldnames or [], cols):
        raise SheetError(f"{label}: row 1 differs from the column list: {err}")
    return [{c: r.get(c) or "" for c in cols} for r in reader]


def load_csv(fname: str, cols: list[str]) -> list[dict]:
    with open(DATA / fname, encoding="utf-8-sig", newline="") as f:
        return parse_csv(f.read(), cols, f"data/{fname}")


def check_ref(ref: str):
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=ROOT, capture_output=True).returncode:
        sys.exit(f"git ref '{ref}' not found: fetch the history (fetch-depth: 0) or pass another --since")


def load_csv_at(ref: str, fname: str, cols: list[str]) -> list[dict]:
    """The rows of data/<fname> at a commit; [] when the file did not exist there."""
    r = subprocess.run(["git", "show", f"{ref}:data/{fname}"], cwd=ROOT, capture_output=True)
    return parse_csv(r.stdout.decode("utf-8-sig"), cols, f"data/{fname} at {ref}") if r.returncode == 0 else []


# ---- Comparison ------------------------------------------------------------------------------------------------

def keyed(rows: list[dict]) -> dict[str, dict]:
    """slug -> row with normalised cells. A repeated or empty slug gets a key that tells it apart."""
    out: dict[str, dict] = {}
    for n, r in enumerate(rows, start=2):
        key = base = r["slug"].strip() or f"(row {n})"
        k = 2
        while key in out:
            key, k = f"{base}#{k}", k + 1
        out[key] = {c: norm(v) for c, v in r.items()}
    return out


def changes(old: dict, new: dict, cols: list[str]) -> list[tuple]:
    """Entries ("+", key, row), ("~", key, [(col, old, new)]), ("-", key, row), from the slugs of two tables."""
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


def excerpt(s: str, other: str) -> str:
    """`s` around the first character where it differs from `other`, on one line."""
    same = next((i for i, (a, b) in enumerate(zip(s, other)) if a != b), min(len(s), len(other)))
    start = max(0, same - 20)
    text = s[start:start + 80].replace("\n", "\\n")
    return f"'{'...' if start else ''}{text}{'...' if start + 80 < len(s) else ''}'"


def render(name: str, entries: list[tuple], extra: str = "") -> list[str]:
    counts = {k: sum(1 for e in entries if e[0] == k) for k in "+-~"}
    head = f"{name}: +{counts['+']} -{counts['-']} ~{counts['~']}" if entries else f"{name}: no differences"
    lines = [head + (f" ({extra})" if extra else "")]
    for kind, key, data in entries:
        if kind == "~":
            lines.append(f"~ {key}")
            lines += [f"    {c}: {excerpt(a, b)} -> {excerpt(b, a)}" for c, a, b in data]
        elif kind == "order":
            lines.append("~ the rows are in a different order")
        else:
            lines.append(f"{kind} {key}: {data.get('nume', '')}")
    return lines


# ---- Subcommands -----------------------------------------------------------------------------------------------

def cmd_diff(sh: gspread.Spreadsheet):
    for name, (fname, cols) in TABS.items():
        head, rows = keyed(load_csv(fname, cols)), read_sheet(sh.worksheet(name), cols)
        if not rows:
            print(f"{name}: the Sheet tab has no data rows (the CSV has {len(head)})")
            continue
        sheet = keyed(rows)
        entries = changes(head, sheet, cols) + ([("order", "", None)] if reordered(head, sheet) else [])
        print("\n".join(render(name, entries, f"CSV {len(head)} rows, Sheet {len(sheet)}")))
        if not entries:  # same cells, but pull would still write other bytes (trailing spaces, line endings)
            with open(DATA / fname, encoding="utf-8-sig", newline="") as f:
                if f.read() != render_csv(cols, rows):
                    print(f"{name}: only the file format differs (trailing spaces or line endings); pull rewrites data/{fname}")


def render_csv(cols: list[str], rows: list[dict]) -> str:
    out = io.StringIO(newline="")
    w = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def cmd_pull(sh: gspread.Spreadsheet):
    pulled = {}
    for name, (fname, cols) in TABS.items():
        pulled[name] = read_sheet(sh.worksheet(name), cols)
        if not pulled[name]:
            raise SheetError(f"tab '{name}' has no data rows: pull would empty data/{fname}")
    for name, (fname, cols) in TABS.items():
        path = DATA / fname
        before = path.read_bytes() if path.exists() else b""
        write_csv(path, cols, pulled[name])
        print(f"{name}: {len(pulled[name])} rows written to data/{fname} ({'changed' if path.read_bytes() != before else 'unchanged'})")


def dropdowns() -> dict[str, tuple[list[str], bool]]:
    """column -> (allowed values, strict). `tip` takes a comma-separated list, so its drop-down only suggests."""
    tax = json.loads((DATA / "taxonomy.json").read_text(encoding="utf-8"))
    return {"fel": (["proiect", "resursa"], True), "domeniu": ([d["key"] for d in tax["domenii"]], True),
            "tip": ([t["key"] for t in tax["tipuri"]], False), "acoperire": ([a["key"] for a in tax["acoperire"]], True),
            "stare": (["arhivat", "offline"], True), "civictech": (["0", "1"], True)}


def format_requests(ws: gspread.Worksheet, cols: list[str]) -> list[dict]:
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
    for col, (values, strict) in dropdowns().items():
        if col in cols:
            i = cols.index(col)
            reqs.append({"setDataValidation": {"range": area(1, col0=i, col1=i + 1), "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in values]},
                "strict": strict, "showCustomUi": True}}})
    return reqs


def push_tab(ws: gspread.Worksheet, cols: list[str], rows: list[dict]):
    need = len(rows) + 1
    if ws.row_count < need or ws.col_count < len(cols):
        ws.resize(rows=max(ws.row_count, need), cols=max(ws.col_count, len(cols)))
    ws.update(values=[cols] + [[r[c] for c in cols] for r in rows], range_name="A1", raw=True)
    ws.spreadsheet.batch_update({"requests": format_requests(ws, cols)})  # after the values: a raw update resets the cell format
    if ws.row_count > need:
        ws.batch_clear([f"A{need + 1}:{rowcol_to_a1(ws.row_count, len(cols))}"])


def cmd_push(sh: gspread.Spreadsheet, since: str, force: bool):
    if since:
        check_ref(since)
    plan, found = {}, []
    for name, (fname, cols) in TABS.items():
        ws, head = sh.worksheet(name), load_csv(fname, cols)
        plan[name] = (ws, cols, head)
        if force:
            continue
        sheet = keyed(read_sheet(ws, cols))
        if not sheet:  # an empty tab holds no edits
            continue
        if since:
            entries = pending(keyed(load_csv_at(since, fname, cols)), keyed(head), sheet, cols)
        else:
            entries = changes(keyed(head), sheet, cols) + ([("order", "", None)] if reordered(keyed(head), sheet) else [])
        if entries:
            found += render(name, entries)
    if found:
        print("\n".join(found))
        log("The Sheet has changes that are not in the repo. Nothing was written."
            + ("" if since else " Compare with --since <ref>, run pull, or use --force to overwrite the Sheet."))
        sys.exit(PENDING)
    for name, (ws, cols, head) in plan.items():
        push_tab(ws, cols, head)
        print(f"{name}: {len(head)} rows written to the Sheet")


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("diff", help="Sheet vs the CSVs; no writes")
    sub.add_parser("pull", help="write the Sheet's tabs to the CSVs")
    push = sub.add_parser("push", help="write the CSVs to the Sheet")
    push.add_argument("--since", default="", metavar="REF", help="commit the Sheet was last synced from")
    push.add_argument("--force", action="store_true", help="overwrite the Sheet without the check")
    args = ap.parse_args()

    try:
        sh = open_sheet()
        if args.cmd == "diff":
            cmd_diff(sh)
        elif args.cmd == "pull":
            cmd_pull(sh)
        else:
            cmd_push(sh, args.since, args.force)
    except SheetError as e:
        sys.exit(str(e))
    except gspread.exceptions.SpreadsheetNotFound:
        sys.exit("spreadsheet not found: check SHEET_ID and that the service account has access")
    except gspread.exceptions.WorksheetNotFound as e:
        sys.exit(f"tab not found: {e}")
    except gspread.exceptions.APIError as e:
        sys.exit(f"Google API error: {e}")


if __name__ == "__main__":
    main()
