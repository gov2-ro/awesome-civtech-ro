"""Check proiecte.csv and orgs.csv before they are merged (CI on every PR, and for rows coming from the Google Sheet).

    python3 scripts/validate.py                 # the repo files
    python3 scripts/validate.py some.csv ...    # extra files in the proiecte.csv format (e.g. a Sheet export)

Exits 1 on errors; warnings don't fail. Messages are file:line, and GitHub Actions shows them on the PR diff.
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

from common import DATA, MENTIUNI, MENTIUNI_COLS, ORGS_COLS, PROIECTE_COLS, split_list, split_tip, to_href

TAX = json.loads((DATA / "taxonomy.json").read_text())
DOMENII = {d["key"] for d in TAX["domenii"]}
TIPURI = {t["key"] for t in TAX["tipuri"]}
ACOPERIRE = {a["key"] for a in TAX["acoperire"]}
ROLURI = {r["key"] for r in TAX["linkuri"]["roluri"]}
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
URL = re.compile(r"^https?://[^\s/$.?#][^\s]*\.[^\s]+$", re.I)
GH = os.environ.get("GITHUB_ACTIONS") == "true"

errors = warnings = 0


def report(level: str, path: Path, line: int, msg: str):
    global errors, warnings
    if level == "error":
        errors += 1
    else:
        warnings += 1
    rel = path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
    print(f"::{level} file={rel},line={line}::{msg}" if GH else f"{rel}:{line}: {level}: {msg}")


def norm_url(u: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", u.lower()).rstrip("/")


def check(path: Path, cols: list[str], seen: dict, urls: dict, is_org: bool):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing, extra = [c for c in cols if c not in header], [c for c in header if c not in cols]
        if missing:
            report("error", path, 1, f"lipsesc coloanele: {', '.join(missing)}")
        if extra:
            report("error", path, 1, f"coloane necunoscute: {', '.join(extra)}")
        if missing or extra:
            return
        for r in reader:
            line = reader.line_num
            r = {k: (v or "").strip() for k, v in r.items() if k}
            err = lambda m: report("error", path, line, f"{r.get('slug') or '?'}: {m}")
            warn = lambda m: report("warning", path, line, f"{r.get('slug') or '?'}: {m}")

            if not SLUG.match(r["slug"]):
                err("slug invalid (litere mici, cifre, cratime)")
            elif r["slug"] in seen:
                err(f"slug duplicat (și în {seen[r['slug']]})")
            seen[r["slug"]] = f"{path.name}:{line}"
            if not r["nume"]:
                err("lipsește numele")
            if not r["url"]:
                warn("fără url")
            elif not URL.match(to_href(r["url"])):
                err(f"url invalid: {r['url']}")
            else:
                u = norm_url(r["url"])
                if u in urls:
                    warn(f"același url ca {urls[u]}")
                urls[u] = r["slug"]
            if r["domeniu"] not in DOMENII:
                err(f"domeniu necunoscut: '{r['domeniu']}' (valori: {', '.join(sorted(DOMENII))})")
            if r["acoperire"] not in ACOPERIRE:
                err(f"acoperire necunoscută: '{r['acoperire']}'")
            if r["acoperire"] == "local" and not r["oras"]:
                warn("acoperire locală fără oraș")
            if r["stare"] not in ("", "arhivat", "offline"):
                err(f"stare necunoscută: '{r['stare']}' (gol, arhivat sau offline)")
            try:
                for tok in split_list(r["linkuri"]):
                    m = re.match(r"^([a-z]+):(https?://.+)$", tok)
                    if m and m.group(1) not in ROLURI:
                        err(f"rol de link necunoscut: '{m.group(1)}'")
                    elif not URL.match(m.group(2) if m else to_href(tok)):
                        err(f"link invalid: {tok}")
            except json.JSONDecodeError:
                err("linkuri: listă JSON invalidă")
            if not is_org:
                if r["fel"] not in ("proiect", "resursa"):
                    err(f"fel necunoscut: '{r['fel']}' (proiect sau resursa)")
                for t in split_tip(r["tip"]):
                    if t not in TIPURI:
                        err(f"tip necunoscut: '{t}' (valori: {', '.join(sorted(TIPURI))})")
                if r["fel"] == "proiect" and not r["tip"]:
                    warn("proiect fără tip")
                if r["civictech"] not in ("", "0", "1"):
                    err(f"civictech: '{r['civictech']}' (0 sau 1)")
                if not r["descriere_scurta"] and not r["descriere"]:
                    warn("fără descriere")


def check_mentiuni(path: Path):
    """mentiuni.csv is generated; a person edits only `editor`, and a typo there would silently drop the row."""
    if not path.exists():
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != MENTIUNI_COLS:
            report("error", path, 1, f"coloane diferite de MENTIUNI_COLS din scripts/common.py: {reader.fieldnames}")
            return
        for r in reader:
            if (r["editor"] or "").strip() not in ("", "0", "1"):
                report("error", path, reader.line_num, f"{r['slug']}: editor: '{r['editor']}' (gol, 0 sau 1)")


def main():
    seen, urls = {}, {}
    check(DATA / "proiecte.csv", PROIECTE_COLS, seen, urls, False)
    check(DATA / "orgs.csv", ORGS_COLS, seen, urls, True)
    check_mentiuni(MENTIUNI)
    for extra in sys.argv[1:]:
        check(Path(extra).resolve(), PROIECTE_COLS, seen, urls, False)
    print(f"{errors} erori, {warnings} avertismente", file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
