"""Reader for an API reference page that lists its endpoints as cards. Stdlib only.

Format name: `html-api-docs`. The reader needs a server-rendered page where every endpoint has a header (a method badge followed by a
`<code>` path template with `:name` segments), optional access badges, a `Cache:` label, a description paragraph and a paragraph that starts
with `Parametri:`. It reads what the page states and nothing else. It never calls the API.

Three kinds of record stay apart:

- operations (`operations`): method, path template, category, description, access badges, cache label. They are not variables.
- request inputs (`fields`): path and query parameters (role `parametru-api`), body members (role `corp-cerere`).
  Each one belongs to one operation (`operatie`, `aparitii`). The page text is kept as `descriere` (after a dash) or `indicatie_pagina`
  (in parentheses). No type is inferred: `tip_declarat` is set only when the page writes one, as in `body: { cuis: string[] }`.
- response members (`fields`, role `camp-raspuns`): the envelope named on the page (`Format: { success, data, meta }`) and the members of
  the error example. The page documents no other response member.

Locators are exact: `char:START-END` is a character interval of the retained body. `inventory.py --check` parses the body again.
"""
from __future__ import annotations

import html
import json
import re

METHODS = 'GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS'
HEADER = re.compile(rf'<span\b[^>]*>({METHODS})</span><code\b[^>]*>(/[^<\s]*)</code>')
HEADING = re.compile(r'<h2\b[^>]*>(.*?)</h2>', re.S)
SEPARATOR = r'(?:<!--\s*-->|\s)*'
IDENTIFIER = r'[A-Za-z_]\w*'
UNRESOLVED_KEY = re.compile(r'^ep\.[\w.-]+\.description$')
ENUM_HINT = re.compile(r'^[\w-]+(?:\|[\w-]+)+$')
FIELD_STATE = 'declarat-in-documentatie-api'


def text_of(raw):
    """Visible text of an HTML fragment: tags removed, entities decoded, spaces collapsed."""
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', raw))).strip()


def split_top(text, separator):
    """Spans (start, end) of the parts of `text` between a separator outside brackets, with surrounding spaces removed.
    Brackets that do not close are an error: the text would otherwise lose its last part without a trace."""
    spans, depth, start = [], 0, 0

    def part(end):
        segment = text[start:end]
        lead, tail = len(segment) - len(segment.lstrip()), len(segment.rstrip())
        if tail:
            spans.append((start + lead, start + tail))

    for index, char in enumerate(text):
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth -= 1
            if depth < 0:
                raise ValueError(f'Unbalanced brackets in {text!r}')
        elif char == separator and depth == 0:
            part(index)
            start = index + 1
    if depth:
        raise ValueError(f'Unbalanced brackets in {text!r}')
    part(len(text))
    return spans


def parameter_items(text):
    """Items of a `Parametri:` text as (name, description, hint, body_type, start, end).
    A segment between `;` is either `name — description` (the description runs to the end of the segment), `body: { a: type, b: type }`,
    or names separated by commas, each with an optional parenthesis `name (hint)`. Any other shape is an error, never a guess."""
    items = []
    for start, end in split_top(text, ';'):
        segment = text[start:end]
        described = re.fullmatch(rf'({IDENTIFIER})\s+—\s+(.+)', segment, re.S)
        body = re.fullmatch(r'body:\s*\{(.*)\}', segment, re.S)
        if described:
            items.append((described.group(1), described.group(2).strip(), None, None, start, end))
        elif body:
            inner, offset = body.group(1), start + body.start(1)
            for a, b in split_top(inner, ','):
                member = re.fullmatch(rf'({IDENTIFIER})\s*:\s*(\S.*)', inner[a:b])
                if not member:
                    raise ValueError(f'Unrecognised body member: {inner[a:b]!r}')
                items.append((member.group(1), None, None, member.group(2).strip(), offset + a, offset + b))
        else:
            for a, b in split_top(segment, ','):
                item = re.fullmatch(rf'({IDENTIFIER})(?:\s*\((.*)\))?', segment[a:b], re.S)
                if not item:
                    raise ValueError(f'Unrecognised parameter text: {segment[a:b]!r}')
                items.append((item.group(1), None, item.group(2).strip() if item.group(2) else None, None, start + a, start + b))
    return items


