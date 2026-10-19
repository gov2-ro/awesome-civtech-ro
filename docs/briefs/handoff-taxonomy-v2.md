# Handoff — implement taxonomy v2

This is the entry point for a fresh implementation session in this repository.

## Implementation status — core slices 1–4 done (2026-10-19)

- Slice 1: the package is `2.0.0-draft.2` (128 concepts, 16 code lists, 22 link roles, 29 hosts). See `data/taxonomy-v2/versiuni.json`.
- Integration copy: `data/taxonomy-v2/integrare/`, built by `data/taxonomy-v2/integrare.py` from the sealed run.
  It applies the evaluation's three corrections from `integrare/modificari.csv`. 121 entries are `propus`; `incentru` is `de-revizuit`.
- Slice 2: `scripts/taxonomy_v2.py`, `common.load_catalogue` / `load_vocabulary` / `observation_paths`, `validate.py --data-dir --publication`.
- Slice 3: `build.py --data-dir --site-dir --allow-draft` and the v2 browser code in `site-v2/`.
- Slice 4: `scripts/test_taxonomy_v2.py` (40 tests) and `scripts/check_preview.py` (61 browser checks) pass.
  The v1 build is unchanged; production data and `site/` are unchanged.

Next: owner review of the integration queue, then enrichment, Sheets, Forms and CI in separate slices.
The sections below record the earlier handoff.

## Continuation update — classification completed

The classification experiment and evaluation are now complete in
`data/taxonomy-v2/runs/2026-10-19-reasoned-evidence/`.
Read its `README.md` and `evaluation/REPORT.md` before following the original sequence below.
The run contains 122 schema-valid responses: 105 classified entries, 16 partial entries, and one abstention.
Its vocabulary contains all four agreed maturity stages. The shared package remains draft.1.

Implement core slices 1–4 using the completed run as the candidate source.
Preserve the sealed run. Address the report's three semantic concerns in a separate integration copy.
Keep proposals, partial records, and the abstention distinct. Preserve original availability overrides by source identity.
A new classification run, runner, or provider selection is not a prerequisite for these core slices.
Keep production unchanged and finish with a validated local preview.

The remaining sections record the original handoff. Statements that classification has not run describe its earlier preparation state.

## Original handoff

The owner approved the model and wants implementation to begin.
The current session prepared the data proposal, specification, diagrams, and inference prompt.
It did not adapt the production pipeline or run automated classification.

## Read first

1. Repository `AGENTS.md`, then `docs/BACKLOG.md` and `docs/ACTIVITY.md`.
2. [Taxonomy specification](../specs/taxonomy-v2.md), especially **Agreed implementation revision**.
3. [Package editing guide](../../data/taxonomy-v2/README.md).
4. [Model and complete vocabulary diagrams](../specs/taxonomy-v2-vocabulary.md).
5. [Automated classification prompt](../prompts/taxonomy-v2-classifier.md) and
   [its output schema](../prompts/taxonomy-v2-classifier.schema.json).
6. Current loaders, validator, build, and browser code as each slice needs them.

Use CodeGraph first if the repository has `.codegraph/`. Do not create an index merely for this task.
Do not delegate unless the current session's instructions authorise it.

## Current state versus approved target

The actual package remains **`2.0.0-draft.1`**. It contains:

- 122 entries, 125 concepts, and 13 broad subjects.
- Only `maturitate:prototip`; maturity is currently parsed as a list.
- Code enums in `schema.json`; section and link-role definitions in `setari.json`.
- 86 original attributions with unresolved roles, 66 specific review items, and 822 initial assignment records.
- 22 proposed EuroVoc mappings with target identifiers and labels verified against a stored official response.
- Exact snapshots of all eight original top-level data files, plus separate working observation copies.

The approved target is **`2.0.0-draft.2`**:

- Add `maturitate:experiment`, `maturitate:pilot`, and `maturitate:operational`.
- Enforce zero-or-one maturity. Export one string or null, never an array.
- Keep separate subject, purpose, capability, format, technology, institution, and geography facets.
- Create `valori.csv`, `roluri-linkuri.csv`, and `gazde-linkuri.csv` with the exact headers in the specification.
- Make those CSVs authoritative for code lists, labels, roles, and host lookup.
- Keep structural rules and code-list references in `schema.json`; remove duplicate editable enum arrays.
- Keep only genuine site settings and reporting addresses in `setari.json`.
- Assemble derived settings and lookup dictionaries in generated JSON or loader memory.

Expect 128 concepts after adding the three maturity terms, unless a separately recorded vocabulary decision changes that count.
Do not assign the new maturity values to entries merely to populate the field.

The initial `manifest.json` counts describe creation of draft.1. Preserve that history and its source hashes.
Record the draft.2 revision separately; do not rewrite immutable source files or the initial assignment ledger.
The generated diagrams must follow the edited concept table.

## Authorised implementation sequence

The owner's latest order is **data first, UI later**.
Start with slice 1, then prepare the automated inference runner and evaluate its candidate data.
Proceed with slices 2–4 after the schema and candidate data are settled enough to integrate.
Each slice must leave working validation and a concrete reviewable result.
Do not stop merely to propose the next ordinary coding step.

### Slice 1 — revise the isolated data package

Update the draft package, schema, standalone validator, exporter, guide, and diagrams to match draft.2.
Extract all current link roles, hosts, section labels, and code values without changing their meanings.
Keep link tokens and role IDs compatible with the current data.

Move values without manufacturing blank-code records. Optional blanks belong to structural rules.
Keep `(lista,cod)` unique, validate host role references, and centralise the editable validator lists.
Add meaningful negative checks for multiple maturity values, unknown codes, duplicate codes,
broken role references, and conflicting sources of configuration.

