"""Reader for a page that offers CSV files as download cards. Stdlib only.

Format name: `html-carduri-csv`. The reader needs a server-rendered page where every file is a card with:

- a title (`<h3 data-slot="card-title">`) and a description (`<p data-slot="card-description">`);
- a download link to a `.csv` file (`<a href="/date/file.csv" download>`);
- a list of labelled values (`<dt>Rânduri</dt><dd>37</dd>`, also `Perioada`, `Măsurat la`, `Surse`);
- the heading `Coloanele` followed by a list of the columns (`<dt>` the column name, `<dd>` its description).

The page may also state a licence in a card titled `Licența: …`, with a link marked `rel="license"` and an attribution line `Sursa: …`.
The reader keeps what the page states and nothing else. It never downloads a CSV file and never makes a request.

Two kinds of record stay apart:

- datasets (`datasets`): one per card, with the facts of the card. Each fact is `{valoare, pointer, baza}` like the INS dataset facts
  (`pointer` is `char:START-END`, a character interval of the retained body). A text that the reader changed says how (`transformare`).
- fields (`read`): one per listed column, with the description exactly as the page writes it (entities decoded). The page declares no type,
  so `tip_declarat` is null. A unit is set only when the description states it (`în lei nominali`); the reader never infers one from a name.

Locators are exact. `inventory.py --check` parses the retained body again and compares every dataset and field.
"""
from __future__ import annotations

import html
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin, urlsplit

DECLARED = 'declarat-in-pagina'
FIELD_STATE = 'declarat-in-lista-documentatie'
TITLE = re.compile(r'<h3\b[^>]*\bdata-slot="card-title"[^>]*>(.*?)</h3>', re.S)
DESCRIPTION = re.compile(r'<p\b[^>]*\bdata-slot="card-description"[^>]*>(.*?)</p>', re.S)
ANCHOR = re.compile(r'<a\b([^>]*)>', re.S)
HREF = re.compile(r'\bhref="([^"]*)"')
PAIR = re.compile(r'<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>', re.S)
LIST = re.compile(r'<dl\b[^>]*>(.*?)</dl>', re.S)
COLUMNS_HEADING = re.compile(r'<h3\b[^>]*>\s*Coloanele\s*</h3>', re.S)
LICENCE_TITLE = re.compile(r'<h3\b[^>]*\bdata-slot="card-title"[^>]*>\s*(Licen\w*:\s*([^<]*?))\s*</h3>', re.S)
ATTRIBUTION = re.compile(r'<p\b[^>]*>\s*(Sursa:[^<]*?)\s*</p>', re.S)
DATE = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})')
# A unit is taken only from a phrase that states it. `în lei nominali` is a unit; a column name that ends in `_lei` is not evidence.
UNIT_PHRASE = re.compile(r'\bîn ((?:lei|euro|mii de lei|milioane de lei|miliarde de lei)(?: nominali| reali| constanți| curenți)?)(?=[\s,.;:)]|$)')
LABELS = {'randuri': 'randuri', 'perioada': 'perioada', 'masurat la': 'masurat_la', 'surse': 'surse'}


def fold(value):
    return unicodedata.normalize('NFKD', value.casefold()).encode('ascii', 'ignore').decode()


def text_of(raw):
    """Visible text of an HTML fragment: tags removed, entities decoded, spaces collapsed."""
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', raw))).strip()


def fact(value, start, end, **extra):
    return {'valoare': value, 'pointer': f'char:{start}-{end}', 'baza': DECLARED, **extra}


def download(body, start, end):
    """The first anchor with a `download` attribute and a link to a `.csv` file: (match, href match) or None."""
    for anchor in ANCHOR.finditer(body, start, end):
        attributes, href = anchor.group(1), HREF.search(anchor.group(1))
        if href and re.search(r'(?<![\w-])download\b', attributes) and re.search(r'\.csv(?:$|\?)', href.group(1)):
            return anchor, href
    return None


def card_spans(body):
    """(start, end) of each card that offers a CSV file. A card runs from its title to the next card title or the end of `<main>`."""
    titles = [m.start() for m in TITLE.finditer(body)]
    spans = []
    for index, start in enumerate(titles):
        limit = titles[index + 1] if index + 1 < len(titles) else len(body)
        end_main = body.find('</main>', start, limit)
        end = end_main if end_main >= 0 else limit
        if download(body, start, end):
            spans.append((start, end))
    return spans


def page_licence(body):
    """The licence stated by the page, once for all its files: name, licence link and attribution line, each with its interval. None without a licence card."""
    heading = LICENCE_TITLE.search(body)
    if not heading:
        return None
    name = text_of(heading.group(2))
    licence = {'valoare': name, 'pointer': f'char:{heading.start(2)}-{heading.end(2)}', 'baza': DECLARED, 'acopera': 'fisierele-paginii'}
    for anchor in ANCHOR.finditer(body):
        href = HREF.search(anchor.group(1))
        if href and re.search(r'\brel="license"', anchor.group(1)):
            licence['url'] = fact(html.unescape(href.group(1)), anchor.start(1) + href.start(1), anchor.start(1) + href.end(1))
            break
    attribution = ATTRIBUTION.search(body)
    if attribution:
        licence['atribuire'] = fact(text_of(attribution.group(1)), attribution.start(1), attribution.end(1))
    return licence


