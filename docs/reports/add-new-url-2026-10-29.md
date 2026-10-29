# URL audit — 2026-10-29

The owner requested publication on 2026-10-29. `dimineata` is `acceptat`; `gio` is `ascuns` pending a terms check with Gabriel Popa.

The tables below retain the original audit values. The publication update is recorded at the end.

## Evidence

- D1: [dimineața.de home](https://dimineata.de/): name, canonical URL, editions, articles, search and social links.
- D2: [Biography and method](https://dimineata.de/biografie/): Gabriel Popa, source selection, Claude drafts and human approval.
- D3: [Support](https://dimineata.de/sustine/): project support page.
- D4: [Terms](https://dimineata.de/termeni/): public contact link, protected by Cloudflare email encoding.
- G1: [gio home](https://gio.ciolan.io/): audience, network, search, citations, source timestamps and correction form.
- G2: [gio method](https://gio.ciolan.io/despre): transcript extraction, Claude and review. The document is draft v0.1.
- G3: [gio terms](https://gio.ciolan.io/termeni): Gabriel Popa is the operator; §5.2 excludes automated scraping.
- Both sites returned HTTP 200. No duplicate domain or exact name was found in the live catalogue.
- These pages were read before the collection restriction was discovered. No later request reached gio.ciolan.io.

## Catalogue cells

I = editorial inference from the named evidence. Blank cells remain unknown or inapplicable.

### dimineața.de

| Cell | Value | Basis |
| --- | --- | --- |
| `slug` | dimineata | I: slug convention; proposed classification; confidence and limits recorded by this audit. |
| `tip_entitate` | proiect | I: an ongoing civic instrument or initiative; `publicatie` denotes an individual publication. |
| `sectiune_url` | proiect | I: an ongoing civic instrument or initiative; `publicatie` denotes an individual publication. |
| `nume` | dimineața.de | D1/D2: page text or canonical link; Romanian editorial summary. |
| `descriere_scurta` | Jurnalism civic pentru Sibiu și România, cu surse și proces editorial explicat | D1/D2: page text or canonical link; Romanian editorial summary. |
| `descriere` | Proiect de jurnalism civic pentru cititorii din Sibiu și din România. Selectează informații din surse instituționale, presă și pagini publice, apoi redactează articole cu asistență AI și aprobare umană. Publică sursele consultate și un buletin săptămânal. | D1/D2: page text or canonical link; Romanian editorial summary. |
| `url` | https://dimineata.de/ | D1/D2: page text or canonical link; Romanian editorial summary. |
| `linkuri` | https://facebook.com/dimineata.de\|https://instagram.com/dimineata.de\|donatii:https://dimineata.de/sustine/ | D1 (own social profiles) and D3 (support page). |
| `subiect_principal` | subiect:media-informare | I from D1/D2; controlled codes only. |
| `subiecte` | subiect:media-informare | I from D1/D2; controlled codes only. |
| `teme` | subiect:jurnalism\|subiect:presa-independenta | I from D1/D2; controlled codes only. |
| `scopuri` | scop:informare\|scop:transparenta | I from D1/D2; controlled codes only. |
| `functionalitati` | functie:cautare | I from D1/D2; controlled codes only. |
| `formate` | format:articol | I from D1/D2; controlled codes only. |
| `tehnologii` | tehnologie:ai | D2: Claude drafts and editorial filtering. |
| `institutii_vizate` | — | The broad scope does not establish one controlled institution type. |
| `tip_organizatie` | — | Not an organisation entry. |
| `maturitate` | maturitate:operational | I from D1/D2: published editions and recurring use; the Sibiu edition calls itself a pilot. |
| `nivel_acoperire` | national | I from D1/D2; controlled codes only. |
| `arii_acoperite` | tara:RO | I from D1/D2; controlled codes only. |
| `detaliere_date` | — | No verified geographic breakdown of a structured dataset. |
| `dovada_detaliere` | — | No geographic breakdown was asserted. |
| `relatie_date` | fara-date | I from D1/D2: editorial articles; no extractable dataset identified. |
| `localitate_originala` | — | No legacy locality; coverage is recorded separately. |
| `autor_original` | Gabriel Popa | D2; owner attribution agrees. |
| `contact` | contact@dimineata.de | D4: decoded public Cloudflare email link. |
| `civictech_original` | 1 | D2: independent, self-funded civic project. |
| `stare` | — | No manual offline or archived override. |
| `nota` | — | No separate legacy note. |
| `clasificare_stare` | propus | I: slug convention; proposed classification; confidence and limits recorded by this audit. |
| `incredere` | medie | I: slug convention; proposed classification; confidence and limits recorded by this audit. |
| `sursa_fisier` | — | New v2 entry, not migrated from a v1 file. |
| `sursa_rand` | — | New v2 entry, not migrated from a v1 row. |
| `nota_clasificare` | 2026-10-29 /add-new-url. Surse: https://dimineata.de/ și /biografie/ (autor, metodă, AI, acoperire), /termeni/ și /sustine/. Inițiativă editorială, nu publicație individuală; fara-date descrie articolele, nu o bază de date oferită. Operațional: ediții și articole publice; ediția Sibiu este numită pilot. Nu am identificat un URL de repository sau un export structurat. Contact decodat din linkul public protejat de Cloudflare. | I: slug convention; proposed classification; confidence and limits recorded by this audit. |

### gio

| Cell | Value | Basis |
| --- | --- | --- |
| `slug` | gio | I: slug convention; proposed classification; confidence and limits recorded by this audit. |
| `tip_entitate` | proiect | I: an ongoing civic instrument or initiative; `publicatie` denotes an individual publication. |
| `sectiune_url` | proiect | I: an ongoing civic instrument or initiative; `publicatie` denotes an individual publication. |
| `nume` | gio | G1/G2: page text; Romanian editorial summary. |
| `descriere_scurta` | Explorează relațiile din România citate în videourile lui Valeriu Nicolae | G1/G2: page text; Romanian editorial summary. |
| `descriere` | Instrument civic pentru cetățeni și jurnaliști care organizează relațiile dintre persoane, firme și instituții din România. Extrage informații din videourile publice ale lui Valeriu Nicolae și le prezintă într-o rețea navigabilă, cu citatul și minutul sursei. Relațiile afișate reprezintă afirmații ale sursei, nu constatări judiciare. | G1/G2: page text; Romanian editorial summary. |
| `url` | https://gio.ciolan.io/ | G1/G2: page text; Romanian editorial summary. |
| `linkuri` | — | No own repository, social profile or export URL was linked. The source author’s YouTube channel is not a project profile. |
| `subiect_principal` | subiect:guvernare-democratie | I from G1/G2; controlled codes only. |
| `subiecte` | subiect:guvernare-democratie\|subiect:media-informare\|subiect:economie-munca | I from G1/G2; controlled codes only. |
| `teme` | subiect:integritate-publica\|subiect:jurnalism\|subiect:firme | I from G1/G2; controlled codes only. |
| `scopuri` | scop:informare\|scop:transparenta | I from G1/G2; controlled codes only. |
| `functionalitati` | functie:cautare\|functie:analiza\|functie:sesizare | I from G1/G2; controlled codes only. |
| `formate` | format:vizualizare\|format:registru | I from G1/G2; controlled codes only. |
| `tehnologii` | tehnologie:ai | G2: Claude extracts entities and relations. |
| `institutii_vizate` | — | The broad scope does not establish one controlled institution type. |
| `tip_organizatie` | — | Not an organisation entry. |
| `maturitate` | maturitate:operational | I from G1: public instrument with 908 entities and 1,422 relations; legal documents remain drafts. |
| `nivel_acoperire` | national | I from G1/G2; controlled codes only. |
| `arii_acoperite` | tara:RO | I from G1/G2; controlled codes only. |
| `detaliere_date` | — | No verified geographic breakdown of a structured dataset. |
| `dovada_detaliere` | — | No geographic breakdown was asserted. |
| `relatie_date` | date-proprii | I from G1/G2: editorial structuring of video statements, not public-sector data. |
| `localitate_originala` | — | No legacy locality; coverage is recorded separately. |
| `autor_original` | Gabriel Popa | G2 and G3; owner attribution agrees. |
| `contact` | — | The project addresses are marked as not configured. The personal address was not used. |
| `civictech_original` | 1 | G1: non-commercial civic project. |
| `stare` | — | No manual offline or archived override. |
| `nota` | — | No separate legacy note. |
| `clasificare_stare` | propus | I: slug convention; proposed classification; confidence and limits recorded by this audit. |
| `incredere` | medie | I: slug convention; proposed classification; confidence and limits recorded by this audit. |
| `sursa_fisier` | — | New v2 entry, not migrated from a v1 file. |
| `sursa_rand` | — | New v2 entry, not migrated from a v1 row. |
| `nota_clasificare` | 2026-10-29 /add-new-url. Surse: https://gio.ciolan.io/ (scop, rețea, sursă video), /despre (metodă, Claude, Gabriel Popa), /termeni (operator). Operațional dedus din instrumentul public și înregistrările afișate; documentele despre și termeni sunt încă draft v0.1. Date proprii: structurare editorială a unor videouri, nu date ale sectorului public. Nu am identificat URL-ul repository-ului gio-data, un export sau un contact de proiect confirmat (adresele sunt marcate de configurat). Termenii §5.2 exclud scraping-ul automat; nicio cerere suplimentară către gazdă după citirea lor. | I: slug convention; proposed classification; confidence and limits recorded by this audit. |

## Attribution rows

| Cell | dimineata | gio | Basis |
| --- | --- | --- | --- |
| `id` | L227 | L228 | Next unused L identifiers. |
| `subiect` | dimineata | gio | Catalogue slug. |
| `predicat` | atribuit_in_sursa | atribuit_in_sursa | Skill attribution convention; role awaits owner review. |
| `obiect` | — | — | No catalogue entry represents the author. |
| `obiect_literal` | Gabriel Popa | Gabriel Popa | D2 / G2 and G3. |
| `camp_sursa` | autor | autor | Author attribution. |
| `valoare_sursa` | Gabriel Popa | Gabriel Popa | Name as printed by each site. |
| `stare` | rol_neconfirmat | rol_neconfirmat | Skill convention; no role was accepted. |

## Profiling and search

- dimineata: `activ`, HTTP 200; OG image 1200 × 630, icon 128 px, and link icon saved.
- First domain capture: 2021-12-29; latest capture: 2025-04-01. These dates do not prove the current project’s age.
- Latest profiler update: 2026-10-01, from RSS. No repository URL or certificate-first date was found.
- gio: profiling skipped through `forbidden`; no generated HTTP status, image, capture or update date exists.
- Search: six Serper requests and two Brave requests, all successful; estimated cost $0.016.
- dimineata: 29 stored rows; 19 kept by existing rules. All 19 kept rows look unrelated from titles and snippets.
- gio: 36 stored rows; 19 kept by existing rules. All 19 kept rows look unrelated from titles and snippets.
- Poems, food, music and other people with the same name dominate the results. Author-only profiles cannot establish project mentions.
- No search row was pruned and no editor cell was changed. dimineata’s profile shows 19 mention hosts. gio has no profile row because collection is blocked.

## Inventory and checks

- Documentation: dimineata made five requests; three pages were collected. `llms.txt` and `/metodologie/` returned 404.
- gio documentation: `colectare-interzisa`, zero requests, zero collected pages.
- Inventory: zero requests; zero structured sources and zero fields added for either entry.
- dimineata has one HTML control candidate; it remains outside `/date/` because it is `fara-date`.
- Regenerated `acoperire.csv` and `inventory-expansion.md`. No source or lot was registered.
- The temporary request hook enforced a 1.1-second interval for dimineata.de and its subdomains. Repository scripts were unchanged.
- Profiler request count: 11 to dimineata.de and 7 to external metadata services. Documentation added five site requests.
- Initial audit: five dimineata.de requests, three gio.ciolan.io requests; no redirect was followed.
- Validation passed: zero errors and zero warnings.
- Isolated draft build passed: 142 visible entries.
- Public build refused both proposed classifications, as expected. No public build output changed.

- Full suite outside the sandbox: 1,102 tests, 18 assertion failures, zero errors, eight skips (148.488 seconds).
- All failures arise from publication-gate expectations while `dimineata` and `gio` remain `propus`. The HTTP check panel likewise reports the rejected publication check.
- The first sandbox run had 17 failures and nine localhost binding errors. Approved execution removed the binding errors.
- Test assumptions are recorded in the backlog. No production classification or test was changed to bypass the gate.

## Publication update — 2026-10-29

- The owner requested commit, push and publication of dimineata.de.
- `dimineata.clasificare_stare` changed from `propus` to `acceptat`.
- `gio.clasificare_stare` changed from `propus` to `ascuns`; it remains unpublished pending review.
- Both classification notes record the reason and date. Other catalogue cells remain unchanged.
- The backlog reminds the owner to check gio’s terms with Gabriel Popa before collection or publication.
- Publication validation and build pass with 141 visible entries. Existing public entries are unchanged.
- Final full suite: 1,102 tests, zero failures or errors, eight skipped (161.125 seconds).
