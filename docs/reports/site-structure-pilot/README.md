# Site structure pilot — 2026-10-30

Status: completed bounded investigation. All four profiles remain partial; the format remains provisional.
Spec: [site-structure-profiler.md](../../specs/site-structure-profiler.md).
Brief: [site-structure-pilot.md](../../briefs/site-structure-pilot.md).

## 1. Result

The pilot supports two proposed correspondences through observed CUI values.
It also records one relationship between a fiscal institution record and a territorial record.
No identity decision was accepted. [decisions.json](decisions.json) is empty.
The pilot did not build a general discovery engine, a skill or public profile pages.

| Project profile | Collections | Page patterns | API operations | Operations tested live | Record samples | Charged requests |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [Transparenta.eu](profiles/transparenta-eu.json) | 2 | 3 | 1 | 1 | 2 | 20 |
| [SICAP.ai](profiles/sicap-ai.json) | 4 | 2 | 4 | 0 | 0 | 5 |
| [Registrul firmelor](profiles/registrul-firmelor.json) | 1 | 2 | 2 | 0 | 2 | 7 |
| [România Transparentă](profiles/romania-transparenta.json) | 7 | 12 | 9 | 4 | 3 | 12 |
| Total | 14 | 19 | 16 | 5 | 7 | 44 |

The five tested operations produced six successful API responses: two GraphQL samples and four REST samples.
Each REST listing had one page. No listing exceeded the two-page limit.
There were 39 successful HTTP responses, five DNS failures and one policy skip.
The 44 charged requests include all five failed attempts, conservatively charged before dispatch.
There were zero redirects, browser requests and search queries.
There were zero requests to forbidden hosts. All five SICAP requests went to GitHub.

The request log has 45 rows, including the unsent SICAP policy skip.
It records UTC times on 2026-10-29, which was 2026-10-30 in Europe/Bucharest.
Five initial attempts failed under the sandbox. The approved retries succeeded outside it.
No retry, failure or policy skip was converted into evidence that an endpoint is absent.

## 2. Record connections

See [correspondences.json](correspondences.json) for keys, typed identifiers and supporting evidence.

| Subject | Projects | Basis | State |
| --- | --- | --- | --- |
| Ministerul Afacerilor Externe | Transparenta.eu ↔ România Transparentă | Both expose self CUI `4266863`; institution names and subject types agree. | Proposed |
| A.D.P. BÂRCA S.R.L. | România Transparentă ↔ Registrul firmelor | Both expose self CUI `43721310`; company names and subject types agree. | Proposed |

The evidence is [the MAE GraphQL response](evidence/transparenta-eu-graphql-mae.txt),
[the central-institution response](evidence/romania-transparenta-central-response.txt),
[the company response](evidence/romania-transparenta-company-response.txt)
and [the company page extract](evidence/registrul-firmelor-adp-page.txt).
Matching CUI values establish a candidate connection; they do not establish historical identity through reorganisations.
The observation dates are known. Legal validity periods remain unknown.

Transparenta.eu associates institution CUI `4267117` with territory SIRUTA `179132`.
România Transparentă exposes the same SIRUTA in its UAT record.
The Transparenta.eu profile records `associated_territory` between those records.
It does not assert that the fiscal institution and the territory are the same entity.
The UAT response has `cui_primarie: null`, so that response alone cannot supply a fiscal mapping.

Another useful identifier is EUID `ROONRC.J16/419/2021`, observed alongside CUI `43721310` on the company page.
It is retained as a second typed identifier, without assuming that registration history is one record per company.

## 3. Project findings and limits

### Transparenta.eu

Current `llms.txt` explicitly declares `/entities/{cui}`.
The sitemap lists 13 top-level pages and no entity detail pages.
A sitemap-only profiler would miss the principal entity route.
The two checked entity pages identify București and MAE in their page metadata.

