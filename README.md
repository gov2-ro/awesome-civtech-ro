<img src="docs/reference/logo/g2-0-128.png" width=128 style="float: right;">

[civtech.gov2.ro](https://civtech.gov2.ro/) &middot; listă de proiecte &amp; resurse de civtech, transparență, bună administrație și tot așa &rarr; [intrari.csv](data/taxonomy-v2/integrare/intrari.csv). Vezi și [roadmap/backlog](docs/BACKLOG.md), [arhitectura](docs/ARCHITECTURE.md), [schema datelor](docs/DATA-SCHEMA.md) &amp; [metodologia](docs/METODOLOGIE.md) (stare, date, scor).

_Notă_: Verificarea datelor **nu este încă finalizată**.

_Since 2026-10-22 the public source is the taxonomy v2 integration copy, `data/taxonomy-v2/integrare/`. The v1 files in `data/` (`proiecte.csv`, `orgs.csv`, `taxonomy.json`, `profil.csv`, `mentiuni.csv`) are frozen and kept for the rollback; no script reads them unless you pass `--data-dir data`._

Pentru erate sau sugestii de resurse noi, submit a PR sau issue, sau via [Google Form](https://forms.gle/wswqrm7P4QV25NZx7).

![civtech.gov2.ro landing light](docs/reference/civtech.gov2.ro-landing-light.png)
![civtech.gov2.ro landing dark](docs/reference/civtech.gov2.ro-landing-dark.png)

# 🤖🗯️

## Layout
Human-edited data is CSV, so it can be changed in a PR or round-tripped through Google Sheets. See [CONTRIBUTING.md](CONTRIBUTING.md) for every column.
- `data/taxonomy-v2/` — the public source since the cutover. See [Taxonomy v2](#taxonomy-v2).
  - `integrare/intrari.csv` is the human-edited catalogue: one row per entry, with the v2 facets. `integrare/relatii.csv` holds the relations (author, data source), and `integrare/revizuire.csv` the review queue.
  - `concepte.csv`, `arii.csv`, `valori.csv` and the link-role files (`roluri-linkuri.csv`, `gazde-linkuri.csv`) hold the vocabulary. `colectare-interzisa.csv` lists the hosts that no script requests.
  - `observatii/` holds the generated files: `profil.csv` (HTTP status, meta description, image, icon, repositories, social links, Wayback), `mentiuni.csv` (web mentions from `search.py`; only the column `editor` is edited by hand), `mentiuni_etichete.csv` (labels from `review.py`), the documentation and the inventory of the data finder.
  - `setari.json` holds the "report a problem" addresses and the gid of the Sheet tab.
- `data/form-v2.json` — the label-to-ID map of the planned v2 Form
- `data/proiecte.csv`, `data/orgs.csv`, `data/taxonomy.json`, `data/profil.csv`, `data/mentiuni.csv`, `data/mentiuni_etichete.csv`, `data/form.json`, `data/site.json` — the v1 files, frozen since the cutover of 2026-10-22 and kept for the rollback
- `data/international.csv` — international entries, same columns as `proiecte.csv`, kept for the future international mirror
- `site/` — static site; `site/data.json`, `site/feed.xml`, `site/llms.txt` and `site/img/` are build output, not edited
- `docs/` — [ARCHITECTURE](docs/ARCHITECTURE.md), [DATA-SCHEMA](docs/DATA-SCHEMA.md), [METODOLOGIE](docs/METODOLOGIE.md) (in Romanian), [BACKLOG](docs/BACKLOG.md), specifications and briefs

## Run
```sh
python3 scripts/validate.py --publication    # check the public root, the v2 integration copy (CI runs it on every push and PR)
python3 scripts/build.py                     # merge everything into site/data.json, site/feed.xml and site/llms.txt (applies the publication gate)
python3 -m http.server -d site 8000          # preview at http://localhost:8000

uv run scripts/profile.py                    # profile entries not in observatii/profil.csv yet (--only slug,slug; --force for all)
uv run scripts/profile.py --extra            # age, activity, volume, repos, certificates, Wikipedia links (free)
uv run scripts/search.py --only slug,slug    # web mentions via Serper + Brave (paid, ~3 requests per entry)
uv run scripts/search.py --prune-only        # re-apply the pruning rules to observatii/mentiuni.csv (no requests)
uv run scripts/review.py --limit 5           # Claude Haiku suggestions → observatii/review/sugestii.csv (--dry-run to inspect)

python3 -m unittest discover -s scripts -p "test_*.py"   # unit tests: no network, no keys (CI runs them)
```
`profile.py`, `search.py` and `review.py` need [uv](https://docs.astral.sh/uv/). Keys and local settings live in
`.env` at the repo root (gitignored, never committed): `SERPER_API_KEY`, `BRAVE_API_KEY`, `ANTHROPIC_API_KEY`,
`OPR_API_KEY` (`profile.py --opr`), `GITHUB_TOKEN` (optional), `GOOGLE_APPLICATION_CREDENTIALS` (path to the service-account JSON,
kept outside the repo), `SHEET_ID` and `FORM_ID`. Load them with `set -a; source .env; set +a` before a paid or keyed run.

## Editing the data

_Since 2026-10-22 the human-edited files are in `data/taxonomy-v2/integrare/`. The v1 files in `data/` are frozen; the commands below take `--data-dir data` to act on them._

You edit `data/taxonomy-v2/integrare/intrari.csv` and `relatii.csv`, and (rarely) the vocabulary files in
`data/taxonomy-v2/`. The columns are in [docs/DATA-SCHEMA.md](docs/DATA-SCHEMA.md) and
[data/taxonomy-v2/README.md](data/taxonomy-v2/README.md) (Romanian). `observatii/` and `site/` are generated.

Open the CSVs in a text editor, LibreOffice or Excel. Save as UTF-8 with commas, and keep the header row as it is.
A cell with a comma or a line break must be in quotes; spreadsheet programs do this for you.

### What to run after an edit

| You changed | Run |
| --- | --- |
| Text only: name, description, facets, `maturitate`, `stare`, `clasificare_stare` | `validate.py`, then `build.py` |
| `linkuri` | `validate.py`, then `build.py` |
| `url` (a moved site) | `profile.py --only <slug>`, then `search.py --only <slug>`, then `validate.py` and `build.py` |
| you added a row | Use `/add-new-url` (below), or run the steps it lists, including the three inventory steps |
| a `slug` | Avoid it. The old slug's profile, images and search results stay behind under the old name. If you must, rename it also in `observatii/profil.csv`, `observatii/mentiuni.csv` and `relatii.csv`, then run `build.py` |
| the vocabulary files of `data/taxonomy-v2/` | `validate.py`, then `build.py` |

Then commit and push. On every push to `main`, GitHub runs `validate.py` and `build.py` again and publishes
`site/`. On a pull request, `validate.yml` also runs the unit tests and the browser checks (see
[Checks in GitHub](#checks-in-github-ci)). CI does **not** run `profile.py` or `search.py`: run those on your machine and commit
their output (`data/taxonomy-v2/observatii/`, `site/img/`).

### Change a property
Edit the cell. To mark a dead or finished project, set `stare` to `offline` or `arhivat`: it leaves the main list.
An offline site with no Wayback capture for a year shows as `arhivat` without an edit.

### Delete an entry
To take an entry off the site and keep its data, set `clasificare_stare` to `ascuns`.

To delete it, remove its row in `intrari.csv` and its rows in `relatii.csv`, then run `validate.py`,
`build.py` and the unit tests. Its rows in `observatii/profil.csv` and `observatii/mentiuni.csv` can stay:
nothing shows an entry that is not in `intrari.csv`, and the `editor` marks come back if you add the entry
again. The inventory files in `observatii/inventare/` may still list the slug; the unit tests show it.

### Add an entry: `/add-new-url`
In Claude Code, in this repo, type `/add-new-url <url>` (for example `/add-new-url techandtonic.ro`).
Claude checks for a duplicate, reads the site, writes the row to `data/taxonomy-v2/integrare/intrari.csv`
(with `clasificare_stare=propus`) and, when the site names an author, to `relatii.csv`. It then runs
`profile.py`, `search.py`, `validate.py`, `collect_docs.py`, `inventory.py`, `inventory_report.py` and the unit
tests, and reports every cell with its source. It does not commit and does not accept the entry: the public
build refuses `propus`. To publish, ask Claude to set `acceptat`, commit and push; the command lists the steps.
The command lives in `.claude/commands/add-new-url.md`.

To add a row by hand instead, follow `data/taxonomy-v2/README.md`. Run the three inventory steps for the new
slug too, or CI fails.

### Prune search results
In `data/taxonomy-v2/observatii/mentiuni.csv`, set the `editor` column to `1` (keep) or `0` (drop). Leave the other columns alone.
Then run `search.py --prune-only` and `build.py`.

## Taxonomy v2

`data/taxonomy-v2/` holds the classification model (`2.0.0-draft.2`). It replaces the single `domeniu`, the `tip`
list and the free `cuvinte` with facets: subjects, purposes, capabilities, formats, technologies, institutions, maturity and
coverage areas. Each value is an ID from a controlled vocabulary. The integration copy `data/taxonomy-v2/integrare/` holds the
classification of all entries.

**Since 2026-10-22 the public site, the default root of every script (`common.PUBLIC_ROOT`) and the Sheet workflows use this model.** The owner accepted all 140 entries in bulk on that day, not one by one (see `docs/ACTIVITY.md`).
`scripts/cutover_v2.py` applied the cutover; the runbook is
[docs/briefs/cutover-taxonomy-v2.md](docs/briefs/cutover-taxonomy-v2.md). The owner detached `integrare/` from the sealed run on 2026-10-21, so its files are edited by hand.

Every script takes `--data-dir` (default `common.PUBLIC_ROOT`, the integration copy). Point it at `data` to act on the frozen v1 files:
```sh
python3 scripts/validate.py                                                       # draft rules for the public root: proposals are allowed
python3 scripts/validate.py --publication                                         # adds the public gate; it fails while an entry is `propus`
python3 scripts/build.py --site-dir /tmp/civtech-v2 --allow-draft                 # isolated preview
python3 -m http.server -d /tmp/civtech-v2 8765
uv run scripts/check_preview.py http://localhost:8765/                            # browser checks of the served preview (Playwright)
python3 data/taxonomy-v2/validate.py --root data/taxonomy-v2/integrare --baseline # package checks, and proof that the copy keeps the source rows
python3 scripts/cutover_v2.py --plan                                              # the cutover was applied on 2026-10-22; this says so and writes nothing
```
- A build with `--site-dir` never writes `site/`. Without `--allow-draft` it applies the publication gate: every entry is
  `acceptat` or `ascuns`, and no high-priority review item is open.
- `profile.py`, `search.py` and `review.py` read and write only `data/taxonomy-v2/observatii/`. No script writes
  `intrari.csv`. `review.py` puts its suggestions in `observatii/review/` (the repository ignores it), and a person accepts them by hand.
- A new entry is `propus`. Only the owner sets `acceptat`. Use `/add-new-url` (above) to add one.
- Contributors do not edit the v2 files yet. [CONTRIBUTING.md](CONTRIBUTING.md) says so in Romanian.

The editing guide of the package (Romanian) is [data/taxonomy-v2/README.md](data/taxonomy-v2/README.md). The model is in
[docs/specs/taxonomy-v2.md](docs/specs/taxonomy-v2.md), the files and columns in [docs/DATA-SCHEMA.md](docs/DATA-SCHEMA.md),
and how the parts connect in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#taxonomy-v2-preview).

## Checks in GitHub (CI)

| Workflow | Runs on | What it does |
| --- | --- | --- |
| `validate.yml` | a pull request, a push to `main` or a manual run, when `data/`, `scripts/`, `site/` or `.github/workflows/` change | Job `data`: `validate.py --publication` and `build.py` on the public root; all `scripts/test_*.py`; the v2 package checks; a `--allow-draft` preview build (artifact `site-v2-preview`). Job `browser`: `node --check` of `app.js` and `check_preview.py`. Job `workflows`: `actionlint`. |
| `pages.yml` | a push to `main` that changes `site/`, `data/`, `scripts/` or the workflow; a manual run | `validate.py --publication` and `build.py --with-inventory` (the public root), then publishes `site/` to GitHub Pages |
| `sheets-pull.yml` | every 6 hours; a manual run | Sheet → one pull request; see [Editing in Google Sheets](#editing-in-google-sheets) |
| `sheets-push.yml` | a push to `main` that changes `data/taxonomy-v2/integrare/intrari.csv`; a manual run | `intrari.csv` → Sheet |

## Editing in Google Sheets

The Sheet `civtech.gov2.ro` has the tab `v2-intrari` (the workflows' tab) and the optional tab `v2-revizuire`. Row 1 of
each tab holds the column names of the CSV, in the same order; they come from `data/taxonomy-v2/schema.json`. The frozen
v1 tabs `proiecte` and `orgs` stay in the Sheet, and only `--data-dir data` touches them. The repo stays the source of
truth. `scripts/sheets.py` and two workflows keep the Sheet and the CSVs in step.

The tab `_sync` is the **sync marker**. It has one row per synced tab: the tab, the commit, the SHA-256 of the CSV
that `push` wrote, and the time. `push` creates and updates it, so do not edit it. Delete a row to make `sheets.py`
forget that tab. The marker names the CSVs that the Sheet and the repo both started from. That is the base of a
three-way comparison.

**Sheet → repo (`sheets-pull`).** The workflow runs every 6 hours, and on demand (*Actions → sheets-pull → Run
workflow*). It reads the Sheet and merges it into the CSVs cell by cell, against the base:
- A cell that only the Sheet changed since the marker takes the Sheet's value.
- A cell that only the repo changed keeps the repo's value. A CSV edit on `main` that `sheets-push` has not written
  yet is no longer a revert.
- A cell that both changed to different values is a conflict. `pull` writes nothing and exits with code 3, and the
  job fails with the list of cells in its log. Make the two values equal, in the Sheet or in the CSV, then run
  `sheets-pull` again. (`pull --since HEAD` lets the Sheet win every conflict.)

If a CSV changed, the workflow runs `validate.py` and `build.py` and opens one pull request from the branch
`sheets-sync`, "Sheets: modificări din tabel". The text of the pull request lists the changed rows and the output of
`validate.py`. You review the pull request and merge it. The workflow never pushes to `main`. It runs `validate.py`
itself, because a pull request opened by a workflow does not start `validate.yml`. When `validate.py` or `build.py`
fails, the workflow still opens or updates the pull request. Then it sets the commit status `validate / sheets-pull`
to `failure` on the head of the pull request, and fails the job.

**Repo → Sheet (`sheets-push`).** When a push to `main` changes `data/taxonomy-v2/integrare/intrari.csv`, the workflow
rewrites the tab `v2-intrari` from the CSV. Every cell is plain text, row 1 is frozen and bold, and the columns with
one allowed value have a strict drop-down from the vocabulary. A column that takes a `|` list gets a suggesting
drop-down only. The workflow
never overwrites an edit that is not in the repo yet. It compares the Sheet with the CSVs at the commit in the
marker (the last successful push), not with the previous commit of the push: a skipped run does not move the base.
If the Sheet holds a cell that differs from the marker's CSVs and from the new CSVs, the job fails with "Tabelul are
modificări nesincronizate; rulează sheets-pull". Run `sheets-pull`, merge the pull request, and the next push writes
the Sheet. A pull request that came from the Sheet needs no such step: its changes are in the new CSVs, so the
check passes. `push` writes the marker last, and only when the CSV it pushed is the file at `HEAD`.

Both workflows share one queue, so they never run at the same time.

**Rules for the editor**
- Do not change row 1 or the column order. `pull` stops with an error that names the difference.
- Do not write to the right of the last column.
- A row deleted in the Sheet is a deleted entry in the pull request.
- `pull` strips trailing spaces and drops empty rows, and nothing more.
- A new column goes into `data/taxonomy-v2/schema.json` and into the CSV header together.
  The next `push` rewrites row 1 of the Sheet and clears a column that left the list. It needs no `--force`. A column
  that a person added to the Sheet, with data in it, stops the push (exit 3).

**By hand** (needs [uv](https://docs.astral.sh/uv/) and `.env`, see above):
```sh
set -a; source .env; set +a
uv run scripts/sheets.py diff                 # what pull would write; what the repo has that the Sheet lacks; conflicts. No writes
uv run scripts/sheets.py pull                 # merge the Sheet into intrari.csv (then: git diff)
uv run scripts/sheets.py pull --check         # ... then run validate.py on the root; exit 1 on errors (the CSVs stay written)
uv run scripts/sheets.py push                 # CSVs -> Sheet; refuses (exit 3) if the Sheet holds edits not in the repo
uv run scripts/sheets.py push --since <ref>   # the same, with the CSVs at <ref> as the base instead of the marker
uv run scripts/sheets.py push --force         # no check: the Sheet becomes a copy of the CSVs
```
Without a marker, `pull` copies the Sheet over the CSVs (it warns), and `push` compares the Sheet with the current CSVs.
The first `push --force` from a clean `main` creates the marker. Exit code 3 means that nothing was written: `push`
found Sheet edits that are not in the repo, or `pull` found a conflict. In GitHub, run *Actions → sheets-push → Run
workflow* with the input `since` (or `force`) to run a push by hand.

### Other tabs and the v1 root

`sheets.py` works on the public root by default: the tab `v2-intrari`. `--tabs v2-intrari,v2-revizuire` adds the review queue
`revizuire.csv`. A v2 root refuses the tabs `proiecte`, `orgs` and `propuneri`, and a v1 root (`--data-dir data`) refuses the
`v2-` tabs. `push` creates a missing `v2-` tab. IDs stay text, a cell with `|` takes several IDs, and only single-value
columns have a strict drop-down. `pull --check` runs the package checks, which test every ID of every cell against its
concept scheme.
```sh
uv run scripts/sheets.py push --tabs v2-intrari,v2-revizuire   # commit the CSV first: the marker names a commit
uv run scripts/sheets.py pull --check
```

### Formular (the proposal Form)

The Form "Sugestii listă civtech.gov2.ro" sends its answers to the tab `propuneri` of the same Sheet. The script
`scripts/form.py` writes the questions of the Form from the data model. **The live Form still has the v1 questions** (it
uses `data/taxonomy.json`), so the commands below take `--data-dir data`. For the public root the script plans the v2
questions offline and never calls Google: `--apply` and `--save` are refused.
```sh
uv run scripts/form.py                                       # the v2 questions from the vocabulary; no Google call
uv run scripts/form.py --import propuneri.csv                # tab `propuneri` export -> intrari.csv rows (--out FILE)
# the v1 Form:
uv run scripts/form.py --data-dir data         # print the planned questions and the Form as it is now; no writes
uv run scripts/form.py --data-dir data --save   # store the Form, as you edited it in Google Forms, in data/form.json
uv run scripts/form.py --data-dir data --apply  # replace ALL items of the Form with the planned ones
```
The scripts read `.env` themselves. To change wording, help texts, order or required flags, edit the Form in
Google Forms and run `--save`: `data/form.json` becomes the template, and a later `--apply` (for example after a
taxonomy change) keeps your edits. The choices of "Ce propui?", "Domeniu", "Tip" and "Acoperire" always come from
the taxonomy, so keep those four titles as they are.
- `--apply` deletes every existing item of the Form and creates the 13 planned questions, in one request. It does not
  change the title, the description, the settings or the response destination of the Form.
- The columns of `propuneri` are named after the question titles. The list `TITLES` at the top of `form.py` holds
  them. Renaming a title renames a column, so change a title only together with whatever reads `propuneri`.
- `ANSWER_KEYS` in `form.py` maps each choice label to its key in the CSV (`Bani publici` → `bani`).
- The Form API cannot validate a URL. `validate.py` checks the URL when you copy an answer into a CSV.
- Give the service account *Editor* access to the Form, and enable the **Google Forms API** in the Google Cloud
  project. Put the Form's ID (the part of the edit URL between `/d/` and `/edit`) in `.env` as `FORM_ID`.

**Taxonomy v2 (offline).** With a v2 `--data-dir`, `form.py` plans the v2 questions from the vocabulary and sends
nothing to Google (`--apply` and `--save` are refused until the cutover). The Form asks for the entity kind, the name,
the addresses, the root subjects and the formats (checkboxes) and the coverage. The file `data/form-v2.json` is the
versioned answer map: for each choice question, label → ID. A label is never removed from it, so that old responses
still map to the same ID after the vocabulary renames a label.
```sh
uv run scripts/form.py --data-dir data/taxonomy-v2/integrare                       # the plan, with the entry counts and the map drift
uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --check               # exit 1 when the map lacks a label of the plan
uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --write-map           # add the new labels to the map (version + 1)
uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --import propuneri.csv --out rows.csv   # responses -> intrari.csv rows
```
`--import` reads an export of the tab `propuneri`. It writes `intrari.csv` rows with IDs and `clasificare_stare` `propus`.
The state is `de-revizuit` when the response names no subject or several (the editor chooses the primary subject). It
reports every unknown label and leaves it out; it never guesses. It does not copy the e-mail of the proposer.
The editor copies the rows to `intrari.csv` by hand and runs `validate.py`.

### Set up (once)

1. **The spreadsheet.** One Google Sheet with two tabs named `proiecte` and `orgs`. Note the Sheet ID: the part
   of the URL between `/d/` and `/edit`. `sheets.py push` fills the tabs, sets the formats and creates the tab
   `_sync` (the marker), so you do not need to prepare them. To fill a Sheet by hand instead: *File → Import →
   Upload* a CSV, with *Convert text to numbers, dates and formulas: No*.
2. **A Google Cloud project.** At [console.cloud.google.com](https://console.cloud.google.com/), create a
   project (e.g. `civtech-sync`). In *APIs & Services → Library*, enable the **Google Sheets API**.
3. **A service account.** In *IAM & Admin → Service accounts*, create one (e.g. `civtech-sheets`). It needs no
   project role. Open it → *Keys → Add key → Create new key → JSON*, and download the file. If your Google
   Workspace blocks key creation (policy `iam.disableServiceAccountKeyCreation`), an admin must allow it for
   this project.
4. **Share the Sheet** with the service account's e-mail (`…@<project>.iam.gserviceaccount.com`) as *Editor*.
   Share only this one Sheet with it.
5. **GitHub.** In the repo, *Settings → Secrets and variables → Actions*: add the secret `GOOGLE_SA_KEY` (the
   whole JSON file) and the variable `SHEET_ID`. Then keep the JSON file outside the repo, or delete it.
6. **Pull requests from workflows.** In *Settings → Actions → General → Workflow permissions*, tick *Allow GitHub
   Actions to create and approve pull requests*. Without it, `sheets-pull` cannot open the pull request.
7. **Locally** (optional): put `GOOGLE_APPLICATION_CREDENTIALS` (path to the JSON file) and `SHEET_ID` in `.env`.
8. **The first marker.** Run *Actions → sheets-push → Run workflow* once from `main`, with `force` ticked (or without
   it, if the Sheet equals the CSVs). Until then `pull` is two-way and warns.
9. **The status of the pull request** (optional). `sheets-pull` sets the commit status `validate / sheets-pull` on the
   head of its pull request. A branch protection rule that requires this status also blocks every pull request that
   never gets it, so require it only if you merge other pull requests as an administrator.

The workflows run on a schedule, on pushes to `main` and by hand only, because GitHub does not give secrets to
pull requests from forks.

-----

<img src="docs/reference/logo/g2-0.png" width=250> 

### Documentarea proiectelor

```sh
python3 scripts/collect_docs.py --only afacut,ins-gov2,ani-de-pensie
python3 scripts/collect_docs.py                 # toate intrările; reutilizează rezultatele existente
python3 scripts/collect_docs.py --force         # descarcă din nou paginile selectate
```

Colectorul caută metodologie, pagini despre proiect și `llms.txt`, inclusiv secțiuni din pagina inițială.
Salvează rezultatele în `data/taxonomy-v2/observatii/documentare/`.
Nu modifică datele editoriale și nu publică automat informații. Nu folosește servicii plătite.
Paginile brute rămân locale; `index.json` și `rezumat.csv` păstrează rezultatele colectării.
După o clonare nouă, folosiți `--force` pentru a recupera paginile necesare verificării.
`pilot-inventare.json` conține primele cinci propuneri de inventar, cu dovezi și lacune explicite.

### Inventarele de variabile

```sh
python3 scripts/inventory.py                  # scheme/date legate în documentație; cel mult 3 surse noi pe intrare
python3 scripts/inventory.py --only demoanaf --offline   # modifică doar proiectul ales; celelalte păstrează înregistrările și dovezile
python3 scripts/inventory.py --offline        # reconstruiește propunerile fără cereri
python3 scripts/inventory.py --check          # verifică dovezile locale; nu descarcă și nu rescrie
python3 scripts/inventory_report.py           # acoperirea (acoperire.csv) și raportul docs/reports/inventory-expansion.md
python3 scripts/collect_docs.py --only afacut --force --follow-data-links
# pagină salvată de proprietar din browserul propriu, când site-ul refuză cererile automate; nu se face nicio cerere
python3 scripts/collect_docs.py --import-saved harta-firmelor https://harta-firmelor.ro/llms.txt FISIER --saved-at 2026-10-25T20:39:00+02:00
python3 scripts/inventory.py --import-saved harta-firmelor https://harta-firmelor.ro/date FISIER --saved-at 2026-10-25T20:39:00+02:00 \
    --add-sources-file data/taxonomy-v2/observatii/inventare/adaugari/harta-firmelor-date.json
```

Rezultatele sunt în `data/taxonomy-v2/observatii/inventare/`.
`campuri.csv` listează câmpurile cu tipuri declarate, observate sau neprecizate.
`intrari-utilizator.csv` listează controalele HTML candidate; ele pot include căutarea și alte elemente generale ale site-ului.
`proiecte.json` leagă fiecare intrare de surse și păstrează descrierea și funcțiile deja catalogate.
`seturi-date.json` păstrează definițiile comune, referințele din scheme și dovezile.
Fișierele descărcate rămân locale în `surse/`, cu versiuni identificate prin hash.
Toate inventarele sunt propuneri parțiale. Colectorul nu publică automat date și nu folosește servicii plătite.
O copie salvată de proprietar (`--import-saved`) are originea `copie-salvata-de-proprietar`, nu este niciodată etichetată ca descărcată și nu este cerută din nou.
Ora salvării are nevoie de decalaj UTC. Fișierul rămâne la proprietar; `--check` verifică amprenta textului păstrat.
Un site care interzice accesul automat se trece în `data/taxonomy-v2/colectare-interzisa.csv`. Niciun script nu mai cere gazda listată; starea rezultatului este `colectare-interzisa`.

### Previzualizarea inventarelor în explorator

```sh
python3 scripts/build.py --site-dir /tmp/civtech-inventory-preview --with-inventory
python3 -m http.server -d /tmp/civtech-inventory-preview 8770
uv run scripts/check_inventory_preview.py http://localhost:8770/
uv run scripts/check_data_finder.py http://localhost:8770/
```

Previzualizarea adaugă marcajul „Inventar de date” în rezultate și secțiunea „Date & metodă” în panoul proiectului.
Câmpurile se caută în panou și prin căutarea principală. Panoul arată tipurile, sursele și referințele.
Parametrii API repetați sunt grupați; operațiile rămân disponibile în context.
Inventarele sunt parțiale. Din 2026-10-26 site-ul public include `/date/` și `/date/lista/`: fluxul Pages rulează `build.py --with-inventory`.

Pagina `/date/` pornește de la date către proiecte. Include toate cele 106 proiecte și, opțional, cele 21 de resurse.
Filtrează după variabile comune, surse de date, subiect și instituții vizate. Selecția se păstrează în URL.
Variabilele selectate se cumulează. În celelalte filtre, opțiunile sunt alternative; filtrele se intersectează.
Asocierile inițiale sunt propuneri în `data/taxonomy-v2/inventar-concepte.json`, cu selectori expliciți pentru proiect și câmp.
Pagina arată dovezi pentru fiecare asociere. Un nume comun nu garantează că seturile se pot combina.

Acoperirea curentă: 28 din 127 de proiecte și resurse au câmpuri extrase din surse structurate.
Cele 3.593 de înregistrări sunt câmpuri și căi din surse, nu variabile independente; 30 de grupuri de variabile sunt propuse.
Raportul complet, cu limite, blocaje și rezultatele verificărilor, este în [inventory-expansion.md](docs/reports/inventory-expansion.md).
Lucrările rămase sunt în [BACKLOG.md](docs/BACKLOG.md#inventory-expansion--implemented-2026-10-25-milestones-ae-v0140v0180).
Specificația implementată este în [inventory-expansion.md](docs/briefs/inventory-expansion.md).

----

Copyright (c) 2026 [gov2.ro](https://gov2.ro)
Date reutilizabile conform [EUPL v1.2](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12) (the "Licence")
