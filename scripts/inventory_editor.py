"""Fields that an editor adds to a source. Stdlib only. It makes no request.

The readers of `inventory.py` miss a field now and then: a name in a page that no reader parses, a column that a dictionary describes in prose. An editor adds
such a field by hand, with the text that proves it, in `observatii/inventare/campuri-editor.csv` (UTF-8, comma-separated, so that it goes through Google Sheets).
One row is one field of one source:

    slug, url_sursa, nume, cale, rol, tip_declarat, unitate, descriere, fragment, nota

- `slug` and `url_sursa` name the entry and one of its structured sources (a row for a URL that is not an active source of that entry is an error).
- `nume`, `cale` and `rol` are the name, the locator and the role of the field. `rol` is one of `ROLES` (the roles of the field browser).
- `tip_declarat` is empty, or one or more of `TYPES` separated by `|`. The editor writes the type that the source declares, never one that the editor infers.
- `fragment` is a text that occurs in the retained body (or the retained snapshot) of the source: the evidence. `nota` is a free note of the editor.

`inventory.py` merges each row into the field records of its source as a record with `stare_tip` `adaugat-de-editor` before the group matching runs, so that a
selector of the dictionary can match it. Each merge starts from the records that the readers wrote: the editor records of an earlier run are dropped first, so a
replay gives the same bytes. The record keeps the hash of the retained text (`dovada_editor.sha256`), never the fragment. `inventory.py --check` finds the fragment again and
compares the hash. A fragment that does not occur is an error. A source whose body is not in this checkout is reported as not verified, as for every other body.
A row for a source with persons (`persoane`) must hold no value that identifies a person; the merge and the check look for such values.
The file is in the scope of the leak check (`inventory_persons.scope_files`).
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from collect_docs import canonical
from inventory_concepts import sha
from inventory_persons import EDITOR_STATE as STATE, body_values, candidates, fingerprint, is_marked, occurs
from inventory_state import source_id

FILE = 'campuri-editor.csv'
COLUMNS = ['slug', 'url_sursa', 'nume', 'cale', 'rol', 'tip_declarat', 'unitate', 'descriere', 'fragment', 'nota']
REQUIRED = ('slug', 'url_sursa', 'nume', 'cale', 'rol', 'fragment')
# The roles of the field records (INV_ROLES in site/app.js; a test keeps the two lists equal) and the types that a source declares in a schema.
ROLES = ('camp-date', 'dimensiune', 'parametru-api', 'corp-cerere', 'camp-raspuns', 'model-de-date', 'camp-dictionar', 'coloana-sql', 'camp-model',
         'cod-enumerare', 'camp-exemplu', 'masura', 'camp-folosit-de-pagina', 'colectie-cu-chei')
TYPES = ('string', 'integer', 'number', 'boolean', 'null', 'object', 'array')
SLUG = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
TEXT_COLUMNS = ('nume', 'cale', 'unitate', 'descriere', 'fragment', 'nota')


def read_file(path):
    """(rows, errors) of the hand-edited file. A missing file has no rows. Each row is a dict of the ten columns plus `linie` (the line number of the file).
    The structure is checked here: the columns, the cells that must not be empty, the code lists, the form of the slug and of the address, and duplicates.
    What needs the inventory (the entry owns the source, the fragment occurs in the body) is checked where the inventory is."""
    path = Path(path)
    if not path.exists():
        return [], []
    errors, rows = [], []
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        missing, extra = [c for c in COLUMNS if c not in header], [c for c in header if c not in COLUMNS]
        if missing or extra:
            return [], [f'{FILE}:1: ' + '; '.join(x for x in ((f'missing columns: {", ".join(missing)}' if missing else ''), (f'unknown columns: {", ".join(extra)}' if extra else '')) if x)]
        seen = {}
        for raw in reader:
            line = reader.line_num
            where = f'{FILE}:{line}'
            if None in raw:
                errors.append(f'{where}: the row has more cells than the header')
                continue
            row = {c: (raw[c] or '').replace('\r\n', '\n') for c in COLUMNS}
            row = {c: (v if c == 'fragment' else v.strip()) for c, v in row.items()}
            if not any(row.values()):
                continue  # an empty line of the sheet
            row['linie'] = line
            problems = [f'{c} is empty' for c in REQUIRED if not row[c].strip()]
            if row['slug'] and not SLUG.match(row['slug']):
                problems.append(f'slug is not valid: {row["slug"]}')
            if row['url_sursa'] and not canonical(row['url_sursa']):
                problems.append(f'url_sursa is not an http or https address: {row["url_sursa"]}')
            if row['rol'] and row['rol'] not in ROLES:
                problems.append(f'rol is unknown: {row["rol"]} (values: {", ".join(ROLES)})')
            types = [t for t in row['tip_declarat'].split('|')] if row['tip_declarat'] else []
            problems += [f'tip_declarat is unknown: {t} (values: {", ".join(TYPES)}, separated by |)' for t in types if t not in TYPES]
            key = (canonical(row['url_sursa']), row['rol'], row['cale'], row['nume'])
            if all(key) and key in seen:
                problems.append(f'the same field as line {seen[key]}')
            seen.setdefault(key, line)
            errors += [f'{where}: {p}' for p in problems]
            if not problems:
                rows.append(row)
    return rows, errors


def membership_errors(rows, members):
    """Each row names a source that its entry owns. `members` is a set of (slug, source id) for the active sources."""
    return [f'{FILE}:{r["linie"]}: {canonical(r["url_sursa"])} is not a source of {r["slug"]}' for r in rows if (r['slug'], source_id(canonical(r['url_sursa']))) not in members]


def field_record(row, evidence=None):
    """The field record of a row, as the generated files keep it. `evidence` is `{'sha256', 'text'}`: the hash of the retained text and the kind of copy
    (`sursa`, `documentatie`, `cache`); both are None for a text that this checkout does not hold. The fragment is never copied into the record."""
    types = row['tip_declarat'].split('|') if row['tip_declarat'] else []
    record = {'nume': row['nume'], 'cale': row['cale'], 'tip_declarat': types[0] if len(types) == 1 else types or None, 'stare_tip': STATE, 'rol': row['rol'],
              'pointer': f'{FILE}:{row["linie"]}'}
    for key, column in (('unitate', 'unitate'), ('descriere', 'descriere'), ('nota_editor', 'nota')):
        if row[column]:
            record[key] = row[column]
    record['dovada_editor'] = evidence or {'sha256': None, 'text': None}
    return record


def is_added(field):
    return field.get('stare_tip') == STATE


def readers_fields(source):
    """The field records that the readers wrote: the source without the records of an editor."""
    return [f for f in source.get('campuri', []) if not is_added(f)]


def without_added(source):
    return {**source, 'campuri': readers_fields(source)} if any(is_added(f) for f in source.get('campuri', [])) else source


def person_prints(row, text, source):
    """Fingerprints of the identifying values of a source with persons that a row repeats. The merge looks for every value of the body; it makes no exception for a
    value that an unmarked body holds too (the check of the files does). Raises ValueError when the text is not a body that the reader of the source knows."""
    try:
        values, names = body_values(text, source.get('format'), source.get('citire'))
    except (ValueError, csv.Error) as exc:
        raise ValueError('the retained text is not a body of the format of the source') from exc
    wanted = candidates(values, names, f'{source.get("url", "")} {source.get("final_url", "")}')
    cells = '\n'.join(row[c] for c in TEXT_COLUMNS)
    return sorted({fingerprint(v) for v in wanted if v in cells and occurs(v, cells)})


def merge(sources, rows, members, locator):
    """Replace the editor records of `sources` ({id: source record}) by the records of `rows`. Returns (errors, notes); a non-empty `errors` means that the state must not be
    written. A source record that changes is a new dict: the tracked state is never changed in place. `locator` is an `EvidenceLocator`."""
    errors, notes = [], []
    for ident, source in list(sources.items()):
        sources[ident] = without_added(source)
    errors += membership_errors(rows, members)
    texts, added = {}, {}
    for row in rows:
        url = canonical(row['url_sursa'])
        ident = source_id(url)
        where = f'{FILE}:{row["linie"]}'
        if (row['slug'], ident) not in members:
            continue  # reported above
        source = sources.get(ident)
        if source is None:
            errors.append(f'{where}: the inventory holds no record of {url}')
            continue
        if url not in texts:
            texts[url] = locator.text(url)
        text, kind = texts[url]
        if any((f['nume'], f['cale'], f.get('rol', 'camp-date')) == (row['nume'], row['cale'], row['rol']) for f in source.get('campuri', [])):
            errors.append(f'{where}: the readers already give the field {row["nume"]} at {row["cale"]}; remove the row')
            continue
        if text is None:
            evidence = {'sha256': None, 'text': None}
            notes.append(f'{where}: no retained text of {url} in this checkout; the fragment is not verified and no hash is recorded')
        elif row['fragment'] not in text:
            errors.append(f'{where}: the fragment is not in the retained text of {url}')
            continue
        else:
            evidence = {'sha256': sha(text), 'text': kind}
            if is_marked(source):
                try:
                    found = person_prints(row, text, source)
                except ValueError as exc:
                    errors.append(f'{where}: {exc}')
                    continue
                if found:
                    errors.append(f'{where}: the row holds a value that identifies a person of a source with persons (fingerprint {", ".join(found)})')
                    continue
        added.setdefault(ident, []).append(field_record(row, evidence))
    for ident, records in added.items():
        sources[ident] = {**sources[ident], 'campuri': [*sources[ident].get('campuri', []), *records]}
    return errors, notes


def check(rows, previous, locator):
    """What `inventory.py --check` says about the file: {'errors', 'unavailable', 'verified', 'rows'}. It compares the file with the generated records and finds each
    fragment again. A text that is not in this checkout is unavailable, never verified and never an error."""
    report = {'errors': [], 'unavailable': [], 'verified': 0, 'rows': len(rows)}
    owners = {slug: set(profile.get('surse_structurate', [])) for slug, profile in previous['profiles'].items()}
    report['errors'] += membership_errors(rows, {(slug, ident) for slug, ids in owners.items() for ident in ids})
    wanted = {}
    for row in rows:
        wanted.setdefault(source_id(canonical(row['url_sursa'])), []).append(row)
    for ident, source in previous['sources'].items():
        have = [f for f in source.get('campuri', []) if is_added(f)]
        want = wanted.pop(ident, [])
        if [{k: v for k, v in f.items() if k != 'dovada_editor'} for f in have] != [{k: v for k, v in field_record(r).items() if k != 'dovada_editor'} for r in want]:
            report['errors'].append(f'The fields of an editor in {source["url"]} differ from {FILE}; run inventory.py --offline')
            continue
        for field, row in zip(have, want):
            where = f'{FILE}:{row["linie"]}'
            recorded = field.get('dovada_editor') or {}
            text, _ = locator.text(source['url'], recorded.get('text'))
            if text is None:
                report['unavailable'].append(f'editor field: {where} {source["url"]}')
            elif row['fragment'] not in text:
                report['errors'].append(f'{where}: the fragment is not in the retained text of {source["url"]}')
            elif not recorded.get('sha256'):
                report['errors'].append(f'{where}: no hash of the retained text is recorded; run inventory.py --offline')
            elif sha(text) != recorded['sha256']:
                report['errors'].append(f'{where}: the retained text of {source["url"]} changed since the hash was recorded; run inventory.py --offline')
            else:
                report['verified'] += 1
    for ident, left in wanted.items():
        report['errors'] += [f'{FILE}:{r["linie"]}: {canonical(r["url_sursa"])} has no record in the inventory; run inventory.py --offline' for r in left]
    return report
