# Spec: site structure and entity correspondences

Date: 2026-10-30. Status: accepted direction; schema provisional until the pilot review.
Pilot: [site-structure-pilot.md](../briefs/site-structure-pilot.md).
This document specifies future work. No structure profiler or correspondence service is implemented by this change.
The [completed pilot](../reports/site-structure-pilot/README.md) supplies observations and an offline checker.
The shared engine and stable schema remain future work.

## 1. Goal and terms

Find records in different projects that describe the same real-world entity.
Collect their page patterns, API operations, identifiers and evidence.
CUI is one shared identifier. Preserve site-specific identifiers when no shared identifier is available.

| Term | Meaning |
| --- | --- |
| Project | A catalogue entry, identified by its existing slug. |
| Collection | A project's set of records with a common meaning, such as companies or contracts. |
| Record | One representation within one collection. |
| Entity | The real-world organisation, institution, place or other subject that a record describes. |
| Identifier namespace | The issuer and scope within which an identifier has meaning. |
| Structure profile | Observed collections, access paths, identifier rules and relationships for one project. |
| Correspondence | An evidenced assertion that two records describe the same entity. |

An organisation can appear as a buyer in one collection and a supplier in another.
Those roles do not create two organisations. A contract that names both is a separate entity.
Sharing a domain, name, operator or data provider does not establish identity.

## 2. Decisions

**D1. Keep structure profiling separate from site health.**
The future entry point is `scripts/profile_structure.py`.
It must not write `profil.csv` or change health scores.
Rationale: structure has different evidence, outputs and refresh rules.
Cost of extending `profile.py`: health refreshes would also change identity findings.

**D2. Use profiles and a shared engine.**
Store site-specific declarations as data. Put reusable discovery and validation in shared code.
Use a skill later for investigation, uncertain findings and maintenance.
Rationale: the four-site pilot must test the workflow before a skill fixes its instructions.
Cost: the pilot needs manual investigation before general automation.

**D3. Separate observations from editorial decisions.**
Discovery can propose patterns and correspondences. It cannot accept an identity match for the owner.
Keep decisions in a separate file keyed by stable assertion IDs.
Rationale: refreshes must preserve editorial work.
Cost: consumers must combine observations with decisions.

**D4. Separate access rules from record correspondences.**
A template can generate a candidate URL. It does not prove that a record exists for every identifier.
A correspondence needs evidence about the records themselves.
Rationale: projects cover different populations and periods.
Cost: some useful links remain candidates until checked.

**D5. Reuse evidence without changing the variable inventory.**
Reference retained documentation, inventory sources, fields and reviewed concept groups where applicable.
The group `cui` can support a semantic interpretation. It does not establish a match between individual records.
Do not write `intrari.csv`, `relatii.csv`, review queues or concept decisions during structure discovery.
Rationale: catalogue relations describe projects and providers; record identity needs its own model.

## 3. Provisional output contract

The pilot writes under `docs/reports/site-structure-pilot/`.
It keeps UTF-8 JSON with English keys, Romanian display labels and `schema_version: 1`.
These outputs are research observations, not public-build inputs.

| File | Contents |
| --- | --- |
| `profiles/<slug>.json` | One structure profile per pilot project. |
| `correspondences.json` | Record references and proposed identity assertions. Empty assertions are valid. |
| `decisions.json` | Editorial decisions, initially an empty list. Discovery never edits existing decisions. |
| `requests.jsonl` | Request metadata and policy skips. No credentials or response bodies. |
| `README.md` | Comparison, measurements, gaps and recommendations. |

Retain small, redacted evidence extracts under `evidence/` when they contain no private-person values.
Each extract must support a precise assertion. Large bodies and browser traces stay in a local scratch directory.
Record a local-only snapshot as such. A reviewer must not need a live request to inspect the tracked assertion's basis.
Existing tracked excerpts can supply that basis without a second copy.

Each profile contains these fields:

