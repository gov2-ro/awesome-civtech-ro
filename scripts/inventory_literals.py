"""Reader for the data that a page script holds as literals. Stdlib only. It makes no request and runs no script.

A single-page tool often carries its data inside the page: `const DATA = {"years": [...], "c": {...}}` in a script, or a data island
`<script id="dataScript" type="application/json">{...}</script>`. No schema or API describes such data. The reader still sees what
the page holds, and it never guesses a meaning.

What it reads:

- A top-level declaration (`const`, `let` or `var` at the start of a line, or an assignment `window.NAME = ...`) whose value is a literal: an object
  or an array that holds only strings, numbers, `true`, `false`, `null`, arrays and objects. Keys may be quoted or bare, strings may use either quote,
  and comments and trailing commas are allowed. This is JSON, plus the habits of hand-written script. The literal may be the one argument of
  `Object.freeze(...)`: the call only seals the object, and the data is the literal. A literal in any other call stays unread.
- A script file. A body that has no `<script>` element and does not look like an HTML page is one script: the file `data.js` that a page loads
  with `<script src>`. Its character offsets are those of the file.
- A data island: a script of type `application/json`, named by its `id`.

JSON-LD (`application/ld+json`) is not read as data, but a schema.org `Dataset` in it is the page's own declaration about a data set. The
reader keeps the facts of each `Dataset` apart in `seturi_ld` (name, description, period, coverage, licence, `isBasedOn`, creator, each with
a locator), and each `variableMeasured` entry becomes a field with the name, description and unit that the page declares.

What it skips, and lists in `declaratii` with the reason: a value that is code (a function, an identifier, a template string), a
literal followed by an expression (`[...].map(...)`), a declaration in the middle of a line and a literal that is nested too deeply.

Each field is a path in a literal with the types that the sample showed. The bounds are those of the JSON sampler: 25 elements of an
array, 25 members of a keyed collection, seven levels, 2,000 fields. An object with 100 members or more, or with 12 to 99 members whose values are
all of one kind (objects, arrays, strings or numbers) and whose keys are not all identifiers, or with 2 members or more whose keys are all years
(`2014`, `2015`) and whose values are of one kind, is a keyed collection (the keys are values such as county names or years and never become field
names; three keys are kept as examples). The plain JSON reader (`inventory.observed_fields`) applies the same rule through `keyed_collection`.
A wide record, whose values differ in kind or whose keys are all identifiers (`country`, `postalCode`, `unique_urls`), stays a record. An array of equal-width rows of scalars gives one field for each position (`ROWS[][0]`, `ROWS[][1]`): the
position is a fact, the meaning of a position is not.
The locator `char:START-END` addresses the first node at that path in the retained body.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import NamedTuple

SAMPLE_ROWS = 25
MAX_DEPTH = 7
MAX_FIELDS = 2000
KEYED_COLLECTION = 12
SURE_COLLECTION = 100
POSITIONAL_WIDTH = 12
YEAR_KEY = re.compile(r'^(?:19|20)[0-9]{2}$')
# A field name: a lowercase letter, then letters, digits and underscores (`country`, `postalCode`, `unique_urls`). A county, a code or an id is not one.
IDENTIFIER_KEY = re.compile(r'^[a-z][A-Za-z0-9_]*$')
MAX_NESTING = 40
EXAMPLE_KEYS = 3
EXAMPLE_LENGTH = 40

SCRIPT = re.compile(r'<script\b([^>]*)>(.*?)</script\s*>', re.S | re.I)
DECLARATION = re.compile(r'^(?:(?:const|let|var)[ \t]+|window\.)([A-Za-z_$][\w$]*)[ \t]*=[ \t]*(Object\.freeze\([ \t]*)?(?=[\[{])', re.M)
# The same, and also a declaration of one of the NAMES with leading spaces (inside a function that wraps the page script).
INDENTED = r'^(?:[ \t]*(?:(?:const|let|var)[ \t]+|window\.)(?=(?:{names})\b)|(?:const|let|var)[ \t]+|window\.)([A-Za-z_$][\w$]*)[ \t]*=[ \t]*(Object\.freeze\([ \t]*)?(?=[\[{{])'
HTML_PAGE = re.compile(r'<(?:!doctype\s+html|html|head|body)(?:\s|>)', re.I)
STRING = {'"': re.compile(r'"[^"\\\n]*(?:\\.[^"\\\n]*)*"', re.S), "'": re.compile(r"'[^'\\\n]*(?:\\.[^'\\\n]*)*'", re.S)}
NUMBER = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
IDENTIFIER = re.compile(r'[A-Za-z_$][\w$]*')
KEYWORDS = {'null': ('nul', None), 'true': ('logic', True), 'false': ('logic', False)}
ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}


class Node(NamedTuple):
    kind: str  # obiect, tablou, text, intreg, numar, logic, nul
    payload: object  # members (key, Node) of an object, the Nodes of an array, or the raw text of a string
    start: int  # offsets in the whole body
    end: int


class NotLiteral(ValueError):
    def __init__(self, reason, at):
        super().__init__(reason)
        self.reason, self.at = reason, at


def line_of(body, offset):
    return body.count('\n', 0, offset) + 1


def decode(raw):
    """The text of a string literal without its quotes. Only the keys of objects need it."""
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if c != '\\' or i + 1 >= len(raw):
            out.append(c)
            i += 1
            continue
        n = raw[i + 1]
        if n == 'u' and re.fullmatch(r'[0-9a-fA-F]{4}', raw[i + 2:i + 6]):
            out.append(chr(int(raw[i + 2:i + 6], 16)))
            i += 6
        elif n == 'x' and re.fullmatch(r'[0-9a-fA-F]{2}', raw[i + 2:i + 4]):
            out.append(chr(int(raw[i + 2:i + 4], 16)))
            i += 4
        else:
            out.append(ESCAPES.get(n, n))
            i += 2
    return ''.join(out)


class Parser:
    """A recursive-descent reader of the literal subset. `base` is the offset of the script text in the body."""

    def __init__(self, text, base=0):
        self.text, self.base, self.i = text, base, 0

    def space(self):
        text = self.text
        while self.i < len(text):
            c = text[self.i]
            if c in ' \t\r\n\f\v﻿ ':
                self.i += 1
            elif text.startswith('//', self.i):
                end = text.find('\n', self.i)
                self.i = len(text) if end < 0 else end
            elif text.startswith('/*', self.i):
                end = text.find('*/', self.i + 2)
                if end < 0:
                    raise NotLiteral('comentariu-neinchis', self.base + self.i)
                self.i = end + 2
            else:
                break

    def value(self, depth=0):
        if depth > MAX_NESTING:
            raise NotLiteral('literal-prea-adanc', self.base + self.i)
        self.space()
        text, start = self.text, self.i
        if start >= len(text):
            raise NotLiteral('literal-neterminat', self.base + start)
        c = text[start]
        if c == '{':
            return self.members(depth)
        if c == '[':
            return self.elements(depth)
        if c in STRING:
            match = STRING[c].match(text, start)
            if not match:
                raise NotLiteral('sir-neinchis', self.base + start)
            self.i = match.end()
            return Node('text', match.group(0)[1:-1], self.base + start, self.base + self.i)
        if c in '-+.' or c.isdigit():
            if text.startswith('...', start):
                raise NotLiteral('valoare-nelitera', self.base + start)  # a spread element is code
            match = NUMBER.match(text, start)
            if not match or (match.end() < len(text) and re.match(r'[\w$]', text[match.end()])):
                raise NotLiteral('numar-neinteles', self.base + start)
            self.i = match.end()
            kind = 'numar' if re.search(r'[.eE]', match.group(0)) else 'intreg'
            return Node(kind, None, self.base + start, self.base + self.i)
        word = IDENTIFIER.match(text, start)
        if word and word.group(0) in KEYWORDS and not re.match(r'[\w$]', text[word.end():word.end() + 1] or ' '):
            self.i = word.end()
            return Node(KEYWORDS[word.group(0)][0], KEYWORDS[word.group(0)][1], self.base + start, self.base + self.i)
        raise NotLiteral('valoare-nelitera', self.base + start)

    def key(self):
        self.space()
        text, start = self.text, self.i
        if start < len(text) and text[start] in STRING:
            match = STRING[text[start]].match(text, start)
            if not match:
                raise NotLiteral('sir-neinchis', self.base + start)
            self.i = match.end()
            return decode(match.group(0)[1:-1])
        match = IDENTIFIER.match(text, start) or NUMBER.match(text, start)
        if not match:
            raise NotLiteral('cheie-nelitera', self.base + start)
        self.i = match.end()
        return match.group(0)

    def members(self, depth):
        start = self.i
        self.i += 1
        found = []
        while True:
            self.space()
            if self.i >= len(self.text):
                raise NotLiteral('literal-neterminat', self.base + self.i)
            if self.text[self.i] == '}':
                self.i += 1
                return Node('obiect', found, self.base + start, self.base + self.i)
            name = self.key()
            self.space()
            if self.i >= len(self.text) or self.text[self.i] != ':':
                raise NotLiteral('cheie-fara-valoare', self.base + self.i)  # shorthand members and methods are code
            self.i += 1
            found.append((name, self.value(depth + 1)))
            self.space()
            if self.i >= len(self.text):
                raise NotLiteral('literal-neterminat', self.base + self.i)
            if self.text[self.i] == ',':
                self.i += 1
            elif self.text[self.i] != '}':
                raise NotLiteral('sintaxa', self.base + self.i)

    def elements(self, depth):
        start = self.i
        self.i += 1
        found = []
        while True:
            self.space()
            if self.i >= len(self.text):
                raise NotLiteral('literal-neterminat', self.base + self.i)
            if self.text[self.i] == ']':
                self.i += 1
                return Node('tablou', found, self.base + start, self.base + self.i)
            found.append(self.value(depth + 1))
            self.space()
            if self.i >= len(self.text):
                raise NotLiteral('literal-neterminat', self.base + self.i)
            if self.text[self.i] == ',':
                self.i += 1
            elif self.text[self.i] != ']':
                raise NotLiteral('sintaxa', self.base + self.i)

    def statement_end(self):
        """The literal must be a whole statement: the next token is `;`, a new line or the end of the script, never `.map(`, `[0]` or `,`."""
        text, i = self.text, self.i
        while i < len(text) and text[i] in ' \t':
            i += 1
        if i >= len(text) or text[i] in ';\r\n' or text.startswith(('//', '/*'), i):
            return
        raise NotLiteral('expresie-dupa-literal', self.base + i)


def indented_names(options):
    """The names that the reader option `indentate` lists, as a sorted tuple. A reader option is the `citire` of the source: {"tip": "js-literale", "indentate": [...]}."""
    names = options.get('indentate') if isinstance(options, dict) else None
    return tuple(sorted({str(n) for n in names})) if names else ()


def omitted_names(options):
    """The names that the reader option `omise` lists, as a sorted tuple: declarations that the reader must not read as data (a dictionary of interface texts)."""
    names = options.get('omise') if isinstance(options, dict) else None
    return tuple(sorted({str(n) for n in names})) if names else ()


def declaration_pattern(indented):
    """The pattern of a declaration. Without names it is `DECLARATION`: a declaration at the start of a line. With names, a declaration of one of them may also
    be indented: `  var DATA = [...]` inside `(function () {...})()`, or `    window.DATA = [...]` in a script element that the page indents. An indented declaration of another name stays unread (it is a local variable, not the page's data)."""
    if not indented:
        return DECLARATION
    return re.compile(INDENTED.format(names='|'.join(re.escape(n) for n in indented)), re.M)


@lru_cache(maxsize=8)
def script_literals(body, indented=()):
    """Every candidate in the body, in page order: dicts with `variabila`, `node` (a Node or None), `reason` and `at` (offsets in the body).
    `indented` lists the names that may be declared with leading spaces (see `declaration_pattern`)."""
    found, names, islands = [], {}, 0
    declaration = declaration_pattern(indented)

    def unique(name):
        names[name] = names.get(name, 0) + 1
        return name if names[name] == 1 else f'{name}#{names[name]}'

    scripts = [(m.group(1), m.group(2), m.start(2)) for m in SCRIPT.finditer(body)]
    if not scripts and not HTML_PAGE.search(body[:2000]):
        scripts = [('', body, 0)]  # a script file, not a page
    for attributes, text, base in scripts:
        if re.search(r'\bsrc\s*=', attributes, re.I):
            continue
        kind = re.search(r'\btype\s*=\s*["\']?([^"\'\s>]+)', attributes, re.I)
        kind = kind.group(1).lower() if kind else ''
        if kind in ('application/json', 'text/json'):
            islands += 1
            name = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attributes, re.I)
            parser = Parser(text, base)
            record = {'variabila': unique(name.group(1) if name else f'json{islands}'), 'forma-sursa': 'json-izolat', 'start': base + len(text) - len(text.lstrip())}
            try:
                node = parser.value()
                parser.space()
                if parser.i < len(text):
                    raise NotLiteral('sintaxa', base + parser.i)
                if node.kind not in ('obiect', 'tablou'):
                    raise NotLiteral('valoare-nelitera', node.start)
                found.append({**record, 'node': node, 'reason': None, 'at': node.end})
            except NotLiteral as exc:
                found.append({**record, 'node': None, 'reason': exc.reason, 'at': exc.at})
            continue
        if kind not in ('', 'text/javascript', 'application/javascript', 'module'):
            continue
        covered = 0  # a line inside a literal that was read is data, not a declaration
        for match in declaration.finditer(text):
            if base + match.start() < covered:
                continue
            parser = Parser(text, base)
            parser.i = match.end()
            record = {'variabila': unique(match.group(1)), 'forma-sursa': 'literal-script', 'start': base + match.end()}
            try:
                node = parser.value()
                if match.group(2):  # Object.freeze(<literal>)
                    parser.space()
                    if parser.i >= len(text) or text[parser.i] != ')':
                        raise NotLiteral('expresie-dupa-literal', base + parser.i)
                    parser.i += 1
                parser.statement_end()
                found.append({**record, 'node': node, 'reason': None, 'at': node.end})
                covered = node.end
            except NotLiteral as exc:
                found.append({**record, 'node': None, 'reason': exc.reason, 'at': exc.at})
    return found


