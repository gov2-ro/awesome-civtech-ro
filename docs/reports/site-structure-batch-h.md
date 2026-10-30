# igov enrichment and five more site profiles — 2026-10-30

igov was already covered by two company references and their local-ID/CUI mappings.
This batch expands its structure profile and verifies its current public organization catalogue.
It also adds Monitor SAFE, Achiziții directe TI 2026, Onorată Instanță, Biografia localității and A Făcut.

[Review packet](site-structure-batch-h/review.json) · [Request journal](site-structure-batch-h/requests.jsonl) · [Preview guide](../STRUCTURE-PREVIEW.md)

## Coverage

| Project | Collections | URL patterns | API/data operations | Record references |
| --- | ---: | ---: | ---: | ---: |
| igov, after enrichment | 8 | 9 | 9 | 5 |
| Monitor SAFE | 3 | 4 | 0 | 3 |
| Achiziții directe TI 2026 | 1 | 2 | 0 | 3 |
| Onorată Instanță | 2 | 3 | 0 | 3 |
| Biografia localității | 2 | 4 | 0 | 3 |
| A Făcut | 4 | 4 | 0 | 0 |

The batch adds nineteen collections, 26 patterns, nine operations and fifteen record references.
The twenty-project set has 99 evidence records, 73 collections, 80 patterns, 96 operations and 64 record references.
It has 58 identifier rules and eleven explicit relationships.
No sample extraction failed; no identifier conflict was found.
Missing coverage remains explicit below, including the aggregate-only A Făcut profile.

## igov: what was covered and what changed

The original recipe retained Active Conexe and Antibiotice from the governance report observed on 2026-10-27.
Their local IDs remain `inst_cui-31029694_fbc8ca0d0e` and `inst_cui-1973096_89f11b5bc5`.
Both records independently contain CUI fields. The importer never parses those CUIs from the opaque ID strings.
The original record keys and owner decisions are preserved.

The same retained report contains a complete company row at index 94 for CUI `8359779`.
Its local ID is `inst_cui-8359779_f989662eb7`.
This identifies the parent company already referenced separately by Companii Publice.
It does not identify that company's child as the same legal subject.
Only corporate ID, CUI and company name were copied; people, appointments and financial values were excluded.

The observed institutions page loads a public organization-directory module.
That module establishes `/organizatii`, `/organizatii/{organization_id}` and their GET APIs.
Exact CUI searches and two detail responses verified these mappings:

| CUI | Canonical API ID | Public profile |
| --- | --- | --- |
| `1973096` | `cui-1973096` | [Antibiotice](https://igov.ro/organizatii/cui-1973096) |
| `31029694` | `cui-31029694` | [Active Conexe](https://igov.ro/organizatii/cui-31029694) |

The response exposes `id` and `cui` as separate fields.
Its `registry_id` is null for both samples; no direct legacy-ID mapping was inferred from that field.
The canonical API IDs use a separate, non-shared namespace.
They remain separate record references from the historical governance nodes.
Their independently observed CUIs connect those representations to other projects.

The profile now includes institution, project and organization sections, plus four governance tabs.
It records channels, institutions, public-flow discovery, inspiration, organization lookup and three report-data operations.
Two legacy API observations remain historical; four public organization requests were observed in this batch.
The other source-code declarations were not invoked.
Account/session and request-submission operations were excluded from this data-profiling scope.

## Five newly enrolled sites

### Monitor SAFE

The existing literal-only reader extracted two `C` contract rows and one `NS` uncontracted proposal from the retained registry.
Each retains only a local slug, title and buyer label.
No CUI was assigned from a corporate name, website or a similarly named shipyard.

The script declares fragment routing through each row's slug.
Contract and proposal bindings use distinct typed placeholders for that shared fragment grammar.
Both survive the store's URL-based pattern identity.
The proposal retains `funding_project` with proposal grain; it is not labelled a signed contract.
No real API was established; the data are embedded literals.

### Achiziții directe TI 2026

Three retained CSV rows provide explicit direct-purchase number strings.
The recipe keeps those in a local namespace and preserves the original source-row references in evidence.
Buyer and supplier names do not become fiscal identifiers.
No company correspondence or source-independent SICAP namespace is inferred.
The dashboard and CSV export are established; a per-purchase frontend URL remains unknown.

### Onorată Instanță

The pinned 2014 table provides three court name/code references.
Its first descriptive row is column metadata, not an institution.
Only name and code were copied, without court metrics, contacts or person-related values.
The source's court-code strings remain local; they are not asserted as CUI or national portal numeric IDs.
The court listing and historical data locator are known; per-court frontend routes remain unknown.

### Biografia localității

The observed locality index explicitly names `siruta` and `slug` in its positional header.
Three complete municipal rows identify Alba Iulia, Cluj-Napoca and București.
The extract omits population and publication metrics.
The script independently maps each position and builds the locality-page route.

The recipe keeps the official SIRUTA value and the local slug as separate identifiers.
It does not extract SIRUTA from the digits inside a slug.
The sampled municipality routes use `/{slug}/`; metropolitan type `z` has a separate route and was not sampled.

### A Făcut

Four retained pages establish water/sewerage, roads, county summaries and gas sections.
Their titles and table headers describe aggregate progress and funding data.
Those observations do not establish stable entity identifiers.
The profile therefore has sections and document evidence, without invented entity samples or API claims.

## Twenty new direct identity proposals

| Source of new representation | Identifier | New pairs |
| --- | --- | ---: |
| igov canonical organization catalogue | Antibiotice CUI `1973096` | 5 |
| igov canonical organization catalogue | Active Conexe CUI `31029694` | 4 |
| igov retained parent-company reference | CUI `8359779` | 1 |
| Biografia localității | București SIRUTA `179132` | 5 |
| Biografia localității | Alba Iulia SIRUTA `1017` | 2 |
| Biografia localității | Cluj-Napoca SIRUTA `54975` | 3 |

These are direct pairs between record references, not unique-person counts or transitive entity clusters.
The two igov representations of each company remain distinct; no within-project merge is inferred.
The previous 39 proposals and these twenty remain proposed, giving 59 pending pairs.
Four previous owner decisions remain accepted.
Observation times remain explicit; legal validity periods are unknown.

## Measurement and checks

The offline pass imported eighteen retained documentation observations for six selected projects and made zero requests.
The live work sent 25 GET requests, all HTTP 200, including five robots checks.
Only igov and the scoped Biografia localității pages/assets were visited.
No forbidden host, paid API, paid search, browser source crawl, account operation or owner contact was used.
The request journal retains every charged request.

Eight offline checks pass on Python 3.12.
The full suite passes 1,273 tests with eight skips.
They cover legacy record preservation, canonical namespaces, fragment bindings, purchase IDs, court metadata, independent SIRUTA fields and request restrictions.
All 46 browser checks pass, including igov's canonical company URL and the proposal label.
The original pilot, structure integrity, repository validation and public build pass.
The public build changed only its generated timestamp; that drift is excluded.
The recipes replay from tracked evidence alone.

The preview remains local. No identity decision or catalogue classification changed.
Open [igov's site profile](http://127.0.0.1:8784/proiect/igov/) or the [Antibiotice lookup](http://127.0.0.1:8784/entitati/?namespace=ro:cui&value=1973096).
