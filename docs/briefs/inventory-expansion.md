# Specification and implementation handoff — expand the data inventory

Date: 2026-10-25. Baseline: commit `f013a88`, tag `v0.12.0`.
Status: ready for implementation. Collection and publication have not started under this brief.

## 1. Start here

Read `AGENTS.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md` first.
Read the inventory sections in `docs/DATA-SCHEMA.md` and the implementation files listed below.
Treat older migration briefs as historical. The public data root is already taxonomy v2.

Copy this prompt into the implementation session:

> Implement `docs/briefs/inventory-expansion.md` in milestone order.
> Start with safe incremental collection and its offline regression tests.
> Then deepen INS and investigate the bounded project batch.
> Extend variable meanings and source evidence, and update the existing preview.
> Keep the publication boundary and existing evidence intact.
> Make routine implementation decisions within the brief. Record external blockers and measured results.
> Do not replace missing evidence with guesses. Finish with the acceptance report specified in section 10.

The task is implementation and a bounded collection pass. A plan alone does not finish it.
This brief does not request a push, deployment, Google synchronisation, paid service or message to project owners.
Follow the repository's commit and version rules when recording completed milestones.

## 2. Product goal

A visitor knows a data need or institution and wants to find relevant projects.
The inventory must explain what the data describes, what each project allows, and where the evidence comes from.
It must reveal meaningful overlap between projects without claiming that their datasets can automatically be joined.

Examples of the intended route:

- A company identifier leads to projects that accept or expose CUI, with each field's role visible.
- A statistical indicator leads to its dataset, dimensions, originating provider and projects that demonstrably use it.
- An institution leads to projects that obtain its data, separately from projects that examine that institution.

Improve the existing `/date/` preview and project field browser. Do not create a second explorer or redesign the ordinary sidebar.

## 3. Measured starting point

These numbers describe the baseline commit. Recompute them before collection and after each milestone.

| Measure | Baseline |
| --- | ---: |
| Catalogue entries | 140 |
| Projects / resources / organisations | 106 / 21 / 13 |
| Projects and resources in the data finder | 127 |
| Entries with structured field evidence | 14 |
| Projects/resources without extracted structured fields | 113 |
| Retained structured-source URLs | 25 |
| Successfully parsed sources / HTTP failures | 24 / 1 |
| Source-scoped field records | 2,302 |
| Schema declarations / sampled JSON paths / CSV headers / INS dimensions | 1,312 / 904 / 82 / 4 |
| HTML control candidates / entries containing candidates | 308 / 78 |
| Partial / unconfirmed profiles across all 140 entries | 78 / 62 |
| Accepted provider relations / entries with accepted providers | 26 / 11 |
| Pending provider proposals | 15, review items D132–D146 |
| Proposed business-variable groups | 7 |
| Unit tests discovered / skipped | 308 / 6 |
| Explorer inventory / dedicated finder browser checks | 25 / 25 |

The field total is not a count of independent variables. Paths repeat concepts across representations and operations.
The 62 unconfirmed profiles and the 113 entries without structured fields use different denominators.
Missing extraction does not prove missing data. An organisation need not expose a dataset.

The 14 entries with structured evidence are:

```text
achizitii-directe-ti-2026  codurbanism          companii-de-stat
complet-online           demoanaf             ins-gov2
orasul-care-se-intinde   posturi-gov2          prima-cifra
ro-api-hub               romania-transparenta transparenta-eu
ultima-noapte-pib        unde-se-termina-asfaltul
```

Existing group sizes are CUI 4, CPV 3, SIRUTA 2, county 5, locality 3, population 2 and turnover 1.
These are unique catalogue entries, including resources. CUI plus CPV currently matches two projects.
INS currently matches nine entries, or three when resources are excluded.
Preserve those supported memberships. Additional evidence can increase the counts.

## 4. Existing implementation and boundaries