COMMENT_LIMIT = 600


def preceding_comment(body, start):
    """The comment directly above a declaration, as the page wrote it: a run of `//` lines or one `/* ... */` block that ends on the
    line above. None when the line above is not a comment. `trunchiat` is true when the text is cut at a limit (the locator still covers it all)."""
    line_start = body.rfind('\n', 0, start) + 1
    if line_start == 0:
        return None
    above_end = line_start - 1  # the newline that ends the line above
    above_start = body.rfind('\n', 0, above_end) + 1
    above = body[above_start:above_end]
    if above.rstrip().endswith('*/'):
        open_at = body.rfind('/*', 0, above_end)
        if open_at < 0 or '*/' in body[open_at + 2:above_start + len(above.rstrip()) - 2]:
            return None
        first, last = open_at, above_start + len(above.rstrip())
        text = re.sub(r'^\s*\*\s?', '', body[open_at + 2:last - 2], flags=re.M)
        text = re.sub(r'^[=\s-]+|[=\s-]+$', '', text.strip()) if re.match(r'^[=\s-]', text.strip()) else text.strip()
    else:
        lines, cursor = [], line_start
        while cursor > 0:
            previous_start = body.rfind('\n', 0, cursor - 1) + 1
            line = body[previous_start:cursor - 1]
            if not line.lstrip().startswith('//'):
                break
            lines.append((previous_start, line))
            cursor = previous_start
        if not lines:
            return None
        lines.reverse()
        first, last = lines[0][0], lines[-1][0] + len(lines[-1][1])
        text = '\n'.join(re.sub(r'^\s*//\s?', '', line) for _, line in lines).strip()
    if not text:
        return None
    comment = {'valoare': text[:COMMENT_LIMIT], 'pointer': f'char:{first}-{last}'}
    if len(text) > COMMENT_LIMIT:
        comment['trunchiat'] = True
    return comment


