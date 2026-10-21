# /// script
# requires-python = ">=3.11"
# dependencies = ["google-auth>=2.30", "requests>=2.32"]
# ///
"""Generate the questions of the proposal Form ("Sugestii listă civtech.gov2.ro") from the data model.

    uv run scripts/form.py            # print the planned questions and the Form as it is now; writes nothing
    uv run scripts/form.py --json     # the same, plus the forms.batchUpdate body
    uv run scripts/form.py --apply    # replace ALL items of the Form with the planned ones (one batchUpdate)
    uv run scripts/form.py --save     # read the Form as edited by hand and store it as the template, data/form.json

    uv run scripts/form.py --data-dir data/taxonomy-v2/integrare              # plan the v2 questions from the vocabulary; offline
    uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --check      # ... and exit 1 when data/form-v2.json lacks a label
    uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --write-map  # add the new labels to data/form-v2.json (version + 1)
    uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --import propuneri.csv [--out rows.csv]   # responses -> intrari rows

The template (data/form.json, when it exists) sets the questions: their order, titles, types, help texts and
required flags. Edit the Form in Google Forms, then `--save`. The choices of "Ce propui?", "Domeniu", "Tip" and
"Acoperire" always come from the taxonomy (so the answers map back to CSV keys); other choices from the template.

Needs FORM_ID and a service-account key (an editor of the Form): GOOGLE_SA_KEY (the JSON text) or
GOOGLE_APPLICATION_CREDENTIALS (a path). Without a key the default mode prints the plan only.
The choices come from data/taxonomy.json, so after a taxonomy change run `--apply` again.
The script never changes the title, description, settings or response destination of the Form.
`--apply` sends the revision ID it just read, so the Form must not change in between; the API then refuses.
The REST API has no URL validation for text questions (TextQuestion has only `paragraph`), so the Form accepts
any text in "Adresa (URL)"; `validate.py` checks the URL when a person copies the answer to a CSV.

Taxonomy v2. With a v2 --data-dir the script plans the v2 questions (entity kind; subjects and formats as checkboxes; coverage)
from the vocabulary, and never calls Google: --apply and --save are refused, because the live Form stays on the v1 questions
until the cutover. The answer map (label -> ID, per question) is the versioned file data/form-v2.json. A label that the
vocabulary renames keeps its old row, so old responses still map to the same ID. `--import` maps the rows of an export of
the tab `propuneri` to rows of intrari.csv (clasificare_stare `propus`, or `de-revizuit` when the subject is not one clear
choice); an unknown label is reported, never guessed. The editor copies the rows by hand, as for review.py.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from common import load_env, DATA, PUBLIC_ROOT, data_schema, split_list

# Question titles, in Form order. The response columns in the Sheet tab `propuneri` are named after these titles:
# renaming one renames a column there (and breaks any importer that reads it). Change a title only together with
# that importer.
TITLES = [
    "Ce propui?", "Nume", "Adresa (URL)", "Pe scurt", "Descriere", "Domeniu", "Tip", "Acoperire", "Oraș", "Autor",
    "Alte linkuri", "E-mailul tău", "Altceva?",
]
(Q_FEL, Q_NUME, Q_URL, Q_SCURT, Q_DESCRIERE, Q_DOMENIU, Q_TIP, Q_ACOPERIRE, Q_ORAS, Q_AUTOR, Q_LINKURI, Q_EMAIL,
 Q_ALTCEVA) = TITLES

SCOPES = ["https://www.googleapis.com/auth/forms.body"]
API = "https://forms.googleapis.com/v1/forms"
TEMPLATE = DATA / "form.json"
ANSWER_MAP = DATA / "form-v2.json"  # taxonomy v2: label -> ID per question, versioned
HINT_MAX = 60  # a taxonomy hint longer than this stays out of the help text
CHOICE_TYPES = {"radio": "RADIO", "dropdown": "DROP_DOWN", "checkbox": "CHECKBOX"}
KIND_NAMES = {"short": "short text", "paragraph": "paragraph", "radio": "radio", "dropdown": "drop-down",
              "checkbox": "checkboxes"}
# What the first question offers: (label in the Form, `fel` in proiecte.csv; "organizatie" = a row of orgs.csv).
FEL_CHOICES = [("Proiect", "proiect"), ("Resursă (listă, ghid, colecție)", "resursa"), ("Organizație", "organizatie")]


@dataclass
class Question:
    title: str
    kind: str  # short | paragraph | radio | dropdown | checkbox
    required: bool = False
    help: str = ""
    choices: list[tuple[str, str]] = field(default_factory=list)  # (label shown in the Form, key in the CSV)

    def item(self) -> dict:
        """The Forms API item for this question."""
        if self.kind in CHOICE_TYPES:
            q = {"choiceQuestion": {"type": CHOICE_TYPES[self.kind], "options": [{"value": label} for label, _ in self.choices]}}
        else:
            q = {"textQuestion": {"paragraph": self.kind == "paragraph"}}
        item = {"title": self.title, "questionItem": {"question": {"required": self.required, **q}}}
        if self.help:
            item["description"] = self.help
        return item


def taxonomy_choices(tax: dict, name: str) -> list[tuple[str, str]]:
    return [(e["label"], e["key"]) for e in tax[name]]


def with_hints(intro: str, tax: dict, name: str) -> str:
    """Help text: the intro, then one `label: hint` line per entry whose hint is short (a drop-down has no per-choice text)."""
    lines = [f"{e['label']}: {e['hint']}" for e in tax[name] if e.get("hint") and len(e["hint"]) <= HINT_MAX]
    return "\n".join([intro, *lines])


def build_questions() -> list[Question]:
    tax = json.loads((DATA / "taxonomy.json").read_text(encoding="utf-8"))
    by_title = {
        Q_FEL: Question(Q_FEL, "radio", required=True, choices=FEL_CHOICES),
        Q_NUME: Question(Q_NUME, "short", required=True, help="Așa cum îl numește proiectul însuși."),
        Q_URL: Question(Q_URL, "short", required=True, help="Adresa principală, cu https://"),
        Q_SCURT: Question(Q_SCURT, "short", help="O frază, sub 90 de caractere."),
        Q_DESCRIERE: Question(Q_DESCRIERE, "paragraph", help="Ce face, pentru cine, din ce date."),
        Q_DOMENIU: Question(Q_DOMENIU, "dropdown", help=with_hints("Domeniul principal.", tax, "domenii"),
                            choices=taxonomy_choices(tax, "domenii")),
        Q_TIP: Question(Q_TIP, "checkbox", help=with_hints("Alege unul sau mai multe.", tax, "tipuri"),
                        choices=taxonomy_choices(tax, "tipuri")),
        Q_ACOPERIRE: Question(Q_ACOPERIRE, "radio", choices=taxonomy_choices(tax, "acoperire")),
        Q_ORAS: Question(Q_ORAS, "short", help="Pentru proiectele locale."),
        Q_AUTOR: Question(Q_AUTOR, "short", help="Oameni sau organizații."),
        Q_LINKURI: Question(Q_LINKURI, "paragraph", help="Rețele sociale, cod sursă, donații; câte unul pe rând."),
        Q_EMAIL: Question(Q_EMAIL, "short", help="Doar dacă vrei să te contactăm."),
        Q_ALTCEVA: Question(Q_ALTCEVA, "paragraph"),
    }
    questions = [by_title[t] for t in TITLES]  # the order of TITLES is the order in the Form
    if TEMPLATE.exists():
        questions = from_template(json.loads(TEMPLATE.read_text(encoding="utf-8")), by_title)
    for q in questions:
        labels = [label for label, _ in q.choices]
        if q.kind in CHOICE_TYPES and not labels:
            raise SystemExit(f"question '{q.title}': the taxonomy gives no choices")
        if len(set(labels)) != len(labels):
            raise SystemExit(f"question '{q.title}': two choices have the same label")
    return questions


def from_template(template: list[dict], defaults: dict[str, Question]) -> list[Question]:
    """The saved Form, with taxonomy-driven choices refreshed from the taxonomy (matched by title)."""
    out = []
    for t in template:
        d = defaults.get(t["title"])
        tax_choices = d.choices if d and d.kind in CHOICE_TYPES and t["kind"] in CHOICE_TYPES else None
        out.append(Question(t["title"], t["kind"], t.get("required", False), t.get("help", ""),
                            tax_choices or [(c, c) for c in t.get("choices", [])]))
    return out


def to_template(form: dict) -> list[dict]:
    """The Form's questions as template entries; items that are not questions (sections, images) are skipped."""
    kinds = {v: k for k, v in CHOICE_TYPES.items()}
    out = []
    for item in form.get("items", []):
        q = item.get("questionItem", {}).get("question")
        if not q or not ("choiceQuestion" in q or "textQuestion" in q):
            log(f"  skipped (not a text or choice question): {item_summary(item)}")
            continue
        entry = {"title": item.get("title", ""), "required": bool(q.get("required"))}
        if "choiceQuestion" in q:
            entry["kind"] = kinds.get(q["choiceQuestion"].get("type"), "radio")
            entry["choices"] = [o.get("value", "") for o in q["choiceQuestion"].get("options", [])]
        else:
            entry["kind"] = "paragraph" if q["textQuestion"].get("paragraph") else "short"
        if item.get("description"):
            entry["help"] = item["description"]
        out.append(entry)
    return out