| File or directory | Responsibility |
| --- | --- |
| `scripts/collect_docs.py` | Collect static first-party pages, llms files, methodology, about pages and optional data-page links. |
| `scripts/inventory.py` | Discover explicit structured links, parse sources, generate profiles and review exports, check local evidence. |
| `scripts/inventory_site.py` | Project draft metadata into the isolated explorer and finder. |
| `scripts/build.py` | Build the public catalogue or an explicit inventory preview. |
| `scripts/test_inventory.py`, `scripts/test_inventory_site.py` | Offline parser, provenance, grouping and publication-boundary tests. |
| `scripts/check_inventory_preview.py`, `scripts/check_data_finder.py` | Browser checks for the two inventory interfaces. |
| `site/app.js`, `site/style.css` | Existing explorer and project field browser. |
| `site/inventory.js`, `site/inventory.css`, `scripts/templates/inventory.html` | Dedicated data finder. |
| `data/taxonomy-v2/observatii/documentare/` | Tracked documentation metadata; downloaded bodies under `pagini/` are ignored. |
| `data/taxonomy-v2/observatii/inventare/` | Tracked inventory records and exports; downloaded bodies under `surse/` are ignored. |
| `data/taxonomy-v2/inventar-concepte.json` | Hand-edited proposed business groups and exact project/field selectors. |
| `data/taxonomy-v2/integrare/relatii.csv` | Accepted source relations and other live relations. |
| `data/taxonomy-v2/integrare/revizuire.csv` | Editorial review queue. |

Keep the following boundaries:

1. The public root remains `data/taxonomy-v2/integrare/`.
2. Keep frozen v1 files and sealed `source/`, `reference/` and `runs/` unchanged.
3. Generate inventory exports and site output through scripts. Do not repair generated records by hand.
4. Keep inventory assertions proposed and partial. Do not accept source relations through collection code.
5. Preserve the `--with-inventory` boundary. It requires a separate site directory and cannot write `site/`.
6. Keep build, validation and core inventory parsing compatible with Python 3.12 and stdlib-only execution.
7. Use optional PEP 723 helpers for browser rendering or binary formats when needed. Document and test each added dependency.
8. Keep UI text and data labels in Romanian. Keep code comments and this technical guidance in English.
9. Use bounded public reads. Do not submit forms, authenticate, execute project actions or bypass access restrictions.

A fresh checkout can build the preview from tracked metadata. It cannot verify ignored source bodies that are absent.
Do not assume that `tmp/ins-llms.txt`, local caches, preview servers or a previous Python environment exist.

### Known limitations to address

- Discovery currently prefers explicit JSON/CSV/TSV/GeoJSON links and defaults to three files per entry.
- File limits also affect candidate reconstruction. A larger previous inventory can disappear when rebuilt with the default limit.
- `inventory.py --only` restricts fetching, but regenerates all profiles and sources from available documentation and caches.
  On a fresh checkout, missing caches can downgrade unrelated records to `necolectat` and erase their fields.
- `--offline` also rebuilds records. It must not silently replace tracked evidence with empty results when bodies are missing.
- The fetcher decodes text. It is not a binary spreadsheet or PDF reader.
- Sample extraction is bounded to 25 array elements, seven nested levels and 2,000 fields per source.
- Shared-host pages and sibling project paths are deliberately excluded unless project-specific evidence establishes a relationship.
- Monitor Energie's linked contract returned HTTP 401. Keep it blocked unless public documentation provides another usable source.

## 5. Evidence and meaning contract

Keep three layers distinct:

| Layer | What it records | What it does not establish |
| --- | --- | --- |
| Source observation | A field, parameter, dimension or header at a source location. | A complete project model or business meaning. |
| Business interpretation | A proposed label, definition, role, unit and concept mapping, with evidence. | Reviewed equivalence or compatible join keys. |
| Project use | Evidence that a project consumes, transforms, accepts or exposes the data. | Use by every project with the same provider. |

For each new field, retain the source URL, source ID, retrieval time, body hash and exact location.
Keep the requested URL and final URL where redirects occur.
Use a JSON pointer, CSV column, spreadsheet sheet/cell range, document page/table, or equivalent reproducible locator.
Record extraction and sampling limits. Retain immutable local evidence versions.

