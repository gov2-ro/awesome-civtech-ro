# Backlog

Statuses: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` dropped.

## Filter simplification and data provenance — 2026-10-25

- [x] Combine subjects and themes in one `Subiect` filter. Keep old topic URLs working.
- [x] Sort each facet by its current count. Hide options with at most three matches under `Mai multe`.
- [x] Move geography to secondary filters. Stop adding national projects to each named locality's count.
- [x] Separate national totals, nationwide data with local detail, and local reach. Preserve unverified detail explicitly.
- [x] Add evidence-backed data sources, separate from authors and monitored institutions: 26 accepted relations for 11 entries.
- [x] Add 15 source proposals for review. Proposed sources stay out of the public filter.
- [x] Compact the sidebar: inline tags, 260 px width, shorter source labels, grouped Parliament, sources before format.
- [x] Fix the 320 px overflow: the sort controls forced 347 px. The result column and select can now shrink to the viewport.
- [x] Preview inventories in the explorer: result markers, a Date & metodă panel, lazy field search, sources and evidence.
- [x] Add a dedicated data finder preview: all projects/resources, shared variables, accepted sources and target institutions, with evidence and shareable selections.
- [x] Extend the seven proposed business-variable groups in `inventar-concepte.json` with explicit project/field evidence (milestone D, v0.17.0): 30 groups now,
      selector constraints on source, path and role, evidence pins checked by `inventory.py --check`.
- [ ] Review the 30 proposed groups (23 are new). Decide each `ambiguitati` entry and each unit fact. A group is a discovery aid, not a join key.
- [ ] Review the inventory preview labels and business meanings before enabling it in the public build.
- [x] Pilot project data inventories: purpose, source datasets, variables/types/units, user inputs, transformations, and outputs.
      Collected documentation for 140 entries; drafted five profiles and 19 field candidates with evidence and completeness.
- [ ] Review the five `observatii/documentare/pilot-inventare.json` profiles. Confirm types and units from data dictionaries or schemas.
- [x] Extend inventory drafts to all 140 entries. Reuse source records and shared schema models; keep evidence kinds distinct.
- [ ] Review the 2,302 structured field records and 308 control candidates. Map technical paths to business variables, meanings and units.
- [ ] Resolve unconfirmed inventories for 62 entries; a missing static schema does not prove that the project has no data.
- [ ] Inspect the protected Monitor Energie contract only if public documentation becomes available; the linked URL returned 401.
- [x] First structured-source pass beyond the pilot: 25 retained source URLs, 14 projects with field records.
      A Făcut?’s three edition pages now contribute an actual search control; their raw data schema remains unconfirmed.
- [ ] Correct or report INS llms examples: POP101A is absent (earlier measurement); ACC102B is workplace accidents, not GDP (measured again 2026-10-25,
      same body hash). The list route and the ACC102B, POP107D, LOC101B, TRN139A and GOS104A metadata routes work.
- [ ] Add browser rendering or document-format extraction where static HTML and llms.txt leave gaps.
      Done in v0.14.0: the fetcher detects binary bodies (`format-binar`) instead of decoding them. No spreadsheet or PDF reader yet.
- [ ] Review D132–D146 in `data/taxonomy-v2/integrare/revizuire.csv`. Confirm the provider and evidence before accepting each relation.
- [ ] Continue provenance and geographic-detail review. 129 entries have no accepted source; 130 have no verified data detail.
      Empty fields can also mean not applicable. Do not infer a provider from monitored institutions or authors.
      Do not infer complete county or locality coverage from national reach.

## Inventory review and public data finder — 2026-10-25

- [x] Local review interface for provider items and variable groups (brief: [review-ui.md](briefs/review-ui.md); v0.20.0).
      `python3 scripts/review_ui.py` serves it on 127.0.0.1. It adds per-group and per-selector review states to `inventar-concepte.json`
      (the finder hides `respins` groups and `exclus` members and shows a state badge). No real item or group was decided.
- [ ] Run `node --check scripts/templates/review_ui.js` and `scripts/check_review_ui.py` in `validate.yml`. A workflow change was outside the brief.
- [ ] Decide whether accepting a provider should pin the hash of its evidence page. D132–D146 record no hash, so the tool shows them as `fără amprentă`
      (readable, never `verificat`). A pin needs a convention or a column; `relatii.csv` has none today.
- [ ] `inventory_report.py --check --data-dir <other root>` still compares `docs/reports/inventory-expansion.md` under the repository root.
      The review tool's check panel shows that report as out of date on a copy of the data root whose decisions differ. Add a `--report` path if copies need a clean check.
- [ ] Owner review: decide D132–D162 and the 30 groups with the interface.
- [x] Group the variable groups into families (identifiers, geography, time, then subject areas); the finder groups its variable facet by family.
- [x] Per-project table of variables at `/date/lista/`: one row per entry with fields, one column per family, normalised names only, and a count of ungrouped fields ("Altele").
      Desktop first; the table scrolls horizontally in its frame.
- [ ] Project variables profile page: the source field names (`source:field`) of one project, by family and by source. The table above leaves them out on purpose.
- [ ] Let an editor add a field that the extractors missed: a hand-edited file with slug, source URL, name, locator, role, declared type, unit,
      description and an evidence fragment; `inventory.py` merges it as an editor-added field and `--check` verifies the fragment. Entry from the review interface.
      Needs a short brief.
- [ ] Publish `/date/` on the public build. Needs its own brief after the review: which states appear, labelling of proposals,
      and the change to the `--with-inventory` boundary.

## Inventory expansion — implemented 2026-10-25 (milestones A–E, v0.14.0–v0.18.0)

Implementation handoff: [inventory-expansion.md](briefs/inventory-expansion.md).
The brief fixes the batch, evidence rules, preservation requirements and acceptance report.

Baseline: 127 projects/resources; 14 have structured field evidence. Another 113 have no extracted structured fields.
The 2,302 field records are source paths, not independent business variables. Seven business groups are proposed.
The 62 unconfirmed profiles cover the full 140-entry catalogue, including organisations; this is a different measure.

- [x] Write the implementation specification and a copyable prompt for a fresh session.
- [x] Fix targeted/offline preservation before new collection (milestone A, v0.14.0). `inventory.py` now reads the tracked state first.
      `--only` changes only the selected projects. A smaller file limit keeps earlier members. A failed refresh keeps the last evidence.
      `descoperiri.json` holds 59 discoveries (25 active, 34 found but not admitted). 34 new offline tests cover the failure modes.
- [x] Deepen INS (milestone B, v0.15.0): the dataset listing (3,368 datasets; llms.txt says about 3,600) and five verified metadata records
      (ACC102B, POP107D, LOC101B, TRN139A, GOS104A) with dimensions, unit options, period, geographic levels and the declared source note.
      Each dataset has the project-use evidence that named its code. 6 requests. The mirror's period ends earlier than the projects cite (see ACTIVITY).
- [x] Deepen the other existing inventories where a named gap exists: six more sources (data index, 2025 company financials, parameter index,
      law source manifest, two Romania Transparentă files). 6 requests. 28 documented candidates stay unfetched (codurbanism 26, one each elsewhere).
- [ ] Fetch the 26 codurbanism data files only if a reviewer needs them; its `source-manifest.json` already names the sources.
- [ ] Verify the INS `POP101A` example route again with a fresh request. The 404 in the brief is not re-measured here.
- [x] Investigate the bounded batch of 12 entries (milestone C, v0.16.0): all 12 have structured sources now; see `docs/ACTIVITY.md` for outcomes and blockers.
- [x] Inspect rendered pages and their public data requests where static collection is incomplete (4 navigations). Repository files at recorded commits are read
      for 5 repositories. HTML and markdown tables are read; spreadsheets and PDF files are not (no selected entry needed them).
- [ ] Tell the `desprefemicid.ro` owners that the page script contains an Airtable access token. This pass did not contact them.
- [ ] Re-run the `aerlive.ro` render with a third navigation and keep the data response (`/wp-json/api/v1/data?city=BUC`, 12,647 bytes). It needs permission beyond the two-page limit.
- [ ] Read the other 74 Dignitas patches (or its running database) to complete the table list; read the Scramble API documents of Rezultate Vot if they are public.
- [ ] Ask for the working EuropeScope API documentation (`/api/docs` returns 404) and the Registrul Firmelor API schema (a free key is needed; none was requested).
- [x] Add the DemoANAF `api-docs` page to its inventory (v0.21.0, reader `html-api-docs`): 60 operations, 113 inputs and 6 response members, compared with `openapi.json`
      (14 operations and 22 inputs only on the page). 4 requests. See `docs/ACTIVITY.md`.
- [x] Count a record that restates another source (`in_contract`) once. `inventory_state.counted_fields` drives the profile and report counts;
      the preview folds the restatement into the restated record as `also` evidence. DemoANAF: 221 → 130 counted fields; finder card 85 → 57; `cui` evidence 5 → 3.

- [x] `harta-firmelor.ro/date` lists "Surse" for each dataset: provider evidence for D136–D139 (ONRC, ANAF, SICAP/SEAP, Monitorul Oficial). Done 2026-10-25 (v0.24.0) from copies that the owner saved
      from their browser (`/date` and `llms.txt`, 20:39 +02:00), kept with `inventory.py --import-saved` and `collect_docs.py --import-saved`: no request was made. Reader `html-carduri-csv`: 8 datasets,
      40 fields with a declared description, 1 unit, no type. D136–D139 now cite the retained text (`verificat`); D170–D173 propose the other providers the page names (Ministerul Finanțelor, the courts portal, BPI, ANRM).
      Every automated request gets HTTP 429 from a Vercel Security Checkpoint, and `llms.txt` forbids automated extraction (see Verified limits).
- [ ] Decide D136–D139 and D170–D173 in the review interface. The page labels are `ONRC — Registrul Comerțului`, `ANAF — evidența fiscală`, `SICAP — achizițiile publice`, `Monitorul Oficial, partea a IV-a`,
      `MFP — bilanțurile`, `Justiție — dosarele`, `BPI — Buletinul Procedurilor de Insolvență` and `ANRM — licențe și permise miniere`; `Geocodare — adresele pe hartă` names no provider and has no item.
      The page does not name the operator of the courts portal or the publisher of the BPI; D171 and D172 say so.
- [ ] Group candidates from the `harta-firmelor` columns, for the owner to review (nothing was added to `inventar-concepte.json`): the seven `year` columns look like members of `perioada-de-referinta`
      (the reference year of an aggregate row; each file dates a different event). `employees_reported` (a sum over balance sheets) and `median_turnover_lei` (a median) are not `numar-salariati` / `cifra-afaceri`:
      those groups hold the value of one company, and their notes already keep national aggregates out.
- [ ] If more columns are needed than the page lists: ask `harta-firmelor.ro` for a key to the official API (`https://api.harta-firmelor.ro/docs`, keys on request) or for the CSV headers. Do not download the CSV files.
- [ ] Show the origin of an owner-saved copy in the review interface. The evidence panel says "sursă păstrată" for it; the record has `origine` `copie-salvata-de-proprietar`.
- [x] `registru.horecaos.org/surse` names nine sources. D153–D156 (ONRC, ANAF, Ministerul Finanțelor, SEAP) already cited it; done 2026-10-25 (v0.24.1): D174 proposes OpenStreetMap and
      D175 proposes the courts portal (Ministerul Justiției, marked „în lucru” on the page). The retained text of 2026-10-24 (sha256 `81cd22875d06a3b4`) holds every source, so the owner's copy of 2026-10-25 was not imported.
      D140 and D141 (candidates from the description, with rows L140 and L141) now point at D153 and D154, which carry the evidence.