QUESTIONS = build_questions()
# Answer label -> CSV key, per question title. A later importer of the tab `propuneri` maps the answers back with it.
ANSWER_KEYS = {q.title: dict(q.choices) for q in QUESTIONS if q.choices}


def batch_body(old_items: int, revision: str | None, questions: list[Question] | None = None) -> dict:
    """One batchUpdate: delete the old items (last first, so each index stays valid), then create the planned ones."""
    requests = [{"deleteItem": {"location": {"index": i}}} for i in reversed(range(old_items))]
    requests += [{"createItem": {"item": q.item(), "location": {"index": i}}} for i, q in enumerate(questions or QUESTIONS)]
    body = {"requests": requests, "includeFormInResponse": True}
    if revision:
        body["writeControl"] = {"requiredRevisionId": revision}  # the API refuses (400) if the Form changed since the read
    return body


# ---- Taxonomy v2: questions, answer map, importer --------------------------------------------------------------

# Question titles of the v2 Form, in Form order (the order of the columns of intrari.csv). The response columns of the
# tab `propuneri` are named after them: renaming a title renames a column. Raise `version` in data/form-v2.json first
# (`--write-map` does), and change the importer together with the title.
TITLES_V2 = ["Ce propui?", "Nume", "Pe scurt", "Descriere", "Adresa (URL)", "Alte linkuri", "Subiecte", "Formate",
             "Acoperire", "Oraș", "Autor", "E-mailul tău", "Altceva?"]
