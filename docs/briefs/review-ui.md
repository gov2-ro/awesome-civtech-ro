# Specification and implementation handoff — local review interface

Date: 2026-10-25. Baseline: commit after tag `v0.18.1` (this brief is committed as `v0.19.0`).
Status: ready for implementation.

## 1. Start here

Read `CLAUDE.md`, `docs/BACKLOG.md`, `docs/ACTIVITY.md`, `docs/reports/inventory-expansion.md` (sections 3, 5, 9),
and the `relatii.csv`, `revizuire.csv (v2)` and inventory-concept sections of `docs/DATA-SCHEMA.md`.
Read `scripts/inventory_concepts.py`, `scripts/inventory_site.py` (`variable_matches`, `publish_finder`) and the evidence checks in `scripts/inventory.py`.

Copy this prompt into the implementation session:

> Implement `docs/briefs/review-ui.md`.
> Build the local review server, its data writes and their offline tests first. Then build the page and its browser check.
> Keep every write atomic, validated and byte-stable. Keep the public build unchanged.
> Make routine decisions within the brief. Stop and report if a step needs a decision that the brief does not make.
> Finish with the report in section 9.

## 2. Goal

The owner reviews the inventory proposals in a browser, one item at a time.
Each item shows the proposal, its evidence and the consequence of each decision.
The owner can see the progress and the validation state at any time, and can follow every decision afterwards in git.

The review covers two queues:

| Queue | Items | Files written |
| --- | --- | --- |
| Providers | Open `revizuire.csv` items with `camp=surse_date` (today D132–D162, 31 items). | `integrare/revizuire.csv`, `integrare/relatii.csv` |
| Variable groups | The 30 groups in `inventar-concepte.json`, each with its members (selectors). | `data/taxonomy-v2/inventar-concepte.json` |

Out of scope: field records and HTML control candidates (they are generated), the public `/date/` page (next brief),
Google Sheets synchronisation, and any network request from the server.

## 3. Decisions

1. **A local tool, never published.** `scripts/review_ui.py`, stdlib only, Python 3.12.
   `python3 scripts/review_ui.py [--port 8790] [--data-dir …]` serves one page and a small JSON API.
   It binds `127.0.0.1` only. `build.py` never copies its page or its script into any site directory.
   The name avoids `review.py`, which is the paid Haiku search review.
2. **Git is the audit trail.** The tool writes the repository files and never commits.
   The page shows `git status`/`git diff --stat` for the files it writes and the suggested next commands.
3. **Additive state for groups** (a format change that this brief approves):
   - Group keys: `stare` (`propus` | `revizuit` | `respins` | `amanat`), `decizie_editor` (text), `data_revizie` (ISO date).
   - Selector keys: `stare` (`propus` | `confirmat` | `exclus`), `nota_editor` (text).
   - A missing key means `propus`. Existing files stay valid without change.
   - An `exclus` selector stays in the file for history and never matches a field.
     `inventory_concepts.selector_matches` and every caller honour this.
   - A group with state `respins` produces no matches in the finder. `revizuit` and `propus` groups both appear; the finder shows the state as a badge.
   - The top-level `"stare": "propunere"` of the file keeps its meaning: groups remain discovery aids, never join keys. `revizuit` means "the editor checked the members and the wording".
   - Validation: unknown state values fail; `revizuit` and `respins` need `decizie_editor`; `exclus` needs `nota_editor`.
4. **Provider decisions** follow the existing rules in `DATA-SCHEMA.md`:
   - **Accept:** set the item to `acceptat` with `decizie_editor`. If the item names a `relatii.csv` row (`L132: …` in `propunere`), set that row to `acceptat`, `camp_sursa=surse_date`, `valoare_sursa=<evidence URL>`.
     Otherwise append a `date_din` row with the next free `L` id. The editor confirms or edits the canonical provider name and the evidence URL before saving; both are prefilled from the item.
   - **Reject:** item `respins` with `decizie_editor`; a linked `propus` relation row becomes `respins`.
   - **Defer:** item `amanat`; a relation row stays `propus`.
   - **Duplicate:** item `tehnic` with `motiv` naming the other item (`Duplicat: D153`), empty `decizie_editor`. The other item must exist.
   - **Reset:** puts the item and its relation row back to their values at `HEAD`. Appended rows are removed.
   - Never edit `motiv` or `propunere` text except the duplicate case above.
5. **Writes are safe.**
   - Each write reads the file, applies one decision, validates the result with the existing loaders and validators, then replaces the file atomically.
   - A failed validation writes nothing and returns the error text to the page.
   - Each request carries the hash of the file the page loaded. A different hash on disk (an editor, a Sheet pull, `git checkout`) refuses the write and asks the page to reload.
   - CSV output is byte-stable: same column order, quoting style, line endings and trailing newline. Loading and saving without a change gives an identical file.
   - JSON output keeps the existing indentation and key order; new keys go after the existing ones.
   - POST requests need a per-process token embedded in the page, and a `Host` of `localhost` or `127.0.0.1` with the server port. Others get 403.
