# Site structure expansion — 2026-10-30

Status: five new recipes implemented and replayed. The 26 new identity pairs await owner review.
[Review packet](site-structure-batch-f/review.json) · [Request journal](site-structure-batch-f/requests.jsonl) · [Preview guide](../STRUCTURE-PREVIEW.md)

## Completed sites

| Project | Collections | URL patterns | API operations | Observed records |
| --- | ---: | ---: | ---: | ---: |
| lista-firme.info | 1 | 2 | 1 | 3 |
| DemoANAF | 12 | 5 | 46 | 2 |
| Companiile de stat | 7 | 8 | 20 | 2 |
| Companii Publice — România | 3 | 2 | 0 | 6 |
| Se golesc de oameni, dar nu de locuințe | 1 | 3 | 0 | 3 |
| **Added** | **24** | **20** | **67** | **16** |

The combined ten-project recipe set has 58 evidence records, 40 collections, 39 URL patterns and 83 API operations.
It has 35 identifier rules, 27 observed record references and five explicit relationships.
The importer reports zero sample gaps and zero identity conflicts.
The recipes replay from tracked evidence alone, without ignored snapshots or live requests.

An API declaration is not an executed operation.
The two sites without an API contract retain their JSON/CSV resources as document patterns.
No invented dynamic API or per-entity frontend URL fills those gaps.

## What each site establishes

### lista-firme.info

Two live company responses establish Antibiotice CUI `1973096` and Active Conexe CUI `31029694`, with their EUIDs.
The previous retained operator response adds RTI Global Services CUI `51859625`.
Only corporate name, CUI and EUID were copied.
Legal representatives and every other response field were excluded.
An exact-value check tested 28 individual names and birth dates from the sampled responses against the tracked artifacts; none matched.

The pinned `routes/web.php` declares `/companie/{cui}` and the root company search page.
These are route declarations, not separate live availability checks for those frontend pages.
The retained company migration declares an internal table ID.
No actual local-ID correspondence was obtained; the recipe keeps that rule declared only.
It does not extract a company ID from a legal-representative record.

`GET /api/v1/info?cui={cui}` was observed without authentication.
The sampled requests do not establish the complete parameter contract or whether CUI is required.
The recipe leaves that requirement unspecified and marks the contract incomplete for automatic probes.

### DemoANAF

The retained OpenAPI contract contributes 46 operations across company, finance, classification, exchange-rate, procurement and other sections.
The contract and `llms.txt` document paid programmatic API access.
This batch invoked none of those API operations and used no credential or payment.

Two public HTML pages independently identify Antibiotice and Active Conexe.
Only each page's exact title, canonical URL and financial-profile links were retained.
No page tables about persons were copied.

The frontend route `/verificare-cui/{cui}` is explicit in retained documentation and present in the observed canonical URLs.
Financial pages retain their own collection grain; their records are not treated as company identity records.
A contracting-authority CUI remains a related procurement role, distinct from the enclosing contract or notice.

### Companiile de stat

The retained OpenAPI contract contributes 20 method/path operations.
Two current company-detail JSON responses identify the same Antibiotice and Active Conexe subjects.
Their corporate CUI/name extracts exclude financial and people-related fields.

The deployed search script builds `/companii/${e}/` from its company-data key.
The contract identifies those keys as CUIs.
Together they support `/companii/{cui}/` without guessing a numeric path's meaning.
Retained documentation supplies company, year, geography, governance, procurement, subsidy and data sections.
Annual financial records retain a separate grain from a legal company subject.

### Companii Publice — România

The retained `companii.json` is a partial read.
The existing `inventory_jsonsample.recover` reader supplied complete rows at indices 96, 293 and 79.
The extract keeps only company, authority and parent CUIs, plus their corporate names.
It does not repair a cut record or infer an unseen value.

These rows identify six subjects:

- Active Conexe and Antibiotice.
- Their supervising authorities: CUI `11795573` and CUI `4266456`.
- Piața de Gros CUI `5622225` and its parent company CUI `8359779`.

Three authority-to-company `administers` relationships and one child-to-parent `parent` relationship remain separate from identity.
The child company has only CUI `5622225` as its own identifier.
Its authority and parent CUIs never identify that child.
The explorer is a single-page listing; no distinct company profile URL was established.

### Se golesc de oameni, dar nu de locuințe

The retained `localitati.csv` supplies exact SIRUTA rows for Alba Iulia `1017`, Cluj-Napoca `54975` and București `179132`.
The extract retains the original header, row indices, territory names, counties and types.
It omits metric values.

The Romanian and English explorer pages are sections of this catalogue entry.
The host-level `llms.txt` also describes sibling projects; those projects were not imported into this profile.
No town-hall CUI or distinct locality detail URL was inferred.

## New identity proposals

Each proposal is a direct pair supported by an observed shared identifier.
The grouped summary below is for owner review; it does not create a transitive identity cluster.
The review packet lists all 26 assertion IDs, both subjects, source receipts and candidate profile URLs.

| Subject | Identifier | Representations now observed | New direct pairs |
| --- | --- | --- | ---: |
| Antibiotice SA | CUI `1973096` | igov, Registrul firmelor, lista-firme, DemoANAF, Companiile de stat, Companii Publice | 14 |
| Active Conexe SA | CUI `31029694` | igov, lista-firme, DemoANAF, Companiile de stat, Companii Publice | 10 |
| București territory | SIRUTA `179132` | România Transparentă, Transparenta.eu, Se golesc de oameni… | 2 |

The original four owner decisions remain unchanged.
For Antibiotice, the prior igov–Registrul firmelor pair was already accepted; the other fourteen are new.
For București territory, the prior România Transparentă–Transparenta.eu pair was already accepted; the other two are new.
The fiscal institution CUI `4267117` is outside those territory pairs.
Observation times remain explicit; legal validity periods are unknown.

## Requests and checks

The offline discovery pass selected all five projects and imported fourteen retained documentation observations with zero requests.
The live pass sent fifteen GET requests: fourteen HTTP 200 responses and one HTTP 404 response for GitHub's robots file.
No listed host, paid API, browser source crawl, paid search or owner contact was used.
The journal retains every charged request, including robots checks.

Six new offline tests check sample extraction, corporate whitelists, parent/authority roles, territory identity, API access distinctions and idempotence.
They pass on Python 3.12.
The full suite passes 1,258 tests with eight skips.
All thirty browser checks pass, including the five new project profiles.
The browser checker now derives record counts and confirmations from the payload and owner decisions.
It does not pin the original two-record examples after coverage grows.
The original pilot checker, structure-store integrity, repository validation and the public build pass.
Generated public timestamps are excluded from this research change.

## Reproduce and review

Build the current tracked recipes:

```sh
python3 scripts/build.py --with-structure --site-dir /tmp/civtech-entity-preview
python3 -m http.server 8784 --bind 127.0.0.1 -d /tmp/civtech-entity-preview
```

Open [Antibiotice](http://127.0.0.1:8784/entitati/?namespace=ro:cui&value=1973096),
[Active Conexe](http://127.0.0.1:8784/entitati/?namespace=ro:cui&value=31029694), or
[București territory](http://127.0.0.1:8784/entitati/?namespace=ro:siruta&value=179132).

The preview shows all observed records but confirms only explicitly accepted direct pairs.
The remaining owner decision is whether to accept, reject or defer the 26 new pairs.
Acceptance does not authorize publication.
