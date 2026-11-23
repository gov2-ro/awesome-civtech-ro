# Spec: a card for each data set (fișa setului de date)

Status: accepted 2026-11-23 (owner's answers in section 9). Briefs: [`docs/briefs/data-set-card-build.md`](../briefs/data-set-card-build.md) (the build), [`docs/briefs/data-set-card-pilot.md`](../briefs/data-set-card-pilot.md) (the pilot cards).
Source: item 1 of the external review (`docs/BACKLOG.md`, section "External review of `/date/` and the taxonomy — 2026-11-23"; local copy `tmp/261123/Revizie civtech.gov2.ro_date.pdf`, not tracked).
Measured at commit `e300e9b` (2026-11-23). The measuring scripts are not in the repository; Appendix B gives the method, so a person can repeat it.

## 1. Goal

A visitor of an entry or of `/date/` must read, in one block for each data set that the entry uses:
the data set, its provider, what one record is, the period, the access (web, file, API) and the identifiers with their role.
The raw fields (10,212 field records at `e300e9b`) stay as evidence, in a technical view, behind one link.

Example of the target, for SICAP.ai (values from the evidence in Appendix A; a person confirms them before publication):

> **Achiziții directe din SEAP** · furnizor: SEAP (e-licitatie) · o înregistrare: o achiziție directă · perioada: nedeclarată · acces: web, API (cheie)
> Identificatori: CUI al autorității contractante · CUI al furnizorului · cod CPV al obiectului
> Variabile principale: cod CPV, … · [Vedere tehnică: 1,263 câmpuri →]

The line of key variables is illustrative: a person chooses them.

## 2. Terms

One word, one meaning. The site uses "sursă" today for two different things; the card separates them.

| Term (RO) | Meaning | Where it lives today |
| --- | --- | --- |
| furnizor | The organisation that publishes the data (INS, ONRC, SEAP). | `relatii.csv` (`date_din`) + `furnizori.csv` |
| set de date | One body of data from one provider that the entry uses: for example "achiziții directe din SEAP" or "bilanțuri de la MF". | Nowhere. This spec adds it. |
| înregistrare | What one row or one object of the data set describes: a contract, a company, a UAT for one year. | `record_grain` of a collection in `structura/recipes/` (20 entries) |
| document citit | A file that the inventory read to find fields: an OpenAPI file, a `types.ts`, a CSV header. Today the site calls it "sursă" or "fișier consultat". | `seturi-date.json`, `inventar/<slug>.json` |
| câmp | One field of a document citit. | `campuri.csv` |
| identificator | A code that names an entity: CUI, SIRUTA, EUID, CPV, CAEN, or a local ID of one site. | identifier groups of `inventar-concepte.json`; namespaces of `structura/recipes/` |
| rolul identificatorului | Which entity the code names in this data set: the contracting authority, the supplier, the UAT. | `context` of a selector; `relationships` of a recipe (4 entries) |

A document citit is not a data set. SICAP.ai has 6 documents citite (one OpenAPI file and five `types.ts` files) and, by its own documentation, 3 or 4 data sets (tenders, direct purchases, ONRC registrations, MF financial statements).

## 3. What exists today (measured)

Population: the 137 entries of the finder index (`inventar/index.json`: 112 projects, 24 publications, 1 resource), that is, the entries in scope of the variable inventory.

| Card field | Evidence today | Entries with it | Missing |
| --- | --- | --- | --- |
| Provider | accepted `date_din` relation (shown on the site) | 46 | 91 |
| | any `date_din` relation, `propus` included (96 of 217 rows are `propus`) | 76 | 61 |
| Data set named | INS metadata (`dataset`), schema.org `Dataset` or a page of described sets (`facts`) | 16 | 121 |
| Record (what one row is) | a declared statement (INS indicator, described set) | 9 | 128 |
| | the same, or a collection with a `record_grain` in a structure recipe | 25 | 112 |
| Period | declared (INS metadata, schema.org `temporalCoverage`) | 15 | 122 |
| | only a time field, no declared period | 8 | — |
| Access | any document citit (86); of these: an API document 20, a data file 57, only source code 5 | 86 | 51 |
| Identifiers | a field in an identifier group (`cui`, `cpv`, `siruta`, `cod-caen`) | 15 | 122 |
| | the same, with a role (`context` on the selector) | 12 | 125 |
| | a shared namespace (CUI, SIRUTA, EUID) in a structure recipe | 15 | — |

Missing most often, in order: record (128 of 137 without a declared statement), identifiers with role (125), period (122), data set named (121), provider (91 without an accepted relation; 61 without any relation), access (51).

The three evidence layers do not meet on one unit:

- `date_din` names a provider for the entry, not a data set. 30 entries have only `propus` provider rows, so the site shows no provider for them.
- The inventory names documents citite and fields. It measures what is easy to extract, not what matters (the review's point; confirmed: 5 entries have only source code as evidence, so a visitor gets no file or API from them).
- The structure recipes (20 entries, 73 collections, 70 with a known `record_grain`, 21 shared and 14 local namespaces, 96 operations) are the nearest thing to a card. But a collection is a part of a site, not a data set of a provider, and only 4 recipes record roles (`buyer`, `supplier`).

How many entries can get a card today from existing evidence:

| Tier | Rule | Entries |
| --- | --- | --- |
| A | structure recipe + accepted provider: record, identifiers and often access are in the evidence | 19 |
| B | accepted provider + at least one document citit, no recipe: provider and access; record, period and identifiers need a person | 26 |
| C | accepted provider, no document citit | 1 |
| — | only `propus` providers: the owner must accept them first | 30 |
| — | no provider relation | 61 |

All five fields filled from evidence alone: 1 entry (`demoanaf`). With a person who reads the evidence and confirms each field: tier A (19), then tier B (26). So 45 entries can get a card without a new request; a person fills the gaps.

Procurement and companies (the review's first area), 15 entries: `achizitii-directe-ti-2026`, `banii-nostri`, `ce-cumpara-primaria`, `ce-face-statul-cu-1000-de-lei`, `companii-de-stat`, `data-expertforum`, `harta-firmelor`, `igov`, `monitor-safe`, `pe-datorie`, `prima-cifra`, `registrul-firmelor`, `romania-transparenta`, `sicap-ai`, `statul-digital`. Ten of them have a structure recipe. `romania-transparenta` (1,147 field records, the second largest) has no `date_din` relation at all.

Correction to the review: `source_row` and `risk_score` are fields of `achizitii-directe-ti-2026` (one CSV), not of SICAP.ai. SICAP.ai has `cpvCode` (in the OpenAPI file and in four `types.ts` files) and `riskIndicators` (OpenAPI). The rule of the example stays the same.

## 4. The card

### 4.1 Storage: one hand-edited file

New file `data/taxonomy-v2/integrare/fise-date.csv`. One row for each pair of entry and data set. A person edits it in the repository (like `relatii.csv`; not a tab of the Sheet in the first version).

| Column | Meaning | Rule |
| --- | --- | --- |
| `id` | The card (`S001`, …). | Unique. Never reused. |
| `slug` | The entry. | A `slug` of `intrari.csv`. |
| `set` | The name of the data set, in Romanian, as a visitor says it. | Required. At most about 80 characters. |
| `furnizor` | The provider. | A `furnizor` id of `furnizori.csv` with `stare=acceptat`, or `autor` for the entry's own data. The entry must have a `date_din` relation to a name of that provider (a warning, not an error, while that relation is `propus`). |
| `inregistrare` | What one record describes, in Romanian: "o achiziție directă", "o firmă într-un an", "un UAT". | Required for `acceptat`. |
| `granularitate` | The record grain as a code. | Optional. A code of the new list `granularitate_set` in `valori.csv`. The first list is the 22 known values of `record_grain` in the recipes (70 of 73 collections have one), translated (for example `contract`, `achizitie-directa`, `subiect-juridic`, `teritoriu`, `firma-an`, `institutie-an`, `agregat`). |
| `perioada` | The period of the data: `2007–2025`, `2019–` (still updated) or empty. | Empty means "nedeclarată": the card says so. Never guess a period from the fields. |
| `acces` | How a visitor gets the data. | List of codes of the new list `acces_set`: `web` (pages only), `fisier` (a download: CSV, JSON, XLSX), `api`, `api-cheie` (an API that needs a key), `la-cerere` (on request, for example under Law 544/2001). |
| `url_acces` | The address for each access code. | Same order as `acces`; empty for `web` when it is the entry's own address. |
| `identificatori` | The identifiers and their role. | List of `cod:rol`. `cod`: `cui`, `siruta`, `euid`, `cpv`, `caen`, `local`. `rol`: a code of the new list `rol_identificator` (first list: `autoritate-contractanta`, `furnizor`, `firma`, `institutie`, `uat`, `obiect`, `contribuabil`, `creditor`). A local ID is `local:<namespace of the recipe>`. |
| `variabile_cheie` | The few variables that a visitor needs, at most six. | List. Each item is a group id of `inventar-concepte.json` or `<sursa_id>#<path>` of `campuri.csv`. `validate.py` checks that each one exists for the entry. |
| `nota_metoda` | How a derived value is calculated (the review's `risk_score`), or another warning. | Optional. A derived value in `variabile_cheie` without a note is a warning. |
| `dovada` | Where a person can check the card. | One or more URLs. Required for `acceptat`. |
| `baza` | How the card was made. | `declarat` (the project or the provider says it), `observat` (seen in a document citit or a recipe), `editorial` (a person's reading of several pieces of evidence). |
| `verificat_la` | The date of the last editorial check. | ISO date. It is the third date of review item 4 ("ultima verificare editorială"). |
| `stare` | `propus` or `acceptat`. | Only the owner sets `acceptat`. The build shows only `acceptat` rows. |
| `nota` | Free text for editors. | Not published. |

Why a new file and not new columns on the `date_din` rows of `relatii.csv`: one provider can give one entry several data sets (SICAP.ai: tenders and direct purchases, both from SEAP), and one data set can come from a provider that the entry names through an intermediary (ANAF data through transparenta.eu). A relation row stays "the entry uses this provider"; a card is "the entry uses this data set". Cost of the alternative: 13 more columns on a file of 445 rows with 4 predicates; the 228 rows that are not `date_din` would leave them empty.

Why a hand-edited file and not a generated one: the review's main finding is that extraction does not measure relevance. Record, role and key variables need a person. A script may write proposals later (see 7), never `acceptat` rows.

### 4.2 What the card takes from existing evidence

A person who fills a row reads, in this order:

1. `relatii.csv` `date_din` and `furnizori.csv`: the provider.
2. The structure recipe, when there is one: the collections (`record_grain` → `inregistrare`, `granularitate`), the namespaces (`shared: true` → a shared identifier; otherwise `local`), the relationships (`buyer`, `supplier` → the role), the operations (`authentication` → `api` or `api-cheie`).
3. The inventory: the dataset facts (INS metadata, schema.org `Dataset`: name, period, licence), the identifier groups and the `context` of their selectors (role), the fields for `variabile_cheie`.
4. The entry's own documentation (`observatii/documentare/`) for what the first three do not say.

No new request is needed for tiers A and B. A gap stays empty, and the card says "nedeclarat".

### 4.3 What stays in the technical view

The technical view is the existing page `/date/<slug>/` ("Pe familii", "Pe surse") and the field browser of the entry. Nothing in them is removed. They keep:

- every field, its path, type, unit, description, groups and pointer (`char:1083-1094`, JSON pointers);
- the documents citite, their formats, read dates, failed refreshes and licences;
- interface artefacts and row numbers (`source_row`, front-end state);
- local identifiers, until item 3 of the review decides their place on the entry page.

## 5. Changes to the public pages

| Place | Today | With the card |
| --- | --- | --- |
| Entry page, panel "Date & metodă" (`entry_page.data_summary`, `app.js` `inventoryHTML`) | Field count, field examples, "Toate variabilele →" | One block for each accepted card (the fields of 4.1, the provider linked to `/date/furnizori/#f-<furnizor>`). Below the cards: "Vedere tehnică: N câmpuri din M documente →" to `/date/<slug>/`. An entry without a card keeps today's panel. |
| Entry page, facts box, "Surse de date" | Provider chips from `date_din` | Unchanged (the review says that these chips work). |
| `/date/<slug>/` | Header, "Pe familii", "Pe surse" | A part "Seturi de date" first, with the cards. The two parts below get the heading "Vedere tehnică" and one sentence: "Câmpurile sunt extrase automat din documentele citite. Ele arată ce se poate extrage, nu ce contează." |
| `/date/` finder | Results show field examples | A result with a card shows one line for each card (set, provider, access, identifiers). The field examples stay below. New facets are review item 2, not this spec. |
| `data.json` | `dataSources` | New key `datasets`: the accepted cards, with the columns of 4.1 except `nota`. |
| JSON-LD of the entry page | `WebPage`, `BreadcrumbList`, the entry | Optional, second step: one schema.org `Dataset` for each card (`publisher`: the provider; `temporalCoverage`: the period; `distribution`: `fisier` and `api` addresses), linked by `isBasedOn`. |

`entry_page.py` and `app.js` must stay in step (the rule of `CLAUDE.md`), so the card block has one HTML form in both.

## 6. Changes to `DATA-SCHEMA.md`

- New section `fise-date.csv` under "Taxonomy v2 package", with the table of 4.1 and the checks of 8.
- "Conventions of the v2 files" and "Integration overlay: integrare/": list the new file.
- "data.json of the v2 model": the key `datasets`.
- "Explorer inventory preview" and "Cross-project data finder preview": the card block and the heading "Vedere tehnică"; the word "document citit" where the text means a file that the inventory read.
- `valori.csv`: the three new lists `granularitate_set`, `acces_set`, `rol_identificator`.

`docs/METODOLOGIE.md` gets one paragraph: a card is an editorial statement with evidence; the fields are observations.

## 7. Order of work (after the owner's decisions)

1. Brief for Sonnet: the file, its checks in `validate.py`, the three value lists, `datasets` in `data.json`, the card block in `entry_page.py` / `app.js` / `inventory_site.publish_variable_pages`, unit and browser tests. No card rows.
2. Brief for Sonnet: the pilot cards, all `propus`, for the ten procurement and company entries with a structure recipe, then the other five of section 3. One `dovada` and one `baza` for each row. The owner accepts.
3. Measure after the pilot: the time per card, the fields left empty, and the three usability tasks of the review on `/date/`.
4. Only then: tier A outside procurement, then tier B. A proposal script only if a person spends more than about 10 minutes per card.

## 8. Checks (`validate.py`)

Errors: a missing or unknown column; an `id` twice; an unknown `slug`; a `furnizor` that is not an accepted provider and not `autor`; a code outside its list (`granularitate`, `acces`, the `cod` and `rol` of `identificatori`, `baza`, `stare`); `url_acces` and `acces` of different lengths; an item of `variabile_cheie` that does not exist for the entry; an `acceptat` row without `inregistrare`, `dovada` or `verificat_la`; a card on an entry out of the inventory scope (an organisation).
Warnings: no `date_din` relation of the entry to the card's provider, or only a `propus` one; a derived variable (`categorie` `iesire-derivata`) in `variabile_cheie` without `nota_metoda`; `verificat_la` older than 365 days.

## 9. Decisions of the owner (2026-11-23)

1. Accepted: the card is the public unit of `/date/` and of "Date & metodă"; the fields are a technical view.
2. The file is `integrare/fise-date.csv`. The proposed name `seturi-de-date.csv` was too close to the generated `observatii/inventare/seturi-date.json`.
3. The owner decides the 96 `propus` `date_din` rows (30 entries) before the pilot, or asks for help. The pilot brief starts only after that.
4. `romania-transparenta`: the pilot brief proposes its providers as `propus` `date_din` rows (and `furnizori.csv` rows for new names). The owner accepts them.
5. Still open, with the taxonomy items: the review moves `detaliere_date` and `relatie_date` from `intrari.csv` to the card. The card has `granularitate` and `perioada`, which overlap with `detaliere_date`. This spec does not change those columns.

## Appendix A. SICAP.ai, the evidence for the example card

- Providers (accepted `date_din`): SEAP (evidence `sicap.ai`), Ministerul Finanțelor (`docs/company-enrichment-brief.md`), ONRC (`docs/architecture.md`).
- Documents citite: `api.sicap.ai/v1/openapi` (527 response fields, 42 API parameters), `es/licitatii/types.ts` (362), `es/achizitii/types.ts` (115), `es/achizitii-offline/types.ts` (88), `es/company/onrc.ts` (74), `es/types.ts` (55). The four folders of `es/` are the data sets that the code names: tenders, direct purchases, offline direct purchases, ONRC registrations.
- Structure recipe: collections `authorities`, `suppliers` (legal subjects), `contracts` (grain unknown), `registrations`; namespaces `ro:cui` (shared), `ro:onrc:registration`, `sicap-ai:contracts:id` (local); operations need a key (`authentication: key`); no relationship rows.
- Identifier with role: the `cui` group has 11 matching fields; the selector `context` says that `/v1/ac/{cif}/…` is the CUI of the contracting authority and `/v1/supplier/{cif}/…` the CUI of the supplier.
- Period: not declared in any retained evidence.

## Appendix B. Method of the measurement

1. `python3 scripts/build.py --with-inventory --site-dir <tmp>/site` at `e300e9b`.
2. For each entry of `<tmp>/site/inventar/index.json`: the `date_din` rows of `integrare/relatii.csv` (any state, and `acceptat`); the sources of `inventar/<slug>.json` (`dataset` and `facts` keys; formats grouped as API: `openapi`, `llms-api`, `html-api-docs`, `rsc-json`, `baza-datasette`, `metadate-ins`, `lista-ins`; file: `csv`, `json`, `json-esantion`, `json-schema`, `json-comentat`, `html-carduri-csv`, `html-lista-seturi`; code: `php`, `csharp`, `sql`, `typescript`, `django-modele`, `markdown`); the `variables` of the index entry whose family is `identificatori`, and their `context`; the `formate` cell of `intrari.csv` (`format:api`, `format:set-date`).
3. For the structure layer: `data/taxonomy-v2/structura/recipes/*.json` (`collections[].record_grain`, `namespaces[].shared`, `operations[].authentication`, `relationships`).

## Appendix C. The review's figures at `e300e9b`

The review counted at `7b476a5` (2026-11-20). The method above reproduces its inventory numbers exactly at `7b476a5` (8,609 rows, 76 projects, 2,165 with a description, 50 with a semantic type; 3,679 / 2,300 / 1,184 by origin).

| Figure | Review (`7b476a5`) | Now (`e300e9b`) |
| --- | --- | --- |
| Entries | 199: 145 projects, 27 publications, 16 organisations, 11 resources | 202: 148 projects, 26 publications, 16 organisations, 12 resources (198 `acceptat`, 4 `ascuns`) |
| Concepts | 130, 13 top subjects; 22 EuroVoc mappings | 130, 13 top subjects; 22 EuroVoc mappings, all `propus` |
| Columns of `intrari.csv` | 34 | 34 |
| Inventory rows | 8,609 from 76 projects | 10,212 from 87 projects |
| SICAP.ai + România Transparentă | 2,428 (28%) | 2,428 (1,281 + 1,147; 24%) |
| Fields with a description | 2,165 (25%) | 2,165 (21%) |
| Fields with a semantic type | 50 (0.6%) | 50 (0.5%) |
| By origin | JSON samples 3,679, OpenAPI 2,300, source code 1,184 | JSON samples 5,034, schemas 2,300, source code 1,328 |
| Coverage states | 53 not investigated, 6 blocked, 27 without data | 42 not investigated, 6 blocked, 27 without data, 4 investigated without sources, 86 with sources |
| Classification, accepted entries | 195 | 198 |
| `teme` | 176 filled, 61 values, 28 with ≤ 3 entries | 179 filled, 61 values, 28 with ≤ 3 entries |
| `scopuri` | „informare” 132 (68%), „transparență” 77 | „informare” 135 (68%), „transparență” 80 |
| `functionalitati` / `formate` | 159 / 161 | 162 / 164 |
| `institutii_vizate` | 48, 6 values | 48, 6 values |
| `maturitate` | 86; 77 „operațional” | 88; 79 „operațional” |
| `tehnologii` | 20; AI 15 | 21; AI 16 |
| `tip_organizatie`, `detaliere_date` | 14, 26 | 14, 26 |
| `date_din` | 217 relations, 90 providers | 217 relations (121 `acceptat`, 96 `propus`), 90 names, 83 after `furnizori.csv` (58 of 90 rows `acceptat`) |
| Top providers | INS 31, Eurostat 15, MF 12, MO 9, ONRC 7, SEAP 7, AEP 7, ANAF 6 | by name: unchanged; normalised: INS 31, MF 16, Eurostat 15, MO 10, SEAP 9, ANAF 7, ONRC 7, AEP 7 |
| Review queue | 66 items on the first 122 entries | 228 items: 159 `acceptat`, 38 `tehnic`, 20 `deschis`, 11 `respins` |
| Documentation | DATA-SCHEMA.md 193 KB, BACKLOG.md 134 KB, METODOLOGIE.md 23 KB | 196 KB, 144 KB, 23 KB |
| Repository | 67 MB | tracked files 53 MB; `.git` 112 MB |
