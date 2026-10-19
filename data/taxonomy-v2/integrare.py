"""Build the integration copy data/taxonomy-v2/integrare/ from the sealed classification run. Stdlib only.

    python3 data/taxonomy-v2/integrare.py            # check that integrare/ matches a fresh assembly (no writes)
    python3 data/taxonomy-v2/integrare.py --write    # write integrare/ (never the run, the package, or source/)
    python3 data/taxonomy-v2/integrare.py --detach   # owner action: make integrare/ editorial (see "Detach" below)

The copy is an overlay of this package (see integrare/pachet.json). Its intrari.csv takes:
- the classification of each sealed response in runs/<RUN>/responses/;
- the original text, links, contacts, availability override and note from source/ by source identity
  (sursa_fisier + sursa_rand), never from model output;
- the corrections in integrare/modificari.csv, an append-only change log written by a person.
Every imported classification stays `propus`. The abstention keeps its empty classification as `de-revizuit`.
Partial results stay partial: rezultate.csv keeps each result status and response hash, and revizuire.csv
lists their uncertainties. Vocabulary gaps go to propuneri-vocabular.csv, never to concepte.csv.

The review queue comes from three places. The base queue R001-R066 was written for the draft.1 manual proposal, so
integrare/reconciliere.csv (a human-edited input, never written here) compares each R item with this copy. A row has the
result `pastrat` (text unchanged), `rescris` (field, current value, recommendation, reason and evidence rewritten) or
`tehnic` (state `tehnic`: the item needs no editorial decision). The same file can carry a recommendation for any C, S or V
item. Every `dovada` token must resolve to a real file and field. The base queue is never changed.

Detach. While integrare/ is derived, a direct edit (by hand, or `sheets.py pull` into the tab v2-intrari) fails the check.
`--detach` ends that: the owner runs it once, on a clean tree, and commits the result. It records
`"detached": {"commit": <HEAD>, "date": ...}` in pachet.json. From then on the overlay files are editorial and `--write`
is refused. The default check no longer compares the current files. It proves that the sealed run is unchanged, and that
the overlay files at the detach commit (`git show`) still equal a fresh assembly of the package at that commit. The
derivation stays provable; the later edits are the editor's. The check needs that commit in the clone (fetch the history).
"""
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import taxonomy_v2  # noqa: E402

RUN_ID = "2026-10-19-reasoned-evidence"
RUN = HERE / "runs" / RUN_ID
OUT = HERE / "integrare"
GENERATED_FILES = ("intrari.csv", "rezultate.csv", "revizuire.csv", "propuneri-vocabular.csv", "pachet.json")  # what assemble() returns
FACETS = ("subiecte", "teme", "scopuri", "functionalitati", "formate", "tehnologii", "institutii_vizate", "tip_organizatie",
          "arii_acoperite")
