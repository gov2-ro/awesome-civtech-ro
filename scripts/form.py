# /// script
# requires-python = ">=3.11"
# dependencies = ["google-auth>=2.30", "requests>=2.32"]
# ///
"""Generate the questions of the proposal Form ("Sugestii listă civtech.gov2.ro") from the data model.

    uv run scripts/form.py            # print the planned questions and the Form as it is now; writes nothing
    uv run scripts/form.py --json     # the same, plus the forms.batchUpdate body
    uv run scripts/form.py --apply    # replace ALL items of the Form with the planned ones (one batchUpdate)
    uv run scripts/form.py --save     # read the Form as edited by hand and store it as the template, data/form.json

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
"""
import argparse
import json
import os
import sys
from dataclasses import dataclass, field

from common import load_env, DATA

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


def batch_body(old_items: int, revision: str | None) -> dict:
    """One batchUpdate: delete the old items (last first, so each index stays valid), then create the planned ones."""
    requests = [{"deleteItem": {"location": {"index": i}}} for i in reversed(range(old_items))]
    requests += [{"createItem": {"item": q.item(), "location": {"index": i}}} for i, q in enumerate(QUESTIONS)]
    body = {"requests": requests, "includeFormInResponse": True}
    if revision:
        body["writeControl"] = {"requiredRevisionId": revision}  # the API refuses (400) if the Form changed since the read
    return body


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

def print_plan():
    print(f"Planned questions ({len(QUESTIONS)}), in this order:")
    for n, q in enumerate(QUESTIONS, 1):
        print(f"{n:>3}. {q.title}  [{KIND_NAMES[q.kind]}, {'required' if q.required else 'optional'}]")
        for i, line in enumerate(q.help.splitlines()):
            print(f"       {'help: ' if i == 0 else '      '}{line}")
        for label, key in q.choices:
            print(f"       - {label}")
    print("\nAnswer label -> CSV key (ANSWER_KEYS in the script; the response columns are named after the question titles):")
    for title, keys in ANSWER_KEYS.items():
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
    args = ap.parse_args()

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