def labelled_values(body, start, end):
    """The label -> (raw value, interval) pairs of the first value list of a card, before the column list."""
    heading = COLUMNS_HEADING.search(body, start, end)
    block = LIST.search(body, start, heading.start() if heading else end)
    values = {}
    for pair in PAIR.finditer(body, block.start(1), block.end(1)) if block else ():
        key = LABELS.get(fold(text_of(pair.group(1))))
        if key and key not in values:
            values[key] = (pair.group(2), pair.start(2), pair.end(2))
    return values


def column_entries(body, start, end):
    """The columns of a card as (name, description, entry interval, description interval). A duplicated name is an error."""
    heading = COLUMNS_HEADING.search(body, start, end)
    block = LIST.search(body, heading.end(), end) if heading else None
    entries, seen = [], set()
    for pair in PAIR.finditer(body, block.start(1), block.end(1)) if block else ():
        name, description = text_of(pair.group(1)), text_of(pair.group(2))
        if not name or not description:
            raise ValueError('A column of the page has no name or no description')
        if name in seen:
            raise ValueError(f'The page lists the column {name!r} twice in one file')
        seen.add(name)
        entries.append((name, description, (pair.start(), pair.end()), (pair.start(2), pair.end(2))))
    return entries


def sources_of(raw, start, end):
    """The sources of a `Surse` value, split at ` · `. Exact intervals only when the text has no markup or entity; else the whole value."""
    names = [part.strip() for part in raw.split(' · ') if part.strip()] if '<' not in raw else [text_of(raw)]
    exact = '<' not in raw and '&' not in raw
    found, cursor = [], 0
    for name in names:
        at = raw.find(name, cursor) if exact else -1
        found.append(fact(html.unescape(name), start + at, start + at + len(name)) if at >= 0 else fact(html.unescape(name), start, end))
        cursor = at + len(name) if at >= 0 else cursor
    return found


def measured_fact(raw, start, end):
    text = text_of(raw)
    match = DATE.fullmatch(text)
    if match:
        try:
            iso = date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
        except ValueError:
            iso = None
        if iso:
            return fact(iso, start, end, text=text, transformare='data-zz.ll.aaaa-in-iso')
    return fact(text, start, end)


def rows_fact(raw, start, end):
    text = text_of(raw)
    return fact(int(text) if re.fullmatch(r'\d+', text) else text, start, end)


def read(body, base_url=''):
    """(datasets, fields) of the page. Raises ValueError for a page with no file card, a repeated file or a repeated column."""
    spans = card_spans(body)
    if not spans:
        raise ValueError('No file card found: the page has no card with a download link to a .csv file')
    licence = page_licence(body)
    datasets, fields, names = [], [], set()
    for start, end in spans:
        anchor, href = download(body, start, end)
        link = html.unescape(href.group(1))
        filename = urlsplit(link).path.rsplit('/', 1)[-1]
        if filename in names:
            raise ValueError('The page offers the file twice: ' + filename)
        names.add(filename)
        at = anchor.start(1) + href.start(1), anchor.start(1) + href.end(1)
        title = TITLE.search(body, start, end)
        description = DESCRIPTION.search(body, start, end)
        values = labelled_values(body, start, end)
        entries = column_entries(body, start, end)
        dataset = {'fisier': fact(filename, *at), 'adresa': fact(urljoin(base_url, link), *at, legatura=link, transformare='legatura-rezolvata'),
                   'titlu': fact(text_of(title.group(1)), title.start(1), title.end(1)),
                   'descriere': fact(text_of(description.group(1)), description.start(1), description.end(1)) if description else None,
                   'randuri': rows_fact(*values['randuri']) if 'randuri' in values else None,
                   'perioada': fact(text_of(values['perioada'][0]), *values['perioada'][1:]) if 'perioada' in values else None,
                   'masurat_la': measured_fact(*values['masurat_la']) if 'masurat_la' in values else None,
                   'surse': sources_of(*values['surse']) if 'surse' in values else [],
                   'licenta': licence, 'coloane': [name for name, *_ in entries], 'pointer': f'char:{start}-{end}'}
        datasets.append(dataset)
        period = dataset['perioada']['valoare'] if dataset['perioada'] else None
        for name, text, (first, last), _ in entries:
            field = {'nume': name, 'cale': f'{filename}::{name}', 'grup': filename, 'rol': 'camp-date', 'tip_declarat': None,
                     'stare_tip': FIELD_STATE, 'descriere': text, 'pointer': f'char:{first}-{last}'}
            if period:
                field['perioada_declarata'] = period
            unit = UNIT_PHRASE.search(text)
            if unit:
                field.update(unitate=unit.group(1), baza_unitatii='declarat-in-descriere')
            fields.append(field)
    return datasets, fields


def csv_cards(body, options=None):
    """The reader of `citire: html-carduri-csv`: field records in the shape of inventory.parse_source."""
    return 'html-carduri-csv', read(body)[1], False


def csv_datasets(body, base_url=''):
    """The dataset records of the page (source key `seturi`)."""
    return read(body, base_url)[0]