def declarations(body, indented=(), omitted=()):
    """What the reader found, read or skipped. A skipped declaration says why. The comment above a declaration is the page's own words.
    A declaration named in `omitted` is listed as not read, with the reason `omisa-prin-optiune`."""
    out = []
    for item in script_literals(body, indented):
        node = item['node']
        row = {'variabila': item['variabila'], 'forma-sursa': item['forma-sursa'], 'linie': line_of(body, item['start']), 'citit': node is not None}
        if node is not None and item['variabila'] in omitted:
            row.update(citit=False, motiv='omisa-prin-optiune', pointer=f'char:{node.start}-{node.end}')
        elif node is not None:
            row.update(forma='tablou' if node.kind == 'tablou' else 'obiect', elemente=len(node.payload), pointer=f'char:{node.start}-{node.end}')
        else:
            row.update(motiv=item['reason'], pointer=f'char:{item["start"]}-{item["at"]}')
        comment = preceding_comment(body, item['start']) if item['forma-sursa'] == 'literal-script' else None
        if comment:
            row['comentariu'] = comment
        out.append(row)
    return out


def keyed_collection(keys, kinds):
    """The one rule for a keyed collection, for both JSON readers. A keyed collection maps values (county names, identifiers, years) to records.
    `keys` are the member names and `kinds` the kind of each value (`json_kind`, or the kind of a literal Node).
    - 100 members or more is always one.
    - From 2 members, when every key is a year (`^(19|20)[0-9]{2}$`) and the values are of one kind: `{"2014": {...}, "2015": {...}}` repeats
      one record, and its years are values, not field names.
    - From 12 to 99 members, the values must be of one kind (all objects, all arrays, all strings or all numbers), and the keys must not all be
      identifiers (`^[a-z][A-Za-z0-9_]*$`). A record that is 14 fields wide has values of several kinds; an address of 12 text members or a record of
      counters has keys that are field names. Both stay records.
    A null does not count as a kind: a year with no data does not break the collection."""
    if len(keys) >= SURE_COLLECTION:
        return True
    one_kind = len(set(kinds) - {'nul'}) <= 1
    if not one_kind or len(keys) < 2:
        return False
    if all(YEAR_KEY.match(key) for key in keys):
        return True
    return len(keys) >= KEYED_COLLECTION and not all(IDENTIFIER_KEY.match(key) for key in keys)


