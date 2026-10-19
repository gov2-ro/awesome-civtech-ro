"""Build the integration copy data/taxonomy-v2/integrare/ from the sealed classification run. Stdlib only.

    python3 data/taxonomy-v2/integrare.py            # check that integrare/ matches a fresh assembly (no writes)
    python3 data/taxonomy-v2/integrare.py --write    # write integrare/ (never the run, the package, or source/)

The copy is an overlay of this package (see integrare/pachet.json). Its intrari.csv takes:
- the classification of each sealed response in runs/<RUN>/responses/;
- the original text, links, contacts, availability override and note from source/ by source identity
  (sursa_fisier + sursa_rand), never from model output;
- the corrections in integrare/modificari.csv, an append-only change log written by a person.
Every imported classification stays `propus`. The abstention keeps its empty classification as `de-revizuit`.
Partial results stay partial: rezultate.csv keeps each result status and response hash, and revizuire.csv
lists their uncertainties. Vocabulary gaps go to propuneri-vocabular.csv, never to concepte.csv.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
import taxonomy_v2  # noqa: E402

RUN_ID = "2026-10-19-reasoned-evidence"
RUN = HERE / "runs" / RUN_ID
OUT = HERE / "integrare"
FACETS = ("subiecte", "teme", "scopuri", "functionalitati", "formate", "tehnologii", "institutii_vizate", "tip_organizatie",
          "arii_acoperite")
CONFIDENCE = ("mica", "medie", "mare")
EXTRA_HEADERS = {
    "modificari.csv": ["id", "data", "slug", "camp", "tip", "inainte", "dupa", "motiv", "dovada"],
    "rezultate.csv": ["slug", "rezultat", "raspuns", "sha256", "incertitudini", "conflicte", "modificari"],
    "propuneri-vocabular.csv": ["id", "tip", "schema", "eticheta_ro", "eticheta_en", "definitie_ro", "mai_larg", "slug", "motiv", "dovada", "stare"],
}
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


def verify_run(pkg: taxonomy_v2.Package) -> dict:
    """Refuse to read a run whose sealed files or frozen vocabulary changed, or whose vocabulary differs from ours."""
    seal = json.loads((RUN / "classification-seal.json").read_text(encoding="utf-8"))
    changed = [p for p, h in seal["files"].items() if sha(RUN / p) != h]
    if changed:
        raise SystemExit(f"{RUN_ID}: sealed files changed: {changed[:5]}")
    manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
    changed = [p for p, h in manifest["frozen_files"].items() if sha(RUN / p) != h]
    if changed:
        raise SystemExit(f"{RUN_ID}: frozen files changed: {changed}")
    for name in ("concepte.csv", "arii.csv"):
        frozen = taxonomy_v2.read_table(RUN / "frozen" / name)[1]
        if frozen != pkg.tables[name]:
            raise SystemExit(f"{name}: the package table differs from the frozen vocabulary of {RUN_ID}")
    return {"seal": seal, "manifest": manifest}


def lowest_confidence(result: dict) -> str:
    """The entry-level confidence: the lowest of its classification claims (identity preservation excluded)."""
    found = [j["confidence"] for j in result["justifications"] if j["basis"] != "identity_preservation"]
    return min(found, key=CONFIDENCE.index) if found else "mica"


def evidence_exists(ref: str) -> bool:
    """A change log citation `<file>#<source_id>: <excerpt>` or `clasificare-input.csv:<slug>:<field>: <excerpt>`
    must quote its source exactly."""
    where, _, excerpt = ref.partition(": ")
    if "#" in where:
        path, source_id = where.split("#", 1)
        strings, todo = [], [json.loads((HERE / path).read_text(encoding="utf-8"))]
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
    rows = {r["slug"]: r for r in taxonomy_v2.read_table(HERE / name)[1]}
    return excerpt in rows.get(slug, {}).get(col, "")


def assemble() -> dict[str, str]:
    pkg = taxonomy_v2.load(HERE)
    run = verify_run(pkg)
    sources = {p.name: taxonomy_v2.read_table(p)[1] for p in (HERE / "source/proiecte.csv", HERE / "source/orgs.csv")}
    columns = pkg.schema["headers"]["intrari.csv"]
    candidate = {r["slug"]: r for r in taxonomy_v2.read_table(RUN / "candidate/intrari-candidate.csv")[1]}
    changes = taxonomy_v2.read_table(OUT / "modificari.csv")[1] if (OUT / "modificari.csv").exists() else []
    if set(candidate) != set(pkg.entries):
        raise SystemExit("the candidate and the package have different slugs")

    entries, results = {}, []
    for slug in pkg.entries:  # the package's row order
        cand = candidate[slug]
        response_path = RUN / cand["response_file"]
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
        if not evidence_exists(ch["dovada"]):
            raise SystemExit(f"modificari.csv {ch['id']}: the quoted evidence is not in its source")
        row[ch["camp"]] = ch["dupa"]
        row["nota_clasificare"] += f" Modificare {ch['id']}."
        by_slug[ch["slug"]]["modificari"] = "|".join(filter(None, [by_slug[ch["slug"]]["modificari"], ch["id"]]))

    reviews = list(pkg.tables["revizuire.csv"])
    queue = json.loads((RUN / "candidate/review-queue.json").read_text(encoding="utf-8"))
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
    for gap in json.loads((RUN / "candidate/vocabulary-gaps.json").read_text(encoding="utf-8")):
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

    overlay = {
        "purpose": f"Integration copy of the sealed run {RUN_ID}, with the evaluation's three semantic corrections. "
                   "All classifications remain proposals; this is not an accepted catalogue.",
        "base": "..",
        "local_files": ["intrari.csv", "revizuire.csv", "modificari.csv", "rezultate.csv", "propuneri-vocabular.csv", "catalogue.json"],
        "headers": EXTRA_HEADERS,
        "source_run": {
            "id": RUN_ID, "path": f"runs/{RUN_ID}",
            "classification_seal_sha256": sha(RUN / "classification-seal.json"),
            "candidate_csv_sha256": sha(RUN / "candidate/intrari-candidate.csv"),
            "frozen_concepts_sha256": run["manifest"]["frozen_files"]["frozen/concepte.csv"],
            "frozen_areas_sha256": run["manifest"]["frozen_files"]["frozen/arii.csv"],
        },
        "notes": [
            "Review items R001-R066 are copied unchanged from the base queue. They were written for the draft.1 manual proposal.",
            "C items carry the run's specific uncertainties and conflicts. Generic maturity and attribution-role uncertainties stay in the responses.",
            "S items are the evaluation's three semantic concerns; modificari.csv records the corresponding changes.",
            "V items point to vocabulary proposals; none of them is in concepte.csv or arii.csv.",
        ],
        "counts": {
            "entries": len(entries),
            "results": {s: sum(r["rezultat"] == s for r in results) for s in ("classified", "partial", "insufficient_evidence")},
            "changes": len(changes), "review_items": len(reviews), "vocabulary_proposals": len(proposals),
        },
    }
    review_cols = pkg.schema["headers"]["revizuire.csv"]
    return {
        "intrari.csv": csv_text(columns, list(entries.values())),
        "rezultate.csv": csv_text(EXTRA_HEADERS["rezultate.csv"], results),
        "revizuire.csv": csv_text(review_cols, reviews),
        "propuneri-vocabular.csv": csv_text(EXTRA_HEADERS["propuneri-vocabular.csv"], proposals),
        "pachet.json": json.dumps(overlay, ensure_ascii=False, indent=2) + "\n",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="write integrare/ instead of checking it")
    args = parser.parse_args()
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