| Field | Required content |
| --- | --- |
| `schema_version`, `project_slug`, `input_url` | Format version, catalogue key and requested project URL. |
| `attempts` | Stable attempt IDs, UTC times, method, tool version, budget, usage, outcome and incomplete reasons. |
| `collections` | Stable local keys, labels, entity types, coverage and evidence references. Unknown coverage stays explicit. |
| `namespaces` | Namespace keys, issuer, scope, normalization rule and its evidence. |
| `patterns` | Stable keys, collection, kind, URL template, variables, extraction rule, examples and evidence. |
| `operations` | API operations, each linked to its collection and evidence. |
| `identifier_rules` | Namespace, extraction location, subject role, normalization and evidence. |
| `relationships` | Directed record references with a named relation, such as buyer or supplier. |
| `evidence` | Evidence records referenced by the other objects. |
| `checks` | Planned checks, outcomes, reasons and attempt references. |

An evidence record has a stable `id`, source URL or repository path, acquisition method and UTC observation time.
It records the source revision or sanitized snapshot SHA-256, artifact path, locator and supporting excerpt.
Locators are JSON pointers, line intervals, HTML selectors or text intervals, as appropriate.
Owner-saved evidence keeps its supplied save time and a separate import time.
Repository evidence records the commit. Historical evidence never implies a live verification today.

Use explicit, stable keys within a project. Never derive identity from array positions or display labels.
Record keys combine project, collection and the record's local namespace/value.
Use a canonical URL only when no local identifier is available. Preserve it when redirects appear later.
An assertion ID hashes its kind and sorted record keys, excluding timestamps, evidence and decisions.
Refreshing evidence must not change the assertion ID.

### 3.1 URL patterns

Pattern kinds are `listing`, `search`, `detail`, `pagination` and `download`.
Record every variable's name, location, namespace when known, and percent-encoding rule.
Keep path variables separate from query parameters and fragments.
Retain meaningful parameters. Remove tracking parameters only with an explicit rule.
Keep project scope distinct from host scope on shared domains.

An inferred template needs at least two distinct examples and a common structure.
One example can establish an observed URL, but cannot alone establish a template.
An explicit route definition or documented template can establish a declared pattern without two live examples.
Confirm identifier meaning independently. Numeric shape and a CUI checksum are insufficient semantic evidence.
An HTTP 200 alone is insufficient evidence of a detail record: check content and the identifier.

### 3.2 API operations

Each operation records:

- HTTP method and URL template; GraphQL operations also record their operation name and query shape.
- Purpose: `list`, `search`, `detail`, `schema` or `download`.
- Collection, input variables, parameter locations and response paths for records and identifiers.
- Pagination mechanism, any observed totals, and the limits actually tested.
- Authentication: `none`, `key`, `session`, `oauth` or `unknown`.
- Required header names and content types, without credential or session values.
- Basis: `documented`, `observed` or `tested`, with evidence for each applicable basis.
- Last test outcome and time, separately from documentation dates.
- Links to related page patterns when the evidence establishes that association.

A browser-observed internal endpoint is not automatically a supported public API.
A documented authenticated endpoint remains useful even when no test is possible.
Test only read operations. A POST search or GraphQL query needs evidence that it only reads data.
Never issue mutations or submit forms that change state.

### 3.3 Identifiers and correspondences

Use a shared namespace such as `ro:cui` only when its meaning is evidenced.
Use local namespaces such as `<project_slug>:<collection>:id` for site-specific identifiers.
Preserve identifier values as strings and retain their original form.
Do not remove leading zeroes, prefixes or punctuation without a documented normalization rule.
A prefixed VAT number is not silently interchangeable with CUI.

Every identifier rule specifies its subject role: `self`, `buyer`, `supplier`, `parent` or an explicit other role.
A JSON pointer to a supplier CUI identifies the supplier, not the enclosing contract.
Store related entities as distinct record references.
Represent composite identifiers as named components with namespaces, never as ambiguous concatenated strings.

The pilot stores a bounded sample of record references, not an entity database.
A reference records project, collection, local key, page/API locators, typed identifiers and evidence.
A correspondence contains `id`, `kind: same_entity`, two record keys, basis, evidence references and limitations.
Basis is `shared_identifier`, `explicit_mapping`, `explicit_link` or `name_candidate`.
A local ID and CUI in one self record can establish a namespace mapping for that record.
A name match remains a candidate. An explicit link needs evidence that it points to the same subject.

