"""Reader for a page that pastes Eurostat data browser extractions as HTML tables. Stdlib only.

Format name: `html-tabele-eurostat`. Monitorul Social shows each indicator as the table that the Eurostat data browser exports, pasted into the page under a heading
that names the data set and its code:

    <h2>Structure of consumption expenditure by COICOP consumption purpose<br><b>[hbs_str_t211__custom_8391811]</b></h2>
    <table> Data extracted on 08/11/2023 17:23:16 from [ESTAT] | Last updated: | Time frequency | Unit of measure | Time | COICOP (Labels) | data rows ... </table>

A table counts as an extraction when its first cell reads `Data extracted on DD/MM/YYYY HH:MM:SS from [SOURCE]`. Other tables are not read. In an extraction:

- the rows up to the last row whose first cell ends with `(Labels)` are the metadata and the dimensions; the rows after it are data rows;
- `Last updated:` and `Unit of measure` are metadata. The unit is the first value on the `Unit of measure` row;
- every other metadata row names a dimension (`Time frequency`, `Time`, `Geopolitical entity (reporting)`, `TIME`, `COICOP (Labels)`). The row says how many values the
  table shows for it (`valori_in_tabel`): 0 for the dimension of the rows, 1 for a dimension fixed in this extraction, more for the dimension of the columns. A value is never copied;
- the measure is one field with the title of the data set, the unit and the written form of the cells of the first five data rows.

The dimension of the data rows is named only when the extraction names it (`GEO (Labels)` above the row labels). When the first cell of a data row is a label with no heading
(a country), the reader names no dimension: the page does not say which one it is. The reader never opens a link and makes no request.

Locators are table coordinates, as for `html-tabele`: `/tabele/T/randuri/R` with the 1-based table and the 0-based row. `inventory.py --check` parses the retained body again
and compares every field.
"""
from __future__ import annotations

import html
import re

STATE = 'antet-tabel-html'
SAMPLE_ROWS = 5
EXTRACTION = re.compile(r'^Data extracted on (\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) from \[([^\]]+)\]$')
TITLE = re.compile(r'^(?P<title>.*?)\s*\[(?P<code>[A-Za-z0-9_]+)\]$')
HEADED_TABLE = re.compile(r'<h([1-6])\b[^>]*>(?P<heading>.*?)</h\1\s*>(?:\s|<p\b[^>]*>(?:\s|&nbsp;|<br\s*/?>)*</p\s*>)*<table\b', re.S)
LABELS = re.compile(r'\s*\(Labels\)\s*$')
METADATA = ('dataset:', 'last updated:', 'unit of measure')


def text_of(raw):
    """Visible text of an HTML fragment: tags removed, entities decoded, spaces collapsed. A line break becomes a space."""
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', re.sub(r'<br\s*/?>', ' ', raw)))).strip()


def headings(body):
    """The text of the heading directly above each table, by the 1-based position of the table among all tables of the page. A table with no such heading is absent."""
    found = {}
    for match in HEADED_TABLE.finditer(body):
        position = body.count('<table', 0, match.end() - len('<table')) + 1
        found[position] = text_of(match.group('heading'))
    return found


def locator(position, index, offset):
    """The locator of a row of the combined list (header first): `/tabele/T/antet/0` for a header row, `/tabele/T/randuri/R` for a data row."""
    return f'/tabele/{position}/antet/0' if offset and index == 0 else f'/tabele/{position}/randuri/{index - offset}'


def dimension_name(cell):
    return LABELS.sub('', cell).strip()


def values(row):
    """The non-empty cells of a row after its first cell."""
    return [cell for cell in row[1:] if cell]


def read(body, tables, sample_type):
    """The field records of every extraction of the page. `tables` come from `inventory_text.parse_tables` and `sample_type` is its cell classifier."""
    titles = headings(body)
    fields, extractions = [], 0
    for position, table in enumerate(tables, 1):
        offset = 1 if table['header'] else 0
        rows = ([table['header']] if offset else []) + table['rows']  # a pasted table may use `<th>` cells in its first row; the locators count the data rows only
        first = rows[0][0] if rows and rows[0] else ''
        stamp = EXTRACTION.match(first)
        if not stamp:
            continue
        extractions += 1
        marks = [index for index, row in enumerate(rows) if row and LABELS.search(row[0])]
        if not marks:
            raise ValueError(f'Table {position} is an extraction with no row that ends with (Labels): its data rows cannot be told from its dimensions')
        last = marks[-1]
        labelled = TITLE.match(titles.get(position, ''))
        title, code = (labelled.group('title'), labelled.group('code')) if labelled else (titles.get(position) or f'Tabel {position}', None)
        base = code or f'tabel{position}'
        unit = updated = None
        unit_row = 0
        for index, row in enumerate(rows[1:last + 1], 1):
            key = row[0].casefold()
            if key == 'unit of measure':
                unit, unit_row = (values(row) or [None])[0], index
            elif key == 'last updated:':
                updated = (values(row) or [None])[0]
        types = []
        for row in rows[last + 1:last + 1 + SAMPLE_ROWS]:
            for cell in row[1:]:
                kind = sample_type(cell)
                if kind not in types:
                    types.append(kind)
        measure = {'nume': title, 'cale': base, 'tip_declarat': None, 'stare_tip': STATE, 'rol': 'masura', 'pointer': locator(position, unit_row, offset),
                   'unitate': unit, 'tipuri_observate': types, 'sursa_declarata': stamp.group(2), 'extras_la': stamp.group(1), 'actualizat_declarat': updated}
        if code:
            measure['cod_set'] = code
        fields.append(measure)
        for index, row in enumerate(rows[1:last + 1], 1):
            if row[0].casefold() in METADATA:
                continue
            name = dimension_name(row[0])
            fields.append({'nume': name, 'cale': f'{base}.{name}', 'tip_declarat': None, 'stare_tip': STATE, 'rol': 'dimensiune',
                           'pointer': locator(position, index, offset), 'grup': title, 'valori_in_tabel': len(values(row))})
    if not extractions:
        raise ValueError('The page has no table that starts with `Data extracted on ... from [SOURCE]`')
    return fields
