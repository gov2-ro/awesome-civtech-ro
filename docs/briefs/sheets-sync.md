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

## v2: sync base, v2 tabs, blocking validation (2026-10-20)

Slice B of `docs/briefs/v2-migration-completion.md`. Production stays on v1: the live tabs `proiecte` and `orgs`
behave as before (same headers, same commands). No v2 job runs in the workflows. Offline tests are in
`scripts/test_sheets_form.py` (a Sheet double, a temporary git repository, stub commands for the workflow shell).

### Decisions

- **V1. Data root and tabs.** `sheets.py diff|pull|push --data-dir <root> [--tabs a,b]`. The default root is `data/`
  (tabs `proiecte`, `orgs`). A v2 root has the tab `v2-intrari` (a mirror of its `intrari.csv`; the headers come from
  `schema.json`) and the optional `v2-revizuire` (`revizuire.csv`, keyed by `id`). A root refuses the tabs of the
  other schema, `propuneri` and `_sync` before it calls the Sheet. `push` creates a missing `v2-` tab and never a v1
  tab. IDs stay text (every cell is `TEXT`). A cell with `|` takes several IDs, so a drop-down is strict only in a
  single-value column; multi-value columns get a suggestion list when it has at most 40 values.
- **V2. Sync marker.** The tab `_sync` has one row per synced tab: `tab, commit, sha256, time`. `push` writes it last,
  and only when the CSV it pushed equals the file at `HEAD` (else it warns and keeps the old row). A reader runs
  `git show <commit>:<path>` and compares the SHA-256. A mismatch or a missing commit is an error (exit 1) with three
  ways out: fetch the history, pass `--since <ref>`, or run `push --force` from a clean checkout. Deleting a row makes
  that tab two-way again. Without a marker, `pull` copies the Sheet over the CSV (a warning says so), and `push`
  compares the Sheet with the current CSV (the old rule).
- **V3. Three-way pull.** Base = the CSV at the marker's commit (or at `--since`), head = the CSV now, sheet = the
  Sheet. Per cell: sheet = head → that value; only the sheet differs from the base → the sheet's value; only the head
  differs → the repo's value; all three differ → conflict. A row is added or deleted when only one side did it; a row
  deleted on one side and changed on the other is a conflict. The row order follows the side that did not move rows;
  when both did, the repo order wins. Any conflict: exit 3, the list on stdout, nothing written for any tab.
  `pull --since HEAD` lets the Sheet win every conflict. `diff` shows what `pull` would write, what the repo has that
  the Sheet lacks, and the conflicts. `pull` lists the cells each side changed since the base.
- **V4. Push check.** A Sheet cell is pending when it differs from the base and from the head. The base is the marker's
  CSV, not the `before` of the workflow run: a skipped run does not move it, so the false exit 3 of superseded runs is
  gone. Base and Sheet are read by column name, so a changed column list needs no `--force`. A Sheet column that holds
  data and is not in the base header stops the push. `push` clears the rows below and the columns to the right of the
  table, so a dropped column leaves nothing behind.
- **V5. Validation.** `pull --check` writes the CSVs, runs `validate.py --data-dir <root>`, prints its output and exits 1
  on errors. A v2 root gets the package checks (per-token IDs, schemes, levels, counts). The workflow keeps its own
  `validate.py` and `build.py` step, because the pull request text needs their output apart.
- **V6. Workflows.** `sheets-pull`: `fetch-depth: 0` (the marker commit is older than the tip); exit 3 of `pull` fails
  the step with an annotation before any pull request is touched; after the pull request exists, a last step sets the
  commit status `validate / sheets-pull` on its head (`gh api`, needs `permissions: statuses: write`) to `success` or
  `failure`, and fails the job on `failure`. `sheets-push`: no `--since $BEFORE`; the manual inputs `since` and `force`
  stay.
- **V7. Form (v2).** `form.py --data-dir <v2 root>` plans offline from the vocabulary: entity kind (radio), name,
  short text, description, URL, other links, subjects and formats (checkboxes), coverage, city, author, e-mail, notes.
  The Form offers every active root subject and format, and the plan shows how many entries use each. The versioned
  answer map is `data/form-v2.json` (`version`, `titles`, `answers`: title → label → ID, `kind_section`). `--write-map`
  adds new labels and raises `version`; it never removes a label, and it refuses to change the ID of a label.
  `--check` exits 1 on drift. `--apply` and `--save` are refused for a v2 root. `--import` maps an export of the tab
  `propuneri` to `intrari.csv` rows (see the README). The question order follows the columns of `intrari.csv`.

### Rules for the importer

- An unknown label is reported and left out. A label matches only when it is equal (after Unicode normalisation).
- `clasificare_stare` is `propus` when exactly one root subject is ticked. With no subject or several, it is
  `de-revizuit`, and `subiect_principal` and `subiecte` stay empty (the package checks fail on `subiecte` without a
  primary subject). The ticked IDs go to `nota_clasificare`.
- Coverage `Local` needs a locality or county of `arii.csv` that equals the typed city (case and diacritics aside). If
  none does, the level is `necunoscut`, and the typed text stays in `localitate_originala`. `Național` gives `tara:RO`,
  as in the 104 national entries.
- The slug comes from the name. A slug that exists already skips the row. The e-mail of the proposer is not copied: the
  repository is public.

### Activation (owner)

1. Merge the branch. Nothing runs until a workflow or a command runs.
2. v1: Settings → Actions → General → allow Actions to create pull requests (still open from the first brief).
3. v1: decide the cell `demoanaf` / `descriere`. Then run *Actions → sheets-push → Run workflow* from `main` with
   `force`. That creates the tab `_sync` and the first markers. Until then `sheets-pull` is two-way and warns.
4. Optional: require the status `validate / sheets-pull` in the branch protection of `main`. The status exists only on
   the head of the `sheets-sync` pull request, so a required status blocks every other pull request unless you merge
   as an administrator. Without the rule, the red status and the failed job are the signal.
5. v2 (later, by hand): commit `intrari.csv`, then `uv run scripts/sheets.py push --data-dir data/taxonomy-v2/integrare`.
   It creates `v2-intrari` and its marker. Then put the tab's `gid` in `tabs.intrari` of `setari.json` of the v2
   package. Add `--tabs v2-intrari,v2-revizuire` for the review queue.
6. v2 Form: nothing to do now. At the cutover, run `form.py` against the live Form with a new `--apply` path.

### Not verified (no Google call was made)

- The double mimics `get_all_values`, `update`, `resize`, `batch_clear`, `add_worksheet`, `batch_update`, and the
  refusal of a write outside the grid. The signatures of these calls were read in gspread 6.2.1 (installed from PyPI;
  no Google call): they match the calls of `sheets.py`. No call was run against a real Sheet. Open points:
  `add_worksheet` by the service account (an Editor should be allowed); `batch_clear` with two ranges in one call;
  the shape of `get_all_values` on a new empty tab (the code accepts `[]` and `[[]]`).
- Hex digests in `_sync` stay text because the values go in raw and the format is `TEXT`; not seen in a real Sheet.
- `gh api .../statuses/<sha>` with `GITHUB_TOKEN` and `statuses: write`; the 140-character limit of `description` is
  respected (the texts are under 40 characters). The shell of each step ran against stub commands, not on GitHub.
- Suggestion drop-downs on multi-value cells replace the cell with one value when a person picks one. The list only
  suggests, but the pick overwrites. Tell the editors, or remove those lists.
