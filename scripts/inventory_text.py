"""Readers for text formats that declare fields without being a schema file. Stdlib only.

Each reader returns field records in the shape of inventory.parse_source and never guesses a meaning:

- `html-tabele`: HTML tables. A dictionary table (a name column plus a description, unit or type column) gives one field per row.
  A data table gives one field per header cell, with the types seen in up to five sample rows. A headerless two-column table whose
  second column lists items (`group | a, b, c`) gives one field per item.
- `sql`: CREATE TABLE and single-column ALTER TABLE statements (declared SQL types).
- `csharp`: public properties of classes, records and structs, and enum members (declared C# types).
- `php`: Laravel migrations (`Schema::create`, and `Schema::table` in `up()` with `modificare` `alter-add`), API resources (`toArray`) and class constants (code lists).
- `markdown`: dictionary tables written with pipes.
- `js-acces`: names that a page script reads from a record object (`fields['Name']`). It is not a schema: it shows what the page uses.
- `json-comentat`: annotated JSON examples in fenced code blocks of a design document (`"kind": "a | b"`, `// comment`, bare type names).
  It lists the keys the document shows, the alternatives it declares and its comments. Example values are not a type contract.
- `html-api-docs` (module `inventory_apidocs`): an API reference page whose endpoints are cards. Request inputs and response members become
  fields; the operations themselves are a separate list (`inventory_apidocs.operations`).
- `js-literale` (module `inventory_literals`): the data that a page script holds as literals (`const DATA = {...}`) and data islands
  (`<script type="application/json">`). Each path in a literal is a field with the types that a bounded sample shows. The option `tabele`
  (`true`, or a list of positions) adds the table readers of the same page.
- `html-carduri-csv` (module `inventory_csvcards`): a page whose cards offer CSV files with a list of columns. Each column becomes a field with
  the description that the page declares; the files themselves are a separate list of datasets (`inventory_csvcards.csv_datasets`).
- `html-lista-seturi` (module `inventory_setlist`): a page whose tables list data sets (category, name, description, related reports, links to external files).
  It returns no field: the page declares no column. The data sets are a separate list (`inventory_setlist.list_datasets`).

Locators are exact. A character interval `char:START-END` addresses the declaration in the retained body. A table cell is addressed as
`/tabele/T/randuri/R` or `/tabele/T/antet/C`. `inventory.py --check` parses the retained body again and compares every field.
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

from inventory_apidocs import api_docs
from inventory_csvcards import csv_cards
from inventory_literals import read as read_literals
from inventory_setlist import set_list

SAMPLE_ROWS = 5
NAME_COLUMNS = {'matrice', 'nume', 'denumire', 'variabila', 'camp', 'coloana', 'field', 'column', 'name', 'variable', 'indicator',
                'cod', 'code', 'parametru', 'parameter', 'serie', 'atribut', 'attribute', 'tool', 'instrument'}
DESCRIPTION_COLUMNS = {'ce masoara', 'descriere', 'definitie', 'semnificatie', 'explicatie', 'description', 'definition', 'meaning',
                       'detalii', 'details', 'continut', 'purpose', 'scop'}
UNIT_COLUMNS = {'unitate', 'unit', 'um', 'unitate de masura', 'unitati'}
TYPE_COLUMNS = {'tip', 'type', 'format'}
PERIOD_COLUMNS = {'ani', 'an', 'perioada', 'period', 'years', 'acoperire'}
UPDATED_COLUMNS = {'actualizat', 'updated', 'ultima actualizare'}
CONSENT_COLUMNS = {'cookie'}


def plain(value):
    return unicodedata.normalize('NFKD', value.casefold()).encode('ascii', 'ignore').decode().strip()


def clean(value):
    return re.sub(r'\s+', ' ', value or '').strip()


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.stack, self.hidden = [], [], 0
        self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'table':
            self.stack.append({'rows': [], 'header_row': None, 'in_head': False})
        elif tag == 'thead' and self.stack:
            self.stack[-1]['in_head'] = True
        elif tag == 'tr' and self.stack:
            self.row = {'cells': [], 'th': 0, 'head': self.stack[-1]['in_head']}
        elif tag in ('th', 'td') and self.row is not None:
            self.cell = {'text': [], 'th': tag == 'th'}
        elif tag == 'br' and self.cell is not None:
            self.cell['text'].append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag in ('th', 'td') and self.cell is not None and self.row is not None:
            self.row['cells'].append(clean(' '.join(self.cell['text'])))
            self.row['th'] += self.cell['th']
            self.cell = None
        elif tag == 'tr' and self.row is not None and self.stack:
            if self.row['cells'] and any(self.row['cells']):
                self.stack[-1]['rows'].append(self.row)
            self.row = None
        elif tag == 'thead' and self.stack:
            self.stack[-1]['in_head'] = False
        elif tag == 'table' and self.stack:
            self.tables.append(self.stack.pop())

    def handle_data(self, data):
        if not self.hidden and self.cell is not None:
            self.cell['text'].append(data)


def parse_tables(body):
    """Tables of an HTML or markdown-free document as {'header': [...] | None, 'rows': [[...]]}. A header is a row of th cells or thead."""
    parser = _Tables()
    parser.feed(body)
    tables = []
    for raw in parser.tables:
        rows = raw['rows']
        header = None
        if rows and (rows[0]['head'] or rows[0]['th'] == len(rows[0]['cells'])):
            header, rows = rows[0]['cells'], rows[1:]
        tables.append({'header': header, 'rows': [r['cells'] for r in rows]})
    return tables


def markdown_tables(body):
    """Pipe tables of a markdown document. Returns tables like parse_tables, with `linie` of the header row."""
    tables, lines, i = [], body.split('\n'), 0
    while i < len(lines) - 1:
        if '|' in lines[i] and re.match(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$', lines[i + 1]):
            cells = lambda line: [clean(c) for c in line.strip().strip('|').split('|')]
            header, rows, j = cells(lines[i]), [], i + 2
            while j < len(lines) and '|' in lines[j] and lines[j].strip():
                rows.append(cells(lines[j]))
                j += 1
            tables.append({'header': header, 'rows': rows, 'linie': i + 1})
            i = j
        else:
            i += 1
    return tables


def sample_type(value):
    """The written form of a table cell. A cell is always text; `forma-numerica` and `forma-de-data` say how it looks, not what it is
    (an identifier such as a CUI looks numeric and stays an identifier)."""
    value = clean(value)
    if not value:
        return 'null'
    if re.fullmatch(r'-?\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?\s*%?|-?\d+(?:[.,]\d+)?\s*%?|\+?-?\d+(?:[.,]\d+)?', value):
        return 'forma-numerica'
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[T ].*)?|\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2} [^\W\d_]{3,12}\.? \d{4}|[^\W\d_]{3,12} \d{4}', value):
        return 'forma-de-data'
    return 'text'


def header_unit(label):
    """A unit written in parentheses at the end of a header, for example `Tranșa (mld lei)`. It is a declared label, not a type."""
    match = re.search(r'\(([^()]{1,14})\)\s*$', label)
    return match.group(1).strip() if match else None


def column_of(header, names):
    for index, label in enumerate(header):
        if plain(label) in names:
            return index
    return None


def table_fields(tables, fmt='html', selected=None):
    fields = []
    for t, table in enumerate(tables, 1):
        if selected and t not in selected:
            continue
        header, rows = table['header'], table['rows']
        if header and any(plain(h) in CONSENT_COLUMNS for h in header):
            continue
        name = column_of(header, NAME_COLUMNS) if header else None
        meaning = [column_of(header, s) for s in (DESCRIPTION_COLUMNS, UNIT_COLUMNS, TYPE_COLUMNS)] if header else []
        if header and name is not None and any(c is not None for c in meaning):
            description, unit, kind = meaning
            period = column_of(header, PERIOD_COLUMNS)
            updated = column_of(header, UPDATED_COLUMNS)
            for r, row in enumerate(rows):
                if len(row) <= name or not row[name]:
                    continue
                field = {'nume': row[name], 'cale': f'tabel{t}.{row[name]}', 'tip_declarat': row[kind] if kind is not None and len(row) > kind and row[kind] else None,
                         'stare_tip': 'declarat-in-tabel-documentatie', 'rol': 'camp-dictionar', 'pointer': f'/tabele/{t}/randuri/{r}',
                         'descriere': row[description] if description is not None and len(row) > description else '',
                         'unitate': row[unit] if unit is not None and len(row) > unit and row[unit] not in ('', '—', '-') else None}
                if period is not None and len(row) > period and row[period]:
                    field['perioada_declarata'] = row[period]
                if updated is not None and len(row) > updated and row[updated]:
                    field['actualizat_declarat'] = row[updated]
                fields.append(field)
        elif header:
            for c, label in enumerate(header):
                if not label:
                    continue
                types = []
                for row in rows[:SAMPLE_ROWS]:
                    # A row with another width than the header (spanning cells, icons) cannot be matched to its columns.
                    if len(row) == len(header):
                        kind = sample_type(row[c])
                        if kind not in types:
                            types.append(kind)
                field = {'nume': label, 'cale': f'tabel{t}.{label}', 'tip_declarat': None, 'stare_tip': 'antet-tabel-html', 'rol': 'camp-date',
                         'pointer': f'/tabele/{t}/antet/{c}', 'tipuri_observate': types, 'unitate': header_unit(label)}
                if fmt == 'markdown':
                    field['linie'] = table.get('linie')
                fields.append(field)
        elif len(rows) >= 2 and all(len(r) == 2 for r in rows):
            for r, (group, items) in enumerate(rows):
                parts = [clean(p) for p in re.split(r'[,;]', items)]
                if len(parts) >= 2 and all(0 < len(p) <= 60 for p in parts):
                    for n, item in enumerate(parts):
                        fields.append({'nume': item, 'cale': f'tabel{t}.{group}.{item}', 'tip_declarat': None, 'stare_tip': 'declarat-in-text-documentatie',
                                       'rol': 'camp-raspuns', 'grup': group, 'pointer': f'/tabele/{t}/randuri/{r}/elemente/{n}'})
    return fields


def html_tabele(body, options=None):
    return 'html-tabele', table_fields(parse_tables(body), selected=set((options or {}).get('tabele', ()))), False


def markdown(body, options=None):
    tables = [t for t in markdown_tables(body)
              if t['header'] and column_of(t['header'], NAME_COLUMNS) is not None
              and any(column_of(t['header'], s) is not None for s in (DESCRIPTION_COLUMNS, UNIT_COLUMNS, TYPE_COLUMNS))]
    fields = table_fields(tables, 'markdown')
    return 'markdown', fields, False


# --- code readers -----------------------------------------------------------------------------------------------

def line_of(body, offset):
    return body.count('\n', 0, offset) + 1


def code_field(body, name, path, declared, start, end, role='camp-model', **extra):
    return {'nume': name, 'cale': path, 'tip_declarat': declared, 'stare_tip': 'declarat-in-cod-sursa', 'rol': role,
            'pointer': f'char:{start}-{end}', 'linie': line_of(body, start), **extra}


CS_TYPE = re.compile(r'^\s*(?:(?:public|internal|private|protected|sealed|abstract|static|partial|readonly)\s+)*(class|record|struct|enum|interface)\s+(\w+)', re.M)
CS_FROM_QUERY = re.compile(r'\[FromQuery(?:\s*\(\s*Name\s*=\s*"([^"]+)"\s*\))?\]')
CS_PROPERTY = re.compile(r'^[ \t]*(?:\[[^\]\n]*\]\s*)*public\s+(?:required\s+|virtual\s+|override\s+)*([\w<>\[\]\?,\.]+(?:\s*<[^>\n]+>)?\??)\s+(\w+)\s*\{\s*get\s*;', re.M)
CS_ENUM_MEMBER = re.compile(r'^[ \t]*(\w+)\s*(?:=\s*([-\w]+))?\s*,?\s*(?://.*)?$', re.M)


def csharp(body):
    fields, owners = [], [(m.start(), m.group(1), m.group(2)) for m in CS_TYPE.finditer(body)]
    for index, (start, kind, name) in enumerate(owners):
        end = owners[index + 1][0] if index + 1 < len(owners) else len(body)
        chunk = body[start:end]
        if kind == 'enum':
            opening = chunk.find('{')
            closing = chunk.find('}', opening)
            if opening < 0 or closing < 0:
                continue
            for member in CS_ENUM_MEMBER.finditer(chunk[opening + 1:closing]):
                if member.group(1):
                    a = start + opening + 1 + member.start(1)
                    fields.append(code_field(body, member.group(1), f'{name}.{member.group(1)}', None, a, a + len(member.group(0).strip()),
                                             role='cod-enumerare', valoare=member.group(2), grup=name))
            continue
        for member in CS_PROPERTY.finditer(chunk):
            a = start + member.start()
            text = member.group(0)
            required = '[Required' in text or 'required ' in text
            query = CS_FROM_QUERY.search(text)
            extra = {'rol': 'parametru-api', 'loc': 'query', 'nume_in_cod': member.group(2)} if query else {}
            field = code_field(body, query.group(1) if query and query.group(1) else member.group(2), f'{name}.{member.group(2)}',
                               re.sub(r'\s+', '', member.group(1)), a + len(text) - len(text.lstrip()), a + len(text.rstrip()),
                               obligatoriu=required, grup=name)
            fields.append({**field, **extra})
    return 'csharp', fields, False


SQL_CREATE = re.compile(r'create\s+table\s+(?:if\s+not\s+exists\s+)?[`"]?(\w+)[`"]?\s*\(', re.I)
SQL_ALTER = re.compile(r'alter\s+table\s+[`"]?(\w+)[`"]?\s+add\s+(?:column\s+)?[`"]?(\w+)[`"]?\s+([a-z]+(?:\s*\([^)]*\))?(?:\s+unsigned)?)([^;]*);', re.I)
SQL_SKIP = re.compile(r'^\s*(primary\s+key|unique|key|index|constraint|foreign\s+key|fulltext|check)\b', re.I)


def split_top(text, offset):
    """Split a SQL column list on top-level commas, keeping each item's offset."""
    depth, start, parts = 0, 0, []
    for i, char in enumerate(text):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append((offset + start, text[start:i]))
            start = i + 1
    parts.append((offset + start, text[start:]))
    return parts