Distinguish declared storage types, observed sample types, semantic roles and HTML controls.
An identifier can look numeric while remaining a string. Preserve leading zeros.
A CSV header alone declares no storage type. A chart label alone declares no dataset schema.
Separate API parameters, request bodies, returned fields, statistical dimensions, measures and derived outputs.
Generic search, pagination, authentication and newsletter controls must not become business variables automatically.

Extend the existing records additively. Keep old records readable.
Document every new key in `docs/DATA-SCHEMA.md`, with its evidence and missing-value rules.
If an incompatible format change is necessary, version it and supply a migration with regression fixtures.

The expanded inventory must support these facts where evidence exists:

| Scope | Facts |
| --- | --- |
| Dataset | Name, identifier/version, publisher, originating provider, license link, period and geographic level. |
| Field | Original name/path, Romanian label, meaning, role, declared/observed type, unit, codes/enums and missing-value rules. |
| Project | What the data describes, supported user inputs, transformations, outputs and what the user can do with them. |
| Interpretation | Proposal state, supporting evidence and any unresolved ambiguity. |

Unknown facts remain empty or null. Do not infer units from magnitude, periods from retrieval dates, or providers from project authors.
Represent each new factual interpretation with its value, evidence reference and evidence basis.
Keep an editorial paraphrase distinguishable from a direct declaration or sample observation.
Existing catalogue descriptions remain a labelled fallback, not evidence for newly asserted transformations.

Provider evidence must distinguish original producer, distributor/API host and project author when the documentation permits it.
The accepted provider facet continues to use accepted `date_din` relations only.
Put new provider findings into review proposals; do not change live relations or close D132–D146 under this brief.
Use the next unused review identifier if adding queue rows. Preserve existing editor decisions.

## 6. Milestones

### A. Make targeted collection safe before making new requests

Implement and test this milestone before a live inventory refresh.

1. Load tracked source/profile metadata before reconstructing candidates.
2. Preserve unselected project records and their source references during `--only` runs.
3. Preserve shared sources still referenced by other projects, including their previous evidence versions.
4. Persist discovered source membership and its discovery evidence, separately from the per-run fetch limit.
   Add generated `observatii/inventare/descoperiri.json`, keyed by project and source URL.
   Each discovery records its parent URL, method, evidence locator/hash when available, and retrieval time.
5. Seed that registry from existing source memberships. Mark an unavailable original discovery locator as unknown, rather than inventing one.
6. Apply file/request budgets to selected work. A smaller budget must not delete previous discoveries or unrelated sources.
7. Define missing-cache behaviour explicitly. Offline rebuilds must preserve prior metadata or fail before writing affected records.
8. Record refresh failures separately from the last successful field evidence. The UI must not label stale evidence as freshly verified.
9. Validate proposed output before replacing generated files. A failed parse or validation must not leave half-written exports.
10. Keep deterministic ordering. A replay from identical complete caches must produce identical inventory content.

Allow explicit retirement of an obsolete source only with a recorded reason and retained history.
Do not treat a temporary 404, 401 or timeout as proof that the dataset never existed.
Audit the documentation collector's save path for the same preservation requirement; change it only if the tests show a defect.

Required regression cases:

- Target one project with no caches for unrelated projects; their records and references remain unchanged.
- Increase a selected project's source count, then rerun with the default limit; prior membership survives.
- Refresh one of two projects sharing a source; the other retains usable evidence.
- Simulate a failed refresh and a missing offline body; prior data survives and the failure is explicit.
- Corrupt a proposed output; no partial replacement occurs.

### B. Deepen existing inventories, with INS first

Inspect the 14 existing inventories for documented additional datasets, endpoints and definitions.
Fetch additional sources only where they answer a named gap in the report.
Do not raise limits globally or fetch every observation from a data warehouse.

For `ins-gov2`:

