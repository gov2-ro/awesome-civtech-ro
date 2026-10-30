# Institutions, territories and local identifiers — 2026-10-30

Status: five more catalogue sites profiled. Thirteen new identity pairs remain proposed.
The preceding commit `8e0febe` and tag `v0.50.0` were pushed before this batch.
GitHub [validation](https://github.com/gov2-ro/awesome-civtech-ro/actions/runs/41088799424) and [Pages](https://github.com/gov2-ro/awesome-civtech-ro/actions/runs/41088799465) both succeeded.

[Review packet](site-structure-batch-g/review.json) · [Request journal](site-structure-batch-g/requests.jsonl) · [Preview guide](../STRUCTURE-PREVIEW.md)

## Delivered coverage

| Project | Collections | URL patterns | API/data operations | Observed subjects |
| --- | ---: | ---: | ---: | ---: |
| Execuții Bugetare | 3 | 2 | 3 | 3 |
| Banii Noștri | 4 | 3 | 1 | 5 |
| Data Expert Forum | 3 | 3 | 0 | 8 |
| Ce cumpără primăria | 3 | 4 | 0 | 3 |
| Hazard seismic 2026 pe localități | 1 | 3 | 0 | 3 |
| **Added** | **14** | **15** | **4** | **22** |

The fifteen-project set has 75 evidence records, 54 collections, 54 URL patterns and 87 API/data operations.
It has 48 identifier rules, 49 record references and eleven explicit relationships.
There are zero sample gaps and zero identity conflicts.
All recipes replay from tracked evidence without requests or ignored caches.
The current catalogue has 146 entries, of which 142 pass the public selection.

## Source findings

### Execuții Bugetare

Three institutions are identified by their retained fiscal `cif`: București municipality and sectors 1 and 2.
The source represents CIF as a JSON integer; the extract preserves that source representation.
Lookup values remain strings. No missing leading zero can be reconstructed from the numeric source.

The observed homepage loads a named `home` module through its configured bootstrap.
That deployed module reads `judet`, `institutie` and `an` from URL query parameters.
It assigns `institutie.cif` to the institution selector and builds the JSON resource paths.
Those statements support the CUI binding independently of numeric URL resemblance.

The detail pattern fixes the observed context to county `B` and year `2026`.
The institution is a legal subject; the budget resource has a separate institution/year grain.
Three GET operations describe counties, institution lists and annual budget data.
The institution-list and budget responses were observed in retained snapshots; this batch did not re-probe them.

### Banii Noștri

The retained report and direct-purchase endpoint identify RAJA S.A. as buyer and two corporate suppliers.
The extract retains only local purchase IDs, buyer/supplier fiscal codes and corporate names.
Existing owner-confirmed selectors establish the meaning of the ambiguous API fields `afn` and `sfn`.
Their receipt points to the committed catalogue definition, read locally; no extra GitHub request was made.

The two purchases use a local `daid` namespace.
Neither the buyer's CUI nor a supplier's CUI identifies the enclosing purchase.
Four separate buyer/supplier relationships connect the purchase records to their corporate subjects.

Only the endpoint for buyer CUI `1890420` is established here.
It reports `hasMore`, `limit`, `offset` and `count`; one retained page was sampled.
The recipe does not infer arbitrary-buyer coverage, query parameters or tested pagination.

### Data Expert Forum

The host remains on the do-not-request list.
This batch read the owner's saved page and previously retained Google Sheet exports only.
It requested neither the host nor Google Sheets.

Two allocation rows provide both fiscal CIF and territory SIRUTA codes for Aiud and Blaj.
The recipe creates separate institution and territory references, joined by `associated_territory` relationships.
It never equates a fiscal subject with a geographic territory.

Four retained funding-request rows reference București, Alba Iulia, Cluj-Napoca and Arad by SIRUTA.
Repeated requests for the same territory do not create duplicate territory subjects.
Only territory identifiers, names and counties were copied.
Amounts, investment descriptions, party values and candidate/person records were excluded.
Published sheet links retain their clean target URLs; Google redirect tracking wrappers were removed.
No per-UAT frontend detail page was established.

### Ce cumpără primăria

The retained Arad page and two observed public pages expose a named `siruta` component property beside the locality name.
The route state also names its dynamic segment `siruta`.
The reader decodes JSON string chunks without executing JavaScript.
It retains only the named locality component, not procurement tables or other page data.

Arad `9262`, București `179132` and Cluj-Napoca `54975` are therefore explicit SIRUTA observations.
Their 2025 detail URLs retain the reporting-year context.
Supplier and ranking pages remain separate sections.
No underlying API was invented from the page's internal data or route structure.

### Hazard seismic 2026 pe localități

The retained partial JSON supplied three complete positional rows for Alba Iulia, București and Cluj-Napoca.
The script explicitly maps row position 15 to a locality slug and position 16 to a legacy row number.
It also defines both a `?l=<slug>` restore path and a configured `/l/<slug>/` share path.
The retained page configuration enables that share format.

Both identifier namespaces are local to this project and release.
The legacy number is not SIRUTA. The slug is not a cross-project identifier.
Equal locality names create no identity proposal.
No hazard values, rankings or geometry were copied into the identity extracts.

## New direct identity proposals

| Subject | Shared identifier | Representations now observed | New pairs |
| --- | --- | --- | ---: |
| București fiscal institution | CUI `4267117` | Transparenta.eu, Execuții Bugetare | 1 |
| București territory | SIRUTA `179132` | Transparenta.eu, România Transparentă, Se golesc de oameni…, Data Expert Forum, Ce cumpără primăria | 7 |
| Cluj-Napoca territory | SIRUTA `54975` | Se golesc de oameni…, Data Expert Forum, Ce cumpără primăria | 3 |
| Alba Iulia territory | SIRUTA `1017` | Se golesc de oameni…, Data Expert Forum | 1 |
| Arad territory | SIRUTA `9262` | Data Expert Forum, Ce cumpără primăria | 1 |

These are thirteen independent direct pairs, not a transitive entity cluster.
The original four decisions remain accepted.
The prior 26 proposals and these thirteen remain proposed: 39 proposals in total.
The fiscal București institution is outside the SIRUTA territory pairs.
The hazard explorer's local identifiers participate in none of these proposals.
Source observation dates remain visible; legal validity periods remain unknown.

## Verification

The offline pass imported eight retained documentation observations for the five projects and made zero requests.
The live pass made nine GET requests, all HTTP 200, including four robots checks.
It visited only the budget explorer and Ce cumpără primăria.
No forbidden host, paid API, paid search, browser source crawl or owner contact was used.

Seven new offline tests cover purchase roles, local identifiers, fiscal/territory associations, named route semantics and request restrictions.
They pass on Python 3.12.
The final full suite passes 1,265 tests with eight skips.
All 37 browser checks pass, including all ten expansion profiles and mobile local-ID lookup.
The original pilot checker, repository validation and public build pass.
A comparison shows that the public build changed only its generated timestamp; that drift is excluded.

The review packet resolves its artifact hashes and recipe aliases offline.
The preview remains isolated; the public build still omits structure observations and entity lookup.
No owner identity decision changed.

## Preview

Rebuild with:

```sh
python3 scripts/build.py --with-structure --site-dir /tmp/civtech-entity-preview
python3 -m http.server 8784 --bind 127.0.0.1 -d /tmp/civtech-entity-preview
```

Open the [București territory lookup](http://127.0.0.1:8784/entitati/?namespace=ro:siruta&value=179132)
or the [București institution lookup](http://127.0.0.1:8784/entitati/?namespace=ro:cui&value=4267117).
They show different subjects and different correspondences.
The pending identity reviews do not block further profiling.
