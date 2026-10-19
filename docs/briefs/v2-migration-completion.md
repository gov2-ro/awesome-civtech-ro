# Brief — complete the taxonomy v2 migration work (before the cutover)

Written by Opus on 2026-10-19 for Sonnet sessions. Branch: `taxonomy-v2-migration`.
Read `AGENTS.md`, `docs/specs/taxonomy-v2.md` and the audit items in `docs/BACKLOG.md` first.

## Ground rules for every slice

- Production stays on v1. `data/` stays the default root of every script. Do not run a source cutover.
- Do not call Google, Serper, Brave, Anthropic or Open PageRank. Do not trigger workflows, push, deploy or tag.
- Never write into `data/taxonomy-v2/source/`, `reference/` or `runs/`. Never change `data/*.csv` or `data/taxonomy.json`.
- Tests are stdlib `unittest` files in `scripts/`, run with plain `python3`. Network code gets a fake or a pure function.
  A script with PEP 723 dependencies must stay importable by a test: import a third-party module inside the function that needs it.
- Keep `python3 scripts/test_taxonomy_v2.py` (40 tests) and `uv run scripts/check_preview.py` (63 checks) passing.
- A v1 build must stay byte-identical, except where this brief names a v1 correction.
- Do not edit `docs/BACKLOG.md`, `docs/ACTIVITY.md` or `docs/RELEASES.md`. Opus writes those after review.
  Put your activity notes (Done / Hard / Decided, with measured numbers) in your final report.
- Stop and ask when a step would change the specification, an invariant, or a file outside your slice.
- Do not accept classifications, close review items with an editor decision, or invent evidence.
- Commit your slice on your branch with a conventional message. Do not merge.

## Slice A — enrichment on explicit roots, and its audit defects

Files: `scripts/profile.py`, `scripts/search.py`, `scripts/review.py`, `scripts/common.py`, `scripts/build.py`
(only `last_activity`, `reach_features` and their callers), new `scripts/test_enrichment.py`.

1. `--data-dir` on `profile.py`, `search.py` and `review.py`. Default `data/`. Entries come from `load_catalogue(root)`;
   observations from `observation_paths(root)`. A v2 run reads and writes only the root's `observatii/` files.
   Images stay in `site/img/` (shared by slug); add `--site-dir` only if a test needs to redirect them.
2. Profile preservation (backlog: `profile.py --force` drops `mentions`, `search_social`, `opr`; `cert_first` lost on a 502).
   A pure function merges a fresh HTTP profile with the old row. Fields owned by other stages survive:
   `mentions`, `mention_hosts`, `search_social` (search.py), `opr` (--opr), and the `--extra` signals when the new fetch
   returned nothing for them (`cert_first`, `wiki_refs`, repo fields). Test it without the network.
3. `search.py` on v2: author names from the attribution relations (the literal or the target entry's name), with
   `autor_original` as a fallback. Organisation URLs only for relation targets that are organisation entries.
   Keep the mention row format, the `editor` column and the slug join.
4. `review.py` on v2 (spec "Profiling, search, and model review"): the system text lists each facet with scheme-qualified
   IDs and definitions; the answer schema has separate arrays per facet; technology claims and typed roles need a cited
   source; unknown terms go to a proposal list, never into IDs. Suggestions go to `observatii/review/` (gitignored), never
   to `intrari.csv`. Keep the v1 mode unchanged. `--dry-run` must work without a key and without the network
   (skip the homepage fetch in a dry run, or use a cached page).
5. Label invalidation (audit): store, per reviewed slug, a hash of the entry text, the kept mention URL set, the vocabulary
   version, the prompt, and the model. A changed hash makes the slug due again, and `build.py` ignores labels whose
   URL set no longer matches. Report label coverage (labelled kept rows / kept rows) in `review.py` and in the build line.
   In `reach_features`, a slug with partial labels counts labelled independent hosts plus unlabelled kept hosts, and
   carries `provisional: true`; a fully labelled slug counts labelled hosts only.
6. `last_activity` (audit): a dated update wins. The copyright year is a fallback only, as `<year>-01-01`, never after
   today. This is a named v1 correction: record how many v1 items change `stale` and `score`.
7. Tests in `scripts/test_enrichment.py`: profile merge, v2 observation paths for each script, search plan from
   relations, review dry run on a v2 root (prompt holds IDs, no write to `intrari.csv`), label invalidation, coverage,
   copyright date. Each test works on a temporary copy.

## Slice B — Sheets and Form for v2, sync base, blocking validation

Files: `scripts/sheets.py`, `scripts/form.py`, `.github/workflows/sheets-pull.yml`, `sheets-push.yml`,
new `scripts/test_sheets_form.py`, `docs/briefs/sheets-sync.md` (append a v2 section).

1. `sheets.py --data-dir <v2 root>` works on **new** tabs only: `v2-intrari` (mirror of `intrari.csv`, headers from
   `schema.json`). Optional `v2-revizuire` for the review queue. Never the live `proiecte`/`orgs` tabs from a v2 root;
   refuse explicitly. IDs stay text; `|` cells get no strict drop-down (a suggestion drop-down at most).
2. Sync base: a real last-synced marker. Store it in the Sheet (a tab `_sync`, one row per synced tab: tab, commit,
   SHA-256 of the CSV text pushed, time). `push` without `--since` uses the marker's commit as the base; `pull` reports
   (3-way) cells the Sheet changed since the marker and cells the repo changed since the marker, and refuses to write a
   cell that both changed (exit 3, the conflict list). `--since` stays as an override. `push` updates the marker last.
3. Validation after pull: run the root's checks on the pulled rows (v1: `validate.py`; v2: the package checks with
   per-token ID and scheme checks). `pull --check` exits 1 on errors after writing, so CI can fail.