The initial source data, slug set, text fields, original manual overrides, and source snapshots must remain recoverable byte for byte.
All proposed classifications stay proposed.

### Slice 2 — shared loading and validation

Adapt `scripts/common.py` and `scripts/validate.py` with explicit schema-aware loaders and data-root selection.
Keep v1 as the default. The specification names the functions and field mappings to change.
For v2, observations live under `observatii/`; snapshots are never working output.
Preserve accepted editorial fields independently from generated observations.

Add the selected-root tests and publication-readiness checks before connecting the new frontend.
The draft validator permits proposals; a public build requires accepted entry classifications.
An explicit preview option can permit proposals without implying acceptance.

### Slice 3 — build, public JSON, and frontend together

Implement the v2 build and its consumers as one compatible change.
Provide explicit data-root and output-directory selection as specified.
An isolated preview must not stamp the production template or delete its generated page directories.
Keep existing entry slugs, URL sections, and image/profile joins.

Use the approved filter design:

- Three existing tabs, desktop sidebar, mobile filter sheet, and detail panel.
- Subject and contextual topic filters; capabilities separate from formats.
- Specialist facets under more filters, with relevant organisation-specific labels.
- OR within a facet and AND across facets, with unique entry counts.
- Default grouping by primary subject; a flat list after subject filtering.
- Searchable Romanian/English labels and synonyms, while retaining free-text search.
- Compatibility for old category/type/keyword bookmarks through preserved legacy fields.

Do not expose migration notes, private notes, review decisions, or raw model evidence in public JSON.
Do not make a relevance score depend on how many concepts have been assigned.

### Slice 4 — verify the implementation preview

Run the legacy validator and an isolated legacy build.
Run draft.2 validation, then the v2 build into a separate output directory.
Check desktop and mobile filtering, overlapping subjects, counts, direct links, archive pages, and old bookmarks.
Check that maturity is scalar and that no unsupported technology claim appears from a topic-only assignment.
Keep the current public data source unchanged at the end of this handoff's core implementation.

Update the activity log, backlog, and affected schema/contributor documentation with measured results.
Use the documented acceptance checks; do not invent a framework migration or database server.

## Automated inference experiment — after package preparation, before UI integration

`data/taxonomy-v2/clasificare-input.csv` is the consolidated input for all 122 original entries.
It is derived from the immutable source snapshots and excludes the manually proposed v2 assignments and private notes.
Use it as source evidence, together with the frozen target vocabulary and code lists.
The input CSV does not replace the vocabulary, prompt, or output contract.

The owner wants an initially fully automated pass over the original data, with a prompt prepared first.
The prompt and machine-readable output contract are now available under `docs/prompts/`.
No model/provider was selected, and no API or classification job was run in the preparation session.

After slice 1 establishes a consistent frozen draft.2 vocabulary:

1. Implement a runner and a no-call dry run from the prompt's input/output contract.
2. Classify one entry per response. Account for all 122 source entries and failed calls.
3. Withhold manual v2 assignments and review conclusions until evaluation.
4. Keep local-only and retrieved-evidence runs separate. Use cached public-page evidence when available.
5. Validate JSON, supplied IDs, hierarchy, excerpts, source references, and attribution preservation deterministically.
6. Produce candidate tables, uncertainty queues, vocabulary proposals, and a comparison report in a new run directory.
7. Keep complete candidates `propus`; keep abstentions in raw output without fabricating a primary subject.

The current request asks for the prompt first. Do not interpret this brief as choosing a paid provider or starting real API calls.
When the owner explicitly starts an inference run, use the authorised provider and budget from that session.
The experiment needs no manual classification between individual entries.
Model confidence and successful validation do not establish editorial acceptance.

The draft's existing model-review script handles another task. Reuse suitable utilities if helpful,
but keep mention relevance labels separate from taxonomy assignments and their evidence.

## Later integration and cutover

The full specification covers enrichment, Sheets, Forms, and CI.
After the preview works, adapt those consumers in separate slices.
Create separate v2 Sheet tabs during migration; avoid two writers for the same live tabs.
Fix validation gating and use a genuine last-synced base for Sheets reconciliation.
Do not trigger workflows, change live Google files, switch production data, deploy, or publish a release merely to finish a preview.
Those are later actions with their own concrete reviewable result and session authorisation.

## Starting checks

These commands exist now:

```sh
python3 data/taxonomy-v2/validate.py --baseline
python3 data/taxonomy-v2/export_mermaid.py
python3 scripts/validate.py
git diff --check
```

Before implementation, the first command reports 122 entries, 125 concepts, and 0 errors.
The production validator reports 0 errors and 28 existing warnings.
An isolated v1 build produces 122 entry pages and 3 archives.
Previous integrity checks covered twelve failure/preservation cases using temporary copies.

The `scripts/* --data-dir` and `--site-dir` options in the specification do not exist yet.
Implement them before invoking the proposed preview commands.
Read `git status` before editing: this working tree already contains the uncommitted proposal and other user files.
Do not discard, overwrite, or commit unrelated work.

## Suggested message for a fresh implementation session

> Read `docs/briefs/handoff-taxonomy-v2.md` and begin its data-first implementation sequence.
> Upgrade the isolated package to draft.2 and prepare the classification runner and no-call dry run.
> Use `data/taxonomy-v2/clasificare-input.csv` as the original entry input, with the frozen vocabulary and classifier prompt.
> Leave UI integration for after candidate-data evaluation.
> Keep production unchanged and do not run model calls until the experiment's provider and budget are selected.