def json_kind(value):
    """The kind of a parsed JSON value, in the vocabulary of a literal Node (a number is a number whether it is whole or not)."""
    if value is None:
        return 'nul'
    if isinstance(value, bool):
        return 'logic'
    if isinstance(value, (int, float)):
        return 'numar'
    return 'text' if isinstance(value, str) else 'tablou' if isinstance(value, list) else 'obiect'


def keyed_object(value):
    """True when a parsed JSON object is a keyed collection (see `keyed_collection`)."""
    return keyed_collection(list(value), [json_kind(child) for child in value.values()])


def keyed(members):
    """`keyed_collection` for the members (name, Node) of a literal object."""
    return keyed_collection([key for key, _ in members], ['numar' if child.kind in ('intreg', 'numar') else child.kind for _, child in members])


class Walk:
    def __init__(self, body):
        self.body, self.found, self.limit = body, {}, False

    def register(self, variable, path, node, kind, role='camp-date', **extra):
        field = self.found.get(path)
        if field is None:
            if len(self.found) >= MAX_FIELDS:
                self.limit = True
                return
            field = {'nume': path.rsplit('.', 1)[-1], 'cale': path, 'tip_declarat': None, 'tipuri_observate': [], 'stare_tip': 'observat-in-esantion-json',
                     'rol': role, 'pointer': f'char:{node.start}-{node.end}', 'linie': line_of(self.body, node.start), 'variabila': variable, **extra}
            self.found[path] = field
        if kind not in field['tipuri_observate']:
            field['tipuri_observate'].append(kind)

    def walk(self, variable, node, path, depth):
        kind = node.kind
        if kind in ('obiect', 'tablou') and depth > MAX_DEPTH:
            self.limit = True
            return
        if kind == 'obiect':
            members = node.payload
            if keyed(members):
                here = path + '{*}'
                keys = [k[:EXAMPLE_LENGTH] for k, _ in members[:EXAMPLE_KEYS]]
                self.register(variable, here, node, 'object', 'colectie-cu-chei', numar_chei=len(members), chei_exemplu=keys)
                self.limit = self.limit or len(members) > SAMPLE_ROWS
                for _, child in members[:SAMPLE_ROWS]:
                    self.walk(variable, child, here, depth + 1)
            else:
                for key, child in members:
                    self.walk(variable, child, path + '.' + key, depth + 1)
        elif kind == 'tablou':
            elements = node.payload[:SAMPLE_ROWS]
            self.limit = self.limit or len(node.payload) > SAMPLE_ROWS
            here = path + '[]'
            widths = {len(e.payload) for e in elements if e.kind == 'tablou'}
            rows = elements and all(e.kind == 'tablou' and e.payload and all(c.kind not in ('obiect', 'tablou') for c in e.payload) for e in elements)
            if rows and len(widths) == 1 and 1 < next(iter(widths)) <= POSITIONAL_WIDTH:
                for element in elements:
                    for position, cell in enumerate(element.payload):
                        self.register(variable, f'{here}[{position}]', cell, TYPES[cell.kind])
            else:
                for element in elements:
                    self.walk(variable, element, here, depth + 1)
        else:
            self.register(variable, path, node, TYPES[kind])


