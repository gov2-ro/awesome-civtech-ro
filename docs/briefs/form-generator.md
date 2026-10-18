# Brief: generate the proposal Form from the data model

Owner model: Sonnet. Approved by the owner on 2026-10-18.

## Given

- Form `Sugestii listă civtech.gov2.ro`; its edit ID is `FORM_ID` in `.env`. The service account
  is an editor (checked: `GET forms/{id}` answers 200). Google Forms API is enabled.
- Responses go to tab `propuneri` of the Sheet `SHEET_ID`. It has 0 responses.
- Credentials as in `scripts/sheets.py` (being written in parallel; do not edit it):
  `GOOGLE_SA_KEY` JSON text, else the file in `GOOGLE_APPLICATION_CREDENTIALS`.
  Scope `https://www.googleapis.com/auth/forms.body`.

## Decisions (fixed)

- **D1. A separate script, `scripts/form.py`** (PEP 723; `google-auth`, `requests` or `httpx`).
  Default mode prints the planned questions (no writes). `--apply` replaces **all** items of the
  Form with the planned ones in one `forms.batchUpdate` (delete existing items, then create).
  It never changes the Form's title, description, settings or response destination.
- **D2. Questions, in this order** (titles in Romanian with diacritics, short help text):
  1. `Ce propui?` — radio: Proiect / Resursă (listă, ghid, colecție) / Organizație → `fel`
     (`proiect` / `resursa` / orgs.csv). Required.
  2. `Nume` — short text. Required.
  3. `Adresa (URL)` — short text, URL validation if the API allows it. Required.
  4. `Pe scurt` — short text, help "o frază, sub 90 de caractere".
  5. `Descriere` — paragraph.
  6. `Domeniu` — drop-down from `taxonomy.json` → `domenii` (`label`; show the `hint` in the help
     text only if short).
  7. `Tip` — checkboxes from `tipuri` (`label`).
  8. `Acoperire` — radio from `acoperire`.
  9. `Oraș` — short text, help "pentru proiectele locale".
  10. `Autor` — short text, help "oameni sau organizații".
  11. `Alte linkuri` — paragraph, help "rețele sociale, cod sursă, donații; câte unul pe rând".
  12. `E-mailul tău` — short text, optional, help "doar dacă vrei să te contactăm".
  13. `Altceva?` — paragraph, optional.
  Choice labels come from the taxonomy so that a taxonomy change only needs a re-run. Keep a
  `LABEL → key` map in the script (and print it) so a later importer can map answers back.
- **D3. Stable titles.** The response columns in `propuneri` follow the question titles. Put
  the titles in one constant list at the top of the script, with a comment that renaming one
  renames a Sheet column.

## Rules

- Write only `scripts/form.py`, `README.md` (a short "Formular" part in the Google Sheets
  section), `docs/BACKLOG.md`, `docs/ACTIVITY.md`.
- **Do not run `--apply`.** Run the default mode and put its full output in your report; the owner
  approves before the Form changes.
- Load credentials only with `set -a; source .env; set +a` in the same command; never print them.
- Do not commit or push.

## Report

Files changed; the dry-run output (questions with types, choices, required flags); the API calls
`--apply` will make; anything assumed.