- Begin with the documented dataset listing at `https://ins.gov2.ro/api/datasets?limit=1` and project documentation.
- Inspect the actual listing response before choosing pagination or dataset routes. Do not guess its schema or dataset codes.
- Use up to five verified dataset metadata records for this batch, including ACC102B if it remains available.
- Prefer datasets demonstrably used by selected projects. Record the evidence for each such use.
- Capture dataset title/code, indicator meaning, dimensions, units, period and geographic level where explicitly declared.
- Distinguish an indicator, a dimension and its possible values. Do not export each dimension value as another variable.
- Keep code-list versions or validity periods where supplied. Preserve source codes alongside display labels.

Known checks from 2026-10-25:

- INS `llms.txt` was fetched successfully. An earlier inability to fetch it is not a verified limitation.
- `https://ins.gov2.ro/api/datasets/ACC102B?lang=en` returned workplace-accident metadata, not GDP.
- Its four declared dimensions were CATEGORY, REF_AREA, TIME_PERIOD and UNIT_MEASURE.
- The metadata source note named labour-inspection/ministry sources. INS distribution alone did not prove original authorship.
- The POP101A example route returned 404. Do not reuse that example without fresh evidence.

A provider shared by nine projects is not proof that all nine use the same five INS datasets.

### C. Investigate a bounded batch of missing inventories

Use these 12 primary entries. They had zero structured fields at the baseline.
The signals below come from catalogue and documentation metadata; they do not prove that a usable schema exists.

| Slug | Starting signal | Initial question |
| --- | --- | --- |
| `afacut` | Three collected edition/data pages. | Which investment, administrative and statistical fields support the comparisons? |
| `biografia-localitatii` | Catalogue describes locality statistics from INS TEMPO. | Which exact indicators, locality identifiers and periods are used? |
| `registrul-firmelor` | Collected llms, methodology and about pages. | Which company identifiers, attributes and source registries are exposed? |
| `dignitas` | Methodology and linked `TeamDignitas/dignitas` repository. | Which structured records drive the project, and what do their fields mean? |
| `monitorul-ai` | Methodology and linked `ciocan/monitorul-ii` repository. | How are parliamentary sessions, speakers and transcript records represented? |
| `rezultate-vot` | Linked `code4romania/rezultatevot` repository. | Which election, geography, candidate and result fields are used? |
| `votdiaspora` | Linked `code4romania/vot-diaspora-api` repository. | Which public station, location and election fields exist? |
| `aerlive` | About pages and visible control candidates. | Which public sensor, pollutant, time and unit definitions can be verified? |
| `calitate-aer-radauti` | Existing editorial pilot; catalogue describes a sensor network. | Which measurements, sensor identifiers and time fields are documented? |
| `banii-nostri` | About pages; catalogue describes procurement and public finance. | Which entities, financial measures, periods and providers are documented? |
| `europescope` | Collected methodology and about pages. | Which institutions, events, documents and identifiers form its data model? |
| `despre-femicid` | Collected methodology and about pages. | Which published aggregate variables and definitions support the project? |

Reserve entries: `ce-fac-politicienii`, `onorata-instanta`, `guvernezi`.
Use at most three replacements. Record the reason before replacing a primary entry.
An inaccessible primary remains in the report; replacement does not erase the failed investigation.

Use this discovery order:

1. Existing project-specific llms, methodology, about pages and data dictionaries.
2. Explicit downloads, dataset catalogues, schemas and API documentation.
3. Project-linked repositories: documentation, schema/type definitions, data folders and relevant notebooks.
4. Rendered public pages and their data requests when static evidence is insufficient.
5. Spreadsheet or document extraction only where an identified source needs it.

Resolve repository paths at a recorded commit. Distinguish current deployed usage from historical repository fixtures or tests.
An arbitrary repository on the same account is not project-use evidence.
Do not clone an organisation's entire account or guess protected endpoints.
For case-based or personal data, prefer published schemas, dictionaries and aggregates over copying individual records.

Use public search only to locate a project's missing documentation. Record the resulting primary-source evidence.
Do not run paid search/review scripts or infer a schema from third-party prose.