TYPES = {'text': 'string', 'intreg': 'integer', 'numar': 'number', 'logic': 'boolean', 'nul': 'null'}


def read(body, indented=(), omitted=()):
    """(fields, truncated). Fields are in page order; the same body always gives the same list. A declaration named in `omitted` is not walked."""
    walker = Walk(body)
    for item in script_literals(body, indented):
        if item['node'] is not None and item['variabila'] not in omitted:
            walker.walk(item['variabila'], item['node'], item['variabila'], 0)
    return measured_variables(body) + list(walker.found.values()), walker.limit or len(walker.found) >= MAX_FIELDS


# --- schema.org Dataset in JSON-LD --------------------------------------------------------------------------------------

def json_ld(body):
    """The JSON-LD blocks of the page that are literals, as Nodes in page order. A block that does not parse is not read."""
    found = []
    for script in SCRIPT.finditer(body):
        attributes, text, base = script.group(1), script.group(2), script.start(2)
        kind = re.search(r'\btype\s*=\s*["\']?([^"\'\s>]+)', attributes, re.I)
        if not kind or kind.group(1).lower() != 'application/ld+json' or re.search(r'\bsrc\s*=', attributes, re.I):
            continue
        parser = Parser(text, base)
        try:
            node = parser.value()
            parser.space()
            if parser.i == len(text) and node.kind in ('obiect', 'tablou'):
                found.append(node)
        except NotLiteral:
            continue
    return found


