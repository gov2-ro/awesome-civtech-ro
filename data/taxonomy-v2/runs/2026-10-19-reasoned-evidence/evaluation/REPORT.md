# Evaluation of the frozen classification candidate

Run: `2026-10-19-reasoned-evidence`. Target: `2.0.0-draft.2`. Source mode: `retrieved_evidence`.

All 122 original entries have a separate schema-valid response. The candidate is a proposal, not an accepted catalogue.
The classification contains 105 classified records, 16 partial records, and one valid abstention: `incentru`.
No entry required an intervening manual decision. Existing data and production code remain unchanged.

## Outputs

- Candidate CSV: [intrari-candidate.csv](../candidate/intrari-candidate.csv).
- Candidate JSON: [catalogue-candidate.json](../candidate/catalogue-candidate.json).
- Exact schema responses: [results.jsonl](../results.jsonl), with one object per line.
- Per-entry input and output: `../requests/<slug>.json` and `../responses/<slug>.json`.
- Review queue: [review-queue.json](../candidate/review-queue.json).
- Vocabulary gaps: [vocabulary-gaps.json](../candidate/vocabulary-gaps.json).
- Evaluation metrics: [summary.json](summary.json).

The CSV preserves every consolidated input field verbatim. All candidate rows have `clasificare_stare=propus`.
The JSON retains the original record alongside its complete classification response.
The CSV is a staging export. It is not the production or draft.1 import format.
The abstention must remain outside canonical import. Partial records require resolution before a later acceptance decision.
The review queue contains 23 records with partial results, an abstention, or explicit conflicts.
Optional maturity unknowns and unspecified attribution roles remain in every affected response.

## Protocol and freezing

The run copied `clasificare-input.csv`, the classifier prompt, its JSON Schema, and the area list before classification.
It read all concept definitions and parent relationships. It did not use the v1 crosswalk to generate decisions.
The run-local vocabulary contains 128 concepts and 11 areas. All concepts remain proposals.
It replaces the draft.1 prototype definition and adds the three missing stages:

| ID | Definition used |
| --- | --- |
| `maturitate:experiment` | Explores an approach; practical use is not established. |
| `maturitate:prototip` | Demonstrates intended functionality. |
| `maturitate:pilot` | Limited deployment or trial in real conditions. |
| `maturitate:operational` | Offered for ordinary use by its intended audience. |

The run copied code values from the existing structural contract into its own `valori.csv` and vocabulary envelope.
CSV labels mirror code strings. They are not reviewed translations. Empty availability sentinels remain in the vocabulary envelope.
The non-empty code rows in `valori.csv` do not implement the shared draft.2 package.
The production and isolated shared vocabulary files were not changed.
No proposed new concept entered a classification field.

`intrari.csv`, `revizuire.csv`, and `atribuiri-initiale.csv` were withheld until the candidate passed validation and received a hash seal.
Preparation hashed existing files for the non-mutation audit. Their withheld text was not exposed during that operation.
Evaluation first opened their records after sealing. The seal covers inputs, vocabulary, decisions, responses, and candidate exports.
The seal timestamp is `2026-10-19T15:04:06.928166+00:00`.
The evaluation timestamp is `2026-10-19T15:07:24.063722+00:00`.
Every sealed hash still matches. Evaluation did not change the candidate.

## Execution and evidence

The assistant used its own reasoning for each entry. `decisions.tsv` records those explicit decisions.
`assemble.py` serializes them into separate schema responses. It does not infer categories from keyword rules.
This was direct session work, not a deployed inference runner or 122 isolated external API calls.
The manifest records the available model identity and these execution limits.
Exact backend model ID, sampling settings, seed, and per-entry token usage are unavailable. None were invented.
The prompt block was retained verbatim. The required JSON format governs each persisted response.