(P_KIND, P_NAME, P_SHORT, P_DESC, P_URL, P_LINKS, P_SUBJECTS, P_FORMATS, P_COVERAGE, P_CITY, P_AUTHOR, P_EMAIL,
 P_OTHER) = TITLES_V2
CHOICE_TITLES_V2 = (P_KIND, P_SUBJECTS, P_FORMATS, P_COVERAGE)  # the questions whose choice labels map to IDs
# The site has three sections. A kind that is neither a project nor an organisation goes to "Resurse & liste", as every
# `fel` but `proiect` does in v1. The stored map (data/form-v2.json, `kind_section`) has the final word.
KIND_SECTION = {"proiect": "proiect", "organizatie": "organizatie", "resursa": "resursa", "publicatie": "resursa",
                "set-date": "resursa", "campanie": "resursa"}
# Every national entry of the integration copy (104 of 104) has the area România; the label "Național" says the same.
NATIONAL_AREA = "tara:RO"


def vocabulary_choices(pkg) -> dict[str, list[tuple[str, str]]]:
    """title -> [(label, ID)]: the active entity kinds, the root subjects, the formats and the coverage levels, with the
    labels of the vocabulary, in its order. Topics, purposes and capabilities stay out: the editor assigns them."""
    live = lambda row: row["statut"] != "retras"
    return {
        P_KIND: [(r["eticheta_ro"], c) for c, r in pkg.codes["tip_entitate"].items() if live(r)],
        P_SUBJECTS: [(r["eticheta_ro"], i) for i, r in pkg.concepts.items() if r["schema"] == "subiect" and not r["mai_larg"] and live(r)],
        P_FORMATS: [(r["eticheta_ro"], i) for i, r in pkg.concepts.items() if r["schema"] == "format" and live(r)],
        P_COVERAGE: [(r["eticheta_ro"], c) for c, r in pkg.codes["nivel_acoperire"].items() if live(r)],
    }


def usage_counts(pkg) -> dict[str, int]:
    """ID -> number of entries that use it (shown in the plan; the Form offers every active choice, used or not)."""
    out: dict[str, int] = {}
    for row in pkg.entries.values():
        for col in ("tip_entitate", "subiecte", "formate", "nivel_acoperire"):
            for ident in (row[col].split("|") if row[col] else []):
                out[ident] = out.get(ident, 0) + 1
    return out