def sql(body):
    fields = []
    for create in SQL_CREATE.finditer(body):
        depth, i = 1, create.end()
        while i < len(body) and depth:
            depth += {'(': 1, ')': -1}.get(body[i], 0)
            i += 1
        inner = body[create.end():i - 1]
        for offset, item in split_top(inner, create.end()):
            if not item.strip() or SQL_SKIP.match(item):
                continue
            column = re.match(r'\s*[`"]?(\w+)[`"]?\s+([a-zA-Z]+(?:\s*\([^)]*\))?(?:\s+unsigned)?)(.*)', item, re.S)
            if not column:
                continue
            lead = len(item) - len(item.lstrip())
            rest = column.group(3).lower()
            fields.append(code_field(body, column.group(1), f'{create.group(1)}.{column.group(1)}', re.sub(r'\s+', ' ', column.group(2).lower()),
                                     offset + lead, offset + len(item.rstrip()), role='coloana-sql', grup=create.group(1),
                                     obligatoriu='not null' in rest, cheie_primara=False))
    for alter in SQL_ALTER.finditer(body):
        fields.append(code_field(body, alter.group(2), f'{alter.group(1)}.{alter.group(2)}', re.sub(r'\s+', ' ', alter.group(3).lower()),
                                 alter.start(), alter.end(), role='coloana-sql', grup=alter.group(1), obligatoriu='not null' in alter.group(4).lower(),
                                 modificare='alter-add'))
    fields.sort(key=lambda f: int(f['pointer'].split(':')[1].split('-')[0]))
    return 'sql', fields, False