The original consolidated CSV supplied the editorial evidence. Legacy labels remained weak historical claims.
Public retrieval supplied evidence to 28 entries from 26 selected public sources.
The raw retrieval ledger has 119 source records: 95 text results, 22 failures, and two empty pages.
These are returned source records, not unique HTTP requests. Repeated fetches and search results are counted separately.
Only entry-relevant sources were placed in classification requests. Unrelated search results remain outside those requests.
A failed or empty fetch was not interpreted as proof of closure.
The retrieval date records when the tool returned content. The raw capture preserves any older crawl or publication date.
There is no `local_only` control arm. Retrieval improvements cannot be measured causally from this run.

Notable evidence changes include:

- EFOR identifies `7-ani-de-acasa` as voter education, supporting a governance primary subject.
- The careers page identifies job descriptions and career planning, supporting employment rather than generic civic education.
- The democracy school describes courses for teachers, supporting a course format rather than an assumed game.
- The corruption museum launch describes a gallery and quiz. The candidate does not treat fictional examples as criminal records.
- The court page supports performance comparisons. Its legacy AI tag remains unsupported.
- The diaspora page describes polling stations abroad. The countries remain unspecified.

## Deterministic validation

| Check | Result |
| --- | --- |
| Original entry coverage | 122/122 |
| JSON Schema validity | 122/122 |
| Distinct original slugs | 122 |
| Justified positive assignments | 1439 |
| Citation references checked | 2363 |
| Unknown or retired assigned IDs | 0 |
| Missing topic ancestors | 0 |
| Missing or duplicate assignment justifications | 0 |
| Broken source IDs, locators, or exact excerpts | 0 |
| Original attribution atoms preserved | 86/86 |
| Unresolved identity literals | 66 |
| Newly asserted typed attribution roles | 0 |
| Existing file hashes checked | 495 |
| Existing files changed | 0 |

Citation validity checks exact excerpts, source membership, and locators. It does not establish semantic entailment.
The original attribution cells split into 86 names or organisations. Twenty match supplied identities exactly.
The other 66 remain literal names. Similar names and acronyms were not silently merged.
All roles remain `atribuit_in_sursa`. Confidence does not express legal verification or editorial acceptance.

The four-stage vocabulary is complete. The evidence supports one prototype and 29 operational proposals.
The other 92 maturity fields are null. No entry was forced into experiment or pilot to populate every stage.
Five entries explicitly describe AI in operation. One describes an offered mobile application.
No candidate claims an offered MCP server on the supplied evidence.
A repository, an `.ai` name, a legacy tag, or linked projects did not establish these technologies.

## Comparison with the withheld proposal

The baseline contains 122 entries, 66 review items, and 822 initial assignment rows.
It is a draft proposal, not ground truth. Agreement measures overlap, not correctness.
The baseline follows draft.1 maturity rules; the new run follows the agreed four-stage rules.
There are 283 differing entry-field pairs among 1,586 comparisons.

| Field | Exact agreement | Different entries |
| --- | --- | --- |
| tip_entitate | 121 | 1 |
| subiect_principal | 116 | 6 |
| subiecte | 90 | 32 |
| teme | 76 | 46 |
| scopuri | 69 | 53 |
| functionalitati | 75 | 47 |
| formate | 87 | 35 |
| tehnologii | 121 | 1 |
| institutii_vizate | 104 | 18 |
| tip_organizatie | 118 | 4 |
| maturitate | 92 | 30 |
| nivel_acoperire | 117 | 5 |
| arii_acoperite | 117 | 5 |

List comparison ignores order and deduplicates values. Both empty sets count as exact agreement.
`field-metrics.json` includes mean Jaccard overlap and assignment totals for each list field.
The full comparison is [field-disagreements.csv](field-disagreements.csv).

Six primary subjects differ:

