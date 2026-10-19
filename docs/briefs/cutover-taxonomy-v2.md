# Runbook — cutover to taxonomy v2

Written on 2026-10-20 for the owner. The public site still reads the v1 source (`data/`).
This runbook moves it to the taxonomy v2 integration copy (`data/taxonomy-v2/integrare/`).
The owner runs it. One command, `scripts/cutover_v2.py`, makes the change in the code and the workflows.
That command never commits, pushes, deploys, or calls Google. Every other step is below, in order.

## Terms

- **Public root**: the data root that builds the public site. `PUBLIC_ROOT` in `scripts/common.py` names it.
  Today it is `data/`. After the cutover it is `data/taxonomy-v2/integrare`.
- **Integration copy**: the folder `data/taxonomy-v2/integrare/`. It holds the classifications of the sealed run.
- **Detach**: the step that makes the integration copy editable. Before it, `integrare.py` regenerates the copy from the sealed run.
  A direct edit then fails the check. After it, the editor owns the files, and the check proves the derivation at the detach commit.
- **Gate**: the publication gate. Every entry must be `acceptat`. No review item of high priority may be `deschis`.
  A public build always applies the gate. `--allow-draft` never writes `site/`.
- **Rehearsal**: `python3 scripts/cutover_v2.py --rehearse DIR`. It runs the cutover on a copy of the repository.
  CI runs it on every change, so the cutover keeps working while the code changes.

## 1. State on 2026-10-20

Run `python3 scripts/cutover_v2.py --plan` for the state today. It prints these blockers:

| Blocker | Count today |
| --- | --- |
| Entries that are not `acceptat` | 122 of 122 (121 `propus`, 1 `de-revizuit`) |
| Open review items of high priority | 27 |
| `site.tabs.intrari` in `data/taxonomy-v2/setari.json` | `null` |
| The integration copy is not detached | yes |

It also prints two notices that do not block: 27 entries have no description, and 10 vocabulary proposals are open.
`--apply` refuses while any blocker exists. The rehearsal waives the blockers inside its copy only.

## 2. Decisions of the owner (preconditions)

The owner takes these decisions. The command checks the results, not the reasons.
Take decision 1 first: it makes the files editable. Take decisions 2 and 3 before decision 5.
An entry can use a new term only after the vocabulary has it.

| # | Decision | What to do | How to check |
| --- | --- | --- | --- |
| 1 | Detach | Run the detach (step 1 below). The vocabulary and the entries are editorial files only after it. | `python3 data/taxonomy-v2/integrare.py` prints "detached since" |
| 2 | Vocabulary proposals (10) | Read `integrare/propuneri-vocabular.csv`. For each row, accept it into `concepte.csv` or `arii.csv`, or reject it. Set `stare` to `acceptat` or `respins`. Follow `data/taxonomy-v2/README.md` for a vocabulary change. Then update the Form answer map (see below). | `python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare` has no error |
| 3 | Identifier of Moldova | Choose the area ID. The queue recommends `tara:MD` with `cod_iso_3166_1=MD`, in the style of `tara:RO`. The proposal row uses `tara:republica-moldova`. Use one ID in `arii.csv` and in the entries of the proposal row (`crpe`, `data-expertforum`). | `arii.csv` has the area; no proposal row keeps the other ID |
| 4 | Review queue | Give every open item of high priority a decision in `integrare/revizuire.csv`. Set `stare` to `acceptat`, `respins` or `amanat`, and write `decizie_editor`. The gate counts only `deschis`, so a deferred item (`amanat`) passes it. Defer an item only when the entry can be public without that decision. | `python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare --publication` shows no review item |
| 5 | Acceptance of the 122 entries | Check each entry in full. Set `clasificare_stare` to `acceptat`. The entry `incentru` has no primary subject: the run had too little evidence. Give it a subject with evidence, or decide how the public site treats it. An accepted entry needs a primary subject. | the same command shows no entry |
| 6 | Text for entries without description | 27 entries have no `descriere_scurta` and no `descriere`. The gate does not check text. Decide whether the public site may show them without text. If it may not, write the text before the cutover. The site shows the description of the entry's own website only when that website is active. | the owner's decision; `--plan` shows the count |