def example_query_names(block):
    """Parameter names that the card's example request writes in its query string."""
    example = re.search(r'curl\s+(?:<!--\s*-->)?https?://[^<\s]+(?:<!--\s*-->)?([^<]*)</code>', block)
    path = html.unescape(example.group(1)) if example else ''
    return {pair.split('=', 1)[0] for pair in path.partition('?')[2].split('&') if pair}


def error_example(body):
    """Members of the JSON error example (`Când depășești limita (429)`): (path, kind, key span) in document order, or []."""
    marker = body.find('(429)')
    block = re.compile(r'<pre\b[^>]*>(.*?)</pre>', re.S).search(body, marker) if marker >= 0 else None
    if not block:
        return []
    try:
        data = json.loads(html.unescape(block.group(1)))
    except ValueError as exc:
        raise ValueError(f'The error example is not JSON: {exc}') from exc
    members, cursor = [], 0

    def walk(value, path):
        nonlocal cursor
        for key, item in value.items():
            span = None
            for quoted in (f'&quot;{key}&quot;', f'"{key}"'):
                found = block.group(1).find(quoted, cursor)
                if found >= 0:
                    span = (block.start(1) + found, block.start(1) + found + len(quoted))
                    cursor = found + len(quoted)
                    break
            if span is None:
                raise ValueError(f'Key {key!r} of the error example is not in the retained text')
            kind = 'object' if isinstance(item, dict) else 'boolean' if isinstance(item, bool) else 'string' if isinstance(item, str) else 'number'
            members.append((f'{path}.{key}', key, kind, span))
            if isinstance(item, dict):
                walk(item, f'{path}.{key}')

    if isinstance(data, dict):
        walk(data, '$')
    return members


def envelope(body):
    """Members named by the `Format: { a, b, c }` line of the page header, as (name, span)."""
    line = re.search(rf'Format:{SEPARATOR}<code\b[^>]*>\{{\s*([\w\s,]+?)\s*\}}</code>', body)
    if not line:
        return []
    names, offset = [], line.start(1)
    for start, end in split_top(line.group(1), ','):
        names.append((line.group(1)[start:end], (offset + start, offset + end)))
    return names


def cards(body):
    """The endpoint cards of the page in document order: method, path template, category, spans and the raw block of the card."""
    headers = list(HEADER.finditer(body))
    if not headers:
        raise ValueError('No endpoint card found: the page has no method badge followed by a path template')
    headings = [(m.start(), text_of(m.group(1))) for m in HEADING.finditer(body)]
    result = []
    for index, header in enumerate(headers):
        following = [headers[index + 1].start()] if index + 1 < len(headers) else [len(body)]
        limit = min(following + [start for start, _ in headings if start > header.start()])
        category = next((name for start, name in reversed(headings) if start < header.start()), None)
        result.append({'method': header.group(1), 'path': header.group(2), 'category': category, 'header': header,
                       'block': body[header.end():limit], 'offset': header.end()})
    return result


def operation_name(method, path):
    return method + ' ' + re.sub(rf':({IDENTIFIER})', r'{\1}', path)


