# Brief: two-way sync between Google Sheets and the CSVs

Owner model: Sonnet. Approved by the owner on 2026-10-18.

## Goal

The editor can edit `proiecte.csv` and `orgs.csv` in a Google Sheet. Sheet edits reach the repo
as a pull request; merged changes flow back to the Sheet. The repo stays the source of truth.

## Given

- Sheet `civtech.gov2.ro`, tabs `proiecte` and `orgs`. The service account can open it (checked).
- Locally: `.env` at the repo root has `GOOGLE_APPLICATION_CREDENTIALS` (path to the key) and
  `SHEET_ID`. Load with `set -a; source .env; set +a`.
- On GitHub: secret `GOOGLE_SA_KEY` (the key's JSON content) and variable `SHEET_ID`.
- Column lists: `PROIECTE_COLS` and `ORGS_COLS` in `scripts/common.py`.

## Decisions (fixed)

- **D1. One script, `scripts/sheets.py`** (PEP 723 header; dependencies `gspread`, `google-auth`).
  Subcommands:
  - `diff`: print, per tab, rows added / removed / changed (by `slug`, cell by cell). No writes.
  - `pull`: write the Sheet's tabs to `data/proiecte.csv` and `data/orgs.csv`.
  - `push`: write the CSVs to the Sheet.
  Credentials: `GOOGLE_SA_KEY` (JSON text) when set, else the file in
  `GOOGLE_APPLICATION_CREDENTIALS`. Sheet: `SHEET_ID`.
- **D2. Pull keeps the CSV format.** Read with `get_all_values()` (strings). Row 1 must equal the
  column list exactly; otherwise exit with an error that names the difference. Drop trailing empty
  rows and rows with every cell empty; strip each cell's trailing spaces and line-ending `\r`.
  Write with `csv.DictWriter(lineterminator="\n")`, so that an unchanged Sheet gives a
  byte-identical file (`git diff` empty). Test that round trip.
- **D3. Push writes the whole tab** in one `update` call (header + rows), clears rows below,
  freezes row 1, makes it bold, and sets every cell to plain text (`numberFormat TEXT`), so Sheets
  never turns `1`, dates or slugs into numbers. Optional: data-validation drop-downs for `fel`,
  `domeniu`, `tip` (first value only is enough), `acoperire`, `stare`, `civictech`, from
  `data/taxonomy.json`.
- **D4. Push never destroys pending Sheet edits.** `push --since <git-ref>` first compares the
  Sheet with the CSVs at `<git-ref>` (the state the Sheet was last synced from). If they differ,
  the Sheet holds edits not yet in the repo: do not write; exit 3 and print the diff. Without
  `--since`, `push` refuses when the Sheet differs from the current CSVs, unless `--force`.
- **D5. Workflow `.github/workflows/sheets-pull.yml`**: on `schedule` (every 6 hours) and
  `workflow_dispatch`. Steps: checkout, setup-python 3.12, install uv, `sheets.py pull`. If the
  CSVs changed: run `validate.py` and `build.py` (do not commit `data.json`; Pages rebuilds it),
  then create or update one PR from branch `sheets-sync` (force-pushed) to `main`, titled
  "Sheets: modificări din tabel", body = the `diff` output plus the `validate.py` output.
  Use `gh pr create`/`gh pr edit` with `GITHUB_TOKEN`. Permissions: `contents: write`,
  `pull-requests: write`. Never push to `main`.
  Note in the report: a PR opened with `GITHUB_TOKEN` does not trigger `validate.yml`; that is
  why validation runs inside this job.
- **D6. Workflow `.github/workflows/sheets-push.yml`**: on `push` to `main` with paths
  `data/proiecte.csv`, `data/orgs.csv`; plus `workflow_dispatch`. Runs
  `sheets.py push --since ${{ github.event.before }}`. Exit 3 (pending Sheet edits) fails the job
  with a clear message: "Tabelul are modificări nesincronizate; rulează sheets-pull".
- **D7. Concurrency:** both workflows share `concurrency: group: sheets`, `cancel-in-progress:
  false`.

## Rules

- Stay in `scripts/sheets.py`, `.github/workflows/sheets-*.yml`, `README.md` (the Google Sheets
  section: replace "Planned" with how it works now), `docs/BACKLOG.md`, `docs/ACTIVITY.md`.
- Never edit `proiecte.csv` / `orgs.csv` by hand. A `pull` that changes them is a test result:
  report the diff, then restore them with `git checkout -- data/proiecte.csv data/orgs.csv`.
- **Before the first `push` to the real Sheet, run `diff`.** If a tab has data rows that differ
  from the CSVs, stop and report: the owner may have edits there. If the tabs are empty or match,
  run `push` once to fill them, then `pull` and confirm `git diff` is empty.
- Do not commit, do not push to GitHub, do not trigger workflows.
- Match the style of the other scripts.

## Report

Files changed; the round-trip result (`push` → `pull` → `git diff`), byte for byte; what `diff`
showed before the first push; anything the owner must switch on in GitHub (e.g. Settings → Actions
→ General → "Allow GitHub Actions to create and approve pull requests"); what you assumed.
Add an ACTIVITY entry and flip the BACKLOG item.

## Accepted at review (2026-10-18)

- **D4 refined to a three-way check.** As written, merging a Sheet PR (Sheet = A+E, `before` = A)
  always exited 3, so the Sheet was never rewritten. Now a Sheet change counts as pending only when
  it is in neither the CSVs at `--since` nor the current CSVs. A Sheet edit missing from the repo
  still exits 3 and writes nothing.
- The first push to the real tabs was not made: `proiecte` differs in one cell
  (`demoanaf` / `descriere`), probably an owner edit. The owner decides: `pull` or `push --force`.
