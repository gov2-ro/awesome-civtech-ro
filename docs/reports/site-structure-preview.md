# Site structure and entity lookup preview — 2026-10-30

The local preview now joins the measured structure work to the catalogue's project profiles.
The standalone entity lookup uses the same observations and explicit owner decisions.
[Build and usage guide](../STRUCTURE-PREVIEW.md).

## Delivered

`build.py --with-structure` replays five retained recipes offline.
`--structure-store` can instead project a checked discovery store without changing it.
Both modes require an isolated v2 preview and preserve the public build's payload contract.

Each profiled project shows sections and collections, URL patterns, API declarations and source receipts.
A section link needs an exact listing URL; a collection alone does not establish a website section.
An API's documented access and observed enforcement remain separate.
The page never invokes an endpoint.

The entity lookup searches CUI, SIRUTA, EUID ONRC and igov local IDs.
It shows exact observed values, source dates and accepted direct correspondences.
An arbitrary CUI without a sampled record produces no result, even when a project declares a compatible URL template.
This is a bounded lookup over retained observations, not a bulk registry or live federation.

## Measurements

| Measure | Tracked recipes | Existing catalogue discovery store |
| --- | ---: | ---: |
| Selected catalogue entries | 141 | 141 |
| Projects with structure observations | 5 | 141 |
| Sections or data collections | 16 | 25 |
| URL patterns | 19 | 77 |
| API operations | 16 | 16 |
| Observed record references | 11 | 11 |
| Accepted direct correspondences | 4 | 4 |
| Lookup namespaces | 4 | 4 |
| New source-project requests | 0 | 0 |

The broader store includes projects with empty structure findings.
An included project does not imply a complete inventory or fresh source access.
The default preview works from tracked files alone.
The broader store remains an optional, local measurement artifact.

## Checked behaviour

The projection suite covers exact identifier preservation, issuer/local scope separation, hidden endpoints, changed project URLs and conflicts.
Equal collection labels retain distinct section and API scopes through stable collection IDs.
It also covers unsafe URLs, local source receipts, owner-decision validation and source-store immutability.
An isolated real-recipe build is reproducible and offline.
A later plain build removes the lookup output and structure payloads.

All 16 focused tests pass on Python 3.12. All 24 new browser acceptance checks and 141 existing catalogue checks pass.
The final full suite passes 1,252 tests with eight skips.
The browser verifies the Antibiotice and MAE pairs, the igov local ID, the territory distinction and exact leading zeroes.
It also verifies deep links, Back, Reload, unknown namespaces, failed-load retry and one-hop accepted expansion.
Mobile lookup and project profiles have no horizontal overflow at 390 pixels.
Screenshots were inspected locally; no browser request reached a project host.

## Decisions and remaining scope

The owner requested the lookup prototype and structure details in the existing site profile.
The flag keeps this deliverable reviewable before a publication decision.
No catalogue classification, identity decision or health observation changed.
The accepted pairs remain in the durable owner file.

The project profile uses inline structure data; the lookup loads its own compact payload.
This keeps drawer rendering synchronous and limits the lookup data request to its own page.
A future larger inventory may need per-project loading.

Broader identifier mappings and the 21 documentation gaps remain separate backlog items.
Live entity federation, bulk harvesting, transitive resolution and public cross-links remain outside this preview.
