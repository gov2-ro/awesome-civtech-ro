# Structure curation and skill — 2026-10-30

Status: implemented and independently exercised. The owner accepted all four identity pairs on 2026-10-30.
[Review packet](site-structure-curation/review.json) · [Recipe guide](../STRUCTURE-CURATION.md) · [Skill](../../.agents/skills/profile-structure/SKILL.md)

## Delivered

The project now has an offline curation importer, five reusable recipes and a discoverable `profile-structure` skill.
Recipes supply typed collections, namespaces, URL bindings, API uses and exact evidence locators.
The importer extracts bounded samples, proposes cross-project pairs and preserves owner decisions.
It retains conflicting observations and sample gaps for review instead of inventing missing identifiers.
The review report instantiates typed detail-page templates, while marking those URLs `template-derived`.
A constructed URL does not become a live verification.

The tracked recipes cover `transparenta-eu`, `romania-transparenta`, `registrul-firmelor`, `sicap-ai` and `igov`.
They work from tracked evidence; ignored caches are optional.
`data/taxonomy-v2/structura/decisions.json` records the four explicit owner acceptance decisions.
The report can read it through `--decisions`, without replacing a store's own decision file.

## Measurements

An offline pass selected all 145 catalogue entries in `/tmp/civtech-structure-catalogue`.
Retained documentation was available for 124 entries. Missing caches stayed explicit gaps.
The pass made zero requests, then applied the five curation recipes.

| Measure | Result |
| --- | ---: |
| Projects in the isolated store | 145 |
| Evidence records | 375 |
| Page-pattern declarations or candidates | 77 |
| API operations | 16 |
| Typed identifier rules | 22 |
| Extracted real record references | 11 |
| Generated identity proposals / owner-accepted pairs | 4 / 4 |
| Identity conflicts / failed sample extractions | 0 / 0 |
| Offline discovery requests | 0 |
| Corporate verification requests | 2 |

These are bounded observations, not complete site inventories. The owner accepted the four identity pairs separately.
SICAP has identifier declarations but no real sampled record. Its live host was not requested.
The two corporate verification requests were robots.txt and one public company page on Registrul firmelor.
Both returned HTTP 200. [The journal](site-structure-curation/requests.jsonl) records them.
There were zero forbidden-host requests, browser calls, paid searches or messages to project owners.

## Accepted identity pairs

The owner accepted all four pairs after reviewing this packet.
Generated assertions remain proposals; the review packet applies the four durable acceptance decisions.

| Subject | Shared identifier | Projects | Evidence |
| --- | --- | --- | --- |
| Ministerul Afacerilor Externe | CUI `4266863` | România Transparentă ↔ Transparenta.eu | Retained central-institution data and GraphQL identity sample. |
| A.D.P. BÂRCA S.R.L. | CUI `43721310` | România Transparentă ↔ Registrul firmelor | Retained company data and public company-page identity metadata. |
| Antibiotice SA | CUI `1973096` | igov ↔ Registrul firmelor | igov's local-ID/CUI row and newly checked company-page metadata. |
| Municipiul București, territory | SIRUTA `179132` | România Transparentă ↔ Transparenta.eu | Two territory representations with the same code; separate from the fiscal institution. |

For the first two pairs, both projects have documented detail-page templates.
Antibiotice has a public company page on Registrul firmelor; igov contributes a record in its governance data.
The territorial pair has a România Transparentă page. No distinct Transparenta.eu territory-page URL was established.
The packet distinguishes source locators from template-derived page candidates.
Legal validity periods remain unknown; observation times are retained.

## Real local-ID correspondences

The retained `igov` report provides complete company objects inside a partial JSON read.
The existing `inventory_jsonsample.recover` reader retains complete objects without inventing missing bytes.
Two whitelisted records establish these observed mappings:

| igov local ID | CUI | Company |
| --- | --- | --- |
| `inst_cui-31029694_fbc8ca0d0e` | `31029694` | Active Conexe SA |
| `inst_cui-1973096_89f11b5bc5` | `1973096` | Antibiotice SA |

The [retained extract](site-structure-curation/evidence/igov-company-identifiers.json) keeps only company ID, CUI and company name.
It records the original sample hash, source indices, observation time, partial-document status and extraction method.
The original report also contains people and appointments; none of their values were copied.
The existing confirmed CUI selector supplies the semantic binding for `companies[].cui`.
The opaque `id` is kept in a separate, non-shared `igov:companies:id` namespace.
Its numeric-looking substring is not treated as a separate identifier or parsed to obtain CUI.

The public [Antibiotice identity extract](site-structure-curation/evidence/registrul-firmelor-antibiotice-page.txt) independently identifies CUI `1973096`.
This supports an additional project connection through an actual local-ID-to-CUI observation.
The igov sample remains historical; its live data were not re-requested.

## Skill validation and independent forward test

The skill-creator validator passes using the existing `240826` environment.
The global Python interpreters lack the validator's optional PyYAML dependency; no dependency was added to the project.
The versioned skill is `.agents/skills/profile-structure/`.
A new symlink at `~/.codex/skills/profile-structure` makes it discoverable from the default Codex skill directory.
The existing `add-new-url` skill was not changed.

An independent agent used the skill in `/tmp/profile-structure-forward-test/evaluation/` with only three supplied synthetic files.
The trial's two primary records had the same local ID and name but different self CUIs.
One record also named a supplier whose CUI matched the other project's primary company.

The first trial exposed a real limitation: truthful local file origins were rejected by the recipe importer.
The importer now accepts local file provenance, marks it local-only, and still makes no file-URL network requests.
The HTTP discovery transport remains HTTP(S)-only.
The evaluator retried unchanged recipes after that correction.

Observed result: four subjects, two buyer/supplier relationships, one correct proposed pair, zero conflicts and zero sample gaps.
There was no false primary-company match from the equal local IDs or names.
Leading zeroes remained intact. Reapplication left store.json, decisions.json and requests.jsonl byte-identical.
No synthetic record entered the real recipes or review packet.

## Checks and remaining scope

The focused suites contain 38 curation tests and 56 shared-engine tests, passing on Python 3.12.
Curation also passes on Python 3.15. The full suite passes 1,236 tests with eight skips.
The local OpenAPI parameter resolver now preserves required arguments through local references.
Cycles, missing definitions and external references remain unresolved and prevent probing.

The review packet resolves all cited artifact hashes and recipe aliases offline.
The original version-1 pilot remains unchanged.
All four owner decisions are recorded with their assertion IDs and decision time.
Acceptance does not authorize publication or remove any source restriction.
Further unsampled sources, composite record extraction and browser-specific routes remain future expansion work.