def build_questions_v2(pkg) -> list[Question]:
    """The v2 questions: entity kind, free text, URL, then subjects and formats as checkboxes, coverage, city, author."""
    choices = vocabulary_choices(pkg)
    by_title = {
        P_KIND: Question(P_KIND, "radio", required=True, choices=choices[P_KIND],
                         help="\n".join(["Ce fel de intrare propui?", *(f"{r['eticheta_ro']}: {r['definitie_ro']}" for c, r in pkg.codes["tip_entitate"].items()
                                                                          if r["statut"] != "retras")])),
        P_NAME: Question(P_NAME, "short", required=True, help="Așa cum îl numește proiectul însuși."),
        P_SHORT: Question(P_SHORT, "short", help="O frază, sub 90 de caractere."),
        P_DESC: Question(P_DESC, "paragraph", help="Ce face, pentru cine, din ce date."),
        P_URL: Question(P_URL, "short", required=True, help="Adresa principală, cu https://"),
        P_LINKS: Question(P_LINKS, "paragraph", help="Rețele sociale, cod sursă, donații; câte unul pe rând."),
        P_SUBJECTS: Question(P_SUBJECTS, "checkbox", help="Alege unul sau mai multe subiecte generale. Editorul adaugă temele precise.",
                             choices=choices[P_SUBJECTS]),
        P_FORMATS: Question(P_FORMATS, "checkbox", help="Cum se oferă conținutul. Alege tot ce se potrivește.", choices=choices[P_FORMATS]),
        P_COVERAGE: Question(P_COVERAGE, "radio", choices=choices[P_COVERAGE]),
        P_CITY: Question(P_CITY, "short", help="Pentru proiectele locale: localitatea sau județul."),
        P_AUTHOR: Question(P_AUTHOR, "short", help="Oameni sau organizații."),
        P_EMAIL: Question(P_EMAIL, "short", help="Doar dacă vrei să te contactăm. Nu apare pe site."),
        P_OTHER: Question(P_OTHER, "paragraph"),
    }
    questions = [by_title[t] for t in TITLES_V2]
    for q in questions:
        labels = [label for label, _ in q.choices]
        if q.kind in CHOICE_TYPES and not labels:
            raise SystemExit(f"question '{q.title}': the vocabulary gives no choices")
        if len(set(labels)) != len(labels):
            raise SystemExit(f"question '{q.title}': two choices have the same label")
    return questions


def planned_map(pkg) -> dict[str, dict[str, str]]:
    return {title: dict(pairs) for title, pairs in vocabulary_choices(pkg).items()}


