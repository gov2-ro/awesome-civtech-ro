"""Reader for a page that lists data sets in tables and links each one to an external file. Stdlib only.

Format name: `html-lista-seturi`. The reader needs a page with one `<h3>` heading for each category and, below it, a table whose header cells are
`Categoria secundară`, `Baza de date`, `Descrierea setului`, `Rapoarte relevante` and `Link` (the letters may differ in accents and case).
One body row is one data set. The page of the Expert Forum open-data section (data.expertforum.ro) has this shape.

The reader keeps what the page states and nothing else. It never requests a link, so it never opens a file that the page offers.
It lists no field: the page declares no column of the files. The columns come from the files themselves, one source each.

Each data set (source key `seturi`) has these facts, each `{valoare, pointer, baza}` with `baza` `declarat-in-pagina` and `pointer` `char:START-END`
(an interval of the retained body; `valoare` is the text of that interval with the tags removed, the entities decoded and the spaces collapsed):

- `categorie` (the `<h3>` above the table), `subcategorie` (first cell), `titlu` (second cell), `descriere` (third cell);
- `rapoarte`: one entry for each link of the fourth cell, `{text, adresa}`; an empty list when the cell has no link;
- `legaturi`: one entry for each link of the fifth cell, in page order: `eticheta` (the link text), `text_dupa` (the text after the link in the same
  block, or null), `adresa` (the target), `tip`, `id_document` and `gid`.

A link that the page wraps in `https://www.google.com/url?q=TARGET&...` keeps the page's text in `legatura` and gets the target in `adresa`
(`transformare` `legatura-google-desfacuta`). The reader reads the `q` parameter; it makes no request to `www.google.com`.
`tip` is `foaie-google` (`docs.google.com/spreadsheets/d/ID`), `fisier-drive` (`drive.google.com/file/d/ID`), `dosar-drive` (`drive.google.com/drive/.../folders/ID`)
or `alta-legatura`. `id_document` is the identifier in the address, and `gid` is the number of `#gid=N`, or null. `tip` says what kind of address it is.
It does not say whether the file is a spreadsheet: a Drive file can be any kind of file.

A page with no table of this shape, a row that is not five cells wide, a data set with no title or two data sets with the same title and
address list are errors (state `eroare-parsare`); the reader never guesses.
"""
from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import parse_qs, urlsplit

DECLARED = 'declarat-in-pagina'
HEADER = ['categoria secundara', 'baza de date', 'descrierea setului', 'rapoarte relevante', 'link']
HEADING = re.compile(r'<h3\b[^>]*>(.*?)</h3>', re.S)
TABLE = re.compile(r'<table\b[^>]*>(.*?)</table>', re.S)
ROW = re.compile(r'<tr\b[^>]*>(.*?)</tr>', re.S)
HEAD_CELL = re.compile(r'<th\b[^>]*>(.*?)</th>', re.S)
CELL = re.compile(r'<td\b[^>]*>(.*?)</td>', re.S)
ANCHOR = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.S)
HREF = re.compile(r'\bhref="([^"]*)"')
SHEET = re.compile(r'^https://docs\.google\.com/spreadsheets/d/([\w-]+)')
DRIVE_FILE = re.compile(r'^https://drive\.google\.com/file/d/([\w-]+)')
DRIVE_FOLDER = re.compile(r'^https://drive\.google\.com/drive/(?:u/\d+/)?folders/([\w-]+)')
GID = re.compile(r'(?:^|&)gid=(\d+)(?:&|$)')


def fold(value):
    return unicodedata.normalize('NFKD', value.casefold()).encode('ascii', 'ignore').decode()


def text_of(raw):
    """Visible text of an HTML fragment: tags removed, entities decoded, spaces collapsed (a no-break space counts as a space)."""
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', raw))).strip()


def fact(value, start, end, **extra):
    return {'valoare': value, 'pointer': f'char:{start}-{end}', 'baza': DECLARED, **extra}


def unwrap(href):
    """(target, wrapped) of a link. A `https://www.google.com/url?q=TARGET` link gives its `q` value; any other link is its own target."""
    link = html.unescape(href)
    parts = urlsplit(link)
    if (parts.hostname or '').removeprefix('www.') == 'google.com' and parts.path == '/url':
        target = parse_qs(parts.query).get('q', [''])[0]
        if not target:
            raise ValueError('A google.com/url link of the page has no q parameter: ' + link[:80])
        return target, True
    return link, False