def member(node, name):
    return next((child for key, child in node.payload if key == name), None) if node is not None and node.kind == 'obiect' else None


def types_of(node):
    value = member(node, '@type')
    if value is None:
        return []
    return [decode(value.payload)] if value.kind == 'text' else [decode(v.payload) for v in value.payload if v.kind == 'text'] if value.kind == 'tablou' else []


def dataset_nodes(node):
    """The `Dataset` objects of a JSON-LD block: the top level, the elements of a top-level array and the members of a top-level `@graph`."""
    if node.kind == 'tablou':
        for element in node.payload:
            yield from dataset_nodes(element)
    elif node.kind == 'obiect':
        if 'Dataset' in types_of(node):
            yield node
        graph = member(node, '@graph')
        if graph is not None and graph.kind == 'tablou':
            for element in graph.payload:
                yield from dataset_nodes(element)


def fact(node):
    """A value that the page declares, with its locator. A string keeps its text; a number and a boolean keep their written form."""
    if node.kind == 'text':
        value = decode(node.payload)
    elif node.kind == 'logic':
        value = node.payload
    else:
        return None
    return {'valoare': value, 'pointer': f'char:{node.start}-{node.end}', 'baza': 'declarat-in-pagina'}


def facts(node):
    """One fact for a scalar, a fact for each scalar of an array, and for an object its `name`, else its `@id`."""
    if node is None:
        return []
    if node.kind == 'tablou':
        return [f for element in node.payload for f in facts(element)]
    if node.kind == 'obiect':
        label = member(node, 'name') or member(node, '@id')
        return facts(label) if label is not None and label.kind == 'text' else []
    return [f for f in [fact(node)] if f]