PHP_SCHEMA = re.compile(r"Schema::(create|table)\(\s*'(\w+)'")
PHP_DOWN = re.compile(r'function\s+down\s*\(')
PHP_COLUMN = re.compile(r"\$table->(\w+)\(")
PHP_CONST = re.compile(r'^[ \t]*(?:public\s+|protected\s+|private\s+)?const\s+(\w+)\s*=\s*(-?\d+|\'[^\']*\'|"[^"]*")\s*;[ \t]*(?://\s*(.*))?$', re.M)
PHP_RESOURCE = re.compile(r'function\s+toArray\s*\([^)]*\)[^{]*\{.*?\breturn\s*\[', re.S)
PHP_KEY = re.compile(r"^[ \t]*'([^']+)'\s*=>\s*(.+?),?[ \t]*$", re.M)
TABLE_COLUMNS = {'id': ('id', 'bigint unsigned'), 'timestamps': None, 'softDeletes': ('deleted_at', 'timestamp'), 'rememberToken': ('remember_token', 'string')}


def scan_call(text, i):
    """Return the index after the balanced parentheses that open at text[i]. Quotes and heredoc bodies are skipped."""
    depth, n = 0, len(text)
    while i < n:
        char = text[i]
        if char in '\'"':
            end = text.find(char, i + 1)
            while end > 0 and text[end - 1] == '\\':
                end = text.find(char, end + 1)
            i = (end if end > 0 else n) + 1
            continue
        if text.startswith('<<<', i):
            label = re.match(r"<<<['\"]?(\w+)['\"]?", text[i:])
            if label:
                close = re.compile(r'^\s*' + label.group(1) + r'\b', re.M).search(text, i + len(label.group(0)))
                i = close.end() if close else n
                continue
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def php_chain(text, i):
    """Chained calls after a column definition: [(method, argument text)], and the index where the statement ends."""
    calls = []
    while True:
        match = re.compile(r'\s*->\s*(\w+)').match(text, i)
        if not match:
            break
        i = match.end()
        argument = ''
        if text[i:i + 1] == '(':
            stop = scan_call(text, i)
            argument = text[i + 1:stop - 1]
            i = stop
        calls.append((match.group(1), argument))
    end = re.compile(r'\s*;').match(text, i)
    return calls, (end.end() if end else i)


