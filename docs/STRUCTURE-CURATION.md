# Structure curation recipes

Curation records what a project's paths and fields identify.
The offline importer applies those declarations to an isolated structure store and proposes cross-project links.
It does not accept identity decisions or make network requests.

## Apply the retained recipes

```sh
python3 scripts/curate_structure.py apply --out /tmp/curated-structure \
  --recipe data/taxonomy-v2/structura/recipes/igov.json \
  --recipe data/taxonomy-v2/structura/recipes/transparenta-eu.json \
  --recipe data/taxonomy-v2/structura/recipes/romania-transparenta.json \
  --recipe data/taxonomy-v2/structura/recipes/registrul-firmelor.json \
  --recipe data/taxonomy-v2/structura/recipes/sicap-ai.json
python3 scripts/profile_structure.py --out /tmp/curated-structure --check
python3 scripts/curate_structure.py report --out /tmp/curated-structure --json
```

The recipe selection above reproduces the original curation set from tracked pilot excerpts.
That set produces eleven record references and four correspondences, including two igov local-ID-to-CUI mappings.
Five expansion recipes add sixteen records and 26 proposed pairs. See the [expansion report](reports/site-structure-batch-f.md).
The [institution/territory expansion](reports/site-structure-batch-g.md) adds five more recipes, 22 records and thirteen proposed pairs.
All fifteen recipes work without ignored caches or live sites.
SICAP contributes declarations, not real sample records; its live host remains blocked.
The [curation report](reports/site-structure-curation.md) records the evidence and remaining questions.
The [structure preview](STRUCTURE-PREVIEW.md) shows those observations in project profiles and an exact entity lookup.

## Recipe fields

A recipe has `schema_version: 1`, an `id`, a catalogue `project_slug` and the catalogue `input_url`.
The engine's generated store remains schema version 2.
Use the existing recipes as complete executable examples.
All collection and namespace declarations remain proposed interpretations, supported by their cited evidence.

| Field | Meaning |
| --- | --- |
| `evidence` | Source aliases, URLs, observation times, artifact paths, SHA-256 values and exact locators. |
| `collections` | Stable IDs, Romanian labels, subject types, record grain, identity components and evidence aliases. |
| `namespaces` | Stable IDs, issuer, scope, `shared`, `normalization` and evidence aliases. |
| `patterns` | URL templates, collections, variables with locations/namespaces, and supporting evidence. |
| `identifier_rules` | Collection, namespace, field location, subject role, mapping basis and evidence aliases. |
| `operations` | Method, template, collection uses, declared/observed security, parameters and evidence aliases. |
| `samples` | Bounded extraction instructions for real record references, not literal invented identifier values. |
| `relationships` | Named edges between successfully extracted sample IDs, with supporting evidence. |

Each claim's `evidence` list names aliases from the recipe's evidence list.
Evidence artifact paths are relative to the recipe file.
An artifact must stay within the recipe directory or this repository and cannot be a hidden file.
The importer checks the complete artifact hash before extracting its fragment.
Files have a 2 MiB cap; cited fragments have a 64 KiB cap.
An observation time needs a timezone and cannot be in the future.
When a public origin is unknown, use a truthful `file://` URI with an empty host or `localhost`.
The offline importer marks that evidence local-only and exposes it in the review report.
It never fetches file URLs. Do not invent an HTTP origin to fit the discovery command.
The importer retains source and extraction provenance in the generated evidence.

A text evidence locator has `type: text`, `start`, `end` and an exact `excerpt`.
A JSON evidence locator has `type: json_pointer` and an RFC 6901 `pointer`.
Sample extractors operate inside that selected fragment, not elsewhere in the artifact.
A regex extractor has `type: regex` and a `pattern` with a named group `(?P<value>...)`.
It must produce one distinct value; repeated occurrences of that same value are allowed.

## Identifiers and samples

A namespace declaration explicitly sets `shared: true` or `false`.
A shared namespace needs a consistent issuer across projects before a value can produce a correspondence.
The importer currently supports `normalization: identity` only.
It preserves leading zeroes and does not remove `RO`, punctuation or other prefixes.
Other normalization rules need their own documented support before implementation.

Identifier roles include `self`, `buyer`, `supplier`, `parent`, `associated_territory`, `located_in` and `administers`.
A sample can only use self rules for its own collection.
A related subject can have its own collection and sample, then an explicit relationship.
A contract cannot use CUI as its own identifier.
Registrations and financial-year records need a grain distinct from their parent company.
The first sample importer handles scalar local keys; composite record extraction remains future work.

Here is a sample instruction for a JSON evidence fragment:

```json
{
  "id": "organisation",
  "collection": "companies",
  "local_namespace": "project:companies:id",
  "identifiers": [
    {
      "rule": "local-id-self",
      "source": "record-response",
      "extractor": {"type": "json_pointer", "pointer": "/id"}
    },
    {
      "rule": "cui-self",
      "source": "record-response",
      "extractor": {"type": "json_pointer", "pointer": "/cui"}
    }
  ]
}
```

The named rules and evidence alias must exist in the same recipe.
A sample's `local_namespace` must occur among its self identifiers.
A recipe can extract at most ten samples.
Null, boolean and floating-point identifiers become sample gaps.
An unknown or ambiguous value does not create a record.

## Proposals, conflicts and owner decisions

The importer keeps stable project/collection/local-namespace/local-value record keys.
It proposes pairs between different projects when subject types, shared namespaces, issuer and identifier values agree.
It never proposes a match from a name alone or equal IDs in different local namespaces.
One correspondence is a territory-to-territory SIRUTA pair, not a fiscal-institution-to-territory identity claim.

Repeated application is idempotent. Existing record keys and assertions survive.
A local key observed with a different self identifier creates an identity conflict.
The earlier value and both evidence sets remain available. The record cannot produce new identity proposals until reviewed.
Existing accepted decisions remain owner decisions; the report adds the conflict flag without changing that decision.
A later successful extraction resolves a prior sample gap while retaining its history.

`decisions.json` belongs to the owner. The importer never replaces its bytes.
The review report combines the current proposals with those decisions; it does not write decisions.
Complete independent source work before presenting the owner with the remaining identity questions.

## Durable owner decisions

The repository owner file is `data/taxonomy-v2/structura/decisions.json`. It records four pairs accepted on 2026-10-30.
Only explicit owner decisions add or change rows with `assertion_id` and `state` (`accepted`, `rejected` or `deferred`).
Keep a note and decision time with each real decision. The importer never writes this file.

```sh
python3 scripts/curate_structure.py report --out /tmp/curated-structure \
  --decisions data/taxonomy-v2/structura/decisions.json --json
```

Decisions outside the selected store appear under `unapplied_decisions`; they are not silently discarded.
The generated report includes typed profile URL candidates and distinguishes them from source locators.
A derived URL is not proof of a live record or permission to publish an identity link.