4. Round trips with an in-memory fake worksheet (no Google): IDs, `|`, commas, quotes, Unicode with diacritics,
   multiline descriptions, trailing spaces, empty cells, column-order errors, and the conflict case.
5. Workflows: `sheets-pull.yml` must fail the job when validation or build fails, after it has opened or updated the PR,
   and set a commit status `validate / sheets-pull` (failure or success) on the PR head with `gh api`. The owner can then
   require that status in branch protection. Keep the v1 tabs as today. `sheets-push.yml` uses the marker
   (no `--since $BEFORE`); manual `since`/`force` inputs stay. Do not add a v2 job to the workflows yet.
6. `form.py --data-dir <v2 root>`: plan the v2 questions (entity kind; subjects and formats as checkboxes with the used
   root subjects and formats; labels from the vocabulary). An answer map (`label -> ID`) is versioned in a new file next to
   `data/form.json` (for example `data/form-v2.json`, with `version`). An importer function maps one `propuneri` response
   row to an `intrari.csv` row with IDs and `clasificare_stare=propus`; unknown labels are reported, never guessed.
   No `--apply` against the live Form. Test the plan and the importer offline.

## Slice C — frontend audit defects in the v2 browser code

Files: `site-v2/app.js`, `site-v2/v2.css`, `site/index.html` (shared template: only the noscript fallback and the
footer methodology link), `scripts/check_preview.py`, new `docs/METODOLOGIE.md` (Romanian).

`site/app.js` and `site/style.css` stay unchanged: the cutover replaces `site/app.js` with `site-v2/app.js`.
Check each item against the code first; some may be partly done.

1. Data-load failure: a failed or aborted `data.json` request shows a message, a retry button, and links to the three
   static archives. No blank results.
2. No-JavaScript fallback: a `<noscript>` block in `site/index.html` with the short introduction and links to the archives.
   This changes the v1 page too; keep it small.
3. Canonical and share metadata follow SPA navigation: opening an entry sets `canonical`, `og:url`, title and description;
   closing restores the home values (audit: open Factual directly, close it, the canonical stays on Factual).
4. Observed dates: `since` is the first observed trace (archive, repository, certificate), not a confirmed launch.
   Rename the badges and sort label so that they say "observed" (for example "Apărut recent", "prima urmă: 2019, arhivă web"),
   and explain the date columns (abbreviations) in a tooltip and in the methodology page.
5. `docs/METODOLOGIE.md`, in Romanian, from the code (`build.py` `status_of`, `score`, `since`, `last_activity`): what each
   status means and does not mean (HTTP reachability is not an operating service), that a code link is not an open-source
   licence, the score terms and weights, and what the score favours (age, page count, visibility). Link it from the footer.
6. Browser checks for each item (failed load with retry, noscript, canonical after close, badge wording), plus the existing
   63. Report the new total.

## Slice D — reconcile the integration review queue

Files: `data/taxonomy-v2/integrare.py`, new `data/taxonomy-v2/integrare/reconciliere.csv`, regenerated
`integrare/revizuire.csv` and `integrare/pachet.json`, `data/taxonomy-v2/valori.csv` (one new code),
`scripts/taxonomy_v2.py` (the rule for the new code), tests in `scripts/test_taxonomy_v2.py`, `data/taxonomy-v2/README.md`.