| Entry | Baseline → candidate | Interpretation |
| --- | --- | --- |
| `7-ani-de-acasa` | Civil society → governance | Publisher evidence identifies election education. |
| `data-expertforum` | Digital society → public finance | Data content concerns public spending and elections; the primary emphasis remains debatable. |
| `hoover` | Media → digital society | The description identifies a general document search engine. Its journalistic context is not its only capability. |
| `incentru` | Civil society → null | The original fields do not establish a subject. Uncertain search identity was not merged. |
| `jailando` | Governance → law and justice | The description establishes convictions, without establishing that all offences concern corruption. |
| `apti-unelte-democratie` | Digital society → governance | This is a primary emphasis difference. The candidate retains digital society as secondary. |

Four differences replace the baseline root. One changes primary emphasis while retaining the old root.
One is an abstention. These categories are not interchangeable with classification errors.
The other subject-list differences can add legitimate secondary subjects or omit unsupported associations.
The field-level file marks additions, omissions, and mixed membership separately.
Of the 822 initial assignment rows, 718 have the same field and concept in the candidate.
That overlap is not an accuracy estimate.

The existing review comparison retains all 66 items and indicates whether public evidence was supplied.
It does not mark those items accepted or resolved. The original review table remains untouched.

## Semantic spot-check and remaining concerns

After sealing, the assistant examined 27 varied entries against their evidence and the withheld baseline.
See [semantic-sample.csv](semantic-sample.csv). This is an assistant review, not an independent human audit.
The sample spans sparse records, organisations, publications, maps, disputed AI, attribution, geography, and maturity.
No calibrated precision or error rate is claimed from this selected sample.

Three concerns remain in the frozen candidate:

1. **Data EFOR:** the complete retrieved source includes media datasets and data about Moldova.
   The chosen excerpt does not support the media root separately. Its inherited national scope also needs refinement.
2. **Jailando:** the convictions subject is supported. The register format relies mainly on its historical type.
   The candidate marks the record partial and gives that assignment low confidence.
3. **PressPay:** financing independent publications is explicit. `scop:sprijin-organizatii` names civic organisations in its definition.
   That purpose may be too narrow for every publication. A press-sustainability purpose could express the outcome more precisely.

These findings are evaluation results. They did not feed back into the sealed responses.
A later accepted dataset should address them before import.
Other retained limits include weak legacy format evidence, inherited editorial geographic claims, and unresolved historical availability.
The 29 operational values are evidence-based proposals, often inferences from concrete service workflows.
They do not prove adoption, reliability, maintenance, or current availability through an independent functional test.

## Vocabulary gaps

Seven concept proposals remain outside the frozen vocabulary:

- Sensor networks: `aerlive`.
- Calendar: `reciclare-arad`.
- Document signing: `econtractauto`.
- Citizenship authority: `monitor-cetatenie`.
- Scenario simulation: `sondaje-romania`.
- Geographic information: `proiecte-geo-spatial`.
- Agriculture and rural development: `crpe`.

Two area proposals cover Eastern Europe and the Republic of Moldova.
The exact diaspora country list remains an uncertainty; the run did not invent an aggregate area ID.
The semantic review adds a possible press-sustainability purpose for later vocabulary work.
It remains an evaluation suggestion, outside the candidate's seven schema proposals.

## Handoff for later implementation

Use the sealed dataset as a reproducible candidate for review and preview. Keep every imported proposal in `propus`.
Do not treat `classified` as editorial acceptance. Keep the abstention and partial records available for review.
Resolve the three semantic concerns before accepting those fields.
Use source identity to preserve availability overrides, contacts, and notes excluded from the consolidated input.
The run does not reconstruct those fields or overwrite them from model output.

Implement the draft.2 package, source-preserving adapter, and normal runner separately.
The run-local Python files are serialization, validation, and evaluation aids, not production implementation.
Production validation and build were not run because this task changes neither production data nor code.
The run-specific JSON Schema, citation, hierarchy, preservation, and hash checks all pass.
No commit, tag, version bump, deployment, or release was made.