Collection limits for this batch:

- At most 150 direct HTTP fetches, including retries; report browser navigation/request counts separately.
- At most six workers and two concurrent requests per host.
- Keep the existing text response-size and timeout defaults unless one identified source needs a documented exception.
- At most ten new structured sources per selected entry and two browser pages per selected entry.
- Read bounded samples. Do not download full archives or exhaustively enumerate API observations.

Keep a request log with outcomes, method, bytes and cache reuse. Do not record credentials or unrelated browser traffic.
If the budget ends, finish offline work and list the uninspected sources. Do not claim complete coverage.

### D. Add meanings and meaningful shared variables

Expand the existing dictionary from actual evidence. Do not create a broad speculative vocabulary first.
Prioritise identifiers, geography, time, financial measures and environmental measures supported by this batch.

Keep CUI, CPV and SIRUTA distinct from names, internal IDs and human-readable labels.
Keep a company's address separate from a contracting authority's address, even when both expose a locality field.
Keep totals, rates, percentages and per-capita measures distinct.
Different units, time bases or geographic levels can belong to a discovery family without becoming equivalent measures.

Extend selectors with optional source URL, exact path and role constraints where a field name is ambiguous.
Within one selector, supplied constraints must all match. Alternative selectors remain alternatives.
Keep existing project/name selectors working. Keep a fixture for each new constraint combination.
Do not group arbitrary `id`, `value`, `name` or `year` fields solely by spelling.

For every new group, record a Romanian label, definition, category and evidence-backed memberships.
Retain the original field role and representation for each member.
Use categories such as identifier, dimension, measure, user input and derived output only when supported.
New groups remain proposals; this brief does not certify join compatibility or editorial acceptance.

### E. Integrate, report and hand over

Keep the current finder behaviour:

- All selected variables are required; other facets use alternatives within a facet. Facets intersect.
- Providers remain separate from target institutions.
- Counts use distinct entries. Selected values remain visible; small categories stay under `Mai multe`.
- Search and selection survive reload and browser history through the URL.
- Entries without inventories remain discoverable.
- Project fields load on demand. Keep roles, source references, types and partial labels visible.

Expose new verified definitions through the existing summaries, search and evidence views where useful.
Keep sample observations visibly different from declarations. Display unknown types and units honestly.
Do not show raw cache paths, raw snapshots, browser request dumps or HTML-control candidates as accepted data inputs.
Deduplicate shared source records without merging unrelated datasets or dropping project-use evidence.

Update browser checks to derive expected counts from the generated index and independently defined filter rules.
Do not retain baseline count assertions that make valid new memberships fail.
Preserve tests for the existing supported members and for negative cases.

## 7. Output and coverage report

Generate `observatii/inventare/acoperire.csv` and a readable `docs/reports/inventory-expansion.md`.
Do not overwrite the ordinary project summary with a count that conflates field paths and business variables.

The CSV must include one row per catalogue entry, with:

```text
slug, tip_entitate, investigat_in_lot, stare_investigare,
surse_structurate, campuri_din_surse, concepte_propuse,
campuri_cu_definitie, campuri_cu_tip_declarat, campuri_cu_tip_observat,
masuri_cu_unitate, masuri_fara_unitate, surse_cu_provenienta_verificata,
limite, blocaj, urmatorul_pas
```

Define each denominator in `docs/DATA-SCHEMA.md`.
Count semantic measures separately from generic fields when reporting missing units.
Do not count existing catalogue text as a newly evidenced variable definition.
If a denominator is unknown, leave it unknown and explain why.

The readable report must include:

- Before/after coverage for the 127 projects/resources, and a separate summary for all 140 catalogue entries.
- A per-selected-project outcome: source URLs, new fields/groups, supported inputs, meaning, limitations and remaining work.
- Additional source findings for the 14 existing inventories and dataset-specific INS results.
- Shared groups with at least two supported project memberships, plus ambiguous candidates kept separate.
- Provider proposals with their evidence, without silently accepting them.
- Network totals, elapsed work, bytes/limits, cache reuse, parser/browser methods and external blockers.
- Test results and the public-build boundary check.