def load_answer_map(path: Path) -> dict | None:
    """The stored answer map, or None when the file does not exist."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not (isinstance(data["version"], int) and isinstance(data["answers"], dict) and isinstance(data["kind_section"], dict)
                and isinstance(data["titles"], list)):
            raise TypeError
        return data
    except (ValueError, KeyError, TypeError):
        sys.exit(f"{path}: not a valid answer map (needs version, titles, answers, kind_section)")


def map_drift(pkg, planned: dict, stored: dict | None) -> dict[str, list]:
    """How the vocabulary and the stored map differ. `new`, `changed`, `titles` and `sections` need an action;
    `kept` (a label that the vocabulary no longer offers) and `dead` (an ID that is gone or retired) are information."""
    out = {"new": [], "changed": [], "kept": [], "dead": [], "titles": [], "sections": []}
    answers = (stored or {}).get("answers", {})
    offered = {ident for labels in planned.values() for ident in labels.values()}
    for title, labels in planned.items():
        have = answers.get(title, {})
        for label, ident in labels.items():
            if label not in have:
                out["new"].append((title, label, ident))
            elif have[label] != ident:
                out["changed"].append((title, label, have[label], ident))
        for label, ident in have.items():
            if label not in labels:
                out["kept" if ident in offered else "dead"].append((title, label, ident))
    if stored is not None and stored["titles"] != TITLES_V2:
        out["titles"].append((stored["titles"], TITLES_V2))
    sections = {r["cod"] for r in pkg.tables["valori.csv"] if r["lista"] == "sectiune_url" and r["statut"] != "retras"}
    for _, kind in planned[P_KIND].items():
        section = (stored or {}).get("kind_section", {}).get(kind)
        if section is None or section not in sections or (kind == "organizatie") != (section == "organizatie"):
            out["sections"].append((kind, section))
    return out


def drift_needs_action(drift: dict) -> bool:
    return any(drift[k] for k in ("new", "changed", "titles", "sections"))


ANSWER_MAP_DOC = ("Answer map of the v2 proposal Form: for each choice question, the label shown in the Form and the ID it stands for. "
                  "`kind_section` gives the site section of each entity kind. `version` goes up whenever a title or a label is added; "
                  "a label is never removed, so that old responses in the tab `propuneri` still map to the same ID. "
                  "Write it with `scripts/form.py --data-dir <v2 root> --write-map`.")


def updated_answer_map(stored: dict | None, planned: dict) -> dict:
    """The stored map plus the new labels. Old labels stay (old responses still map to their IDs). `version` goes up by
    one when anything changes (1 for a new file)."""
    data = {"version": 0, "titles": TITLES_V2, "answers": {}, "kind_section": {}}
    if stored:
        data = {**stored, "answers": {t: dict(m) for t, m in stored["answers"].items()}, "kind_section": dict(stored["kind_section"])}
    before = json.dumps({k: v for k, v in data.items() if k not in ("version", "_doc")}, sort_keys=True)
    for title, labels in planned.items():
        data["answers"].setdefault(title, {}).update({label: ident for label, ident in labels.items() if label not in data["answers"][title]})
    for _, kind in planned[P_KIND].items():
        data["kind_section"].setdefault(kind, KIND_SECTION.get(kind, "resursa"))
    data["titles"] = TITLES_V2
    after = json.dumps({k: v for k, v in data.items() if k not in ("version", "_doc")}, sort_keys=True)
    data["version"] = data["version"] + 1 if (after != before or not stored) else data["version"]
    return {"_doc": ANSWER_MAP_DOC, **{k: v for k, v in data.items() if k != "_doc"}}



def print_drift(drift: dict, stored: dict | None, path: Path):
    shown = path.name
    print(f"\nAnswer map {shown}: " + (f"version {stored['version']}" if stored else "missing (run --write-map)"))
    for title, label, ident in drift["new"]:
        print(f"  new label, not in the map: {title}: {label!r} -> {ident}")
    for title, label, old, new in drift["changed"]:
        print(f"  CHANGED: {title}: {label!r} is mapped to {old}, the vocabulary says {new}")
    for old, new in drift["titles"]:
        print(f"  titles differ: the map has {old}, the script has {new}")
    for kind, section in drift["sections"]:
        print(f"  no valid site section for the kind {kind!r} (map says {section!r})")
    for title, label, ident in drift["kept"]:
        print(f"  kept for old responses: {title}: {label!r} -> {ident} (the Form no longer offers it)")
    for title, label, ident in drift["dead"]:
        print(f"  dead: {title}: {label!r} -> {ident} (the vocabulary has no active {ident})")
    if not any(drift.values()):
        print("  every label of the plan is in the map")


# ---- Importing the responses (tab `propuneri`) -----------------------------------------------------------------

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def fold(s: str) -> str:
    """Case and diacritics removed, spaces collapsed: for comparing a typed place name with a label."""
    s = unicodedata.normalize("NFD", s)
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).casefold().split())


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")


def split_choices(cell: str, labels) -> tuple[list[str], list[str]]:
    """(known labels, unknown pieces) of a checkbox answer. Google Forms joins the ticked labels with ", ", and a label may
    hold a comma itself ("Drept, justiție și drepturi"), so the known labels are matched first, longest first."""
    rest, known, unknown = nfc(cell), [], []
    by_length = sorted(labels, key=len, reverse=True)
    while rest:
        hit = next((label for label in by_length if rest == label or rest.startswith(label + ", ")), None)
        if hit:
            known.append(hit)
            rest = rest[len(hit) + 2:]
        else:
            piece, _, rest = rest.partition(", ")
            unknown.append(piece)
    return known, unknown


@dataclass
class FormModel:
    pkg: object  # taxonomy_v2.Package
    version: int
    titles: list[str]
    answers: dict[str, dict[str, str]]  # title -> NFC label -> ID
    kind_section: dict[str, str]


def load_model(pkg, path: Path = ANSWER_MAP) -> FormModel:
    data = load_answer_map(path)
    if data is None:
        sys.exit(f"{path}: not found. Run --write-map first.")
    return FormModel(pkg, data["version"], data["titles"],
                     {t: {nfc(label): ident for label, ident in m.items()} for t, m in data["answers"].items()}, data["kind_section"])


@dataclass
class Imported:
    row: dict | None  # an intrari.csv row; None when the response cannot become an entry
    problems: list[str] = field(default_factory=list)


def import_response(model: FormModel, response: dict, number: int, taken: set[str]) -> Imported:
    """One response row of `propuneri` (title -> answer) as an intrari.csv row: IDs from the stored answer map,
    clasificare_stare `propus`. A label that the map does not know is reported and left out, never guessed. When the
    subject is not exactly one clear choice, the state is `de-revizuit` and the subjects stay empty (the checks need a
    primary subject whenever `subiecte` has a value). The proposer's e-mail is not copied (the repository is public)."""
    pkg, problems, notes = model.pkg, [], []
    answer = lambda title: nfc(response.get(title) or "")
    where = f"row {number}"
    offered = {title: {ident for _, ident in pairs} for title, pairs in vocabulary_choices(pkg).items()}  # an alias to a gone ID is unusable

    def pick(title: str) -> str | None:
        """The ID of a single-choice answer; None (with a problem) when it is empty or unknown."""
        label = answer(title)
        ident = model.answers.get(title, {}).get(label)
        ident = ident if ident in offered[title] else None
        if label and ident is None:
            problems.append(f"{where}: unknown answer to «{title}»: {label!r}")
            notes.append(f"Răspuns necunoscut la «{title}»: {label}.")
        return ident

    def pick_many(title: str) -> list[str]:
        known, unknown = split_choices(answer(title), model.answers.get(title, {}))
        for piece in unknown:
            problems.append(f"{where}: unknown label in «{title}»: {piece!r}")
            notes.append(f"Etichetă necunoscută la «{title}»: {piece}.")
        ids = [model.answers[title][label] for label in known]
        for label in known:
            if model.answers[title][label] not in offered[title]:
                problems.append(f"{where}: the label {label!r} in «{title}» maps to an ID that the vocabulary no longer offers")
        return list(dict.fromkeys(i for i in ids if i in offered[title]))

    kind = pick(P_KIND)
    name = answer(P_NAME)
    slug = slugify(name)
    section = model.kind_section.get(kind or "")
    if kind is None or section is None:
        return Imported(None, problems + [f"{where}: no entity kind («{P_KIND}»); row skipped"])
    if not slug:
        return Imported(None, problems + [f"{where}: no name; row skipped"])
    if slug in taken:
        return Imported(None, problems + [f"{where}: the slug {slug!r} exists already; row skipped"])

    subjects = pick_many(P_SUBJECTS)
    formats = pick_many(P_FORMATS)
    coverage = pick(P_COVERAGE) or "necunoscut"
    city = answer(P_CITY)
    areas: list[str] = []
    if coverage == "national":
        areas = [NATIONAL_AREA] if NATIONAL_AREA in pkg.areas else []
    elif coverage == "local":
        places = {fold(r["eticheta_ro"]): i for i, r in pkg.areas.items() if r["tip"] in ("localitate", "judet")}
        if city and fold(city) in places:
            areas = [places[fold(city)]]
        else:  # local coverage needs a locality or county of arii.csv; without one the level stays unknown
            coverage = "necunoscut"
            problems.append(f"{where}: local coverage, but {city!r} is not a locality or county of arii.csv; the level is set to necunoscut")
            notes.append(f"Formularul indică acoperire locală; localitatea «{city}» nu este în arii.csv.")
    state = "propus"
    if len(subjects) == 1:
        primary = subjects[0]
    else:  # no subject, or several: the editor picks the primary one (`subiecte` stays empty, or the checks fail)
        primary, state = "", "de-revizuit"
        notes.append(f"Subiecte indicate în formular: {'|'.join(subjects)}. Alegeți subiectul principal." if subjects
                     else "Fără subiect în formular.")
        subjects = []
    when = answer("Timestamp")
    columns = pkg.schema["headers"]["intrari.csv"]
    row = dict.fromkeys(columns, "")
    row.update({
        "slug": slug, "tip_entitate": kind, "sectiune_url": section, "nume": name, "descriere_scurta": answer(P_SHORT),
        "descriere": answer(P_DESC), "url": answer(P_URL), "linkuri": " ".join(split_list(answer(P_LINKS))),
        "subiect_principal": primary, "subiecte": "|".join(subjects), "formate": "|".join(formats),
        "nivel_acoperire": coverage, "arii_acoperite": "|".join(areas), "localitate_originala": city,
        "autor_original": answer(P_AUTHOR), "nota": f"Formular: {answer(P_OTHER)}" if answer(P_OTHER) else "",
        "clasificare_stare": state, "incredere": "mica",
        "nota_clasificare": " ".join([f"Propunere din formular, rândul {number}" + (f" ({when})." if when else "."), *notes]),
    })
    if answer(P_EMAIL):
        problems.append(f"{where}: the e-mail is not copied to the entry (the repository is public)")
    taken.add(slug)
    return Imported(row, problems)


