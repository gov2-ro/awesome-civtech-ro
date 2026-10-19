# Frozen reclassification experiment

Start with [the evaluation report](evaluation/REPORT.md).
The candidate tables are in [candidate/](candidate/).

The run uses 122 original records and a frozen vocabulary with four maturity stages.
All outputs remain proposals. Existing data and production code are unchanged.

- `manifest.json`: execution identity, source mode, and preparation hashes.
- `frozen/`: original input, exact prompt and schema, vocabulary, areas, and code values.
- `requests/`, `responses/`: one complete input envelope and schema object per original slug.
- `results.jsonl`: all 122 schema objects, one per line.
- `candidate/`: preserved source fields, candidate facets, review queue, and vocabulary gaps.
- `evidence/`: raw web-tool results and retrieval ledger, including failed or irrelevant results.
- `validation.json`: deterministic checks and measured counts.
- `classification-seal.json`: hashes written before withheld evaluation material was read.
- `evaluation/`: baseline comparisons and semantic review. These never overwrite the candidate.

`prepare.py` and `assemble.py` document preparation and serialization. Do not rerun them over this frozen run.
`check.py` requires the existing `jsonschema` package. It can recheck the candidate without regenerating it.
`evaluate.py` checks the seal and writes evaluation files only.
`write_report.py` renders the report from the evaluated results.
The Python files do not implement an automated production inference runner.

The candidate preserves the consolidated input exactly. Availability overrides, contacts, and notes are outside that input.
A later adapter must preserve those fields from their original source records.