- [ ] Decide D140/D153 and D141/D154 for `registrul-firmelor`: each pair names the same provider. Accept the item with evidence and close the other one as a duplicate.
- [-] Propose BPI and Monitorul Oficial Partea a IV-a for `registrul-firmelor`. Reason: the page marks both „cerut oficial”, so the project does not have their data yet. Its insolvency state comes from the ONRC
      status codes (D153). Propose them when the page says that the data arrived.
- [ ] A guard for sites that forbid automated access. Only the saved addresses are protected today (`collect_docs.py` and `inventory.py` never request them). A run of `collect_docs.py --force`, `profile.py` or
      `search.py` for the whole catalogue still requests the other addresses of `harta-firmelor.ro`. Skip the entry, with a recorded reason, in every script that requests a project's site.

### DemoANAF — paused 2026-10-25

**Conclusions.** Three sources: `openapi.json` (46 operations, 95 parameters, no response schemas), the `api-docs` page (60 operations, 14 and 22 inputs
only on the page, response envelope only) and the INS dataset POP107D that the site cites. 130 counted fields, all request inputs except the envelope.
DemoANAF is a strong source of request keys (CUI, CPV, county, locality, year), and an unknown source of returned fields. Every operation needs a Pro key
(some accept x402 per-request payment), so nothing was called.