def cmd_import(model: FormModel, source: Path, out: Path | None) -> int:
    """Map the responses of an export of the tab `propuneri` to intrari.csv rows: CSV to `out` or stdout, a report on stderr."""
    reader = csv.DictReader(io.StringIO(source.read_text(encoding="utf-8-sig"), newline=""))
    missing = [t for t in model.titles if t not in (reader.fieldnames or [])]
    if missing:
        sys.exit(f"{source}: the columns {missing} are missing. Version {model.version} of the answer map expects these titles.")
    taken, rows, skipped = set(model.pkg.entries), [], 0
    columns = model.pkg.schema["headers"]["intrari.csv"]
    for number, response in enumerate(reader, start=2):  # row 1 is the header, as in the Sheet
        done = import_response(model, response, number, taken)
        for p in done.problems:
            log(p)
        if done.row:
            rows.append(done.row)
        else:
            skipped += 1
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    if out:
        out.write_text(buf.getvalue(), encoding="utf-8")
    else:
        sys.stdout.write(buf.getvalue())
    log(f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'} mapped, {skipped} row(s) skipped. "
        f"The editor copies the rows to intrari.csv by hand and checks them with validate.py.")
    return 1 if skipped else 0


def main_v2(args, root: Path):
    """The v2 mode: offline. It plans from the vocabulary, keeps the answer map, and maps responses. No Google call."""
    if args.apply or args.save:
        sys.exit("--apply and --save are not available with a v2 --data-dir: the live Form keeps the v1 questions until the cutover")
    from taxonomy_v2 import load
    pkg = load(root)
    path = args.answer_map
    stored = load_answer_map(path)
    if args.import_file:
        if args.write_map or args.check:
            sys.exit("--import does not combine with --write-map or --check")
        sys.exit(cmd_import(load_model(pkg, path), args.import_file, args.out))
    planned, questions = planned_map(pkg), build_questions_v2(pkg)
    drift = map_drift(pkg, planned, stored)
    if args.write_map:
        if drift["changed"]:
            print_drift(drift, stored, path)
            sys.exit("a label is mapped to another ID than the vocabulary says. Fix the map by hand: a renamed label must keep its ID.")
        data = updated_answer_map(stored, planned)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {path} (version {data['version']})")
        stored, drift = data, map_drift(pkg, planned, data)
    print_plan(questions, planned, usage_counts(pkg), f"{path.name}, version {stored['version']}" if stored else "the plan; no map file yet")
    print_drift(drift, stored, path)
    if args.json:
        print("\nbatchUpdate body (for a Form with no items):")
        print(json.dumps(batch_body(0, None, questions), ensure_ascii=False, indent=2))
    print("\nNothing is sent to Google: a v2 root only plans. The live Form keeps the v1 questions until the cutover.")
    if args.check and drift_needs_action(drift):
        sys.exit(1)


