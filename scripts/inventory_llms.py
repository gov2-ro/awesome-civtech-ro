"""Reader for the API section of an `llms.txt` file. Stdlib only.

Format name: `llms-api` (named with `citire`; no extension selects it). An `llms.txt` file is a Markdown page for language models. Some sites
use its `## API` section to list the endpoints of an API:

    ## API
    Endpoints need a key, sent in the header `X-API-Key` (or `Authorization: Bearer`, or `?key=`). It is free.
    - [Archive](https://example.org/api/archive.php?from=2026-01-01&to=2026-01-31): time series on an interval

The reader keeps what the text states:

- Each list item `- [Name](URL): text` of the section is an endpoint: a field with the role `operatie-api`, `nume` the last path segment, `cale` the path,
  `descriere` the text after the colon.
- Each query parameter of such a URL is a field with the role `parametru-api`, `loc` `query`, `cale` `PATH?name`, and `exemplu_valoare` the value that the example shows.
  The example is not a type: `tip_declarat` is null.
- Each backticked name in a sentence of the section that mentions a key (`cheie`, `key`, `token`) is a field with the role `autentificare` (a header or a query name).
  A name that holds a space (`Authorization: Bearer`) is kept as written.
- The file is not fetched, executed or called. A section without an endpoint, or a file without the section, is an error (state `eroare-parsare`).
- The locator `char:START-END` covers the list item, or the backticked name, in the retained body.

The reader says that the API exists and what the text names. It does not show that a key is easy to get, or that an endpoint works.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

FORMAT = 'llms-api'
HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*$', re.M)
ITEM = re.compile(r'^[ \t]*[-*]\s+\[([^\]]+)\]\(([^)\s]+)\)\s*(?::\s*(.*))?$', re.M)
BACKTICK = re.compile(r'`([^`\n]+)`')
KEY_WORDS = re.compile(r'\b(cheie|cheia|key|token)\b', re.I)


def section(body):
    """(start, end) of the text under the heading `API`, or None."""
    for match in HEADING.finditer(body):
        if match.group(2).strip().lower() in ('api', 'api-ul', 'api endpoints'):
            level, start = len(match.group(1)), match.end()
            for later in HEADING.finditer(body, start):
                if len(later.group(1)) <= level:
                    return start, later.start()
            return start, len(body)
    return None


def field(name, path, role, start, end, body, **extra):
    return {'nume': name, 'cale': path, 'tip_declarat': None, 'stare_tip': 'declarat-in-documentatie-api', 'rol': role,
            'pointer': f'char:{start}-{end}', 'linie': body.count('\n', 0, start) + 1, **extra}


def read(body):
    """(fields, cut). Raises ValueError when there is no API section or no endpoint in it."""
    found = section(body)
    if not found:
        raise ValueError('The file has no API section')
    start, end = found
    fields, seen = [], set()
    for item in ITEM.finditer(body, start, end):
        url = urlsplit(item.group(2))
        path = url.path or '/'
        if path not in seen:
            seen.add(path)
            fields.append(field(path.rstrip('/').rsplit('/', 1)[-1] or path, path, 'operatie-api', item.start(), item.end(), body,
                                descriere=(item.group(3) or '').strip() or None, nume_in_text=item.group(1)))
        for name, value in parse_qsl(url.query, keep_blank_values=True):
            cale = f'{path}?{name}'
            if cale not in seen:
                seen.add(cale)
                fields.append(field(name, cale, 'parametru-api', item.start(), item.end(), body, loc='query', exemplu_valoare=value))
    if not fields:
        raise ValueError('The API section lists no endpoint')
    for sentence in re.finditer(r'[^\n]+', body[start:end]):
        text = sentence.group(0)
        if ITEM.match(text) or not KEY_WORDS.search(text):
            continue
        for token in BACKTICK.finditer(text):
            name = token.group(1)
            offset = start + sentence.start() + token.start(1)
            if name not in seen:
                seen.add(name)
                fields.append(field(name, name, 'autentificare', offset, offset + len(name), body))
    return fields, False