6. **Evidence is shown, not re-fetched.** The server reads the retained copies that `inventory.py --check` uses.
   - For each evidence reference, show the URL (opens in a new tab), the fragment highlighted in its retained text, and the verification state: `verificat` (hash and fragment match), `schimbat` (hash differs), `indisponibil local` (no copy). Never show `verificat` without the hash check.
   - Show the basis of each definition and fact (`declaratie-directa`, `observatie-esantion`, `deductie-din-dovezi`, `parafraza-editoriala`) as a visible label. Deductions get a distinct style and need an explicit tick before a group can be `revizuit`.

## 4. The page

Romanian UI, plain HTML/CSS/JS from the server, no framework, no external requests. Reuse `site/style.css` tokens where it is easy; a separate small stylesheet is fine.
Works at 1280 px and at 390 px.

- **Header:** progress per queue (`Furnizori: 12 / 31 decise`, `Grupuri: 4 / 30 revizuite`), and a filter: `Deschise` (default) | `Toate` | `Decise`.
- **List and detail:** a list on the left (one line per item: id, project, short proposal, state chip); the selected item on the right. The selection lives in the URL hash, so reload and back keep it.
- **Provider item:** project name with its catalogue link; `valoare_originala`; `propunere`; `motiv`; the evidence panel; the linked relation row, or "rând nou L…"; related items for the same project and the same provider name (for example D140/D153), with their states; a warning when the proposal text limits the provider to one dataset ("numai pentru setul …"), because a relation applies to the whole project.
  A sentence states the consequence before saving, for example: „Acceptarea adaugă «ONRC» ca sursă de date pentru Registrul Firmelor pe site-ul public.”
  Buttons: `Accept`, `Resping`, `Amân`, `Duplicat…`, `Resetează`; a required note field.
- **Group item:** label, category, definition with its basis, `ambiguitati`, then the members.
  Each member shows the project, field name and path, source URL, role, representation, up to three examples, its facts with basis and evidence, and `context`/`nota`.
  Per member: `Confirm` | `Exclud` (note required). Per group: `Revizuit` | `Resping` | `Amân` with a note, and `Resetează`.
  The `Revizuit` button stays disabled while a member is still `propus` or a deduction is not ticked; the page says why.
- **Check panel** (a tab or a drawer): a button runs `validate.py --publication`, `inventory.py --check` and `inventory_report.py --check` in subprocesses and shows each exit code and the last lines of output.
  It also shows the public consequence: accepted providers per entry at `HEAD` against the working tree, as added/removed lines. And it lists changed files with `git diff --stat`, plus the commands to regenerate (`inventory_report.py`) and to commit.
- **Keyboard:** `j`/`k` next/previous item; no single-key decisions.

## 5. Follow-on changes

- The finder (`site/inventory.js`) shows the group state badge and hides `respins` groups and `exclus` members. Keep the browser checks deriving counts from the generated index.
- `inventory_report.py` counts decided providers and groups by state. The report and `acoperire.csv` stay generated.
- Document the new keys in `docs/DATA-SCHEMA.md`, the command in `CLAUDE.md` and `AGENTS.md`, and a short Romanian section "Revizuirea în interfață" in `data/taxonomy-v2/README.md`.

## 6. Tests

Offline `unittest` in `scripts/test_review_ui.py`, on temporary copies of the data root:

1. Accept with a linked relation row; accept with a new row (next free `L` id); reject flips a linked `propus` row; defer leaves it; duplicate needs an existing target; reset restores `HEAD` values and removes an appended row.
2. Byte-stable round trip of `revizuire.csv`, `relatii.csv` and `inventar-concepte.json`.
3. A stale file hash refuses the write; a failed validation writes nothing; a missing token or a foreign `Host` gets 403.
4. Group states and selector states validate; `exclus` selectors never match; `respins` groups produce no finder matches; `revizuit` needs a decision text and no `propus` members.
5. Evidence states: matching hash gives `verificat`, a changed body gives `schimbat`, an absent copy gives `indisponibil local`.
6. The public payload of `build.py` is unchanged until a provider is accepted, and an accepted provider appears in `dataSources` of that entry only.

Browser check `scripts/check_review_ui.py` (Playwright, PEP 723), against a server on a temporary copy of the data root: list, selection in the URL, one decision of each kind, the consequence sentence, the disabled `Revizuit` reason, the check panel, no horizontal overflow at 390 px.
Never run the browser check against the real data root.

## 7. Boundaries

- Do not decide any real review item. Leave D132–D162 open and all 30 groups `propus`. Use temporary copies for every test and demonstration.
- Do not change `site/` output except through `build.py` and the finder changes above. The default public payload must stay equal to `HEAD` (ignore generation time and asset stamps).
- No network requests from the server or the tests. No new dependency for `review_ui.py`.
- Keep the frozen v1 files and the sealed `source/`, `reference/` and `runs/` unchanged.

## 8. Verification

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/validate.py --publication
python3 scripts/inventory.py --check
python3 scripts/inventory_report.py --check
python3 scripts/build.py
python3 scripts/build.py --site-dir /tmp/civtech-inventory-expanded --with-inventory
node --check site/inventory.js
git diff --check
uv run scripts/check_review_ui.py          # starts its own server on a temporary data copy
uv run scripts/check_data_finder.py http://localhost:8770/   # against the served preview
```

## 9. Report

Return the commit and tag, the command to start the tool, the test and check counts with any failures, the public-payload comparison,
the decisions you made inside the brief, and anything you could not do. Confirm that no real review item changed state.