def read_card(card):
    """The facts of one card: operation record and the request inputs that it states."""
    header, block, base = card['header'], card['block'], card['offset']
    operation = operation_name(card['method'], card['path'])
    badges = re.match(r'((?:<span\b[^>]*>[^<]*</span>)*)', block).group(1)
    cache = re.search(rf'<span\b[^>]*>\s*Cache:{SEPARATOR}([^<]*)</span>', block)
    paragraphs = list(re.finditer(r'<p\b[^>]*>(.*?)</p>', block, re.S))
    described = [p for p in paragraphs if not text_of(p.group(1)).startswith('Parametri:')]
    parameters = next((p for p in paragraphs if text_of(p.group(1)).startswith('Parametri:')), None)
    description = text_of(described[0].group(1)) if described else None
    record = {'operatie': operation, 'metoda': card['method'], 'cale': operation.split(' ', 1)[1], 'categorie': card['category'],
              'descriere': description, 'acces': re.findall(r'>([^<]*)</span>', badges), 'cache': cache.group(1).strip() if cache else None,
              'pointer': f'char:{header.start()}-{header.end()}'}
    if description and UNRESOLVED_KEY.match(description):
        record.update(descriere=None, descriere_cheie_nerezolvata=description)
    path_start = header.start(2)
    in_path = {m.group(1): (path_start + m.start(), path_start + m.end()) for m in re.finditer(rf':({IDENTIFIER})', card['path'])}
    queried, fields, seen = example_query_names(block), [], set()

    def add(name, role, loc, basis, span, **extra):
        field = {'nume': name, 'cale': name, 'rol': role, 'operatie': operation, 'loc': loc, 'tip_declarat': extra.pop('tip_declarat', None),
                 'stare_tip': FIELD_STATE, 'pointer': f'char:{span[0]}-{span[1]}', 'aparitii': [{'operatie': operation, 'cale': name}]}
        if basis:
            field['baza_loc'] = basis
        field.update({k: v for k, v in extra.items() if v not in (None, '', [])})
        fields.append(field)
        seen.add(name)

    if parameters:
        prefix = re.match(rf'Parametri:{SEPARATOR}', parameters.group(1))
        raw = parameters.group(1)[prefix.end():]
        if '<' in raw:
            raise ValueError(f'Markup inside the parameter text of {operation}')
        text, exact = html.unescape(raw), '&' not in raw
        origin = base + parameters.start(1) + prefix.end()
        for name, description, hint, body_type, start, end in parameter_items(text):
            span = (origin + start, origin + end) if exact else (origin, origin + len(raw))
            extra = {'descriere': description, 'indicatie_pagina': hint, 'tip_declarat': body_type,
                     'valori_enum': hint.split('|') if hint and ENUM_HINT.match(hint) else None}
            if name in seen:
                continue
            if body_type is not None:
                add(name, 'corp-cerere', 'body', 'corp-declarat', span, **extra)
            elif name in in_path:
                add(name, 'parametru-api', 'path', 'sablon-cale', span, **extra)
            elif name in queried:
                add(name, 'parametru-api', 'query', 'exemplu-cerere', span, **extra)
            else:
                add(name, 'parametru-api', None, None, span, **extra)
    for name, span in in_path.items():
        if name not in seen:
            add(name, 'parametru-api', 'path', 'sablon-cale', span)
    return record, fields


def read(body):
    """(operations, fields) of the page. Request inputs come in card order; the response members follow."""
    operations, fields = [], []
    for card in cards(body):
        operation, inputs = read_card(card)
        if any(o['operatie'] == operation['operatie'] for o in operations):
            raise ValueError('The page lists an operation twice: ' + operation['operatie'])
        operations.append(operation)
        fields += inputs
    for name, (start, end) in envelope(body):
        fields.append({'nume': name, 'cale': f'$.{name}', 'rol': 'camp-raspuns', 'tip_declarat': None, 'stare_tip': FIELD_STATE,
                       'pointer': f'char:{start}-{end}', 'grup': 'plic-raspuns'})
    for path, key, kind, (start, end) in error_example(body):
        if path == '$.success':
            continue  # the envelope line already declares `success`
        fields.append({'nume': path.rsplit('.', 1)[1], 'cale': path, 'rol': 'camp-raspuns', 'tip_declarat': None,
                       'tipuri_observate': [kind], 'stare_tip': 'exemplu-in-documentatie', 'status_raspuns': '429',
                       'pointer': f'char:{start}-{end}', 'grup': 'plic-raspuns'})
    return operations, fields


def api_docs(body, options=None):
    """The reader of `citire: html-api-docs`: field records in the shape of inventory.parse_source."""
    return 'html-api-docs', read(body)[1], False


def operations(body):
    """The operation records of the page (source key `operatii`)."""
    return read(body)[0]
