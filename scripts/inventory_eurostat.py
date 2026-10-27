"""Reader for a page that pastes Eurostat data browser extractions as HTML tables. Stdlib only.

Format name: `html-tabele-eurostat`. Monitorul Social shows each indicator as the table that the Eurostat data browser exports, pasted into the page by hand. The shapes vary
from page to page. The reader knows these:

    <h2>Structure of consumption expenditure by COICOP consumption purpose<br><b>[hbs_str_t211__custom_8391811]</b></h2>
    <table> Data extracted on 08/11/2023 17:23:16 from [ESTAT] | Last updated: | Time frequency | Unit of measure | Time | COICOP (Labels) | data rows ... </table>

    <table> Title [CODE] Data extracted on 16/10/2023 17:02:49 from [ESTAT] | Last updated: | Time frequency | Reason | Unit of measure | TIME | GEO (Labels) | data rows ...
            Title [CODE] | Last updated: | ... a second extraction in the same table ... </table>

An extraction is a part of a table that starts at the row of its title (or at the first row of the table) and runs to the next extraction. It has a row `Last updated:`.
Inside an extraction:

- the title row holds the title of the data set, the code in square brackets (`[hbs_str_t211__custom_8391811]`) and sometimes the extraction line
  `Data extracted on DD/MM/YYYY HH:MM:SS from [SOURCE]` (also `Date extrase la ...`). Without a title row, the heading directly above the table gives the title and the code;
- the metadata and dimension rows end at the `(Labels)` rows: the first row whose first cell ends with `(Labels)`, and the rows of that kind that follow it directly. The rows after them are
  data rows. When an extraction has no `(Labels)` row, the row `TIME` (a row of years) ends the block. An extraction with neither is not read, and the reader says so by marking the source partial;
- `Last updated:`, `Dataset:` and `Unit of measure` (`Unitate de măsură`) are metadata. The unit is the first value on the unit row;
- every other row of the block names a dimension (`Time frequency`, `Time`, `Geopolitical entity (reporting)`, `TIME`, `COICOP (Labels)`, `Sex`). The row says how many values the table shows
  for it (`valori_in_tabel`): 0 for the dimension of the rows, 1 for a dimension fixed in this extraction, more for the dimension of the columns. A value is never copied.
  A row `Tabel N` is the label of a pasted table, not a dimension;
- the measure is one field with the title of the data set, the unit and the written form of the cells of the first five data rows. A page can paste the same code twice (one extraction for each
  sex): the data set is listed once, with `extractii_in_pagina` 2, and the fields of its first extraction.

The dimension of the data rows is named only when the extraction names it (`GEO (Labels)` above the row labels). When the first cell of a data row is a label with no heading
(a country), the reader names no dimension for it: the page does not say which one it is. The reader never opens a link and makes no request.

Locators are table coordinates, as for `html-tabele`: `/tabele/T/randuri/R` with the 1-based table and the 0-based row (`/tabele/T/antet/0` for a first row of `<th>` cells).
`inventory.py --check` parses the retained body again and compares every field.
"""
from __future__ import annotations

import html
import re

STATE = 'antet-tabel-html'
SAMPLE_ROWS = 5
STAMP = re.compile(r'(?:Data extracted on|Date extrase la) (\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) from \[([^\]]+)\]')
CODED = re.compile(r'^(?P<title>.*?)\s*\[(?P<code>[A-Za-z][A-Za-z0-9_]*)\]\s*$')
HEADED_TABLE = re.compile(r'<h([1-6])\b[^>]*>(?P<heading>.*?)</h\1\s*>(?:\s|<p\b[^>]*>(?:\s|&nbsp;|<br\s*/?>)*</p\s*>)*<table\b', re.S)
LABELS = re.compile(r'\s*\(Labels\)\s*$')
PASTED_LABEL = re.compile(r'^Tabel \d+$')
UNIT_KEYS = ('unit of measure', 'unitate de măsură')
METADATA = ('dataset:', 'last updated:') + UNIT_KEYS


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


def bare(row):
    """The first cell of a row that has no other cell, with the extraction line cut out. Empty when the row has another cell or only the extraction line."""
    return STAMP.sub('', row[0]).strip() if row and not values(row) else ''


def is_metadata(row):
    return bool(row) and (row[0].casefold() in METADATA or (STAMP.search(row[0]) is not None and not bare(row)))


def is_title(row):
    """A row of one cell that is not metadata, not a label of a pasted table and not a `(Labels)` row: the title of an extraction."""
    text = bare(row)
    return bool(text) and row[0].casefold() not in METADATA and not PASTED_LABEL.match(text) and not LABELS.search(text)


