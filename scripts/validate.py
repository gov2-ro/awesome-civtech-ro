"""Check the data root before it is merged (CI on every PR, and for rows coming from the Google Sheet). v1: proiecte.csv and orgs.csv.

    python3 scripts/validate.py                 # the public root (until the cutover: the v1 files)
    python3 scripts/validate.py some.csv ...    # extra files in the proiecte.csv format (e.g. a Sheet export)
    python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare                 # a taxonomy v2 root (draft rules)
    python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare --publication   # ... and the public-build gate

--data-dir selects the data root; the default is PUBLIC_ROOT (common.py; data/, the v1 root, until the cutover).
A v2 root gets the package checks of scripts/taxonomy_v2.py: they permit proposed classifications. --publication also requires every entry to be
accepted and no high-priority review item to be open, as a public build does.
Exits 1 on errors; warnings don't fail. Messages are file:line, and GitHub Actions shows them on the PR diff.
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import common  # the list's path is read from the module at call time, so a test can point it at a temporary file
from common import (FORBIDDEN_COLS, PUBLIC_ROOT, MENTIUNI_COLS, ORGS_COLS, PROIECTE_COLS, data_schema, forbidden, load_catalogue, observation_paths,
                    split_list, split_tip, to_href)

TAX = DOMENII = TIPURI = ACOPERIRE = FEL = ROLURI = ORG_SLUGS = None  # set by setup(), from the selected v1 root
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
            if r["acoperire"] and r["acoperire"] not in ACOPERIRE:  # empty means national
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
                if r["fel"] not in FEL:
                    err(f"fel necunoscut: '{r['fel']}' (valori: {', '.join(FEL)})")
                # An author that is a slug names a row of orgs.csv; a slug-like word that is not one is probably a typo.
                for a in re.split(r"\s+[/&]\s+|,\s*", r["autor"]):
                    if SLUG.match(a) and a not in ORG_SLUGS:
                        warn(f"autor '{a}' arată ca un slug, dar nu există în orgs.csv")
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


HOST = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


def check_forbidden(path: Path, entries: list[dict] | None):
    """colectare-interzisa.csv lists the hosts that no script requests, so a mistake here must stop the merge: a row that
    silently matches nothing leaves a site open to requests. `entries` (the catalogue of the checked root) lets us warn about a
    row whose host belongs to no entry; the row may be stale. That is a warning only."""
    if not path.exists():
        report("error", path, 1, "lipsește fișierul cu gazdele care nu se accesează automat")
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        missing, extra = [c for c in FORBIDDEN_COLS if c not in header], [c for c in header if c not in FORBIDDEN_COLS]
        if missing:
            report("error", path, 1, f"lipsesc coloanele: {', '.join(missing)}")
        if extra:
            report("error", path, 1, f"coloane necunoscute: {', '.join(extra)}")
        if missing or extra:
            return
        seen, rows = {}, []
        for r in reader:
            line = reader.line_num
            r = {k: (v or "").strip() for k, v in r.items() if k}
            host = r["gazda"]
            err = lambda m: report("error", path, line, f"{host or '?'}: {m}")
            if not HOST.match(host):
                err("gazda trebuie să fie un nume de gazdă (litere mici, fără schemă, cale sau port)")
                continue
            if host.startswith("www."):
                err("gazda se scrie fără www. (www. se ignoră, iar subdomeniile sunt incluse)")
            if host in seen:
                err(f"gazdă duplicată (și în linia {seen[host]})")
            seen.setdefault(host, line)
            if not r["motiv"]:
                err("lipsește motivul")
            if not r["dovada"]:
                report("warning", path, line, f"{host}: fără dovadă (o adresă sau un citat scurt)")
            if not re.fullmatch(r"\d{4}-\d\d-\d\d", r["data"]):
                err(f"data invalidă: '{r['data']}' (AAAA-LL-ZZ)")
            else:
                try:
                    date.fromisoformat(r["data"])
                except ValueError:
                    err(f"data invalidă: '{r['data']}' (AAAA-LL-ZZ)")
            rows.append((line, r))
    if entries is not None:
        urls = [e["url"] for e in entries if e.get("url")]
        for line, r in rows:
            if not any(forbidden(u, [r]) for u in urls):
                report("warning", path, line, f"{r['gazda']}: nicio intrare nu are acest domeniu în url (rând depășit?)")


def org_slugs(data_dir: Path) -> set[str]:
    with open(data_dir / "orgs.csv", encoding="utf-8-sig", newline="") as f:
        return {(r.get("slug") or "").strip() for r in csv.DictReader(f)}


def setup(data_dir: Path):
    """The controlled lists of the selected v1 root."""
    global TAX, DOMENII, TIPURI, ACOPERIRE, FEL, ROLURI, ORG_SLUGS
    TAX = json.loads((data_dir / "taxonomy.json").read_text())
    DOMENII = {d["key"] for d in TAX["domenii"]}
    TIPURI = {t["key"] for t in TAX["tipuri"]}
    ACOPERIRE = {a["key"] for a in TAX["acoperire"]}
    FEL = [f["key"] for f in TAX["fel"]]
    ROLURI = {r["key"] for r in TAX["linkuri"]["roluri"]}
    ORG_SLUGS = org_slugs(data_dir)


def check_v2(root: Path, publication: bool):
    """The package checks of a v2 root, reported like the v1 checks (file:line when the message names them)."""
    import taxonomy_v2
    try:
        found, summary = taxonomy_v2.check(root, publication=publication)
    except taxonomy_v2.PackageError as e:
        report("error", root, 1, str(e))
        return
    files = taxonomy_v2.Files(root)
    for msg in found:
        m = re.match(r"^(?:baseline: |publication: )?([\w./-]+\.(?:csv|json))(?::(\d+))?[ :]", msg)
        name = m.group(1) if m else ("revizuire.csv" if "review item" in msg else "intrari.csv" if msg.startswith("publication") else "")
        report("error", files.path(name) if name else files.root, int(m.group(2)) if m and m.group(2) else 1, msg)
    check_mentiuni(observation_paths(root)["mentions"])
    check_relation_fields(root)
    check_editor_fields(root)
    if summary:
        states = ", ".join(f"{k}: {v}" for k, v in sorted(summary["classification_states"].items()))
        print(f"{summary['schema_version']}: {summary['entries']} intrări ({states}), {summary['concepts']} concepte", file=sys.stderr)


def check_relation_fields(root: Path):
    """An entry with `relatie_date` `fara-date` has nothing to extract. Fields in its inventory say the opposite.
    The inventory counts come from `observatii/inventare/rezumat.csv` (written by inventory.py). This is a warning only:
    the editor decides which of the two is wrong. A root without an inventory has nothing to compare."""
    import taxonomy_v2
    summary = observation_paths(root)["profile"].parent / "inventare" / "rezumat.csv"
    path = taxonomy_v2.Files(root).path("intrari.csv")
    if not summary.exists() or not path.exists():
        return
    with open(summary, encoding="utf-8-sig", newline="") as f:
        fields = {r["slug"]: int(r["campuri_din_surse"] or 0) for r in csv.DictReader(f)}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("relatie_date") == taxonomy_v2.NO_DATA and fields.get(r["slug"], 0):
                report("warning", path, reader.line_num,
                       f"{r['slug']}: relatie_date is {taxonomy_v2.NO_DATA}, but the inventory has {fields[r['slug']]} extracted fields")


def check_editor_fields(root: Path):
    """campuri-editor.csv is edited by hand and holds fields that the inventory readers missed (scripts/inventory_editor.py). A row that is wrong must stop the merge: the
    columns, the empty cells, the code lists (`rol`, `tip_declarat`), the form of the slug and of the address, duplicates, and the source (it must be a source of the entry,
    by the generated profiles). The fragment is checked against the retained body by `inventory.py --check`, not here: CI has no bodies."""
    import inventory_editor
    folder = observation_paths(root)["profile"].parent / "inventare"
    path = folder / inventory_editor.FILE
    rows, found = inventory_editor.read_file(path)
    profiles = folder / "proiecte.json"
    if rows and profiles.exists():
        try:
            owned = {(p["slug"], ident) for p in json.loads(profiles.read_text())["proiecte"] for ident in p.get("surse_structurate", [])}
            found += inventory_editor.membership_errors(rows, owned)
        except (OSError, ValueError, KeyError):
            report("error", profiles, 1, "proiecte.json nu poate fi citit; sursele din campuri-editor.csv nu se pot verifica")
    for msg in found:
        m = re.match(r"^[\w.-]+:(\d+): (.*)$", msg, re.S)
        report("error", path, int(m.group(1)) if m else 1, m.group(2) if m else msg)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("extra", nargs="*", type=Path, help="more CSVs in the proiecte.csv format (v1 only)")
    parser.add_argument("--data-dir", type=Path, default=PUBLIC_ROOT, help="data root (default: the public root, PUBLIC_ROOT in common.py)")
    parser.add_argument("--publication", action="store_true", help="v2: require accepted classifications, as a public build")
    args = parser.parse_args()
    root = args.data_dir.resolve()
    if data_schema(root) == "v2":
        if args.extra:
            parser.error("extra CSVs are in the v1 format; use them without a v2 --data-dir")
        check_v2(root, args.publication)
    else:
        if args.publication:
            parser.error("--publication applies to a v2 root")
        setup(root)
        seen, urls = {}, {}
        check(root / "proiecte.csv", PROIECTE_COLS, seen, urls, False)
        check(root / "orgs.csv", ORGS_COLS, seen, urls, True)
        check_mentiuni(observation_paths(root)["mentions"])
        for extra in args.extra:
            check(extra.resolve(), PROIECTE_COLS, seen, urls, False)
    try:
        catalogue = load_catalogue(root)
    except (Exception, SystemExit):  # a broken root has its own errors above; only the stale-row warning is skipped
        catalogue = None
    check_forbidden(common.FORBIDDEN_PATH, catalogue)
    print(f"{errors} erori, {warnings} avertismente", file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