Matching shared identifiers requires compatible subjects, namespace meanings and known time scope.
Expose conflicts, including one local ID associated with different CUIs. Do not resolve them automatically.
Branches, parent organisations and reorganised institutions may require relationships rather than identity assertions.
Missing dates mean unknown temporal validity. Keep observation time separate from the entity's validity period.

Decisions contain `assertion_id`, `state`, `note` and `decided_at`.
States are `accepted`, `rejected` and `deferred`; a missing decision means proposed.
Only an explicit owner decision changes these states.
Keep evidence that an assertion supersedes or contradicts. Do not build transitive entity clusters in the pilot.

## 4. Discovery and access

Start from retained evidence, then inspect these sources within a declared budget:

1. Project page, navigation, search forms, structured data and internal links.
2. `robots.txt`, linked sitemap indexes and bounded sitemap samples.
3. Project-scoped and host-scoped `llms.txt`, documentation and linked API contracts.
4. Public source code at a recorded revision, when linked or explicitly supplied.
5. Bounded domain-search results for missing routes.
6. Browser diagnosis for unresolved navigation or API calls.

Continue across complementary sources after finding a working API.
Sample different collections and branches before spending the budget on repeated URLs.
Do not recursively crawl all records or guess numeric identifiers.
Search results are dated leads. They do not prove live availability, identifier meaning or complete coverage.
Existing mention pruning excludes own-domain results; do not reuse that filter for structure discovery.
Do not write structure queries into `mentiuni.csv` or change mention scores.

Call `common.forbidden(url)` before every request and redirect hop.
The restriction also covers browser subresources and API hosts.
A browser session is permitted only when its requests can enforce the restriction.
Import saved evidence or inspect a public repository for blocked projects.
Stop requests to a host on 401, 403, 429, a challenge or an explicit collection prohibition.
Record the reason. Do not switch clients, hosts or credentials to evade the restriction.
Do not change the blocklist as part of the pilot.

Count redirects, retries and browser requests within the budget.
Record status, content type, truncation, discovery origin and request time.
Keep secrets out of logs, templates, examples and snapshots.
Apply existing private-person handling when evidence contains records about private persons.
The pilot's entity samples concern organisations and institutions.

## 5. Refresh and uncertainty

Attempt outcomes are `observed`, `partial`, `blocked` or `error`.
`observed` means every planned check has a definite outcome within this bounded pass.
It never means that every route on the site was found.
Check outcomes are `observed`, `not_found`, `invalid`, `blocked`, `error`, `unchecked` or `skipped`.
A policy skip records `colectare-interzisa` as its reason, never as an error or an offline site.
Budget exhaustion leaves checks `unchecked` and the attempt `partial`.
An absent sitemap says nothing about the existence of unlisted routes.

Keep acquisition state, assertion basis and editorial state as separate fields.
Retain earlier useful evidence after a failed refresh. Mark its current applicability as stale or unknown.
Record both the latest attempt and the last supporting observation.
A smaller budget cannot silently delete patterns, endpoints, correspondences or decisions.

## 6. Delivery boundaries

First deliver the pilot profiles and an offline checker for their provisional contract.
Use the pilot report to identify schema gaps before implementing the shared discovery engine.
Update this spec with evidence when a pilot finding requires a contract change.
Keep the contract provisional until that review is complete.

The later engine must accept explicit catalogue slugs and an isolated output directory.
It must support importing saved evidence, offline validation and bounded refreshes.
The pilot does not require that engine, a new dependency, a skill, public pages or scheduled collection.
Bulk entity harvesting, fuzzy resolution and transitive merging are later work.

## 7. Design sources

The reviewed local workflows supplied these design choices:

- `haplea-sport/.claude/commands/new-source.md`: structured-source discovery and sample validation.
- `haplea-trips/.claude/commands/new-site.md`: recipes consumed by a shared engine.
- `midas-cc/.claude/commands/new-shop.md`: API discovery during search, filtering and navigation.
- `stiri/.claude/commands/new-source.md` and `docs/site-profiler.md`: scope, dated evidence, budgets and stale observations.

These paths are relative to their repositories under `~/devbox/scraping/` or `~/devbox/gov2/`.
They are design references, not runtime dependencies or delegated instructions.