def link_fact(body, anchor):
    """The address of an anchor as a fact with its locator, and the kind of the address."""
    href = HREF.search(anchor.group(1))
    if not href:
        raise ValueError('A link of the page has no href')
    at = anchor.start(1) + href.start(1), anchor.start(1) + href.end(1)
    target, wrapped = unwrap(href.group(1))
    return fact(target, *at, **({'legatura': html.unescape(href.group(1)), 'transformare': 'legatura-google-desfacuta'} if wrapped else {})), target


def kind_of(target):
    """(tip, id_document, gid) of an address."""
    for pattern, kind in ((SHEET, 'foaie-google'), (DRIVE_FILE, 'fisier-drive'), (DRIVE_FOLDER, 'dosar-drive')):
        match = pattern.match(target)
        if match:
            gid = GID.search(urlsplit(target).fragment)
            return kind, match.group(1), gid.group(1) if gid else None
    return 'alta-legatura', None, None


def following_text(body, anchor):
    """The text that follows an anchor up to the next tag, as a fact; null when it is empty or only the separator `/`."""
    match = re.compile(r'[^<]*').match(body, anchor.end())
    text = text_of(match.group())
    return None if text in ('', '/') else fact(text, match.start(), match.end())


def cells(body, row):
    return [(cell.group(1), cell.start(1), cell.end(1)) for cell in CELL.finditer(body, row.start(1), row.end(1))]


def read(body):
    """The data sets of the page, in page order. Raises ValueError for a page that has no table of this shape."""
    headings = [(m.start(), text_of(m.group(1)), m.start(1), m.end(1)) for m in HEADING.finditer(body)]
    datasets, seen = [], set()
    for table in TABLE.finditer(body):
        head = [fold(text_of(c.group(1))) for c in HEAD_CELL.finditer(body, table.start(1), table.end(1))]
        if head != HEADER:
            continue
        above = [h for h in headings if h[0] < table.start()]
        if not above:
            raise ValueError('A table of data sets has no heading above it')
        category = above[-1]
        for row in ROW.finditer(body, table.start(1), table.end(1)):
            if HEAD_CELL.search(body, row.start(1), row.end(1)):
                continue
            parts = cells(body, row)
            if len(parts) != len(HEADER):
                raise ValueError(f'A row of the table has {len(parts)} cells, not {len(HEADER)}')
            titled = {name: fact(text_of(raw), start, end) for name, (raw, start, end) in zip(('subcategorie', 'titlu', 'descriere'), parts[:3])}
            if not titled['titlu']['valoare']:
                raise ValueError('A data set of the page has no title')
            reports = []
            for anchor in ANCHOR.finditer(body, parts[3][1], parts[3][2]):
                address, _ = link_fact(body, anchor)
                reports.append({'text': fact(text_of(anchor.group(2)), anchor.start(2), anchor.end(2)), 'adresa': address})
            links = []
            for anchor in ANCHOR.finditer(body, parts[4][1], parts[4][2]):
                address, target = link_fact(body, anchor)
                kind, ident, gid = kind_of(target)
                links.append({'eticheta': fact(text_of(anchor.group(2)), anchor.start(2), anchor.end(2)), 'text_dupa': following_text(body, anchor),
                              'adresa': address, 'tip': kind, 'id_document': ident, 'gid': gid})
            key = (titled['titlu']['valoare'], tuple(link['adresa']['valoare'] for link in links))
            if key in seen:
                raise ValueError('The page lists a data set twice: ' + titled['titlu']['valoare'])
            seen.add(key)
            datasets.append({'categorie': fact(category[1], category[2], category[3]), **titled, 'rapoarte': reports, 'legaturi': links,
                             'pointer': f'char:{row.start()}-{row.end()}'})
    if not datasets:
        raise ValueError('No table of data sets found: the page has no table with the header ' + ' | '.join(HEADER))
    return datasets


def list_datasets(body):
    """The dataset records of the page (source key `seturi`)."""
    return read(body)


def set_list(body, options=None):
    """The reader of `citire: html-lista-seturi`: no field records. The page declares no column; the datasets are in the source key `seturi`."""
    read(body)
    return 'html-lista-seturi', [], False