def extractions(rows):
    """(start, end) of each extraction of one table. One starts at the first row, and at the title row above each later `Last updated:` row."""
    anchors = [i for i, row in enumerate(rows) if row and row[0].casefold() == 'last updated:']
    if not anchors and rows and rows[0] and STAMP.search(rows[0][0]):
        anchors = [0]
    starts = []
    for number, anchor in enumerate(anchors):
        if number == 0:
            starts.append(0)
            continue
        j = anchor - 1
        while j > starts[-1] and is_metadata(rows[j]):
            j -= 1
        starts.append(j if j > starts[-1] and is_title(rows[j]) else anchor)
    return list(zip(starts, starts[1:] + [len(rows)]))


def block_end(rows, start, end):
    """The index of the last metadata or dimension row of an extraction, or None when its data rows cannot be told from its dimensions."""
    marks = [i for i in range(start, end) if rows[i] and LABELS.search(rows[i][0])]
    if marks:
        last = marks[0]
        while last + 1 < end and rows[last + 1] and LABELS.search(rows[last + 1][0]):
            last += 1
        return last
    times = [i for i in range(start, end) if rows[i] and rows[i][0].casefold() == 'time' and len(values(rows[i])) > 1]
    return times[0] if times else None


def read(body, tables, sample_type):
    """(fields, complete). The field records of every extraction of the page. `tables` come from `inventory_text.parse_tables` and `sample_type` is its cell classifier.
    `complete` is false when an extraction had to be left out. A page with no extraction at all is an error."""
    above = headings(body)
    fields, measures, found, unread = [], {}, 0, 0
    for position, table in enumerate(tables, 1):
        offset = 1 if table['header'] else 0
        rows = ([table['header']] if offset else []) + table['rows']  # a pasted table may use `<th>` cells in its first row; the locators count the data rows only
        for number, (start, end) in enumerate(extractions(rows)):
            found += 1
            last = block_end(rows, start, end)
            if last is None:
                unread += 1
                continue
            titled = is_title(rows[start]) or (STAMP.search(rows[start][0]) is not None and bool(bare(rows[start])))
            text = bare(rows[start]) if titled else (above.get(position, '') if number == 0 else '')
            stamp = next((m for m in (STAMP.search(rows[i][0]) for i in range(start, last + 1) if rows[i]) if m), None)
            coded = CODED.match(text)
            title, code = (coded.group('title'), coded.group('code')) if coded else (text or f'Tabel {position}', None)
            base = code or f'tabel{position}'
            if base in measures:  # the same code twice (a page pastes one extraction for each sex): one data set, and its fields are already listed
                measures[base]['extractii_in_pagina'] += 1
                continue
            unit = updated = None
            unit_row = start
            for index in range(start, last + 1):
                key = rows[index][0].casefold() if rows[index] else ''
                if key in UNIT_KEYS:
                    unit, unit_row = (values(rows[index]) or [None])[0], index
                elif key == 'last updated:':
                    updated = (values(rows[index]) or [None])[0]
            types = []
            for row in rows[last + 1:min(end, last + 1 + SAMPLE_ROWS)]:
                for cell in row[1:]:
                    kind = sample_type(cell)
                    if kind not in types:
                        types.append(kind)
            measure = {'nume': title, 'cale': base, 'tip_declarat': None, 'stare_tip': STATE, 'rol': 'masura', 'pointer': locator(position, unit_row, offset),
                       'unitate': unit, 'tipuri_observate': types, 'sursa_declarata': stamp.group(2) if stamp else None,
                       'extras_la': stamp.group(1) if stamp else None, 'actualizat_declarat': updated, 'extractii_in_pagina': 1}
            if code:
                measure['cod_set'] = code
            fields.append(measure)
            measures[base] = measure
            for index in range(start, last + 1):
                row = rows[index]
                if not row or is_metadata(row) or (index == start and titled) or PASTED_LABEL.match(bare(row)):
                    continue
                name = dimension_name(row[0])
                fields.append({'nume': name, 'cale': f'{base}.{name}', 'tip_declarat': None, 'stare_tip': STATE, 'rol': 'dimensiune',
                               'pointer': locator(position, index, offset), 'grup': title, 'valori_in_tabel': len(values(row))})
    if not found:
        raise ValueError('The page has no table with a `Last updated:` row or an extraction line `Data extracted on ... from [SOURCE]`')
    if not fields:
        raise ValueError('No extraction of the page has a `(Labels)` row or a `TIME` row: its data rows cannot be told from its dimensions')
    return fields, not unread