The production page declares `VITE_API_URL=https://api.transparenta.eu`.
Pinned client source appends `/graphql` and implements POST queries with optional bearer authentication.
The two read queries succeeded without credentials.
The sampled operation returns self CUI and a related territory's SIRUTA.
For MAE, the territory is Sectorul 1; it must not be interpreted as the ministry's own identifier.
Only the API host configuration was retained from the page's runtime settings.
Analytics keys and unrelated settings were excluded from the evidence.

Client source revision: `8c6b501276652664b08f4d5c77c5be67ecc5c1e1`.
The production response was checked independently. The source revision does not certify every deployed route.
Unperformed checks: entity list/search API, API pagination, exports, PNRR record identities, browser interaction and domain search.
PNRR remains a documented collection without sampled project records.

### SICAP.ai

The repository's existing policy excludes `sicap.ai` and all its subdomains.
The profile uses the owner-saved API contract and pinned public source.
No live record, page response or deployed API operation was sampled.

Source revision: `6697c8068692872d665d6bc7896ade159eb60e16`.
Its route files establish `/autoritate/{nationalId}` and `/firma/{nationalId}`.
Query source connects `nationalId` with fiscal-number fields.
It also declares optional local `entityId` fields. Their namespaces are preserved without inventing example values.
The source's sample `nationalId: "666"` is a build fixture, not a real entity observation.

The saved contract, version `0.44.0`, documents 15 paths; this pilot profiles four identity-relevant operations.
They cover authority contracts, contract detail and fiscal-identifier existence.
Contract IDs need both procurement source and ID. Bare numeric IDs are insufficient.
Buyer and supplier fiscal numbers have separate roles.
The existence operation can find either role; its primary supplier grouping does not restrict its scope.

The contract declares `bearerAuth` and key acquisition documentation.
It lacks an OpenAPI security requirement on the selected operations.
The profile records the documented key scheme and leaves runtime enforcement untested.
The owner saved the contract on 2026-10-27 at 21:24 +02:00; pilot import time is recorded separately.

The retained ONRC source states that one CUI can have several registrations.
It declares a separate CUI/year financial record shape.
These are source declarations, not observed correspondences between live records.
Unperformed checks: all deployed pages and APIs, live local-ID mappings, sitemaps, browser interaction and domain search.

### Registrul firmelor

Current `llms.txt` declares `/firma/<CUI>` and explicitly excludes the `RO` prefix from the URL input.
Both sampled detail pages returned company identity, not a generic HTTP 200 shell.
The profile preserves CUI and an observed EUID.
The home page's GET form declares the query parameter `q` for name/CUI search.
Its execution and search pagination were not sampled.

API documentation declares `/api/v1/firma/{cui}` and `/api/v1/cauta?q={q}` with an `x-api-key` header.
`robots.txt` disallows `/api/v1/` and `/v1/`.
The pilot records the documented operations without requesting either path or obtaining a key.
The sitemap is an index; no company sitemap shard was fetched.
Unperformed checks: sitemap shards, API responses, API pagination, search results, browser interaction and domain search.
No conclusion about endpoint availability follows from these skips.

### România Transparentă

Current documentation declares different collections for central institutions, public companies, UATs, universities, hospitals, aid and debtors.
CUI covers several legal-subject collections. SIRUTA identifies the UAT collection.
The profile retains 12 page patterns, including the CUI/name debtor search.
It does not classify that mixed search input as a CUI-only field.

The current OpenAPI document lists 67 paths. This pilot profiles nine selected operations.
Four operations were tested: company list, company detail, UAT list and central-institution data.
The API returns provenance separately from records and pagination.
No page-two request was needed to test the response shape; archive completeness remains unknown.
Two child sitemaps were fetched after the index.
At most the first 100 detail URLs of each child were inspected; three examples were retained per child.

The central-institution sample includes a financial-ordering identifier distinct from the institution CUI.
It was not normalized into CUI or promoted to a shared namespace.
The company response links purchases and awarded contracts separately, reinforcing the buyer/supplier distinction.
Unperformed checks: the five other profiled API operations, other sitemap branches, live hospital/university/aid/debtor records,
page-two pagination, financial-code interpretation, browser interaction and domain search.