**Hint for resuming.** First run `python3 scripts/inventory.py --only demoanaf` and read `comparatie_contract` in `seturi-date.json`: a contract that gains
response schemas answers the main gap without contact. Otherwise ask the project for a response schema or an example for `company`, `financials` and `health`,
and mention the untranslated keys `ep.seap-cpv-top.description`, `ep.seap-cpv-analysis.description` and `cache.6h`.

- [ ] Use `https://demoanaf.ro/surse-date` as provider evidence. The page is collected (kind `metodologie`, 2026-10-24, sha256 `fcef2fc7f9b21d35…`), but only its
      POP107D line was used. It lists 12 sources with publisher, fields, refresh rate, the feature that uses each, and a "Sursă" link:
      ANAF contributor data and balance sheets (`webservicesp.anaf.ro`), ONRC via data.gov.ro, Ministerul Finanțelor (financial statements; local budget execution),
      INS (POP107D, FOM104D, FOM106E, RPL 2021), MIPE/AFIR, OpenStreetMap, BNR, VIES (European Commission), Monitorul Oficial Partea IV ("disponibilitate neverificată"), ANAF press releases.
      Re-point D132–D134 (ANAF, BNR, ONRC) to this page with exact fragments, and add proposals for the others. It also declares balance-sheet fields
      (cifră de afaceri, profit net, număr angajați): text evidence for `cifra-afaceri`, `profit-net`, `numar-salariati`. DemoANAF also offers an MCP connector (`/conector-mcp`).
- [ ] (paused) Response fields of DemoANAF: schema or example from the project.
- [ ] (paused) Review the 22 inputs that only the page documents and the 4 contract inputs that the page lacks (`comparatie_contract`).
- [ ] (paused) Group candidates: `cuis` (batch body, `string[]`) → `cui`; `year` → `perioada-de-referinta` (`dateFrom`/`dateTo` are filter bounds, keep them out);
      `metric (cifra|profit|angajati)` is a parameter value, not evidence for turnover, profit or employees.

### Related catalogues