def doc_comment(block):
    """Description and `@var` type of a comment block that precedes a declaration."""
    lines = [re.sub(r'^\s*(?:/\*+|\*+/?|//)\s?', '', line).strip() for line in block.strip().split('\n')]
    declared = next((re.match(r'@var\s+([^\s$]+)', line).group(1) for line in lines if re.match(r'@var\s+[^\s$]', line)), None)
    description = ' '.join(line.strip() for line in lines if line.strip() and not line.strip().startswith('@') and line.strip() != '*/')
    return description, declared


def php(body):
    fields = []
    down = PHP_DOWN.search(body)
    for create in PHP_SCHEMA.finditer(body):
        table = create.group(2)
        altered = create.group(1) == 'table'
        alter = {'modificare': 'alter-add'} if altered else {}
        if altered and down and create.start() > down.start():
            continue  # the reverse of a migration drops or restores columns; it adds nothing
        end = body.find('});', create.end())
        stop_at = end if end > 0 else len(body)
        chunk = body[:stop_at]
        for column in PHP_COLUMN.finditer(chunk, create.end()):
            method = column.group(1)
            open_at = column.end() - 1
            stop = scan_call(chunk, open_at)
            argument = chunk[open_at + 1:stop - 1]
            chain, finish = php_chain(chunk, stop)
            start, last = column.start(), finish
            name = (re.match(r"\s*'([^']+)'", argument) or [None, None])[1]
            modifiers = [m for m, _ in chain]
            comment = next((a.strip().strip('\'"') for m, a in chain if m == 'comment'), None)
            nullable = 'nullable' in modifiers
            if method == 'timestamps':
                for stamp in ('created_at', 'updated_at'):
                    fields.append(code_field(body, stamp, f'{table}.{stamp}', 'timestamp', start, last, role='coloana-sql', grup=table, obligatoriu=False, **alter))
                continue
            if method in ('id',) and not name:
                name, method = 'id', 'bigint unsigned'
            elif method == 'foreignIdFor':
                model = re.match(r'\s*(\w+)::class', argument)
                if not model:
                    continue
                name = re.sub(r'(?<!^)(?=[A-Z])', '_', model.group(1)).lower() + '_id'
                extra_name = {'baza_numelui': 'conventie-laravel', **alter}
                fields.append(code_field(body, name, f'{table}.{name}', 'foreignIdFor', start, last, role='coloana-sql', grup=table,
                                         obligatoriu=not nullable, modificatori=modifiers, **extra_name))
                continue
            if not name or method in ('index', 'unique', 'primary', 'foreign', 'dropColumn', 'rename', 'dropIndex', 'fullText'):
                continue
            extra = {'descriere': comment} if comment else {}
            if altered:
                extra['modificare'] = 'alter-change' if 'change' in modifiers else 'alter-add'
            if method == 'enum':
                values = re.findall(r"'([^']+)'", argument)
                if values:
                    extra['valori_enum'] = values[:30]
            stored = next((a for m, a in chain if m in ('storedAs', 'virtualAs')), None)
            if stored:
                extra['formula_declarata'] = re.sub(r'\s+', ' ', re.sub(r"<<<'?\w+'?|^\s*[A-Z]{2,}\s*$", '', stored, flags=re.M)).strip()
            fields.append(code_field(body, name, f'{table}.{name}', method, start, last, role='coloana-sql', grup=table,
                                     obligatoriu=not nullable, modificatori=modifiers, **extra))
    resource = PHP_RESOURCE.search(body)
    if resource:
        depth, i = 1, resource.end()
        while i < len(body) and depth:
            depth += {'[': 1, ']': -1}.get(body[i], 0)
            i += 1
        block = body[resource.end():i - 1]
        klass = re.search(r'class\s+(\w+)', body)
        owner = klass.group(1) if klass else 'Resource'
        previous, stack, level = 0, [], 0
        for line in re.finditer(r'^.*$', block, re.M):
            text = line.group(0)
            key = PHP_KEY.match(text)
            handled = bool(key) and level == len(stack)
            if handled:
                before = block[previous:line.start()]
                comment = re.findall(r'/\*.*?\*/', before, re.S)
                description, declared = doc_comment(comment[-1]) if comment and not before[before.rfind('*/') + 2:].strip() else ('', None)
                a = resource.end() + line.start() + len(text) - len(text.lstrip())
                path = '.'.join([*stack, key.group(1)])
                expression = key.group(2).strip().rstrip(',')
                fields.append(code_field(body, key.group(1), f'{owner}.{path}', declared, a, resource.end() + line.end(), role='camp-raspuns',
                                         expresie=expression, grup=owner, **({'descriere': description} if description else {})))
                if expression == '[':
                    stack.append(key.group(1))
            if handled:
                previous = line.end()
            level += text.count('[') - text.count(']')
            while len(stack) > level:
                stack.pop()
    klass = re.search(r'class\s+(\w+)', body)
    for const in PHP_CONST.finditer(body):
        name = const.group(1)
        fields.append(code_field(body, name, f'{klass.group(1) if klass else "const"}.{name}', None, const.start() + len(const.group(0)) - len(const.group(0).lstrip()),
                                 const.end(), role='cod-enumerare', valoare=const.group(2).strip('\'"'), grup=name.split('_')[0],
                                 descriere=const.group(3) or ''))
    fields.sort(key=lambda f: int(f['pointer'].split(':')[1].split('-')[0]))
    return 'php', fields, False


