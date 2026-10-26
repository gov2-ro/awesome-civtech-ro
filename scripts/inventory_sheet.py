"""CSV header options for the export of a spreadsheet tab. Stdlib only.

A tab that people maintain by hand does not always start with its header. The plain CSV reader of `inventory.parse_source` takes the first row as
the header and refuses a header with an empty or repeated cell. The registry can ask for two exceptions, one by one, with `citire` (the reader of a source):

    {"tip": "csv", "rand_antet": 2}                    the header is the second row; the row above it is a title
    {"tip": "csv", "coloane_fara_nume": "omise"}       header cells that are empty are left out; they are listed, never named

The options can be combined. Without `citire`, or with `{"tip": "csv"}` alone, the plain rules apply. An unknown option is an error.

The reader keeps the header text exactly as the sheet writes it (no trimming, so a name with a line break stays so) and never guesses a type.
The field `pointer` is the cell of the header (`celula:B2`, spreadsheet notation, row counted from 1).
`header_facts` is the part of the header that fields cannot show: the rows above the header and the empty header cells (source key `antet`).
A row above the header is kept as its non-empty cells (at most 300 characters each). The editor who names `rand_antet` has seen that the row is a title.
"""
from __future__ import annotations

import csv
import io

OPTIONS = {'tip', 'rand_antet', 'coloane_fara_nume'}
MAX_CELL = 300


def column_letters(index):
    """Spreadsheet column name of a 0-based index: 0 is A, 25 is Z, 26 is AA."""
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def cell(column, row):
    return f'{column_letters(column)}{row}'


def settings(options):
    """(header row, leave out empty header cells) of the options. Raises ValueError for an unknown option or a wrong value."""
    options = options if isinstance(options, dict) else {}
    unknown = set(options) - OPTIONS
    if unknown:
        raise ValueError('Unknown CSV option: ' + ', '.join(sorted(unknown)))
    row = options.get('rand_antet', 1)
    if not isinstance(row, int) or isinstance(row, bool) or row < 1:
        raise ValueError('rand_antet must be a whole number from 1')
    omit = options.get('coloane_fara_nume')
    if omit not in (None, 'omise'):
        raise ValueError('coloane_fara_nume accepts only the value "omise"')
    return row, omit == 'omise'


def read_rows(body, row):
    """(rows above the header, the header row) of a CSV body. Raises ValueError when the body has too few rows."""
    rows = csv.reader(io.StringIO(body.lstrip('﻿')), csv.excel)
    above = []
    for number in range(1, row):
        record = next(rows, None)
        if record is None:
            raise ValueError(f'The CSV has fewer than {row} rows; rand_antet {row} does not exist')
        above.append({'rand': number, 'celule': [{'celula': cell(i, number), 'valoare': value.strip()[:MAX_CELL]} for i, value in enumerate(record) if value.strip()]})
    header = next(rows, None)
    if not header:
        raise ValueError(f'The CSV has no row {row}: the header is missing')
    return above, header


def read(body, options):
    """The field records of the header row. Raises ValueError for an empty cell (unless left out), a repeated name or a header with no name."""
    row, omit = settings(options)
    _, header = read_rows(body, row)
    names = [name for name in header if name.strip()]
    if len(names) != len(header) and not omit:
        raise ValueError('CSV header is empty or contains duplicate/unnamed columns')
    if len(set(names)) != len(names):
        raise ValueError('CSV header is empty or contains duplicate/unnamed columns')
    if not names:
        raise ValueError(f'Row {row} of the CSV has no column name')
    return [{'nume': name, 'cale': name, 'tip_declarat': None, 'stare_tip': 'neprecizat-in-antet-csv', 'rol': 'camp-date', 'coloana_csv': index,
             'pointer': 'celula:' + cell(index, row)} for index, name in enumerate(header) if name.strip()]


def header_facts(body, options):
    """The source key `antet`: the header row, the rows above it and the empty header cells that the options left out."""
    row, _ = settings(options)
    above, header = read_rows(body, row)
    return {'rand_antet': row, 'randuri_deasupra': above, 'celule_antet_goale': [cell(i, row) for i, name in enumerate(header) if not name.strip()]}