- [ ] Look for correspondences with [ro-api-hub](https://github.com/Jamaalx/ro-api-hub) (catalogue of 125 Romanian public and private APIs).
      It is already a catalogue entry (`ro-api-hub`) whose `catalog.json` and `catalog.schema.json` are inventoried (53 fields). Next: map its services to
      catalogue entries and accepted providers (ANAF, BNR, ONRC, INS, AEP, SEAP), and its declared request fields to the variable groups. Correspondence only; no import.
- [ ] Idea, not decided: an MCP server over the same static JSON, so that AI agents can ask "which projects expose CUI?".
      No proxy is needed: a local stdio server (run with `uvx`) or a small hosted worker reads the published JSON. Tools such as `find_projects(variable, provider)`,
      `get_variable(id)` and `get_project(slug)`. It serves catalogue metadata and links to each source; it does not call the projects' APIs.
      Live calls would make it a proxy: keys (DemoANAF Pro, Registrul Firmelor), blocked plain requests (aerlive), rate limits, and load on small projects.
      A pass-through for a few keyless open APIs (for example ins.gov2.ro) could come later, with the project's consent. Depends on the static API below.
- [ ] Idea, not decided: a static, read-only JSON API over the inventory (variables, projects, sources, evidence), generated by `build.py` and described by an OpenAPI file.
      Preconditions: the owner review, stable group ids, and a state on every assertion so that proposals are never served as facts.
- [x] Extend the business dictionary with evidence-backed aliases, descriptions, roles, units, periods and geographic levels (milestone D).
      Identifiers, dimensions, measures and one derived output are separate categories. Review each proposed equivalence before treating it as a join key.
- [x] Record newly verified providers as proposals: 16 review items D147-D162 (producer, distributor and project author kept apart). No live relation changed.
- [ ] Review the 15 pending provider relations D132-D146 and the 16 new items D147-D162. Keep source organisations separate from target institutions.
- [x] Report coverage by entry, variable definition, type, unit and provider evidence (milestone E, v0.18.0): `observatii/inventare/acoperire.csv` and
      `docs/reports/inventory-expansion.md`, regenerated by `scripts/inventory_report.py`. Blockers and sampling limits are listed per entry.

## v2 migration completion — execution checklist (brief: `docs/briefs/v2-migration-completion.md`)

Branch `taxonomy-v2-migration`. Production stays on v1. No Google, workflow, deploy or release action.

- [x] A. Enrichment on explicit roots: `profile.py`, `search.py`, `review.py --data-dir`; profile merge; label hashes and coverage; copyright date.
- [x] B. Sheets and Form for v2: new tabs, `_sync` marker as the base, 3-way pull, blocking validation, offline round trips, Form plan and importer.
- [x] C. Frontend audit defects in `site-v2/`: failed data load, noscript, canonical, observed dates, methodology page.
- [x] D. Review queue: reconcile R001–R066 with the integration copy; `tehnic` state for non-editorial items; a recommendation on every open item.
- [x] E. CI: tests, v2 validation and preview build, JS syntax, browser checks, workflow lint; path filters for `site/`, `site-v2/`, workflows.
- [x] F. Cutover preparation: runbook, a dry-run check of the cutover, documentation of the v2 model.

### Owner decisions and external activation (nothing here was done; each needs the owner)

Editorial, in this order (runbook `docs/briefs/cutover-taxonomy-v2.md`):
- [x] Merge `taxonomy-v2-migration` into `main` and push (2026-10-22, owner instruction; this deploys the v1 site with the noscript block, the footer methodology link,
      and the `last_activity` correction: 2 `stale` and 19 `score` changes). Then push. Optional: bump `pages.yml` and the Sheets workflows' action versions after the first green `validate.yml`.
- [x] Detach the integration copy: the owner ran `--detach` on 2026-10-21 (recorded commit 97304fa); `integrare/pachet.json` committed on 2026-10-22.
- [x] Decide the 66 open review items (2026-10-22, owner delegated the decisions): 65 closed with their recommendations; C009 left the queue with `incentru`.
- [x] Moldova area ID `tara:MD` and vocabulary proposals (2026-10-22): accepted `tara:MD`, `tehnologie:retea-de-senzori`, `scop:sustenabilitate-presa`;
      deferred 6; rejected `regiune:europa-de-est`. `form.py --write-map` ran; `data/form-v2.json` did not change.
- [x] C013 `nu-astepta-supereroi`: set to `national` + `tara:RO` (2026-10-22).
- [ ] Write a tagline or description for the 12 live entries without text (see the audit item); decide whether that becomes a publication rule.
- [x] Accept the entries (`clasificare_stare=acceptat`). 2026-10-22: 121 accepted in bulk on the owner's instruction, not one by one. The owner gave up `incentru` (parked domain, no text, no evidence), so it left the catalogue. 140 entries, all accepted.
- [ ] Product: introduction text and audience, the rotating jokes, the sort options, and a curated launch date (all in the audit section).

External (Google, GitHub), after the editorial work:
- [ ] Sheets v1: allow Actions to create PRs; decide the `demoanaf` cell; run `sheets-push` with `force` once to create `_sync`. Do not require `validate / sheets-pull` in branch protection.
- [x] Sheets v2: tab `v2-intrari` (gid 541482181 in `setari.json`) holds the 140 entries; marker 3989209 (2026-10-22).
- [x] Form v2: option B chosen on 2026-10-22. The live Form keeps the v1 questions; an editor copies each proposal into `intrari.csv`. Open: implement `form.py --apply` for a v2 root, or edit the Form by hand (option A).
- [x] Cutover: applied by the owner on 2026-10-22, merged as pull request #4 (merge commit fda9545) and deployed. Post-deploy checks passed (see ACTIVITY). Rollback: revert the merge commit.
- [ ] Protect the v1 Sheet tabs `proiecte` and `orgs` (by hand in Google Sheets; runbook step 4).
- [ ] Rewrite the documents for v2 as the public model: the README section "Editing the data", the contributor routes in CONTRIBUTING.md (confirm the route: Form or issue, then an editor copies into `intrari.csv`), the v1 diagrams in ARCHITECTURE.md, and the "preview" wording in DATA-SCHEMA.md and the specification.

## mariuscomper.uk import (2026-10-21)

- [x] Add the 20 pages to `proiecte.csv` (v1), profile them, search them. 19 remain.
- [x] Classify the 19 entries in the v2 integration copy (2026-10-22, after the detach; accepted, confidence `medie`; profile and search rows copied into `observatii/`). Review the facets.
- [-] `tuneluri-feroviare`: dropped by the owner on 2026-10-22 (weak civic fit: a rail-engineering map, no public-interest question).
- [x] At the cutover, put the 19 entries' profile and search rows into `observatii/` (19 rows in `profil.csv`, 213 in `mentiuni.csv`). Done on 2026-10-22, after `--apply` dropped `--baseline`.
- [x] `sheets-pull`, then push, so the v1 tabs get the 19 rows (2026-10-22; see ACTIVITY).
- [ ] Review the 3 entries in `altele` (`ani-de-pensie`, `pensie-din-bursa`, `trei-din-patru`); v1 has no pensions or education domain.
- [ ] Review the kept search results for name collisions: `iqads.ro` (6) and `republica.ro` (3) name a "Marius Comper"; the law-coverage results of `codurbanism` discuss the law, not the page.
- [ ] Decide the `--prune-only` drift: on `HEAD` it changes `regula` on 53 rows and `mentions` on 10 other entries. The import reverted it; review it as a separate change.

## Taxonomy v2 — isolated proposal (spec: `docs/specs/taxonomy-v2.md`)

- [x] Copy all 122 entries into `data/taxonomy-v2/intrari.csv`, with separate subject, purpose, capability, format, technology, and geography facets.
- [x] Supply 125 defined concepts, including 13 local browsing subjects, and a complete crosswalk for the used v1 terms.
- [x] Preserve all eight original top-level data files as hashed snapshots. Keep working observation copies separate.
- [x] Verify 22 EuroVoc target identifiers and Romanian/English labels through the official endpoint. Leave semantic mappings proposed.
- [x] Preserve 86 source attributions without guessing their roles. Supply 66 specific review items and the initial assignment evidence.
- [x] Document the column contract, editing process, integration functions, migration order, and acceptance checks.
- [x] Validate the initial copy and JSON export. Run 12 focused integrity checks on temporary copies.
- [x] Add the Mermaid model overview and complete vocabulary diagrams, with an exporter that reads all 125 concepts.
- [x] Specify the visible filter labels, progressive disclosure, multi-select logic, counts, and grouping behaviour.
- [x] Record the agreed draft.2 revision: single-valued maturity with four stages, CSV-owned code lists/roles, and structural JSON rules.
- [x] Prepare the fresh-session implementation handoff and the automated classifier prompt with its JSON output schema.
- [x] Consolidate all 122 original entries into a single inference input CSV, without leaking the manual v2 classifications into the experiment.
- [x] Implement core handoff slice 1: upgrade the isolated package and validator to draft.2 without reclassifying entries.
- [x] Classify all 122 original entries and evaluate against the withheld draft. Preserve the sealed run in `data/taxonomy-v2/runs/2026-10-19-reasoned-evidence/`.
- [x] Resolve the evaluation's three semantic concerns in a separate integration copy (`data/taxonomy-v2/integrare/`, change log `modificari.csv`).
- [ ] Owner review of the integration queue: 66 open items (27 high priority: 26 R "description absent" + C009 `incentru`), each with a recommendation; 37 closed `tehnic`. Then accept entries one by one (122 are unaccepted). Publication gate: 149 errors on 2026-10-20.
- [x] Rewrite or close review items R001–R066 against the integration copy. Their texts describe the draft.1 manual proposal.
      Done 2026-10-20 (slice D): `integrare/reconciliere.csv`; 29 R open with current values, 37 items `tehnic`.
- [ ] Choose the ID style for proposed areas before accepting them (`tara:republica-moldova` now; existing countries use ISO codes, `tara:RO`).
      Recommendation (S001, V009, V010): `tara:MD` with `cod_iso_3166_1=MD`, like `tara:RO`. Owner decision.
- [ ] Implement an automated inference runner and no-call dry run if a later repeatable experiment needs them. This does not block the current preview.
- [x] Implement the v2 loaders, validator branch, build contract, and browser facets together. Keep the current data source as the default until cutover.
- [x] Verify the isolated preview: 40 unit tests (`scripts/test_taxonomy_v2.py`) and 63 browser checks (`scripts/check_preview.py`).
- [x] Run `scripts/test_taxonomy_v2.py` in `validate.yml`, with the CI slice. Include `site-v2/` changes in PR validation.
      Done 2026-10-20: `validate.yml` runs every `scripts/test_*.py` and the browser checks.
- [~] At the cutover, replace `site/app.js` with `site-v2/app.js`, merge `site-v2/v2.css` into `style.css`, and remove `site-v2/`.
      Prepared 2026-10-20: `scripts/cutover_v2.py --apply` does it; `--rehearse` checks it in CI.
- [~] Adapt enrichment, Sheets, Form, and CI to the accepted schema. Use separate v2 Sheet tabs during migration.
      Done 2026-10-20 for explicit v2 roots (slices A, B, E, F). Open: applying the v2 Form questions to the live Form.

The public site does not consume this package. `common.PUBLIC_ROOT` is `data/` (v1); the scripts read v2 only with `--data-dir` until `cutover_v2.py --apply`.

## Audit — 2026-10-19

- [~] `site/app.js`: a quick click on a choice just after opening a facet can close that facet again. The `toggle` event
      arrives after the re-render, so `closed` still lists the facet. `site-v2/app.js` reads the open state from the page first.
      Fixed in `site-v2/app.js`; production gets it with the cutover (`scripts/cutover_v2.py` replaces `site/app.js`).

- [x] Make Sheets validation a blocking check. `sheets-pull.yml` records both exit codes, but opens the PR even when either command fails.
      The workflow uses `GITHUB_TOKEN`; its PR does not start the normal validation workflow.
      Done 2026-10-20: the job fails after it opens the PR and sets the status `validate / sheets-pull` (slice B).
- [~] Add data-load error handling and a retry to `site/app.js`. An aborted `data.json` request leaves the results blank.
      Offer the static archives when JavaScript fails. The home page also has no main content without JavaScript.
      2026-10-20 (slice C): `site-v2/app.js` shows a message, a retry button and the archives; `site/index.html` has a `<noscript>` block.
      Production JS gets the retry with the cutover.
- [~] Repair dialog focus. Ctrl/Cmd+K can focus the background search while a dialog stays open.
      Shift+Tab from Close selects a hidden link inside the collapsed report panel; focus stays on Close.
      Changing a mobile filter rebuilds the sheet and drops focus to the body.
      `site-v2/app.js` fixes all three (v0.6.1, with browser checks); `site/app.js` keeps them until the cutover.
- [~] Separate observed dates from confirmed launch dates. `isLaunched` uses `since`, which comes from Wayback, repo creation, or TLS.
      Rename inferred badges or add a curated launch date. Do not treat the first observed trace as a confirmed launch.
      2026-10-20 (slice C): `site-v2/` says "prima urmă observată" and "apărut recent", with "nu este data lansării".
      Owner decision: a curated launch-date column. Recommendation: none until a "lansat" badge is wanted again; the observed wording is accurate.
- [x] Remove the future date from `last_activity`. A 2026 copyright footer produces `2026-12-31` during October.
      Give copyright evidence less weight than a dated content update.
      Done 2026-10-20 (slice A): a dated update wins; the copyright year is `<year>-01-01`, never after today.
- [x] Explain the status and ranking methodology. HTTP reachability does not confirm an operating service.
      A source-code link does not establish an open-source licence. The score favours age, page count, and visibility.
      Done 2026-10-20: `docs/METODOLOGIE.md` (Romanian), linked from the footer.
- [ ] Fill the 12 live entries with neither a tagline nor a description in the audit build.
      Validation passes with 28 warnings. Separate publication requirements from optional enrichment.
      Measured 2026-10-20 (12): reciclare-arad, centrul-pentru-cariere, ce-zice-legea, scoala-pentru-democratie, companii-publice-ro,
      data-expertforum, e-cutremur, observatori-votcorect, onorata-instanta, open-budget, rezultate-vot, sanatate-mintala.
      Owner: write the texts (editorial). In v2, the open high-priority R items ("descriere absentă") already block publication.
      Recommendation: make "a live entry has a tagline or a description" a publication rule of `--publication`; keep the rest as enrichment warnings.
- [x] Invalidate review labels when the input URL set or entry changes. `review.py` only detects the old format without `mentiuni_map`.
      Report label coverage: once any label exists for a slug, `reach_features` ignores its unlabelled mentions.
      Done 2026-10-20 (slice A): input hashes per answer; per-URL label join; coverage line in `review.py` and `build.py`.
- [~] Keep canonical and share metadata aligned with SPA navigation. Opening Factual directly, then closing it, leaves its canonical URL on the home view.
      Fixed in `site-v2/app.js` (slice C, with browser checks); production at the cutover.
- [ ] Clarify the primary audience and catalogue scope in the visible introduction. Review the rotating political jokes against that audience.
      Simplify the competing relevance sorts and explain the abbreviated date columns.
      2026-10-20: the date columns have tooltips in `site-v2/`. Owner decisions: the introduction text, the jokes, and the sorts
      (the owner's note under *Misc*: one "Relevanță" sort, remove "Active și relevante", add "Cele mai vechi").
- [x] Add focused regression checks for profile preservation, label invalidation, score dates, dialog focus, and failed data loads.
      Include site changes in PR validation; the current workflow filters only `data/**` and `scripts/**`.
      Done 2026-10-20: `scripts/test_enrichment.py`, `scripts/check_preview.py` (98 checks), `validate.yml` paths and jobs.

Existing items below also cover profile refresh data loss, Sheets merge conflicts, proposal intake, inactive discovery, and sitemap generation.

## Search → relevance (spec: `docs/specs/search-relevance.md`)

- [x] `scripts/search.py`: Serper + Brave, full results in `data/mentiuni.csv` (D1, D3, D4).
      First full run 2026-10-18: 3386 rows, ≈ $0.81.
- [x] Rule-based pruning with an `editor` override column (D5)
- [x] Remove `--search` / `--gdelt` from `profile.py`; drop the `gdelt` column (D1, D2)
- [~] `review.py`: label kept results; write `data/mentiuni_etichete.csv` (D6). Code and dry run
      done; not run against the API yet (next item)
- [x] `build.py`: reach features and new `reach` weights (D7)
- [~] Editor: prune `data/mentiuni.csv` (first pass 2026-10-18: Haiku + Opus set 2,194 cells; 1,149 rows still empty for the editor) before the first labelled review run (column `editor`;
      extend the rules in `search.py` from the top hosts, then `search.py --prune-only`)
- [ ] Run `review.py` against the API (needs `ANTHROPIC_API_KEY`; the key in
      `~/devbox/ePtm/puzzes/.env` is empty). Then check `build.py` output: until labels exist,
      `reach.indep` is the kept-host count and the score is provisional
- [x] `README.md` line 54 still lists `profile.py --search --gdelt --opr` (flags removed)
- [x] `declic`: `url` de-clic.ro is offline; the search finds the live site at declic.ro. Editor
      decides whether to change the url. The `url` is now declic.ro
- [x] `profile.py --force` replaces the whole profile row and drops `mentions`, `search_social`
      and `opr`. Run `search.py --prune-only` after it, or make `profile.py` keep these columns
      Done 2026-10-20: `common.merge_profile` keeps the columns of other stages (slice A).
- [ ] Name-collision noise (`465`, `the-sponge`, `declic`, author names such as "Gabriel Popa"):
      check what the labels fix; if too much remains, add per-entry `search_exclude` terms
- [ ] UI: show the reach features (independent mentions, news, latest mention) on the entry card
- [ ] Run Open PageRank (`--opr`, needs `OPR_API_KEY`, free signup)

## Google Sheets sync (brief: `docs/briefs/sheets-sync.md`)

- [x] `scripts/sheets.py`: `diff`, `pull`, `push [--since REF] [--force]` (D1–D4). Tested on two
      temporary tabs of the real spreadsheet; see `docs/ACTIVITY.md`.
- [x] Workflows `sheets-pull.yml` and `sheets-push.yml`, shared `concurrency` group (D5–D7).
      Not run on GitHub yet: the brief forbids triggering workflows.
- [x] README: section "Editing in Google Sheets" describes how it works now.
- [ ] Owner: turn on Settings → Actions → General → "Allow GitHub Actions to create and approve
      pull requests"; check the secret `GOOGLE_SA_KEY` and the variable `SHEET_ID`; then run
      `sheets-pull` by hand once.
- [ ] Owner decides on the real tab `proiecte`: it differs from the CSV in one cell
      (`demoanaf` / `descriere`: the Sheet lacks "Proiect independent." and the line breaks; checked
      2026-10-18). Keep it: `sheets.py pull`, review, commit. Drop it: `sheets.py push --force`.
      The first `push` to the real tabs is not done yet.
- [x] Trim the trailing space in `orgs.csv`, `descriere_scurta` of `code4ro` and `techsoup`. `pull`
      strips it (D2), so the next pull otherwise rewrites the file.
- [x] `pull` copies the Sheet over the CSVs with no base. A CSV edit on `main` that `sheets-push` has
      not written yet shows as a revert in the next pull request. Option: a 3-way merge with the last
      synced commit (needs a marker: a git tag or a cell in the Sheet).
      Done 2026-10-20: the Sheet's `_sync` tab names the last pushed commit; `pull` merges three ways and stops on a conflict (exit 3).
- [x] `push --since REF` stops with "row 1 differs" when the columns changed between REF and now.
      Run `push --force` once after a column change (README says so). Option: detect this case.
      Done 2026-10-20: `push` reads by column name and clears stale columns; `--force` is no longer needed after a column change.
- [x] GitHub keeps one pending run per concurrency group. If `sheets-push` runs are superseded, the
      next run's `before` is not the state the Sheet was synced from, and the check can give a false
      exit 3. Recovery: run `sheets-push` by hand with `since` or `force`.
      Done 2026-10-20: `sheets-push` uses the `_sync` marker, not `before`.
- [ ] The Sheet has a third tab, `propuneri` (Form responses). `sheets.py` ignores it. The
      "Propune un proiect" form is not wired to the pipeline.
- [x] `CLAUDE.md`: add `sheets.py` to *Commands*, the pipeline sketch and the *Deployment* section.

## Proposal Form (brief: `docs/briefs/form-generator.md`)

- [x] `scripts/form.py`: plans the 13 questions from `data/taxonomy.json`; default mode prints them and
      reads the Form; `--apply` replaces all items in one `forms.batchUpdate` (D1–D3). Tested read only
      on 2026-10-18; the owner ran `--apply` the same day.
- [x] Owner: read the dry run (`uv run scripts/form.py`), then run `--apply` once.
- [ ] After `--apply`: check row 1 of the tab `propuneri`. Before it, it holds `Timestamp` and
      `Untitled Question` (the Form's one default question). The deleted question may leave its column;
      delete that column by hand (0 responses).
- [ ] Importer for `propuneri`: map the answers to a `proiecte.csv` / `orgs.csv` row with `ANSWER_KEYS`
      in `form.py` (needs a `slug`; the editor accepts each row by hand, as for `review.py`).
- [x] Order the Form questions like the `proiecte` columns, so one paste moves a `propuneri` row to
      the tab `proiecte`: Ce propui? (`fel`), Nume, Pe scurt, Descriere, Adresa (URL), Alte linkuri,
      Domeniu, Tip, Acoperire, Oraș, Autor. Today "Adresa (URL)" comes before "Pe scurt". The first
      row pasted by hand (`registrul-firmelor`, 2026-10-18) has `descriere_scurta` and `descriere`
      swapped; it is not known whether the swap came from the Form or from the paste.
      Done for v2 2026-10-20: `form.py --data-dir` plans the questions in `intrari.csv` column order. The live v1 Form is unchanged.
- [ ] The Form's first question ("Ce propui?") offers only Proiect, Resursă and Organizație. It does not
      offer `articol`, `ghid`, `campanie` or `cercetare`. Decide whether to add them (`FEL_CHOICES` in
      `form.py`, then `form.py --apply`) or to let the editor set `fel` when copying a row.
- [x] Authors that look like a slug but have no row in `orgs.csv`: `gabriel-popa` (3 entries) and `gov2`
      (3 entries; the entry `gov2` is no longer in the Sheet). Add the rows to `orgs.csv`, or write the
      names in full. `validate.py` warns about each. The names are now written in full (Gabriel Popa, GOV2).
- [ ] Filter by `fel` in the "Resurse & liste" tab (article, guide, campaign, research). The label shows on
      each entry, but there is no facet yet.
- [ ] Owner: set `email` in `data/site.json`, or the report-a-problem panel has no e-mail option. Check that
      the Sheet's sharing lets the people you want edit it (or only comment); the panel links to its row.
- [ ] `sitemap.xml` and `robots.txt`, written by `build.py`, so that search engines find the
      `/<kind>/<slug>/` pages and the three archives. The home page lists the entries only through JavaScript
      (the footer links the archives).
- [ ] `site/404.html` for a removed slug: send `/<kind>/<old-slug>/` to `/?p=<old-slug>` or to the
      home page. Today a removed entry returns the GitHub Pages 404.
- [ ] The og images are WebP. Check a link preview on the networks that matter (Facebook, LinkedIn,
      Telegram, WhatsApp) once the pages are live.
- [x] `docs/DATA-SCHEMA.md` can drift from `scripts/common.py`. Add a check to `validate.py` (or CI) that
      every column in `PROIECTE_COLS`, `ORGS_COLS`, `PROFIL_COLS`, `MENTIUNI_COLS` and `ETICHETE_COLS` appears
      in that file.
      Done 2026-10-20: `scripts/test_docs.py` (also the v2 headers), run by `validate.yml`.
- [ ] The longest help text (Domeniu, 11 hints) has 772 characters. If the Forms API or the layout
      rejects it, set `HINT_MAX` in `form.py` to 0 to drop the hints from the help text.

## Link icons and GitHub stats (brief: `docs/briefs/link-icons-github-stats.md`)

- [x] Drawer: a link to a network shows its logo (inline SVG, Simple Icons, `currentColor`) with
      `aria-label` and `title` (D1, D2)
- [x] `profile.py` stores the favicon of each non-network link host in `site/img/linkicon/`; `build.py`
      adds `icon` to the link (D3). 12 hosts, 0 failed.
- [x] `profile.py`: the entry icon prefers a candidate of 64 px or more; header logo images are
      candidates (D4)
- [x] GitHub stats in `profile.py --extra` (6 new `profil.csv` columns) and the "Cod" row in the
      drawer (D5, D6). 19 repos.
- [ ] A logo that is an SVG is skipped: Pillow cannot decode it (factual.ro has an SVG logo and a
      32 px favicon). Option: rasterise it with Playwright in the browser pass.
- [x] `profile.py --only` / `--force` drops `cert_first` while crt.sh answers 502 (2026-10-18:
      factual, code4ro; restored later with `--extra --only`). `extras_one` keeps an old value only
      when the profile row survives.
      Done 2026-10-20: the merge keeps `cert_first` when the new fetch has none.
- [ ] `profile.py --extra` runs a GitHub search for every live entry without a repo, on every run
      (about 75 requests, about 3 minutes at the 30 per minute limit). Store the miss to skip it.
- [ ] A link host whose favicon fails is fetched again on every run (no stored miss). Today: 0 failures.
- [ ] Orphans: 23 files in `site/img/icon/` and 12 rows in `profil.csv` have no entry in the CSVs
      (deleted entries, e.g. `rescue-4x4`). Nothing shows them.
- [x] `CLAUDE.md` pipeline sketch names `site/img/{og,icon}/`; add `linkicon`.

## Site (from README *Backlog*)

- [ ] "Vezi și proiectele inactive (N)" link: at the end of each domain section (sort "Pe domenii"),
      or at the end of the list (other sorts). It opens a list of only `arhivat` / `offline` entries
      of that section or tab, for all three tabs (proiecte, resurse & liste, organizații). Today the
      only way in is the "Ascunde proiecte inactive" toggle (`ina=1`), which mixes them into the list.
      Open question: does the inactive-only list replace `ina=1`, or does it get its own URL value
      (e.g. `ina=doar`)?
- [x] Keyboard navigation: `j`/`k` or `←`/`→` step through results (and the open entry),
      `o` opens the entry's own site; key hints in the footer
- [x] Mark fresh projects: `nou` tag when `since` is under 183 days, plus a "Doar proiecte noi"
      toggle (`nou=1`)
- [x] Sort by age: "Cele mai noi" (`o=nou`), by `since`; entries without a date go last
- [x] Update logo: `site/img/logo.png` from `docs/reference/logo/civtech-ro-favicon-2.png`,
      resized to 180 px (apple-touch-icon size)
- [x] GitHub link (icon) in the header instead of "Despre", and in the footer
- [x] Self-host the fonts: `site/fonts/` (latin + latin-ext woff2, 150 KB). The site now loads
      no third-party resource.
- [x] Logo at 40/44 px (no `scale()`); title text with a tricolour sweep and seven swap effects
- [x] "Pe domenii" sorts each group by last sign of life (last update, or launch date if later)
- [x] "Lansat recent" tag (under 60 days), separate from "nou" (60–183 days)
- [x] Sort "Active și relevante" (`o=top`): `score × (0.5 + 0.5·e^(−days/365)) + 8` for a recent launch
- [ ] Move the "Active și relevante" formula into `build.py` once the reach labels exist, if it
      stays; tune the half-life and the bump on real use
- [-] "Remove catalog column": no such column in `proiecte.csv` or the UI. Owner dropped it
      on 2026-10-18.
- [ ] Bookmarks in the browser, with CSV export (site-only; README marks it "later")
- [ ] Wait for search → relevance: static page per project, more than one domain per
      entry, "Altele" domain, methodology text. Each one changes `build.py` or the score.

- [x] Show `arhivat` when the profiler says `offline` and the last Wayback capture is over a year old
      (`build.py` `status_of`). 7 entries switched on 2026-10-18.

- [ ] Profiler: a connection timeout gives `blocat` → "Neconfirmat", which the main list shows.
      Two such entries were dead (parlament-transparent, piata-de-spaga; set `stare=offline` by hand
      2026-10-18). Retry from a second network, or count repeated timeouts as `offline`.
- [~] CI: actions target Node.js 20 (deprecated); bump `actions/checkout` and the Pages actions.
      `validate.yml` uses checkout v7, setup-python v7, upload-artifact v7, setup-uv v10 (latest majors on 2026-10-19; not yet run on GitHub).
      `pages.yml` and the Sheets workflows still use v4/v5: bump them after the first green `validate.yml` run.

## Editorial checks

- [ ] Check doubtful GitHub matches (`rescue-4x4` is deleted): `harta-banilor-publici` → `initiativaromania/HBP-Android`,
      `harta-tv-locale` → `geospatialorg/geospatialorg.github.io`
- [ ] Decide `stare=arhivat` for sites up with no edit in 3+ years: monitor-social,
      calitate-aer-radauti, data-expertforum, onorata-instanta. (pmb-plus and median-research-centre are
      deleted; parlament-transparent has `stare=offline`.)

## Verified limits

- [-] Collect `harta-firmelor.ro` automatically (the site, `/date`, the eight CSV files, `api.harta-firmelor.ro`). Every automated request gets HTTP 429 from a Vercel Security Checkpoint (2026-10-24 and 2026-10-25),
      and its `llms.txt` says that automated mass extraction is not allowed (the terms of use and `robots.txt` protect the database). Do not pass the checkpoint with a headless browser.
      Use a copy that the owner saves from their browser (`--import-saved`), or the official API with a key that the project issues on request.
- [-] Read the script files of `demoanaf.ro/api-docs` for response fields. `ApiDocsPage-*.js` holds the same endpoint list as the page plus translation keys and no schema;
      `/en/api-docs` repeats the page. Measured 2026-10-25 with 3 requests; nothing to gain from more.
- [-] GDELT news counts. GDELT answered "please limit requests" at 12 s spacing, and the
      queries that passed returned 0, also for factual.ro. Dropped (spec D2).
- [-] ROTLD WHOIS for domain age. Their terms forbid automated queries.
- [-] Quoted phrases on Serper's free tier: the API rejects them with HTTP 400. Use Brave for
      phrase queries.
- [-] SerpApi as a provider: ~$25 per 1k queries, 25× Serper.
- [-] Format the cells as text before writing the values. A `values.update` with `RAW` resets the
      number format of the cells it writes (measured 2026-10-18). `sheets.py` writes first and
      formats after.
- [-] A scratch spreadsheet for tests. The service account gets 403 on `spreadsheets.create`. Tests
      used two temporary tabs (`zz-test-*`) of the real spreadsheet, deleted after each run.
- [-] URL validation on "Adresa (URL)" in the Form. The Forms REST API (v1 discovery document,
      checked 2026-10-18) has no text validation: `TextQuestion` has only `paragraph`. `validate.py`
      checks the URL when a person copies an answer to a CSV.
- [-] A dry run of `forms.batchUpdate`. The API has none. The body was checked offline against
      the discovery schema (a scratch check, not in the repo); the first real test is `--apply`
      (all or nothing, guarded by the revision ID).
- [-] Host rules alone against name collisions. Measured 2026-10-18: after all rules, generic
      news sites (digi24.ro, hotnews.ro, adevarul.ro) stay in 21–24 entries each, because the
      name or author query matches common words. Only the page text can decide; that is the LLM
      step.

---


## Misc / unfilled
- assign a resource to more than one domain (and more keywords per resource; the Tip filter is already multi-select)
- maybe an "Altele" domain for things that fit nowhere
- [x] ranking by popularity / relevance — `score` in `build.py`, "Relevanță" sort; reach signals being reworked (`docs/specs/search-relevance.md`)
- [x] sort by age — "Cele mai noi" sort, by `since`
- [x] RSS feed — `site/feed.xml` from `build.py`: 40 newest live projects by `since`
- [x] `site/llms.txt` from `build.py` (llmstxt.org): summary, data links, every entry linked to its page
- [x] update logo — `site/img/logo.png` from `civtech-ro-favicon-2.png` (180 px)
- [x] og image / description — `site/img/share.png` (1200×630), og/twitter tags in `index.html`
- [ ] initial ranking: by domain, then by relevance x last updated x age x novelty – we cam call this "relevanță". Remove active și relevante. Add "cele mai vechi"
- add manual ranking - recomandarea redacției?
- [x] mark fresh projects — `nou` tag (under 6 months) and "Doar proiecte noi" filter
- [x] navigate projects with keyboard, left/right, j/k, open original (`o`)
- [x] more links per resource, plus stats: social media, GitHub, search-engine result counts
- international mirror (projects, orgs, tools — seed: `data/international.csv`), shown contextually next to related Romanian resources
- "Propune un proiect", two ways in: a PR on GitHub, or a Google Form feeding a Google Sheet. Two-way sync via a GitHub workflow: (built 2026-10-18: see *Google Sheets sync*; the Form is not wired yet)
  - auth: Google service account, key stored as a GitHub Actions secret (or keyless via Workload Identity Federation); share only this one Sheet with the service account
  - Sheet → repo: new/changed rows become a PR, checked by `scripts/validate.py`; never commit straight to main
  - repo → Sheet: after merge, rewrite the mirror tabs from `proiecte.csv` / `orgs.csv` and mark proposals as accepted/rejected
  - runs on schedule / push to main only (secrets aren't available to PRs from forks)
- [x] hosting: GitHub Pages mirror, or host there with its own domain
- static HTML page per project at build time (own share preview, indexable)
- profiler: detect donation, terms, about/contact and data-access (download / API / MCP) pages from homepage links, feeding the same `links` roles
- write methodology? In Romanian. 
- later: allow bookmarks. saved in browser, but allow csv export.