# ---- Google access ---------------------------------------------------------------------------------------------

def log(*a):
    print(*a, file=sys.stderr, flush=True)


def credentials_info() -> dict | None:
    """The service-account key as a dict, or None when none is set. Errors never quote the key."""
    key, path = os.environ.get("GOOGLE_SA_KEY", "").strip(), os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not key and not path:
        return None
    try:
        if key:
            return json.loads(key)
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        sys.exit("the service-account key is not readable or not valid JSON (GOOGLE_SA_KEY, GOOGLE_APPLICATION_CREDENTIALS)")


def open_session(info: dict):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials
    try:
        return AuthorizedSession(Credentials.from_service_account_info(info, scopes=SCOPES))
    except (ValueError, KeyError, TypeError):
        sys.exit("the service-account key is not a valid key (GOOGLE_SA_KEY, GOOGLE_APPLICATION_CREDENTIALS)")


def api_error(r) -> str:
    try:
        err = r.json()["error"]
        return f"HTTP {r.status_code} {err.get('status', '')}: {err.get('message', '')}".strip()
    except (ValueError, KeyError, TypeError):
        return f"HTTP {r.status_code}"


def get_form(session, form_id: str) -> dict:
    r = session.get(f"{API}/{form_id}", timeout=30)
    if not r.ok:
        sys.exit(f"cannot read the Form: {api_error(r)}")
    return r.json()


def item_summary(item: dict) -> str:
    """One line for an existing item: its title and kind."""
    title = item.get("title") or "(no title)"
    q = item.get("questionItem", {}).get("question")
    if not q:
        kind = next((k for k in item if k.endswith("Item")), "item")
    elif "choiceQuestion" in q:
        kind = q["choiceQuestion"].get("type", "choice").lower()
    elif "textQuestion" in q:
        kind = "paragraph" if q["textQuestion"].get("paragraph") else "short text"
    else:
        kind = next((k for k in q if k.endswith("Question")), "question")
    return f"{title}  [{kind}{', required' if q and q.get('required') else ''}]"


# ---- Output ----------------------------------------------------------------------------------------------------

def print_plan(questions: list[Question] | None = None, answer_keys: dict | None = None, counts: dict | None = None,
               source: str = "ANSWER_KEYS in the script"):
    """The planned questions and the label -> key map. `counts`: key -> number of entries that use it (v2)."""
    questions, answer_keys = questions or QUESTIONS, answer_keys or ANSWER_KEYS
    print(f"Planned questions ({len(questions)}), in this order:")
    for n, q in enumerate(questions, 1):
        print(f"{n:>3}. {q.title}  [{KIND_NAMES[q.kind]}, {'required' if q.required else 'optional'}]")
        for i, line in enumerate(q.help.splitlines()):
            print(f"       {'help: ' if i == 0 else '      '}{line}")
        for label, key in q.choices:
            n = counts.get(key, 0) if counts is not None else None
            print(f"       - {label}" + ("" if n is None else f"  ({n} {'entry' if n == 1 else 'entries'})"))
    print(f"\nAnswer label -> CSV key ({source}; the response columns are named after the question titles):")
    for title, keys in answer_keys.items():
        print(f"  {title}")
        for label, key in keys.items():
            print(f"    {label!r} -> {key}")


def print_form(form: dict):
    items = form.get("items", [])
    print(f"\nThe Form now: \"{form.get('info', {}).get('title', '')}\", {len(items)} item(s), "
          f"revision {form.get('revisionId', '?')}, linked Sheet {'yes' if form.get('linkedSheetId') else 'no'}")
    for i, item in enumerate(items):
        print(f"  {i}. {item_summary(item)}")
    if items and form.get("linkedSheetId"):
        print("  Note: the Sheet may keep the column of each deleted question (not measured); check row 1 of `propuneri` after --apply.")


