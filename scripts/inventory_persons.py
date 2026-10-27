"""Sources whose body holds records about natural persons. Stdlib only. It makes no request.

A source specification (`observatii/inventare/adaugari/*.json`) and a render specification (`*-randare.json`) accept the key `persoane: true`.
The registry keeps the mark (`descoperiri.json`) and the source record carries it (`seturi-date.json`). The only allowed value is `true`.

What the mark changes:

- The readers keep key names, paths, observed types and counts only. A reader of a marked source is `csv`, `json` or `json-esantion`; every other
  reader copies text (a description, an enumeration, an example) and is refused. A field record keeps the keys of `FIELD_KEYS` and no other.
  The rows above a CSV header keep a cell only when it is a key name (an identifier such as `perf_2015`); a title or any other text is dropped.
- A specification cannot quote the body of a marked source (`inventory.resolve_spec`): the registry stores the quoted fragment.
- The note of a marked specification replaces the note of its registry record, so a value that an earlier note quoted can leave the tracked file.
- `inventory.py --check` looks for the values of each retained body in the tracked files that the inventory and its editors write, and prints a
  fingerprint (the first 8 hex digits of the SHA-256 of the value) for each one found. It never prints a value.

What the check looks for, and why not everything:

- A value is a string of a JSON body, or a data cell of a CSV body, of 4 characters or more. A key name, a CSV header cell and a text that the
  address of the source already holds are not values.
- Only a value that identifies is looked for: a text with a space (a name, an address, a title, a free text), an e-mail address, a date with a time,
  or a string of 10 digits or more (a CNP has 13, a phone number 10). A single word cannot be told from a label (a role, a type, a country, a street kind, an
  identifier of a map object), and the label is in many files that no reader wrote. The structure keeps single words out (`FIELD_KEYS`); the check
  does not look for them. A name that sits alone in a cell is therefore a known gap of the check, not of the readers.
- A value that a retained body of an unmarked source holds too (a county, a town, an institution) is common data and is not a leak.
- The match is a whole-word match, so a number does not hit the inside of a hash.
- The files are those that the inventory writes or that its editors write about it (`scope_files`). Search results, frozen packages and the pages
  that the collector keeps are not in the scope: no reader of the inventory writes them.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from inventory_jsonsample import FORMAT as JSON_SAMPLE, recover
from inventory_sheet import delimiter, settings

MARK = 'persoane'
READERS = ('csv', 'json', JSON_SAMPLE)
# The keys that a field record of a marked source may keep: a name, a path, a type, a role, a position and a count.
FIELD_KEYS = frozenset({'nume', 'cale', 'tip_declarat', 'tipuri_observate', 'stare_tip', 'rol', 'pointer', 'coloana_csv', 'numar_chei', 'numar_elemente'})
# The keys that a source record of a marked source may keep. None of them holds a value of the body.
SOURCE_KEYS = frozenset({'url', 'final_url', 'http_status', 'fetched_at', 'content_type', 'state', 'id', 'campuri', 'completitudine', 'snapshot', 'sha256',
                         'format', 'stare', 'limita_atinsa', 'baza_tipului', 'citire', 'ultima_incercare', 'versiuni_anterioare', 'partial', 'antet',
                         'esantion', 'persoane', 'origine', 'salvat_la', 'nume_fisier', 'sha256_fisier', 'nota_copie', 'via', 'redactari', 'error'})
MIN_VALUE = 4
NAME_CELL = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]*$')
TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}')
LONG_DIGITS = re.compile(r'\+?\d{10,}')
SCOPE = ('observatii/inventare/*.json', 'observatii/inventare/*.csv', 'observatii/inventare/adaugari/*.json', 'observatii/inventare/randare/*.json',
         '*.json', 'integrare/*.csv')
DOCS_SCOPE = ('*.md', 'reports/*.md', 'briefs/*.md')


def mark_errors(record, where):
    """The mark must be `true` or absent. Any other value (`false`, a text, a number) is an error, so that a typo cannot leave a body unmarked."""
    if MARK in record and record[MARK] is not True:
        return [f'{where}: `{MARK}` accepts only the value true']
    return []


def is_marked(record):
    return record.get(MARK) is True


def safe_fields(fields):
    """The field records of a marked source, with the keys of `FIELD_KEYS` only."""
    return [{key: value for key, value in field.items() if key in FIELD_KEYS} for field in fields]


def safe_header(facts):
    """The CSV header facts of a marked source. A cell above the header stays only when it is a key name; any other text is a value."""
    return {**facts, 'randuri_deasupra': [
        {'rand': row['rand'], 'celule': [cell if NAME_CELL.match(cell['valoare']) else {'celula': cell['celula']} for cell in row['celule']]}
        for row in facts.get('randuri_deasupra', [])]}


def problems(source):
    """What a tracked record of a marked source holds that it must not. The messages name keys and the address, never a value."""
    where, found = source.get('url', '?'), []
    if source.get('stare') == 'analizat' and source.get('format') not in READERS:
        found.append(f'{where}: a source with persons is read as {", ".join(READERS)}, not {source.get("format")}')
    found += [f'{where}: the source record has the key {key}' for key in sorted(set(source) - SOURCE_KEYS)]
    for field in source.get('campuri', []):
        found += [f'{where}: field {field.get("cale")} has the key {key}' for key in sorted(set(field) - FIELD_KEYS)]
    for row in (source.get('antet') or {}).get('randuri_deasupra', []):
        found += [f'{where}: the header row {row["rand"]} keeps the text of cell {cell["celula"]}' for cell in row['celule']
                  if 'valoare' in cell and not NAME_CELL.match(cell['valoare'])]
    return found


# --- the values of a body ----------------------------------------------------------------------------------------------

def leaves(value, keys, found):
    """Collect the string leaves of a parsed JSON value into `found` and every object key into `keys`."""
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            leaves(child, keys, found)
    elif isinstance(value, list):
        for child in value:
            leaves(child, keys, found)


def body_values(body, format_name, hint=None):
    """(values, names): the string values of a retained body and its key names. A JSON key and a CSV header cell are names, also a row above the header."""
    values, names = set(), set()
    if format_name in ('json', JSON_SAMPLE):
        document = recover(body)[0] if format_name == JSON_SAMPLE else json.loads(body)
        leaves(document, names, values)
    elif format_name == 'csv':
        options = hint if isinstance(hint, dict) else {}
        try:
            row = settings(options)[0]
        except ValueError:
            row = 1
        separator = delimiter(options)
        text = body.lstrip('﻿')
        if not options:
            try:
                separator = csv.Sniffer().sniff(text[:20000], delimiters=',;\t').delimiter
            except csv.Error:
                separator = ','
        for number, record in enumerate(csv.reader(io.StringIO(text), csv.excel, delimiter=separator), 1):
            (names if number <= row else values).update(record)
    return values, names


def identifies(value):
    """True for a text that can name or locate a person: it has a space, an e-mail address, a date with a time, or 10 digits or more."""
    return bool(re.search(r'\s', value) or '@' in value or TIMESTAMP.search(value) or LONG_DIGITS.fullmatch(value))


def candidates(values, names, url=''):
    """The values that the check looks for, sorted so that two runs give the same list."""
    return sorted(v for v in (value.strip() for value in values) if len(v) >= MIN_VALUE and v not in names and v not in url and identifies(v))


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def occurs(value, text):
    """A whole-word match: the characters next to the value are not letters, digits or an underscore."""
    start = text.find(value)
    while start >= 0:
        before, after = text[start - 1:start] if start else '', text[start + len(value):start + len(value) + 1]
        if not (before.isalnum() or before == '_') and not (after.isalnum() or after == '_'):
            return True
        start = text.find(value, start + 1)
    return False


def scope_files(taxonomy):
    """The files that the check reads: the generated inventory files, the specifications, the render records, the hand-edited dictionary and notes, the review
    and relation tables, and the documents of `docs/`. `taxonomy` is `data/taxonomy-v2`. A folder that is absent adds nothing."""
    taxonomy = Path(taxonomy)
    found = {path for pattern in SCOPE for path in taxonomy.glob(pattern)}
    if taxonomy.name == 'taxonomy-v2' and taxonomy.parent.name == 'data':
        found |= {path for pattern in DOCS_SCOPE for path in (taxonomy.parent.parent / 'docs').glob(pattern)}
    return sorted(path for path in found if path.is_file())


def leaks(values, files, common=lambda value: False):
    """(file, fingerprint) for each value that a file holds as a whole word, unless `common(value)` says that unmarked data holds it too."""
    found = []
    for path in files:
        text = Path(path).read_text(errors='replace')
        for value in values:
            if value in text and occurs(value, text) and not common(value):
                found.append((Path(path), fingerprint(value)))
    return found
