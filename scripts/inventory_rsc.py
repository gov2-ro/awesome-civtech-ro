"""Reader for the data that a Next.js page embeds in its flight payload (`*.txt?_rsc=...`). Stdlib only.

Format name: `rsc-json`. A Next.js app answers a client-side navigation with lines `ID:VALUE`. A line that holds a React element
`["$", tag, key, props]` carries the page data in `props` (for example `{"bills": [...], "mpCount": 471}`).
The reader parses each line that is a JSON array or object, keeps the elements whose `props` is an object, and returns the largest `props`.
It parses JSON only. It never runs a script and never guesses: a payload with no such element is an error (state `eroare-parsare`).
Fields come from the plain observed-fields walk of `inventory.observed_fields` on that document, so a source with persons keeps key names,
paths and types only (the mark `persoane`; see inventory_persons). `stare_tip` is `observat-in-esantion-json`.
"""
from __future__ import annotations

import json

FORMAT = 'rsc-json'


def extract(body):
    """The largest `props` object of the flight payload `body`. Raises ValueError when no line carries one."""
    best, size = None, -1
    for line in body.split('\n'):
        _, colon, payload = line.partition(':')
        if not colon or payload[:1] != '[':
            continue
        try:
            value = json.loads(payload)
        except ValueError:
            continue
        if isinstance(value, list) and len(value) == 4 and value[0] == '$' and isinstance(value[3], dict) and len(payload) > size:
            best, size = value[3], len(payload)
    if best is None:
        raise ValueError('The payload has no React element with an object of properties')
    return best
