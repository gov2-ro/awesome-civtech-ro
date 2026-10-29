# Brief: site structure pilot

Date: 2026-10-30. Status: completed bounded pilot; [report](../reports/site-structure-pilot/README.md).
Authority: owner requested pilot execution on 2026-10-30 ("let's move forward").
Contract: [site-structure-profiler.md](../specs/site-structure-profiler.md).

## 1. Goal

Test the provisional contract on four projects before building a general engine or a skill.
Find how collections expose records through pages and APIs.
Record shared and local identifiers with their subject roles.
Demonstrate possible correspondences only when evidence supports them.

## 2. Read first

- `AGENTS.md`, `docs/BACKLOG.md` and `docs/ACTIVITY.md`.
- The linked spec, especially the distinction between access patterns and identity assertions.
- `docs/DATA-SCHEMA.md`: documentation collection, inventory evidence, forbidden hosts and person data.
- `data/taxonomy-v2/colectare-interzisa.csv`.
- Existing documentation and inventory records for the four slugs below.
- `docs/briefs/inventory-expansion.md` and `docs/briefs/inventory-readers-persons.md` for evidence practices.

Use local evidence before making requests. Existing evidence may be historical or incomplete.
No new observation is implied by the examples in this brief.

## 3. Projects and supplied leads

| Catalogue slug | Project URL | Owner-supplied detail-pattern candidate |
| --- | --- | --- |
| `transparenta-eu` | https://transparenta.eu/ | `/entities/{CUI}` |
| `sicap-ai` | https://sicap.ai/ | `/autoritate/{CUI}` |
| `registrul-firmelor` | https://registru.horecaos.org/ | `/firma/{CUI}` |
| `romania-transparenta` | https://romaniatransparenta.eu/ | `/registre/administratia-centrala/{CUI}` |

Treat all supplied patterns as leads until the pilot records supporting evidence.
Do not assume that all collections use CUI or cover the same organisations.
Inspect both local identifiers and external identifiers when they coexist.

`sicap.ai` and its subdomains are blocked by the repository's collection policy.
Make zero requests to them, including through a browser.
Inspect the existing owner-saved OpenAPI evidence and retained public-repository sources first.
The repository `ciocan/SICAP.ai` is a known source; fetch only relevant files at a recorded commit when needed.
A source declaration proves neither that the deployed route exists today nor that authentication is unnecessary.
Report unsupported SICAP findings as unknown; do not replace the project with another site.

## 4. Limits

- At most 30 network requests per project, and 100 across the pilot.
- Attribute repository requests and third-party API requests to the project they serve.
- Count redirects, retries, browser documents and browser subresources as requests.
- Use at most one in-flight request per host, with at least one second between requests.
- Apply a 20-second request timeout, a 2 MiB body cap and at most five redirects per fetch.
- Fetch at most three sitemap documents per project. Inspect at most 200 detail URLs from them.
- Retain up to three distinct examples per pattern and at most ten organisation/institution record references per project.
- Test at most two pages of any API listing. Never increase page size to discover the server's maximum.
- Use at most two browser navigations per project, within the same network budget.
- Use no paid search or API credentials. A missing capability is an explicit unchecked item.
- Permit at most two domain-search queries per project through an available free search tool.
  Record each query as one request and attribute subsequent result fetches separately.
- Stop requests on the host conditions in spec section 4. Import evidence rather than bypassing a block.

Discover API hosts from links, documentation, source code or observed page calls.
Do not probe an arbitrary list of speculative API paths.
A browser must block forbidden hosts before dispatch and stop new requests when its remaining budget is exhausted.
If the available browser cannot do that, skip it and record the limitation.

## 5. Work and outputs

1. Inventory reusable local evidence and record its dates, revisions and limitations.
2. Create the four profiles under `docs/reports/site-structure-pilot/profiles/`.
3. Inspect listings, detail routes, search, pagination, downloads and API operations within the limits above.
4. Record extraction rules for identifiers, including namespace and subject role.
5. Check a few real organisation/institution records against those rules.
6. Write `correspondences.json`, `decisions.json`, `requests.jsonl` and the report under the same pilot directory.
7. Add `scripts/check_structure_pilot.py`, a stdlib-only offline checker for this pilot contract.
8. Add focused offline tests for the failure cases below. Use synthetic fixtures for identity edge cases.
9. Record the measurements and update the backlog and activity log.

Small evidence acquisition helpers are allowed under the pilot directory or a scratch directory.
Do not implement the general engine, edit existing collectors, add dependencies or change the public build.
If the contract cannot express an observed case, record the evidence and propose the smallest amendment before continuing that case.
Continue independent profiles when one project has a blocker.

The checker validates required fields, types, enums, unique keys, references, budgets and evidence locators.
It verifies tracked evidence hashes and excerpt locations, plus the shape of references to existing inventory evidence.
It makes no network request. It must never accept an editorial identity decision on behalf of the owner.
Document its exact invocation and any contract amendment in the report.

## 6. Acceptance checks

Use these names in the pilot report and tests where applicable:

| Check | Passing evidence |
| --- | --- |
| `SP01-four-profiles` | Four profiles exist. Blocked or partial profiles retain their reasons and unchecked checks. |
| `SP02-pattern-basis` | Each template has two examples or an explicit documented/source route definition. |
| `SP03-api-evidence` | Each operation distinguishes documentation, browser observation and independent testing. Unknowns remain explicit. |
| `SP04-identifier-role` | Identifier rules name namespaces and subjects; a buyer or supplier ID never identifies the enclosing contract. |
| `SP05-local-to-shared` | Demonstrate a real local-to-shared mapping if exposed; otherwise record which checked sources lacked one. |
| `SP06-correspondence` | Demonstrate a real pair if supported. Otherwise report the missing evidence and exercise the format with a synthetic fixture. |
| `SP07-no-false-identity` | Reject automatic acceptance based on names, bare numeric equality, shared hosts or incompatible subjects. |
| `SP08-policy-and-budget` | Zero forbidden-host requests. Request counts include redirects and browser traffic; exhaustion is partial. |
| `SP09-evidence-integrity` | The offline checker resolves keys, evidence hashes, excerpts and artifact references. Broken references fail. |
| `SP10-refresh-preservation` | A synthetic failed refresh preserves earlier findings and decisions while marking stale evidence. |

Do not manufacture matches or endpoints to satisfy the pilot.
`SP05` and `SP06` can pass through an evidenced limitation, but the report must label their live demonstration as unavailable.
Synthetic fixtures demonstrate the contract, never a live correspondence.
`decisions.json` stays empty unless the owner explicitly supplies decisions during the pilot.

Run the checker, its focused tests and `python3 scripts/validate.py`.
Run `python3 scripts/build.py` after a script change, as required by repository guidance.
Inspect generated differences before committing; exclude unrelated timestamp changes.
Do not add public profile pages or change the inventory's reviewed groups.

## 7. Report and next decision

Report each project's collections, patterns, operations, identifier namespaces, mappings, conflicts and blockers.
Compare coverage and roles for any shared identifier.
Give direct, browser and search request counts, retained example counts and offline check results.
Separate measured findings from supplied leads, inferences and historical evidence.
List every unperformed check and explain its cause.

Finish with schema amendments, reusable discovery rules and the proposed scope of the shared engine.
Keep engine implementation, the onboarding skill, bulk resolution and public presentation as separate backlog items.