Target ten new structured inventories from the primary/reserve batch, with useful definitions rather than empty field lists.
This is an outcome target, not permission to invent data or exceed the collection budget.
Report a shortfall explicitly. Complete the investigation report for every attempted primary and replacement entry.

## 8. Verification

Add offline fixtures for actual failure modes and evidence rules, not just copies of the implementation.
Keep network calls fake in unit tests. Keep optional dependencies importable only where used.

Required checks include:

1. Incremental preservation, shared-source retention, failed-refresh handling and deterministic cache replay from milestone A.
2. A captured INS listing plus metadata fixtures. Indicator/dimension/value distinctions and original/distributor attribution remain correct.
3. Cross-project isolation on shared hosts and explicit repository discovery at a recorded revision.
4. Binary/text format detection and exact evidence locators for each newly supported format.
5. Identifier strings with leading zeros, unknown CSV types, sample nulls, units and missing-value conventions.
6. Same-name fields with different sources, paths or roles do not acquire an unsupported shared interpretation.
7. Invalid hashes, pointers or semantic references fail validation. Stale interpretations are flagged when their evidence changes.
8. A source used by several projects contributes once per project to facet counts.
9. Default publication excludes drafts. Reusing an isolated output without the inventory flag removes generated draft pages.
10. Finder intersections, URL restoration, escaped text, failed loads and 320/390 px layouts still work.

Run these existing commands after script changes:

```sh
python3 scripts/validate.py --publication
python3 scripts/build.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/inventory.py --check
python3 scripts/build.py --site-dir /tmp/civtech-inventory-expanded --with-inventory
node --check site/app.js
node --check site/inventory.js
git diff --check
```

Serve the preview in another terminal:

```sh
python3 -m http.server -d /tmp/civtech-inventory-expanded 8770
```

Then run:

```sh
uv run scripts/check_preview.py http://localhost:8770/
uv run scripts/check_inventory_preview.py http://localhost:8770/
uv run scripts/check_data_finder.py http://localhost:8770/
```

The evidence check needs local snapshots. Report unavailable snapshots separately from corrupt evidence.
Do not run a full forced refresh solely to make that check pass on a fresh checkout.
Provide a metadata-only structural check if needed; it must never claim that absent bodies were hash-verified.
Retain the cache hashes in the collection report so another session can identify the evidence versions.

Compare the default public payload before and after, ignoring generation time and asset stamps.
Its catalogue classifications and accepted providers must remain unchanged under this brief.
Do not hand-edit `site/index.html` asset hashes; let the build stamp them.

## 9. Completion criteria

- Safe selected/offline runs pass the new preservation tests before the collection pass starts.
- Existing supported evidence survives, including unchanged entries without local caches.
- INS has dataset-specific findings, with unavailable metadata and misleading examples recorded honestly.
- Every attempted primary/reserve entry has a documented outcome and next step.
- New fields and semantic interpretations have reproducible evidence and explicit missing values.
- New shared groups use contextual matches, with no unsupported join claims.
- Coverage exports distinguish entries, fields, business groups, declarations, observations and unknowns.
- The existing preview consumes the expanded records without changing its publication boundary.
- Required checks pass, or external evidence gaps are reported with their exact scope.
- Update `docs/BACKLOG.md`, `docs/ACTIVITY.md`, schema documentation and the readable report in the same milestone.

Do not mark the coverage target achieved when the measured result is below it.
Do not mark implementation complete while required preservation or publication checks fail.

## 10. Final implementation report

Return the branch/commit identifiers, if committed, and links to the coverage report and preview instructions.
Report the actual before/after numbers, new shared concepts, source proposals, external blockers and remaining review work.
Separate measured results from assumptions. State which milestones are complete and whether the ten-inventory target was met.
State that inventory assertions remain proposals and whether any public or external state changed.