FENCE = re.compile(r'^```[ \t]*(?:json|jsonc|json5)?[ \t]*\n(.*?)^```', re.M | re.S | re.I)


class _Shape:
    """A tolerant reader for annotated JSON examples: comments, bare type names, "a | b" alternatives and "..." ellipses."""

    def __init__(self, text, base, heading):
        self.t, self.base, self.heading, self.i, self.fields, self.last = text, base, heading, 0, [], None

    def ws(self, key_line=None):
        while self.i < len(self.t):
            c = self.t[self.i]
            if c.isspace():
                self.i += 1
            elif self.t.startswith('//', self.i):
                end = self.t.find('\n', self.i)
                end = len(self.t) if end < 0 else end
                self.note(self.t[self.i + 2:end].strip(), self.i)
                self.i = end
            elif self.t.startswith('/*', self.i):
                end = self.t.find('*/', self.i)
                end = len(self.t) if end < 0 else end + 2
                self.note(self.t[self.i + 2:end - 2].strip(), self.i)
                self.i = end
            else:
                break

    def note(self, text, at):
        """A comment belongs to the key on its own line; a comment on a line of its own belongs to the next key."""
        if not text or self.last is None:
            return
        same_line = self.t.count('\n', self.last['_at'], at) == 0 or self.t[self.last['_at']:at].count('\n') <= self.last['_span']
        if same_line:
            self.last['descriere'] = (self.last.get('descriere', '') + ' ' + text).strip()

    def string(self):
        start = self.i
        self.i += 1
        while self.i < len(self.t) and self.t[self.i] != '"':
            self.i += 2 if self.t[self.i] == '\\' else 1
        self.i += 1
        return self.t[start + 1:self.i - 1], start, self.i

    def value(self, path, field):
        self.ws()
        if self.i >= len(self.t):
            return
        c = self.t[self.i]
        if c == '{':
            self.i += 1
            self.obj(path)
        elif c == '[':
            self.i += 1
            while True:
                self.ws()
                if self.i >= len(self.t) or self.t[self.i] == ']':
                    self.i += 1
                    break
                if self.t[self.i] == ',':
                    self.i += 1
                    continue
                before = self.i
                self.value(path + '[]', field)
                if self.i == before:
                    self.i += 1
        elif c == '"':
            text, a, b = self.string()
            if field is not None and text != '...':
                parts = [p.strip() for p in text.split(' | ')]
                if len(parts) > 1 and all(0 < len(p) <= 60 for p in parts):
                    field['valori_enum'] = parts[:40]
                else:
                    field.setdefault('exemplu', text[:80])
                field.setdefault('tipuri_observate', [])
                if 'string' not in field['tipuri_observate']:
                    field['tipuri_observate'].append('string')
        else:
            m = re.compile(r'-?\d+(?:\.\d+)?|true|false|null|[A-Za-z_][\w.]*').match(self.t, self.i)
            if not m:
                self.i += 1
                return
            self.i = m.end()
            token = m.group(0)
            kind = 'number' if re.match(r'-?\d', token) else 'boolean' if token in ('true', 'false') else 'null' if token == 'null' else None
            if field is not None:
                if kind:
                    field.setdefault('tipuri_observate', [])
                    if kind not in field['tipuri_observate']:
                        field['tipuri_observate'].append(kind)
                else:
                    field['tip_referinta'] = token
        if field is not None and c in '{[':
            field.setdefault('tipuri_observate', [])
            kind = 'object' if c == '{' else 'array'
            if kind not in field['tipuri_observate']:
                field['tipuri_observate'].append(kind)

    def obj(self, path):
        while True:
            self.ws()
            if self.i >= len(self.t) or self.t[self.i] == '}':
                self.i += 1
                return
            if self.t[self.i] == ',':
                self.i += 1
                continue
            if self.t[self.i] != '"':
                self.i += 1
                continue
            key, a, b = self.string()
            self.ws()
            if self.t[self.i:self.i + 1] != ':':
                continue
            self.i += 1
            if key == '...':
                self.value(path, None)
                continue
            here = f'{path}.{key}' if path else key
            field = {'nume': key, 'cale': f'{self.heading}::{here}' if self.heading else here, 'tip_declarat': None,
                     'stare_tip': 'exemplu-in-documentatie', 'rol': 'camp-exemplu', 'pointer': f'char:{self.base + a}-{self.base + b}',
                     'linie': None, 'grup': self.heading or None, '_at': self.i, '_span': 0}
            self.fields.append(field)
            self.last = field
            self.value(here, field)
            field['_span'] = self.t.count('\n', field['_at'], self.i)
            self.last = field