def one(node):
    found = facts(node)
    return found[0] if found else None


DATASET_FACTS = (('nume', 'name'), ('descriere', 'description'), ('adresa', 'url'), ('perioada', 'temporalCoverage'), ('licenta', 'license'),
                 ('limba', 'inLanguage'), ('gratuit', 'isAccessibleForFree'))
DATASET_LISTS = (('bazat_pe', 'isBasedOn'), ('creator', 'creator'), ('editor', 'publisher'), ('cuvinte_cheie', 'keywords'))


def datasets(body):
    """The facts of every schema.org Dataset that the page declares. A missing fact is None (a list is empty). `acoperire` is the name of the place."""
    out = []
    for block in json_ld(body):
        for node in dataset_nodes(block):
            row = {name: one(member(node, key)) for name, key in DATASET_FACTS}
            row.update({name: facts(member(node, key)) for name, key in DATASET_LISTS})
            place = member(node, 'spatialCoverage')
            row['acoperire'] = one(member(place, 'name') if place is not None and place.kind == 'obiect' else place)
            measured = member(node, 'variableMeasured')
            row['variabile_masurate'] = [f for item in (measured.payload if measured is not None and measured.kind == 'tablou' else [])
                                         for f in facts(member(item, 'name') if item.kind == 'obiect' else item)]
            row['pointer'] = f'char:{node.start}-{node.end}'
            out.append(row)
    return out


def measured_variables(body):
    """Each `variableMeasured` entry of each Dataset as a field with the name, description and unit that the page declares."""
    fields = []
    for number, (block, node) in enumerate(((b, n) for b in json_ld(body) for n in dataset_nodes(b)), 1):
        listing = member(node, 'variableMeasured')
        if listing is None or listing.kind != 'tablou':
            continue
        title = one(member(node, 'name'))
        for item in listing.payload:
            label = one(member(item, 'name')) if item.kind == 'obiect' else one(item)
            if not label:
                continue
            description, unit = one(member(item, 'description')), one(member(item, 'unitText'))
            field = {'nume': label['valoare'], 'cale': f'Dataset{number}.variableMeasured.{label["valoare"]}', 'tip_declarat': None, 'stare_tip': 'declarat-in-metadate',
                     'rol': 'masura', 'pointer': f'char:{item.start}-{item.end}', 'linie': line_of(body, item.start), 'variabila': f'Dataset{number}',
                     'grup': title['valoare'] if title else None,
                     'descriere': description['valoare'] if description else '', 'unitate': unit['valoare'] if unit else None}
            fields.append(field)
    return fields