Problem: `integrare/revizuire.csv` copies R001–R066 from the base queue. They were written for the draft.1 manual proposal.
Their `valoare_originala` and `propunere` describe values the integration copy may not have.

1. Add the code `revizuire_stare:tehnic` ("Închis tehnic"): the item needs no editorial decision, because its premise does
   not apply to the current classification, it duplicates another item, or a code or data fix resolved it.
   Rule: `tehnic` requires a non-empty `motiv` and an empty `decizie_editor`. The publication gate counts only `deschis`.
2. `integrare/reconciliere.csv` (editable, one row per R item, all 66): `id`, `rezultat` (`pastrat`, `rescris`, `tehnic`),
   the new `camp`, `valoare_originala` (the integration copy's current value), `propunere`, `motiv`, and `dovada`.
   `integrare.py` applies it when it assembles `revizuire.csv`; the base `revizuire.csv` stays unchanged.
   `integrare.py` must still reproduce `integrare/` exactly (`test_integration_copy_is_reproducible`).
3. Per item, compare with the current `integrare/intrari.csv` row, the sealed response in `runs/.../responses/<slug>.json`,
   and the C/S items:
   - The premise still holds (for example a description is still absent) → `pastrat` or `rescris` with current values.
     Keep the priority. Keep `deschis`.
   - The questioned draft.1 value is absent, and the current value does not raise the same question → `tehnic`, with the
     current value in `motiv`.
   - A C or S item asks the same question for the same entry and field → `tehnic`, "dublură a Cxxx".
   - When in doubt, keep it open.
4. Every open item (R, C, S, V) must carry a concrete recommendation in `propunere` and its rationale in `motiv`, based only on
   evidence already in the package or the run. "verificare manuală" alone is not a recommendation. Phrase it as a
   recommendation for the owner, not as a decision. Do not change any classification in `intrari.csv`.
5. Report counts before and after: by prefix, priority and state, and the open high-priority items by slug.
   Report each `tehnic` closure with its reason so Opus can check them.

## Slice F — prepare the cutover (Opus decisions, 2026-10-20)

Slices A–E are merged (v0.7.0). The cutover itself is an owner action. This slice makes it one tested command.

Decisions:
- **F1. Detach the integration copy before the owner edits it.** Today `integrare.py` regenerates `integrare/` from the sealed
  run, so a direct edit (by hand or by `sheets.py pull` into `v2-intrari`) fails the reproduction check.
  `integrare.py --detach` records `{"detached": {"commit": <HEAD>, "date": …}}` in `pachet.json`. After that, the check verifies
  only the run's seal and that `git show <commit>:…` of the overlay still reproduces from the run (the derivation stays provable);
  the current overlay files are editorial. The owner runs `--detach`; the agent does not.
- **F2. One switch for the public root.** `common.PUBLIC_ROOT` (today `DATA`) is the default `--data-dir` of every script.
  `build.py` may write `site/` from a v2 root only when that root is `PUBLIC_ROOT`, and then always with the publication gate
  (`--allow-draft` never writes `site/`).
- **F3. `scripts/cutover_v2.py`.** `--plan` prints the steps and the blockers (publication gate errors, `tabs.intrari` null,
  not detached). `--apply` refuses while a blocker exists; otherwise it edits the working tree: `PUBLIC_ROOT`, `site-v2/app.js`
  → `site/app.js`, `v2.css` appended to `style.css`, `site-v2/` removed, `SITE_V2` copying retired, the Sheets workflows switched
  to `--data-dir` and the `v2-intrari` tab, `pages.yml` with the publication gate. It never commits, pushes or calls Google.
  `--rehearse DIR` runs `--apply` on a copy of the repository in DIR with the blockers waived, then runs `validate.py`, `build.py`
  into the copy's `site/`, and the unit tests there.
- **F4. Runbook `docs/briefs/cutover-taxonomy-v2.md`.** Preconditions (owner decisions), the order of the external actions
  (detach, create `v2-intrari` with `sheets.py push`, set `tabs.intrari`, freeze the v1 tabs, Form v2), the command, checks after
  the deploy, and the rollback (revert the commit; `data/` v1 stays intact).
- CI: `validate.yml` runs `cutover_v2.py --rehearse "$RUNNER_TEMP/rehearsal"`, so the cutover keeps working as the code changes.