def print_calls(form: dict | None):
    if form is None:
        deletes = "one deleteItem per existing item, last first"
    else:
        old = len(form.get("items", []))
        deletes = f"{old} deleteItem" + (f" (index {old - 1} down to 0)" if old > 1 else " (index 0)" if old else "")
    print("\n`--apply` makes these API calls (nothing is sent now):")
    print(f"  1. GET  {API}/<FORM_ID>   (read the items and the revision ID)")
    print(f"  2. POST {API}/<FORM_ID>:batchUpdate   (one call, all or nothing):")
    print(f"       {deletes}, then {len(QUESTIONS)} createItem (index 0..{len(QUESTIONS) - 1})")
    print("       writeControl.requiredRevisionId = the revision read in step 1; includeFormInResponse = true")
    print("     It sends no updateFormInfo, updateSettings or setPublishSettings request: title, description, settings and")
    print("     response destination stay as they are.")


def main():
    load_env()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Default: print the plan and the Form as it is now; no writes.")
    ap.add_argument("--apply", action="store_true", help="replace all items of the Form with the planned ones")
    ap.add_argument("--json", action="store_true", help="also print the batchUpdate body")
    ap.add_argument("--save", action="store_true", help=f"store the Form as it is now in {TEMPLATE.relative_to(DATA.parent)}")
    ap.add_argument("--data-dir", type=Path, default=PUBLIC_ROOT, help="data root (default: the public root, PUBLIC_ROOT in common.py; a v1 root plans the v1 Form, a v2 root plans offline)")
    ap.add_argument("--answer-map", type=Path, default=ANSWER_MAP, help="v2: the versioned label -> ID file")
    ap.add_argument("--write-map", action="store_true", help="v2: add the labels of the plan to the answer map (version + 1)")
    ap.add_argument("--check", action="store_true", help="v2: exit 1 when the answer map lacks a label of the plan")
    ap.add_argument("--import", dest="import_file", type=Path, metavar="CSV", help="v2: map an export of the tab `propuneri` to intrari.csv rows")
    ap.add_argument("--out", type=Path, help="v2 --import: write the rows to this file, not to stdout")
    args = ap.parse_args()
    if data_schema(args.data_dir.resolve()) == "v2":
        return main_v2(args, args.data_dir.resolve())
    if args.write_map or args.check or args.import_file or args.out:
        sys.exit("--write-map, --check, --import and --out need a v2 --data-dir")

    form_id, info = os.environ.get("FORM_ID", "").strip(), credentials_info()
    if (args.apply or args.save) and not (form_id and info):
        sys.exit("--apply and --save need FORM_ID and a key (GOOGLE_SA_KEY or GOOGLE_APPLICATION_CREDENTIALS)")
    if args.save:
        template = to_template(get_form(open_session(info), form_id))
        TEMPLATE.write_text(json.dumps(template, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        missing = [t for t in (Q_FEL, Q_DOMENIU, Q_TIP, Q_ACOPERIRE) if t not in {e["title"] for e in template}]
        print(f"saved {len(template)} questions to {TEMPLATE.relative_to(DATA.parent)}")
        if missing:
            print(f"note: no question titled {missing}: their answers no longer map to taxonomy keys")
        return

    print_plan()
    session = form = None
    if form_id and info:
        session = open_session(info)
        form = get_form(session, form_id)
        print_form(form)
    else:
        log("\nThe Form was not read: set FORM_ID and a key (GOOGLE_SA_KEY or GOOGLE_APPLICATION_CREDENTIALS) to see it.")
    if args.json:
        print("\nbatchUpdate body:")
        print(json.dumps(batch_body(len(form.get("items", [])) if form else 0, form.get("revisionId") if form else None),
                         ensure_ascii=False, indent=2))
    if not args.apply:
        print_calls(form)
        return

    body = batch_body(len(form.get("items", [])), form.get("revisionId"))
    r = session.post(f"{API}/{form_id}:batchUpdate", json=body, timeout=60)
    if not r.ok:
        sys.exit(f"batchUpdate failed, the Form is unchanged: {api_error(r)}")
    done = r.json().get("form", {})
    titles = [it.get("title") for it in done.get("items", [])]
    if titles != [q.title for q in QUESTIONS]:
        sys.exit(f"batchUpdate answered 200, but the Form now has these items: {titles}")
    print(f"\nDone: replaced {len(form.get('items', []))} item(s) with {len(titles)}. Revision {done.get('revisionId', '?')}.")


if __name__ == "__main__":
    main()