## 4. Evidence and executable checks

There are 47 evidence records with tracked extracts, hashes and locators.
Extracts normalize trailing whitespace and record that transformation.
Raw HTTP bodies remain local; they are not required by the offline checker.
`source_sha256` anchors the original body when available. The checker verifies the tracked artifact hash, not an absent original body.
Retained inventory references resolve to source IDs and source URLs in tracked metadata.
Owner-saved evidence retains its save time; repository evidence retains the commit.
No private-person record values or credentials were copied into the pilot evidence.

Run from the repository root:

```sh
python3 scripts/check_structure_pilot.py
python3 -m unittest discover -s scripts -p 'test_structure_pilot.py' -v
python3 scripts/validate.py
```

To check preservation across two saved pilot directories:

```sh
python3 scripts/check_structure_pilot.py --root /path/to/current --previous /path/to/previous
```

The comparison checks findings, immutable evidence and editorial decisions.
A failed refresh must retain prior evidence and mark its applicability stale or unknown.
The checker does not implement fetching or merging.
It checks artifact structure and evidence locations, not the truth of a business interpretation.
Its identity checks require equal subject types; broader compatibility rules remain future work.
Text intervals and JSON pointers are the pilot's supported artifact locators.
HTML selectors and repository paths can be retained as `source_locator` descriptions.
A future engine must add executable source-locator checks for other formats when needed.

| Check | Result |
| --- | --- |
| SP01-four-profiles | Pass: four partial profiles with explicit limits. |
| SP02-pattern-basis | Pass: declarations support variable templates; observed fixed paths are marked exact. |
| SP03-api-evidence | Pass: 16 operations distinguish documentation from live tests. Mutating POSTs fail offline checks. |
| SP04-identifier-role | Pass: self, buyer, supplier, registration and territory roles stay separate. |
| SP05-local-to-shared | Pass through the permitted limitation: SICAP declares local IDs, but no live local-ID mapping was available. A synthetic fixture tests the format. |
| SP06-correspondence | Pass: two real CUI pairs are proposed; no editorial decision is made. |
| SP07-no-false-identity | Pass: negative fixtures cover names, equal local values, incompatible subjects and generated acceptance. |
| SP08-policy-and-budget | Pass: 44 charged requests, zero forbidden-host requests, zero browser/search requests. |
| SP09-evidence-integrity | Pass: hashes, excerpts, namespaces, keys and inventory references resolve offline. |
| SP10-refresh-preservation | Pass on synthetic snapshots: earlier findings, evidence and decisions survive. No live refresh engine is implemented. |

Validation: 40 focused unit tests pass. `validate.py` reports zero errors and warnings.
`build.py` succeeds with 141 public entries.
Its output changed timestamps and the time-dependent `amplify` score (68 → 69).
Those generated changes are excluded from this research deliverable.
No collector, dependency, catalogue source, reviewed concept or public-build implementation changed.

## 5. Schema gaps and next engine scope

No invariant change was needed for the pilot.
The following details need review before the format becomes a stable engine contract:

1. An API operation can serve several collections or subject roles, as SICAP's existence operation does.
2. Source-declared local IDs need a representation distinct from sampled ID mappings.
3. Registration history needs cardinality and time scope; CUI is not a unique registration-record key.
4. Location, administration and identity need separate relation names. A SIRUTA field alone cannot choose among them.
5. API security declarations can be incomplete. Documented schemes and observed enforcement need separate fields.
6. Field names can refer to another issuer's code, as central financial-ordering identifiers do. Keep them uninterpreted until documented.

The first engine should reuse retained evidence, inspect explicit links, parse bounded sitemap samples and register documented API operations.
It should emit extraction candidates and a check plan, then run bounded read tests where access permits.
It must keep original identifier values, namespaced local IDs, subject roles and partial outcomes.
Keep the correspondence review interface and public presentation as separate work.
A skill should follow a tested engine workflow; it should not duplicate the transport or validators.