The tests that describe the classifications of the sealed run read the package as of the detach commit.
Your decisions do not break them. One test follows the vocabulary: it compares `data/form-v2.json` with the Form questions.
After you add a subject or a format to the vocabulary, run `uv run scripts/form.py --data-dir data/taxonomy-v2/integrare --write-map`.
Commit `data/form-v2.json`.

## 3. Steps in order

Run every command from the repository root. Work on a clean tree.

### Step 1. Detach the integration copy

```sh
git switch main && git pull
python3 data/taxonomy-v2/integrare.py             # must print: integrare/ matches a fresh assembly
python3 data/taxonomy-v2/integrare.py --detach    # records HEAD and the date in integrare/pachet.json
git add data/taxonomy-v2/integrare/pachet.json
git commit -m "chore(taxonomy): detach the integration copy"
git push
python3 data/taxonomy-v2/integrare.py             # must print: integrare/ is detached since ...
```

The detach refuses when the copy differs from a fresh assembly or the package has uncommitted changes.
Do not run `--detach` twice. Do not run `integrare.py --write` afterwards: the script refuses it.
CI fetches the full history, because the check reads the detach commit.

### Step 2. Take the decisions 2 to 6

Edit the CSV files of the integration copy, the vocabulary files, and `revizuire.csv`. Commit each group of changes.
After each group, run:

```sh
python3 scripts/validate.py --data-dir data/taxonomy-v2/integrare --publication
python3 -m unittest discover -s scripts -p "test_*.py"
```

Repeat until the first command ends with `0 erori`.

### Step 3. Create the tab `v2-intrari` in the Sheet

Use the same environment as the v1 sync: `SHEET_ID` and the service-account key (`.env` or the shell).
Commit every change of `intrari.csv` first. The command writes a sync marker only for a committed file.

```sh
uv run scripts/sheets.py push --data-dir data/taxonomy-v2/integrare --tabs v2-intrari
```

The command creates the tab, formats it, and writes the row for `v2-intrari` in the tab `_sync`.
Do not add `--force`. It does not touch the tabs `proiecte` and `orgs`.
Open the new tab in the browser. Copy the number after `#gid=` in the address.
Write that number as `site.tabs.intrari` in `data/taxonomy-v2/setari.json`. Replace `null`. Commit and push.
The old `sheets-push` does not watch `intrari.csv`. If `intrari.csv` changes after this step, run the push command again before step 7.

### Step 4. Freeze the v1 tabs

1. Run `uv run scripts/sheets.py diff` (it reads the v1 tabs). If the Sheet holds edits, run `uv run scripts/sheets.py pull --check`.
   Also merge any open pull request from the branch `sheets-sync`. Do not lose a Sheet edit.
2. In the Sheet, protect the tabs `proiecte` and `orgs`. Allow only the owner to edit them.
3. Keep both tabs. The rollback needs them.

### Step 5. Decide on the Form

The Form "Sugestii listă civtech.gov2.ro" still asks the v1 questions. No command changes the live Form to the v2 questions.
`form.py --apply` refuses a v2 root. Choose one option before the cutover:

- **Option A**: Plan the questions with `uv run scripts/form.py --data-dir data/taxonomy-v2/integrare`.
  Edit the live Form by hand to match the plan. Then run `... --write-map` and commit `data/form-v2.json`.
  Responses then go to `form.py --import` (see its header).
- **Option B**: Keep the v1 Form. An editor copies each proposal into `intrari.csv` by hand.

Record the choice in `docs/ACTIVITY.md`.

### Step 6. Rehearse

```sh
export ACTIONLINT=/path/to/actionlint     # optional: lints the changed workflows
python3 scripts/cutover_v2.py --rehearse /tmp/civtech-rehearsal
```

Every line must start with `ok` or `skip`. The last line must say "passed". Read each `skip` line.
The rehearsal changes nothing in the repository. The folder must be outside it.

### Step 7. Run the cutover

```sh
git switch -c cutover-taxonomy-v2
python3 scripts/cutover_v2.py --plan      # must print: No blockers
python3 scripts/cutover_v2.py --apply     # edits the working tree
python3 scripts/build.py                  # the public build; it applies the gate
python3 -m unittest discover -s scripts -p "test_*.py"
git status                                # check the list of changed files
```