CONFIDENCE = ("mica", "medie", "mare")
EXTRA_HEADERS = {
    "modificari.csv": ["id", "data", "slug", "camp", "tip", "inainte", "dupa", "motiv", "dovada"],
    "rezultate.csv": ["slug", "rezultat", "raspuns", "sha256", "incertitudini", "conflicte", "modificari"],
    "propuneri-vocabular.csv": ["id", "tip", "schema", "eticheta_ro", "eticheta_en", "definitie_ro", "mai_larg", "slug", "motiv", "dovada", "stare"],
    "reconciliere.csv": ["id", "rezultat", "camp", "valoare_originala", "propunere", "motiv", "dovada"],
}
RECONCILIATION_RESULTS = ("pastrat", "rescris", "tehnic")
# Besides the columns of intrari.csv, a review item can name the whole classification or a vocabulary proposal.
REVIEW_PSEUDO_FIELDS = ("clasificare", "vocabular")
# Purposes and areas named by the post-seal semantic review (evaluation/REPORT.md), outside the run's own gap list.
REVIEW_PROPOSALS = [
    {"id": "scop:sustenabilitate-presa", "tip": "concept", "schema": "scop", "eticheta_ro": "Sustenabilitatea presei",
     "eticheta_en": "Press sustainability", "definitie_ro": "Sprijină finanțarea și continuitatea publicațiilor de presă.",
     "mai_larg": "", "slug": "presspay", "motiv": "Evaluarea semantică: scop:sprijin-organizatii numește organizații civice.",
     "dovada": "clasificare-input.csv:presspay:descriere"},
    {"id": "tara:republica-moldova", "tip": "arie", "schema": "tara", "eticheta_ro": "Republica Moldova", "eticheta_en": "",
     "definitie_ro": "", "mai_larg": "", "slug": "data-expertforum",
     "motiv": "Evaluarea semantică: un set de date privește Republica Moldova.",
     "dovada": "runs/2026-10-19-reasoned-evidence/evidence/web-01.json#turn0view6"},
]
SEMANTIC_REVIEWS = [
    ("S001", "data-expertforum", "arii_acoperite", "national|tara:RO", "decizie privind tara:republica-moldova",
     "Problema 1 din evaluare. Sursa completă include date despre Republica Moldova. Vocabularul nu are aria; propunerea este în propuneri-vocabular.csv. "
     "Rădăcina media are acum dovada din secțiunea Media (M001).", "medie"),
    ("S002", "jailando", "formate", "format:registru", "dovadă primară pentru format",
     "Problema 2 din evaluare. Formatul registru venea mai ales din tipul istoric; M003 îl lasă necunoscut. Restabiliți-l numai cu dovadă.", "medie"),
    ("S003", "presspay", "scopuri", "scop:sprijin-organizatii", "scop:sustenabilitate-presa",
     "Problema 3 din evaluare. Scopul propus anterior numește organizații civice; M004 îl elimină. Decideți asupra conceptului propus.", "medie"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slugify(text: str) -> str:
    plain = unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def csv_text(columns: list[str], rows: list[dict]) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def verify_seal(run: Path = RUN) -> dict:
    """Refuse to read a run whose sealed files or frozen vocabulary changed."""
    seal = json.loads((run / "classification-seal.json").read_text(encoding="utf-8"))
    changed = [p for p, h in seal["files"].items() if sha(run / p) != h]
    if changed:
        raise SystemExit(f"{RUN_ID}: sealed files changed: {changed[:5]}")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    changed = [p for p, h in manifest["frozen_files"].items() if sha(run / p) != h]
    if changed:
        raise SystemExit(f"{RUN_ID}: frozen files changed: {changed}")
    return {"seal": seal, "manifest": manifest}


def verify_run(pkg: taxonomy_v2.Package, run: Path = RUN) -> dict:
    """verify_seal, and refuse a package whose vocabulary differs from the run's frozen one."""
    checked = verify_seal(run)
    for name in ("concepte.csv", "arii.csv"):
        frozen = taxonomy_v2.read_table(run / "frozen" / name)[1]
        if frozen != pkg.tables[name]:
            raise SystemExit(f"{name}: the package table differs from the frozen vocabulary of {RUN_ID}")
    return checked


def lowest_confidence(result: dict) -> str:
    """The entry-level confidence: the lowest of its classification claims (identity preservation excluded)."""
    found = [j["confidence"] for j in result["justifications"] if j["basis"] != "identity_preservation"]
    return min(found, key=CONFIDENCE.index) if found else "mica"


def evidence_exists(ref: str, root: Path = HERE) -> bool:
    """A change log citation `<file>#<source_id>: <excerpt>` or `clasificare-input.csv:<slug>:<field>: <excerpt>`
    must quote its source exactly."""
    where, _, excerpt = ref.partition(": ")
    if "#" in where:
        path, source_id = where.split("#", 1)
        strings, todo = [], [json.loads((root / path).read_text(encoding="utf-8"))]
        while todo:
            node = todo.pop()
            if isinstance(node, str):
                strings.append(node)
            elif isinstance(node, dict):
                todo += node.values()
            elif isinstance(node, list):
                todo += node
        # The raw capture holds several sources; the excerpt must sit in a text that names this source.
        return any(source_id in s and excerpt in s[s.index(source_id):] for s in strings)
    name, slug, col = where.split(":")
    rows = {r["slug"]: r for r in taxonomy_v2.read_table(root / name)[1]}
    return excerpt in rows.get(slug, {}).get(col, "")


def citation_exists(token: str, generated: dict[str, str], root: Path = HERE) -> bool:
    """One `dovada` token of reconciliere.csv must name a file inside data/taxonomy-v2/ and a field that exists:
    - `<file>.csv:<row key>:<column>`: the key is the value in the first column of that CSV, the column must be in its header
      (a cell may be empty: an empty description is evidence of an absent description);
    - `<file>.json:<key>` or `<file>.json:<key>[<field>[=<value>]]`: a key of a sealed response, with an optional filter on the
      list items (`field`/`value`; `original_field`/`original_value` for excluded_legacy_tags).
    A file under integrare/ that this run assembles is read from `generated`, so the check does not depend on the files on disk."""
    path, _, rest = token.partition(":")
    parts = path.split("/")
    if not rest or path != path.strip() or token != token.strip() or path.startswith("/") or ".." in parts:
        return False
    if path.endswith(".json"):
        target = root / path
        match = re.fullmatch(r"(\w+)(?:\[([^\]]+)\])?", rest)
        if not target.is_file() or not match:
            return False
        key, flt = match.groups()
        node = json.loads(target.read_text(encoding="utf-8")).get(key)
        if not node:
            return False
        if flt is None:
            return True
        field, _, value = flt.partition("=")
        name_key, value_key = ("original_field", "original_value") if key == "excluded_legacy_tags" else ("field", "value")
        return isinstance(node, list) and any(isinstance(i, dict) and i.get(name_key) == field and (not value or i.get(value_key) == value) for i in node)
    if path.endswith(".csv"):
        key, _, column = rest.rpartition(":")
        local = path.removeprefix("integrare/") if path.startswith("integrare/") else None
        if local in generated:
            reader = csv.DictReader(io.StringIO(generated[local]))
            header, rows = list(reader.fieldnames or []), list(reader)
        else:
            target = root / path
            if not target.is_file():
                return False
            header, rows = taxonomy_v2.read_table(target)
        return bool(key) and column in header and any(r[header[0]] == key for r in rows)
    return False


def reconcile(reviews: list[dict], recon: list[dict], intrari_columns: list[str], generated: dict[str, str], root: Path = HERE) -> None:
    """Apply integrare/reconciliere.csv to the review queue in place. Every R item needs a row; a C, S or V item may have one.
    `rescris` and `tehnic` need a recommendation or reason and evidence that resolves. `tehnic` also sets the state `tehnic`."""
    by_id: dict[str, dict] = {}
    for rec in recon:
        if rec["id"] in by_id:
            raise SystemExit(f"reconciliere.csv: duplicate id {rec['id']}")
        by_id[rec["id"]] = rec
    items = {r["id"]: r for r in reviews}
    unknown = [i for i in by_id if i not in items]
    if unknown:
        raise SystemExit(f"reconciliere.csv: no review item for {', '.join(unknown)}")
    uncovered = [i for i in items if i.startswith("R") and i not in by_id]
    if uncovered:
        raise SystemExit(f"reconciliere.csv: no row for {', '.join(uncovered)}")
    fields = set(intrari_columns) | set(REVIEW_PSEUDO_FIELDS)
    for ident, rec in by_id.items():
        item = items[ident]
        if rec["rezultat"] not in RECONCILIATION_RESULTS:
            raise SystemExit(f"reconciliere.csv {ident}: rezultat must be one of {', '.join(RECONCILIATION_RESULTS)}")
        if rec["camp"] not in fields:
            raise SystemExit(f"reconciliere.csv {ident}: camp {rec['camp']!r} is not a column of intrari.csv, clasificare or vocabular")
        if rec["rezultat"] == "pastrat":
            if any(rec[c] != item[c] for c in ("camp", "valoare_originala", "propunere", "motiv")) or rec["dovada"]:
                raise SystemExit(f"reconciliere.csv {ident}: pastrat keeps the text of the item and carries no evidence")
            continue
        if not rec["propunere"].strip() or not rec["motiv"].strip():
            raise SystemExit(f"reconciliere.csv {ident}: {rec['rezultat']} needs a propunere and a motiv")
        tokens = rec["dovada"].split("|") if rec["dovada"] else []
        bad = [t for t in tokens if not citation_exists(t, generated, root)]
        if not tokens or bad:
            raise SystemExit(f"reconciliere.csv {ident}: {rec['rezultat']} needs evidence that exists; not found: {bad or 'no dovada'}")
        item.update(camp=rec["camp"], valoare_originala=rec["valoare_originala"], propunere=rec["propunere"],
                    motiv=f"{rec['motiv']} Dovadă: {'; '.join(tokens)}")
        if rec["rezultat"] == "tehnic":
            item["stare"] = "tehnic"


def assemble(root: Path = HERE) -> dict[str, str]:
    """The overlay files as a fresh assembly of the package at `root` (data/taxonomy-v2/ or a copy of it) and its sealed run
    under root/runs/. The inputs modificari.csv and reconciliere.csv come from root/integrare/. Nothing is written."""
    run, out = root / "runs" / RUN_ID, root / "integrare"
    pkg = taxonomy_v2.load(root)
    sealed = verify_run(pkg, run)
    sources = {p.name: taxonomy_v2.read_table(p)[1] for p in (root / "source/proiecte.csv", root / "source/orgs.csv")}
    columns = pkg.schema["headers"]["intrari.csv"]
    candidate = {r["slug"]: r for r in taxonomy_v2.read_table(run / "candidate/intrari-candidate.csv")[1]}
    changes = taxonomy_v2.read_table(out / "modificari.csv")[1] if (out / "modificari.csv").exists() else []
    if set(candidate) != set(pkg.entries):
        raise SystemExit("the candidate and the package have different slugs")

    entries, results = {}, []
    for slug in pkg.entries:  # the package's row order
        cand = candidate[slug]
        response_path = run / cand["response_file"]
        result = json.loads(response_path.read_text(encoding="utf-8"))
        if result["slug"] != slug:
            raise SystemExit(f"{cand['response_file']}: response for another slug")
        original = taxonomy_v2.source_row(pkg, sources, cand)
        if original is None:
            raise SystemExit(f"{slug}: no source row at {cand['sursa_fisier']}:{cand['sursa_rand']}")
        for col in ("nume", "descriere_scurta", "descriere", "url", "linkuri"):
            if cand[col] != original[col]:
                raise SystemExit(f"{slug}: the candidate's {col} differs from the source snapshot")
        c = result["classification"]
        abstained = result["result_status"] == "insufficient_evidence"
        row = {
            "slug": slug, "tip_entitate": c["tip_entitate"], "sectiune_url": cand["sectiune_url_original"],
            **{col: original[col] for col in ("nume", "descriere_scurta", "descriere", "url", "linkuri")},
            "subiect_principal": c["subiect_principal"] or "",
            **{f: "|".join(c[f]) for f in FACETS},
            "maturitate": c["maturitate"] or "",
            "nivel_acoperire": c["nivel_acoperire"],
            **{dest: original.get(src, "") for dest, src in taxonomy_v2.PRESERVED.items()
               if dest not in ("nume", "descriere_scurta", "descriere", "url", "linkuri")},
            # A valid abstention is not an imported classification; the entry waits for evidence.
            "clasificare_stare": "de-revizuit" if abstained else "propus",
            "incredere": lowest_confidence(result),
            "sursa_fisier": cand["sursa_fisier"], "sursa_rand": cand["sursa_rand"],
            "nota_clasificare": f"Candidat {RUN_ID}, rezultat {result['result_status']}; {cand['response_file']}.",
        }
        entries[slug] = row
        results.append({"slug": slug, "rezultat": result["result_status"], "raspuns": cand["response_file"],
                        "sha256": sha(response_path), "incertitudini": len(result["uncertainties"]),
                        "conflicte": len(result["conflicts"]), "modificari": ""})

    by_slug = {r["slug"]: r for r in results}
    for ch in changes:
        row = entries.get(ch["slug"])
        if row is None or ch["camp"] not in columns or ch["camp"] in taxonomy_v2.PRESERVED or ch["camp"] in ("slug", "sursa_fisier", "sursa_rand"):
            raise SystemExit(f"modificari.csv {ch['id']}: unknown entry, or a column that a change may not edit")
        if row[ch["camp"]] != ch["inainte"]:
            raise SystemExit(f"modificari.csv {ch['id']}: {ch['slug']}.{ch['camp']} is {row[ch['camp']]!r}, not {ch['inainte']!r}")
        if ch["tip"] not in ("valoare", "dovada") or (ch["tip"] == "dovada") != (ch["inainte"] == ch["dupa"]):
            raise SystemExit(f"modificari.csv {ch['id']}: tip=dovada keeps the value; tip=valoare changes it")
        if not evidence_exists(ch["dovada"], root):
            raise SystemExit(f"modificari.csv {ch['id']}: the quoted evidence is not in its source")
        row[ch["camp"]] = ch["dupa"]
        row["nota_clasificare"] += f" Modificare {ch['id']}."
        by_slug[ch["slug"]]["modificari"] = "|".join(filter(None, [by_slug[ch["slug"]]["modificari"], ch["id"]]))

    reviews = [dict(r) for r in pkg.tables["revizuire.csv"]]  # copies: the base queue stays unchanged
    queue = json.loads((run / "candidate/review-queue.json").read_text(encoding="utf-8"))
    for n, item in enumerate(queue, 1):
        specific = [u for u in item["uncertainties"] if u["field"] not in ("maturitate", "attributions")]
        reasons = [u["reason_ro"] for u in specific] + [f"Conflict {x['field']}: {x['reason_ro']} {x['resolution_ro']}" for x in item["conflicts"]]
        if not reasons:
            continue
        status = item["result_status"]
        reviews.append({"id": f"C{n:03d}", "slug": item["slug"], "camp": "clasificare" if specific else item["conflicts"][0]["field"],
                        "valoare_originala": status, "propunere": "verificare cu dovezi primare",
                        "motiv": " ".join(reasons), "prioritate": "mare" if status == "insufficient_evidence" else "medie",
                        "stare": "deschis", "decizie_editor": ""})
    for ident, slug, col, old, proposal, why, priority in SEMANTIC_REVIEWS:
        reviews.append({"id": ident, "slug": slug, "camp": col, "valoare_originala": old, "propunere": proposal, "motiv": why,
                        "prioritate": priority, "stare": "deschis", "decizie_editor": ""})

    proposals = []
    for gap in json.loads((run / "candidate/vocabulary-gaps.json").read_text(encoding="utf-8")):
        for c in gap["concepts"]:
            proposals.append({"id": f"{c['scheme']}:{slugify(c['label_ro'])}", "tip": "concept", "schema": c["scheme"],
                              "eticheta_ro": c["label_ro"], "eticheta_en": c["label_en"], "definitie_ro": c["definition_ro"],
                              "mai_larg": "|".join(c["broader_existing_ids"]), "slug": gap["slug"], "motiv": c["reason_ro"],
                              "dovada": "|".join(e["locator"] for e in c["evidence"])})
        for a in gap["areas"]:
            proposals.append({"id": f"{a['area_type']}:{slugify(a['label_ro'])}", "tip": "arie", "schema": a["area_type"],
                              "eticheta_ro": a["label_ro"], "eticheta_en": "", "definitie_ro": "",
                              "mai_larg": "|".join(a["parent_existing_ids"]), "slug": gap["slug"], "motiv": a["reason_ro"],
                              "dovada": "|".join(e["locator"] for e in a["evidence"])})
    proposals += REVIEW_PROPOSALS
    merged: dict[str, dict] = {}
    for p in proposals:  # one row per proposed ID; several entries can need the same term
        if p["id"] in pkg.concepts or p["id"] in pkg.areas:
            raise SystemExit(f"propuneri-vocabular.csv: {p['id']} already exists in the vocabulary")
        if p["id"] in merged:
            for col in ("slug", "dovada"):
                merged[p["id"]][col] += "|" + p[col]
        else:
            merged[p["id"]] = {**p, "stare": "propus"}
    proposals = list(merged.values())
    n = 0
    for p in proposals:
        for slug in taxonomy_v2.values(p["slug"]):
            n += 1
            reviews.append({"id": f"V{n:03d}", "slug": slug, "camp": "vocabular", "valoare_originala": "",
                            "propunere": p["id"], "motiv": f"Propunere de {p['tip']}: {p['eticheta_ro']}. {p['motiv']}",
                            "prioritate": "mica", "stare": "deschis", "decizie_editor": ""})

    # Reconcile the queue with this copy. Files under integrare/ that this run assembles are cited from memory, not from disk.
    review_cols = pkg.schema["headers"]["revizuire.csv"]
    generated = {"intrari.csv": csv_text(columns, list(entries.values())), "rezultate.csv": csv_text(EXTRA_HEADERS["rezultate.csv"], results),
                 "propuneri-vocabular.csv": csv_text(EXTRA_HEADERS["propuneri-vocabular.csv"], proposals)}
    if not (out / "reconciliere.csv").exists():
        raise SystemExit("integrare/reconciliere.csv is missing: it holds one row for each R item of the review queue")
    header, recon = taxonomy_v2.read_table(out / "reconciliere.csv")
    if header != EXTRA_HEADERS["reconciliere.csv"]:
        raise SystemExit("reconciliere.csv: the header differs from the expected columns")
    reconcile(reviews, recon, columns, generated, root)

    overlay = {
        "purpose": f"Integration copy of the sealed run {RUN_ID}, with the evaluation's three semantic corrections. "
                   "All classifications remain proposals; this is not an accepted catalogue.",
        "base": "..",
        "local_files": ["intrari.csv", "revizuire.csv", "reconciliere.csv", "modificari.csv", "rezultate.csv", "propuneri-vocabular.csv", "catalogue.json"],
        "headers": EXTRA_HEADERS,
        "source_run": {
            "id": RUN_ID, "path": f"runs/{RUN_ID}",
            "classification_seal_sha256": sha(run / "classification-seal.json"),
            "candidate_csv_sha256": sha(run / "candidate/intrari-candidate.csv"),
            "frozen_concepts_sha256": sealed["manifest"]["frozen_files"]["frozen/concepte.csv"],
            "frozen_areas_sha256": sealed["manifest"]["frozen_files"]["frozen/arii.csv"],
        },
        "notes": [
            "Review items R001-R066 come from the base queue, which was written for the draft.1 manual proposal and stays unchanged. "
            "reconciliere.csv compares each one with this copy and keeps, rewrites or closes it technically (state tehnic).",
            "C items carry the run's specific uncertainties and conflicts. Generic maturity and attribution-role uncertainties stay in the responses.",
            "S items are the evaluation's three semantic concerns; modificari.csv records the corresponding changes.",
            "V items point to vocabulary proposals; none of them is in concepte.csv or arii.csv.",
            "Every open item carries a recommendation for the editor, with evidence. A technical closure (tehnic) needs a reason and no editor decision. "
            "The editor still decides every open item.",
        ],
        "counts": {
            "entries": len(entries),
            "results": {s: sum(r["rezultat"] == s for r in results) for s in ("classified", "partial", "insufficient_evidence")},
            "changes": len(changes), "review_items": len(reviews),
            "review_states": {s: sum(r["stare"] == s for r in reviews) for s in ("deschis", "tehnic")},
            "vocabulary_proposals": len(proposals),
        },
    }
    return {
        "intrari.csv": generated["intrari.csv"],
        "rezultate.csv": generated["rezultate.csv"],
        "revizuire.csv": csv_text(review_cols, reviews),
        "propuneri-vocabular.csv": generated["propuneri-vocabular.csv"],
        "pachet.json": json.dumps(overlay, ensure_ascii=False, indent=2) + "\n",
    }


def vcs(*args: str) -> subprocess.CompletedProcess:
    """One version-control command in the repository of this package (bytes out)."""
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)


def at_commit(commit: str, path: str) -> bytes | None:
    """The file `path` (relative to the repository) as it was at `commit`; None when the commit or the file is missing."""
    r = vcs("show", f"{commit}:{path}")
    return r.stdout if r.returncode == 0 else None


def export_tree(commit: str, dest: Path) -> Path:
    """Extract this package (data/taxonomy-v2/) as it was at `commit` into dest, without runs/. The current runs/ is linked in
    its place: the check proves its seal, and the sealed files never change. Returns the package root inside dest."""
    package = HERE.relative_to(REPO).as_posix()
    r = subprocess.Popen(["git", "-C", str(REPO), "archive", "--format=tar", commit, "--", package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    root = dest / package
    with tarfile.open(fileobj=r.stdout, mode="r|") as tar:
        for member in tar:
            parts = Path(member.name).parts
            if member.name.startswith(("/", "..")) or ".." in parts or parts[:len(Path(package).parts) + 1] == (*Path(package).parts, "runs"):
                continue
            target = dest / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
    r.stdout.read()  # the padding after the archive's end marker
    error = r.stderr.read().decode(errors="replace").strip()
    if r.wait() != 0 or not root.is_dir():
        raise SystemExit(f"cannot read {package} at commit {commit}: {error or 'no such path'}")
    (root / "runs").symlink_to(HERE / "runs", target_is_directory=True)
    return root


def detached_record() -> dict | None:
    """The `detached` record of pachet.json ({"commit", "date"}), or None while integrare/ is derived."""
    return json.loads((OUT / "pachet.json").read_text(encoding="utf-8")).get("detached")


def check_detached(record: dict) -> bool:
    """Prove the derivation of a detached overlay. True when the seal holds and the overlay files at the detach commit equal
    a fresh assembly of the package at that commit. The current files are editorial and are not compared; the report lists
    the ones that changed since."""
    commit = record["commit"]
    verify_seal(RUN)
    if vcs("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode != 0:
        raise SystemExit(f"integrare/ is detached at {commit}, but the clone has no such commit: fetch the full history (fetch-depth: 0)")
    with tempfile.TemporaryDirectory() as tmp:
        files = assemble(export_tree(commit, Path(tmp)))
    rel = OUT.relative_to(REPO).as_posix()
    stale = [n for n, text in files.items() if at_commit(commit, f"{rel}/{n}") != text.encode("utf-8")]
    def edited(path: Path) -> bool:  # pachet.json differs from the commit by the record itself; that is no edit
        old = at_commit(commit, f"{rel}/{path.name}")
        if path.name == "pachet.json" and old is not None:
            return {k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if k != "detached"} != json.loads(old)
        return old != path.read_bytes()
    moved = sorted(p.name for p in OUT.iterdir() if p.is_file() and edited(p))
    short = commit[:7]
    if stale:
        print(f"integrare/ is detached at {short}, but its files at that commit differ from a fresh assembly: {', '.join(stale)}")
        return False
    print(f"integrare/ is detached since {short} ({record.get('date', '?')}): the seal of {RUN_ID} holds, and the overlay files at that "
          f"commit match a fresh assembly. The current files are editorial"
          + (f"; changed since: {', '.join(moved)}" if moved else "; unchanged since") + ".")
    return True


def detach() -> None:
    """Owner action. Record the commit that proves the derivation, and make the overlay files editorial. The overlay must
    match a fresh assembly, and the package must have no uncommitted change, so that HEAD holds exactly these files."""
    if record := detached_record():
        raise SystemExit(f"integrare/ is already detached at {record['commit']}")
    files = assemble()
    stale = [n for n, text in files.items() if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != text]
    if stale:
        raise SystemExit(f"integrare/ differs from a fresh assembly: {', '.join(stale)}. Detach a reproducible copy: undo the edit, or run --write.")
    package = HERE.relative_to(REPO).as_posix()
    status = vcs("status", "--porcelain", "--", package)
    if status.returncode != 0:
        raise SystemExit(f"{REPO} is not a repository that this script can read: {status.stderr.decode(errors='replace').strip()}")
    if status.stdout.strip():
        raise SystemExit(f"{package} has uncommitted changes. Commit them first: the detach commit must hold the overlay as it is.\n"
                         + status.stdout.decode(errors="replace").rstrip())
    head = vcs("rev-parse", "--verify", "HEAD").stdout.decode().strip()
    rel = OUT.relative_to(REPO).as_posix()
    if not head or [n for n, text in files.items() if at_commit(head, f"{rel}/{n}") != text.encode("utf-8")]:
        raise SystemExit("HEAD does not hold the overlay files as a fresh assembly makes them")
    pachet = json.loads((OUT / "pachet.json").read_text(encoding="utf-8"))
    recorded = {}
    for key, value in pachet.items():
        recorded[key] = value
        if key == "base":
            recorded["detached"] = {"commit": head, "date": datetime.now(timezone.utc).date().isoformat()}
    (OUT / "pachet.json").write_text(json.dumps(recorded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"detached integrare/ at {head}. Commit pachet.json. From now on the overlay files are editorial; --write is refused.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    what = parser.add_mutually_exclusive_group()
    what.add_argument("--write", action="store_true", help="write integrare/ instead of checking it (refused once it is detached)")
    what.add_argument("--detach", action="store_true", help="owner action: make integrare/ editorial; record HEAD as the proof of its derivation")
    args = parser.parse_args()
    record = detached_record()
    if args.detach:
        return detach()
    if args.write and record:
        raise SystemExit(f"integrare/ is detached at {record['commit']}: its files are editorial, and --write would overwrite them")
    if record:
        raise SystemExit(0 if check_detached(record) else 1)
    files = assemble()
    if args.write:
        OUT.mkdir(exist_ok=True)
        for name, text in files.items():
            (OUT / name).write_text(text, encoding="utf-8")
        print(f"wrote {', '.join(files)} in {OUT.relative_to(HERE.parents[1])}")
        return
    stale = [n for n, text in files.items() if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != text]
    print("integrare/ matches a fresh assembly" if not stale else f"integrare/ differs from a fresh assembly: {', '.join(stale)}")
    raise SystemExit(bool(stale))


if __name__ == "__main__":
    main()