def json_comentat(body):
    """Keys, declared alternatives and comments of annotated JSON examples in a design document."""
    fields, skipped = [], 0
    for block in FENCE.finditer(body):
        text = block.group(1)
        if not text.lstrip().startswith(('{', '[')):
            continue
        heading = None
        for found in re.finditer(r'^#{2,4}\s+(.+)$', body[:block.start()], re.M):
            heading = found.group(1).strip().replace('`', '')
        reader = _Shape(text, block.start(1), heading)
        try:
            reader.value('', None)
        except (IndexError, RecursionError):
            skipped += 1
        for field in reader.fields:
            field['linie'] = line_of(body, int(field['pointer'].split(':')[1].split('-')[0]))
            field.pop('_at'), field.pop('_span')
        fields += reader.fields
    return 'json-comentat', fields[:2000], skipped > 0 or len(fields) > 2000


def js_literale(body, options=None):
    """Data literals of page scripts, and (with the option `tabele`) the tables of the same page. Table fields come first: they are what a visitor sees."""
    fields, truncated = read_literals(body)
    tables = (options or {}).get('tabele')
    if tables:
        fields = table_fields(parse_tables(body), selected=None if tables is True else set(tables)) + fields
    return 'js-literale', fields, truncated


def js_acces(body, objects=('fields',)):
    """Names that inline page scripts read from a record object, `fields['Name']` or `fields.name`. Not a schema."""
    fields, seen = [], {}
    for script in re.finditer(r'<script\b[^>]*>(.*?)</script>', body, re.S | re.I):
        for obj in objects:
            pattern = re.compile(rf"\b{re.escape(obj)}\s*(?:\[\s*(['\"])((?:(?!\1).)+)\1\s*\]|\.([A-Za-z_]\w*))")
            for access in pattern.finditer(script.group(1)):
                name = access.group(2) or access.group(3)
                start = script.start(1) + access.start()
                if name in seen:
                    seen[name]['accesari'] += 1
                    continue
                seen[name] = {'nume': name, 'cale': f'{obj}.{name}', 'tip_declarat': None, 'stare_tip': 'utilizat-in-cod-pagina', 'rol': 'camp-folosit-de-pagina',
                              'pointer': f'char:{start}-{script.start(1) + access.end()}', 'linie': line_of(body, start), 'accesari': 1}
                fields.append(seen[name])
    return 'js-acces', fields, False


READERS = {'html-tabele': html_tabele, 'markdown': markdown, 'csharp': lambda body, options=None: csharp(body),
           'sql': lambda body, options=None: sql(body), 'php': lambda body, options=None: php(body),
           'json-comentat': lambda body, options=None: json_comentat(body), 'html-api-docs': lambda body, options=None: api_docs(body, options),
           'html-carduri-csv': csv_cards, 'js-literale': js_literale, 'html-lista-seturi': set_list}
EXTENSIONS = {'.cs': 'csharp', '.sql': 'sql', '.php': 'php', '.md': 'markdown'}


def read_text(body, kind, options=None):
    if kind == 'js-acces':
        return js_acces(body, tuple((options or {}).get('obiecte', ('fields',))))
    return READERS[kind](body, options)
