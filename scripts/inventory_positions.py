"""Reader for the names that a page script gives to the positions of a row. Stdlib only. It makes no request and runs no script.

Format name: `js-pozitii`. A data file can hold its records as rows of cells with no field names (`["Abrud", "Alba", 2, 4360, ...]`). The script that loads the file
usually decodes each row into an object:

    rows = d.rows.map(function (a, i) {
      return { i: i, name: a[0], county: a[1], kind: a[2], pop: a[3], x: a[11] / 10, bb: a[13].map(function (b) { return b / 10; }) };
    });

The names in that object are the page's own name for each position. The reader lists them and nothing else.

- A decoder is an object literal with at least three members of the form `name: variable[number]`, all on the same variable. A member may continue with an expression
  (`a[11] / 10`, `a[13].map(...)`); the reader keeps the text of the expression and does not run it. Other members (`i: i`, `key: fold(a[0])`) are not positions.
- Each position is a field: `nume` (the name in the script), `cale` (`a[3]`, the variable and the position), `pozitie` (the number), `indice_in` (the variable), `expresie`
  (what follows the index, or null), `stare_tip` `utilizat-in-cod-pagina`, `rol` `camp-folosit-de-pagina`, `pointer` (`char:START-END` of the member) and `linie`.
- It is what the page reads, not a schema. The reader does not say which array the variable stands for, and it declares no type. A person who links the script to a data file
  does it with evidence of the script (`d.rows.map(function (a ...`) and of the file (`places.json`), and keeps that link in the group selector, never in this reader.
- Strings, comments and regular expression literals are skipped when the reader looks for braces. A `/` starts a regular expression after an operator or an opening bracket
  and after `return`; elsewhere it is a division. A script that this rule misreads gives no decoder or a wrong one, and the check (`inventory.py --check`) shows any change of the result.
"""
from __future__ import annotations

import re

STATE = 'utilizat-in-cod-pagina'
ROLE = 'camp-folosit-de-pagina'
MIN_POSITIONS = 3
MEMBER = re.compile(r'^\s*([A-Za-z_$][\w$]*)\s*:\s*([A-Za-z_$][\w$]*)\[(\d+)\](.*)$', re.S)
OPEN, CLOSE = '{[(', '}])'


REGEX_AFTER = set('(,=:[!&|?{};+-*%<>~^')
REGEX_KEYWORDS = ('return', 'typeof', 'case', 'in', 'of', 'void', 'delete')


def regex_allowed(text, i):
    """True when a `/` at i starts a regular expression and not a division: the last significant character before it ends an operator or a bracket that opens, or the word is `return`."""
    j = i - 1
    while j >= 0 and text[j] in ' \t\r\n':
        j -= 1
    if j < 0 or text[j] in REGEX_AFTER:
        return True
    word = re.search(r'[A-Za-z_$][\w$]*$', text[:j + 1])
    return bool(word) and word.group(0) in REGEX_KEYWORDS


def skip(text, i, limit):
    """The index after the string, template string, comment or regular expression that starts at i, or None when none starts there. `limit` bounds the scan."""
    c = text[i]
    if c in '"\'`':
        j = i + 1
        while j < limit and text[j] != c:
            j += 2 if text[j] == '\\' else 1
        return j + 1
    if text.startswith('//', i):
        j = text.find('\n', i)
        return limit if j < 0 else j
    if text.startswith('/*', i):
        j = text.find('*/', i + 2)
        return limit if j < 0 else j + 2
    if c == '/' and regex_allowed(text, i):
        j, in_class = i + 1, False
        while j < limit and (in_class or text[j] != '/') and text[j] != '\n':
            if text[j] == '\\':
                j += 1
            elif text[j] == '[':
                in_class = True
            elif text[j] == ']':
                in_class = False
            j += 1
        return j + 1 if j < limit and text[j] == '/' else None
    return None


def objects(text):
    """(start, end) of each `{...}` span of the script, outermost and nested, in order of their start. Strings, template strings, comments and regular expressions are skipped."""
    spans, stack, i, n = [], [], 0, len(text)
    while i < n:
        after = skip(text, i, n)
        if after is not None:
            i = after
            continue
        if text[i] == '{':
            stack.append(i)
        elif text[i] == '}' and stack:
            spans.append((stack.pop(), i + 1))
        i += 1
    return sorted(spans)


def members(text, start, end):
    """The top-level members of the object that spans text[start:end], as (offset, member text). A comma inside brackets, braces or a string does not split."""
    found, depth, i, here, n = [], 0, start + 1, start + 1, end - 1
    while i < n:
        after = skip(text, i, n)
        if after is not None:
            i = after
            continue
        c = text[i]
        if c in OPEN:
            depth += 1
        elif c in CLOSE:
            depth -= 1
        elif c == ',' and depth == 0:
            found.append((here, text[here:i]))
            here = i + 1
        i += 1
    found.append((here, text[here:n]))
    return found


def read(body):
    """The position fields of every decoder in the script, in order of appearance. A body with no decoder is an error: the file is not what this reader reads."""
    fields, used = [], {}
    for start, end in objects(body):
        positions = []
        for offset, member in members(body, start, end):
            match = MEMBER.match(member)
            if match:
                lead = len(member) - len(member.lstrip())
                positions.append((match, offset + lead, offset + len(member.rstrip())))
        by_variable = {}
        for match, first, last in positions:
            by_variable.setdefault(match.group(2), []).append((match, first, last))
        for variable, items in by_variable.items():
            if len(items) < MIN_POSITIONS:
                continue
            used[variable] = used.get(variable, 0) + 1
            label = variable if used[variable] == 1 else f'{variable}#{used[variable]}'
            for match, first, last in items:
                expression = re.sub(r'\s+', ' ', match.group(4)).strip()
                fields.append({'nume': match.group(1), 'cale': f'{label}[{match.group(3)}]', 'tip_declarat': None, 'stare_tip': STATE, 'rol': ROLE,
                               'pointer': f'char:{first}-{last}', 'linie': body.count('\n', 0, first) + 1, 'pozitie': int(match.group(3)),
                               'indice_in': variable, 'expresie': expression or None})
    if not fields:
        raise ValueError(f'The script has no object that names {MIN_POSITIONS} or more positions of one variable')
    return fields


def positions(body, options=None):
    """The reader of `citire: js-pozitii`: field records in the shape of inventory.parse_source."""
    return 'js-pozitii', read(body), False