`--apply` changes `scripts/common.py`, `scripts/build.py`, four workflow files, `site/app.js`, and `site/style.css`.
It removes `site-v2/`. `build.py` then writes `site/data.json`, `site/feed.xml`, and `site/llms.txt`, and it stamps `site/index.html`.
Commit all of them. The build needs the gate to pass. If it refuses, resolve the named item and run the build again.

Update these documents by hand. The command does not edit them:
`README.md`, `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`, `docs/DATA-SCHEMA.md`, `docs/ARCHITECTURE.md`,
`docs/METODOLOGIE.md` (the paths `site-v2/`), and `docs/specs/taxonomy-v2.md`.
Then commit, push the branch, and open a pull request.

`validate.yml` runs on the pull request. It applies the gate, builds the public site, and runs the tests.
Merge the pull request when all jobs pass. The workflow `pages.yml` then builds and deploys the site.

## 4. Checks after the deploy

1. Open the run of `pages` in GitHub Actions. It must end green.
2. Check the data on the live site:

   ```sh
   curl -s https://civtech.gov2.ro/data.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['schemaVersion'], d['draft'], len(d['items']))"
   ```

   Expected: the schema version `2.…`, `False`, and the number of entries.
3. Open one entry of each kind by its address (`/proiect/<slug>/`, `/organizatie/<slug>/`, `/resursa/<slug>/`). Open the three archive pages.
4. Open an old bookmark with `?d=`, `?t=` or `?kw=`. The filter must still select the same entries.
5. Open "Corectează în tabel" on an entry. It must open the row in the tab `v2-intrari`.
6. Run the browser checks against the live site: `uv run scripts/check_preview.py https://civtech.gov2.ro/`.
7. Reload the page with a clean cache. The links `style.css?v=…` and `app.js?v=…` must carry the new hashes. If they do not, purge the Cloudflare cache.
8. Run `sheets-pull` by hand (`workflow_dispatch`). It must finish without a pull request, because the Sheet and the repository agree.
9. Run `uv run scripts/sheets.py diff --data-dir data/taxonomy-v2/integrare`. It must print "no differences".

## 5. Rollback

Before the merge: close the pull request and delete the branch. Nothing else changed.

After the merge:

1. Revert the merge commit with `git revert -m 1 <merge commit>`. For a squash merge, use `git revert <commit>`.
   Push the revert to `main`. `pages.yml` deploys the v1 site again.
   The cutover never touches `data/*.csv` or `data/taxonomy.json`, so the v1 source is intact.
2. Unprotect the tabs `proiecte` and `orgs` in the Sheet.
3. Keep the tab `v2-intrari`. The v2 files stay in the repository. The edits made since the cutover live in `intrari.csv` of the integration copy.
4. The v1 tabs did not change while frozen. Run `uv run scripts/sheets.py diff` to confirm.

The rollback does not undo the detach. The integration copy stays editable.

## 6. What the command changes

`python3 scripts/cutover_v2.py --plan` lists every step. In short:

- `scripts/common.py`: `PUBLIC_ROOT` points to the integration copy. Every script reads it by default.
- `scripts/build.py`: the copy of `site-v2/` into a preview is removed. The rest of the build stays.
- `site/app.js` is replaced by `site-v2/app.js`. The rules of `site-v2/v2.css` are appended to `site/style.css`. `site-v2/` is removed.
- `pages.yml`: validation with `--publication`, then the build of the integration copy.
- `sheets-pull.yml` and `sheets-push.yml`: the tab `v2-intrari` and `intrari.csv` replace `proiecte`, `orgs` and their CSV files.
- `validate.yml`: the gate and the build of the public root block a pull request.
  The line `node --check site-v2/app.js`, the report-only gate step, and the rehearsal step are removed.
  The package check no longer uses `--baseline`: live enrichment changes `observatii/`, and the baseline compares it with the snapshot.

If a file changed since the command was written, `--apply` stops, names the edit, and writes nothing.
Then update the edit in `scripts/cutover_v2.py`. The rehearsal in CI finds such a change before the cutover day.

## 7. Known limits

- No command applies the v2 questions to the live Form (step 5).
- The rehearsal runs the tests and the build in a copy. It cannot test Google, GitHub Pages, Cloudflare, or the Sheet.
- The public data keeps the schema version `2.0.0-draft.2`. Choose a release version in a separate step.
- `actionlint` runs in the rehearsal only when the binary is available (`ACTIONLINT` or the path).
