"""Reader for the listing of a Datasette database. Stdlib only.

Format name: `baza-datasette`. The input is the JSON that Datasette serves for a database page (`/<database>.json`): a `database` name,
a list of `tables` (each with `name`, `columns`, `count` and `hidden`), `hidden_count`, a list of `views` (names only) and, when the owner of
the server declared them, `source`, `source_url`, `license` and `license_url`.
The reader keeps what the listing states and nothing else. It never requests a table, a view or a query, so it reads no row.

- Fields (`read`): one for each column of each visible table. `nume` is the column name as written (a trailing space stays), `cale` is
  `<table>.<column>`, `grup` is the table and `rol` is `coloana-sql`. The listing declares no type, so `tip_declarat` is null. `randuri_tabel` is
  the row count of the table, as the server counted it when it answered; the key is absent when the server gave no count. `stare_tip` is
  `declarat-in-lista-baza`. The locator is the JSON pointer of the column (`/tables/N/columns/M`).
- Database facts (`database`, source key `baza`): the name, the size in bytes, the declared source and its address, the declared licence with
  its address and attribution, the visible tables (name, row count, column names), the number of hidden tables and the names of the views.
  Each fact is `{valoare, pointer, baza}`. `baza` is `declarat-in-metadate` (the server's metadata: source and licence), `declarat-in-lista`
  (names and the hidden count) or `calculat-de-server` (the size and a row count: the server computed them when it answered).
- A column that names a personal identifier (`PERSONAL_IDS`: the CNP, the Romanian personal numeric code) is discarded: it gets no field and
  its name leaves the column list of its table. The table keeps the count of discarded columns in `coloane_omise`. The catalogue publishes
  the field list, and a personal identifier is not a variable that it lists (owner, 2026-10-26).
- A hidden table (the full-text index tables `*_fts*`) holds no variable: it gets no field. A view has no column in the listing: it is named
  and nothing more. Primary keys, foreign keys, saved queries and the other members of the listing are not read.

A document that has a database name and a table list but no valid shape, a table or a column with no name, a table twice and a column twice in
one table are errors (state `eroare-parsare`); the reader never guesses.
"""
from __future__ import annotations

FIELD_STATE = 'declarat-in-lista-baza'
FORMAT = 'baza-datasette'
METADATA, LISTED, COMPUTED = 'declarat-in-metadate', 'declarat-in-lista', 'calculat-de-server'
MAX_FIELDS = 2000
# Column names (compared without case and outer spaces) that the reader discards.
PERSONAL_IDS = {'cnp'}


def is_listing(doc):
    """True for a document that claims to be the listing of a database: a `database` name, a `tables` list and a `views` member. The strict checks are in `read`."""
    return isinstance(doc, dict) and isinstance(doc.get('database'), str) and isinstance(doc.get('tables'), list) and 'views' in doc


def fact(value, pointer, basis):
    return {'valoare': value, 'pointer': pointer, 'baza': basis}


def text_fact(doc, key, basis=METADATA):
    """A fact for a member that holds text, or None when the member is absent or empty. A member of another type is an error."""
    value = doc.get(key)
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        raise ValueError(f'The member {key} of the listing is not text')
    return fact(value, '/' + key, basis)


def checked_tables(doc):
    """(index, table) of every table in list order. Raises ValueError for a table that is not an object with a name, a column list and a boolean `hidden`."""
    seen, found = set(), []
    for n, table in enumerate(doc['tables']):
        if not isinstance(table, dict) or not isinstance(table.get('name'), str) or not table['name']:
            raise ValueError(f'The table {n} of the listing has no name')
        if not isinstance(table.get('columns'), list) or not isinstance(table.get('hidden'), bool):
            raise ValueError(f'The table {table["name"]!r} has no column list or no hidden flag')
        if table['name'] in seen:
            raise ValueError(f'The listing names the table {table["name"]!r} twice')
        seen.add(table['name'])
        found.append((n, table))
    return found


def columns_of(table):
    """The column names of a visible table. A column with no name or a name twice is an error."""
    names = table['columns']
    for column in names:
        if not isinstance(column, str) or not column:
            raise ValueError(f'The table {table["name"]!r} has a column with no name')
    if len(set(names)) != len(names):
        raise ValueError(f'The table {table["name"]!r} lists a column twice')
    return names


def discarded(column):
    return column.strip().casefold() in PERSONAL_IDS


def row_count(table):
    count = table.get('count')
    return count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None


def read(doc):
    """(fields, truncated) of the listing: one field for each column of each visible table."""
    fields = []
    for n, table in checked_tables(doc):
        if table['hidden']:
            continue
        count = row_count(table)
        for m, column in enumerate(columns_of(table)):
            if discarded(column):
                continue
            field = {'nume': column, 'cale': f'{table["name"]}.{column}', 'grup': table['name'], 'rol': 'coloana-sql', 'tip_declarat': None,
                     'stare_tip': FIELD_STATE, 'pointer': f'/tables/{n}/columns/{m}'}
            if count is not None:
                field['randuri_tabel'] = count
            fields.append(field)
    return fields[:MAX_FIELDS], len(fields) > MAX_FIELDS


def database(doc):
    """The database facts of the listing (source key `baza`)."""
    tables = checked_tables(doc)
    visible = [{'nume': fact(t['name'], f'/tables/{n}/name', LISTED),
                'randuri': fact(row_count(t), f'/tables/{n}/count', COMPUTED) if row_count(t) is not None else None,
                'coloane': [c for c in columns_of(t) if not discarded(c)], 'pointer': f'/tables/{n}',
                **({'coloane_omise': omitted} if (omitted := sum(map(discarded, columns_of(t)))) else {})} for n, t in tables if not t['hidden']]
    views = []
    for n, view in enumerate(doc.get('views') or []):
        if not isinstance(view, dict) or not isinstance(view.get('name'), str) or not view['name']:
            raise ValueError(f'The view {n} of the listing has no name')
        views.append({'nume': fact(view['name'], f'/views/{n}/name', LISTED), 'pointer': f'/views/{n}'})
    size = doc.get('size')
    hidden = doc.get('hidden_count')
    source, source_url = text_fact(doc, 'source'), text_fact(doc, 'source_url')
    licence, licence_url = text_fact(doc, 'license'), text_fact(doc, 'license_url')
    if licence:
        licence = {**licence, 'acopera': 'tabelele-bazei'}
        if licence_url:
            licence['url'] = licence_url
        if source:
            licence['atribuire'] = source
    return {'nume': fact(doc['database'], '/database', LISTED),
            'marime_octeti': fact(size, '/size', COMPUTED) if isinstance(size, int) and not isinstance(size, bool) else None,
            'sursa': source, 'adresa_sursa': source_url, 'licenta': licence, 'tabele': visible,
            'tabele_ascunse': fact(hidden, '/hidden_count', LISTED) if isinstance(hidden, int) and not isinstance(hidden, bool) else None,
            'ascunse_in_lista': sum(1 for _, t in tables if t['hidden']), 'vederi': views}
