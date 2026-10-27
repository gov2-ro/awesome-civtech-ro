"""Reader for the type declarations of a TypeScript file. Stdlib only.

Format name: `typescript` (the extension `.ts` selects it). A project that keeps the shape of its data in TypeScript declares it as `interface` and `type`
declarations: the documents of a search index, the filters of a query, a response of an API. The members of those declarations are the fields that the code
expects. The reader keeps what the text states and nothing else:

- `interface Name extends A, B { … }` and `type Name = { … }` give one field for each member. A declaration that is not an object (`type Id = string | number`, an enum,
  a function, a constant) gives none. Methods and call signatures are not data and give none.
- `nume` is the name of the member, `cale` is `Name.member`, `grup` is the declaration. `tip_declarat` is the type as written, with spaces collapsed (`string | null`,
  `Item[]`, `unknown`): it is a type of the code, not of the stored value. An object type written inline (`{ id: number; text: string }`) is a member of its own with the type
  `object`, and its members follow with the path `Name.member.child`; an array of such objects gives `Name.member[].child` and the type `object[]`.
- `obligatoriu` is false for a member written `name?:`. A member typed `T | null` is still required: the type says that the value can be null, and the reader does not turn it into
  an optional member.
- `extinde` lists the declarations that an interface extends. The members of those declarations are not repeated: they are fields of their own declaration.
- `descriere` is the comment directly above the member (a `//` line, a block of them or a `/** … */` block, no blank line between), or the comment at the end of its line.
  A comment above the declaration belongs to the declaration and to no member.
- Not read, so an error: an index signature (`[key: string]: T`), a mapped type, a getter or a setter inside an interface, and a declaration whose braces do not close.
  The same path under two declarations is an error too.
- Each declaration is read from its own line start. Comments and the text of strings are skipped when the reader looks for braces; the code of a function is never read.

It makes no request and runs no script. The locator `char:START-END` covers the member (its name to the end of its type) in the retained body, so `inventory.py --check`
finds it again. The field limit is 2,000 (`MAX_FIELDS`); a source with more fields is cut and marked partial.
"""
from __future__ import annotations

import re

MAX_FIELDS, MAX_DEPTH = 2000, 12
STATE = 'declarat-in-cod-sursa'
ROLE = 'camp-model'
DECLARATION = re.compile(r'^[ \t]*(?:export\s+)?(?:declare\s+)?(interface|type)\s+([A-Za-z_$][\w$]*)', re.M)
NAME = re.compile(r'[A-Za-z_$][\w$]*')
OPENING, CLOSING = '([{<', ')]}>'


class TypeScriptError(ValueError):
    pass


def blank(text, start, end):
    """`text` with the characters from `start` to `end` replaced by spaces; line breaks stay, so that every offset keeps its place."""
    return text[:start] + re.sub(r'[^\n]', ' ', text[start:end]) + text[end:]


def scan(body):
    """`(structure, clean, comments)`. `structure` is the body with comments and the inside of strings blanked: every brace in it is a real brace.
    `clean` is the body with the comments blanked only: its strings are intact, so that a type written with a literal (`"a" | "b"`) reads as written.
    `comments` lists `(start, end)` of each comment. A quoted string ends at the line end, and a regular expression is not told from a division."""
    structure, clean, comments = list(body), list(body), []
    i, n = 0, len(body)

    def mask(chars, start, end):
        for k in range(start, end):
            if chars[k] != '\n':
                chars[k] = ' '

    while i < n:
        two = body[i:i + 2]
        if two == '//':
            end = body.find('\n', i)
            end = n if end < 0 else end
            comments.append((i, end))
            mask(structure, i, end)
            mask(clean, i, end)
            i = end
        elif two == '/*':
            end = body.find('*/', i + 2)
            end = n if end < 0 else end + 2
            comments.append((i, end))
            mask(structure, i, end)
            mask(clean, i, end)
            i = end
        elif body[i] in '"\'':
            quote, j = body[i], i + 1
            while j < n and body[j] != quote and body[j] != '\n':
                j += 2 if body[j] == '\\' else 1
            mask(structure, i + 1, min(j, n))
            i = j + 1
        elif body[i] == '`':
            j, depth = i + 1, 0
            while j < n and not (body[j] == '`' and depth == 0):
                if body[j] == '\\':
                    j += 1
                elif body[j:j + 2] == '${':
                    depth += 1
                    j += 1
                elif body[j] == '}' and depth:
                    depth -= 1
                j += 1
            mask(structure, i + 1, min(j, n))
            i = j + 1
        else:
            i += 1
    return ''.join(structure), ''.join(clean), comments


def matching(structure, start, opening='{', closing='}'):
    """The index of the bracket that closes the one at `start`."""
    depth = 0
    for i in range(start, len(structure)):
        if structure[i] == opening:
            depth += 1
        elif structure[i] == closing:
            depth -= 1
            if depth == 0:
                return i
    raise TypeScriptError(f'The bracket at character {start} is not closed')


def line_of(body, offset):
    return body.count('\n', 0, offset) + 1


def comment_text(raw):
    if raw.startswith('//'):
        return raw[2:].strip()
    lines = [re.sub(r'^\s*\*+ ?', '', line) for line in raw[2:-2 if raw.endswith('*/') else None].split('\n')]
    return ' '.join(part.strip() for part in lines if part.strip())


def comment_above(body, comments, start):
    """The comment block that ends on the line above `start` (or on the line before a blank-line-free run of comments), when each comment sits on its own lines."""
    texts, edge = [], start
    for c_start, c_end in reversed([c for c in comments if c[1] <= start]):
        between = body[c_end:edge]
        line_start = body.rfind('\n', 0, c_start) + 1
        if between.strip() or between.count('\n') > 1 or body[line_start:c_start].strip():
            break
        texts.append(comment_text(body[c_start:c_end]))
        edge = c_start
    return ' '.join(t for t in reversed(texts) if t)


def comment_after(body, comments, end):
    """The comment that starts on the same line after `end` (after the `;` or `,` of a member)."""
    line_end = body.find('\n', end)
    line_end = len(body) if line_end < 0 else line_end
    for c_start, c_end in comments:
        if end <= c_start < line_end and not body[end:c_start].strip(' \t;,'):
            return comment_text(body[c_start:c_end])
    return ''


def type_end(structure, start, limit):
    """The index where the type of a member ends: a `;` or `,` outside brackets, or a line end where the type cannot go on."""
    depth, i = 0, start
    while i < limit:
        char = structure[i]
        if char == '=' and structure[i + 1:i + 2] == '>':
            i += 2
            continue
        if char in OPENING:
            depth += 1
        elif char in CLOSING:
            depth -= 1
        elif depth == 0 and char in ';,':
            return i
        elif depth == 0 and char == '\n':
            so_far = structure[start:i].strip()
            following = structure[i:limit].lstrip()[:1]
            if so_far and not so_far.endswith(('|', '&', ':', '<', ',', '(', '=>', '?')) and following not in ('|', '&', '.', '?', ':', ''):
                return i
        i += 1
    return limit


class Reader:
    def __init__(self, body):
        self.body = body
        self.structure, self.clean, self.comments = scan(body)
        self.fields, self.paths = [], set()

    def add(self, group, extends, path, name, optional, declared, start, end, description):
        field_path = f'{group}.{path}'
        if field_path in self.paths:
            raise TypeScriptError(f'The path {field_path} occurs twice (two declarations of {group}, or a repeated member)')
        self.paths.add(field_path)
        field = {'nume': name, 'cale': field_path, 'tip_declarat': declared, 'stare_tip': STATE, 'rol': ROLE, 'pointer': f'char:{start}-{end}',
                 'linie': line_of(self.body, start), 'obligatoriu': not optional, 'grup': group}
        if extends:
            field['extinde'] = extends
        if description:
            field['descriere'] = description
        self.fields.append(field)

    def members(self, group, extends, start, end, prefix, depth):
        """The members between `start` and `end` (the text between the braces of one object type)."""
        if depth > MAX_DEPTH:
            raise TypeScriptError('The declaration is nested too deep')
        s, i = self.structure, start
        while True:
            while i < end and s[i] in ' \t\r\n;,':
                i += 1
            if i >= end:
                return
            name_start = i
            modifier = re.match(r'readonly\s+(?=[A-Za-z_$"\'\d])', s[i:end])
            if modifier:
                i += modifier.end()
                name_start = i
            if s[i] in '"\'':
                close = self.body.find(s[i], i + 1)
                name = self.body[i + 1:close]
                i = close + 1
            elif NAME.match(s, i):
                name = NAME.match(s, i).group(0)
                i += len(name)
            elif s[i].isdigit():
                name = re.match(r'\d+', s[i:end]).group(0)
                i += len(name)
            else:
                raise TypeScriptError(f'Line {line_of(self.body, i)}: a member that is not read (index signature, call signature or mapped type): {self.body[i:i + 30]!r}')
            while s[i:i + 1] in (' ', '\t'):
                i += 1
            if name in ('get', 'set') and NAME.match(s, i):
                raise TypeScriptError(f'Line {line_of(self.body, i)}: an accessor is not read')
            optional = s[i:i + 1] == '?'
            if s[i:i + 1] in ('?', '!'):
                i += 1
                while s[i:i + 1] in (' ', '\t'):
                    i += 1
            if s[i:i + 1] in ('(', '<'):  # a method: not data
                i = self.skip_member(i, end)
                continue
            if s[i:i + 1] != ':':
                # a member without a type (`name;`) is `any` in TypeScript: the text states no type
                finish = type_end(s, i, end)
                self.add(group, extends, prefix + name, name, optional, None, name_start, i, self.description(name_start, finish))
                i = finish
                continue
            i += 1
            finish = type_end(s, i, end)
            self.declare(group, extends, prefix + name, i, finish, depth, name_start, name, optional)
            i = finish

    def skip_member(self, i, end):
        """The index after a method signature: its brackets, its return type and the end of the member."""
        s, depth = self.structure, 0
        while i < end:
            if s[i] in OPENING:
                depth += 1
            elif s[i] in CLOSING:
                depth -= 1
            elif depth == 0 and s[i] in ';,\n':
                return i
            i += 1
        return end

    def description(self, start, finish):
        above = comment_above(self.body, self.comments, start)
        return above or comment_after(self.body, self.comments, finish)

    def declare(self, group, extends, path, start, finish, depth, name_start, name, optional):
        """Add the member and then the members of the inline objects of its type."""
        s, c = self.structure, self.clean
        pieces, nested, i, level, last = [], [], start, 0, start
        while i < finish:
            char = s[i]
            if char == '{' and level == 0:
                close = matching(s, i)
                after = s[close + 1:finish]
                arrays = re.match(r'(?:\s*\[\s*\])*', after).group(0)
                suffix = re.sub(r'\s+', '', arrays)
                pieces.append(c[last:i])
                pieces.append('object' + suffix)
                nested.append((i + 1, close, path + suffix + '.'))
                i = close + 1 + len(arrays)
                last = i
                continue
            if char in '([<':
                level += 1
            elif char in ')]>':
                if not (char == '>' and s[i - 1:i] == '='):
                    level -= 1
            i += 1
        pieces.append(c[last:finish])
        declared = re.sub(r'\s+', ' ', ''.join(pieces)).strip().lstrip('|&').strip()
        end = start + len(c[start:finish].rstrip())
        self.add(group, extends, path, name, optional, declared or None, name_start, end, self.description(name_start, finish))
        for inner_start, inner_end, prefix in nested:
            self.members(group, extends, inner_start, inner_end, prefix, depth + 1)

    def read(self):
        found = 0
        for match in DECLARATION.finditer(self.structure):
            kind, name = match.group(1), match.group(2)
            i = match.end()
            if kind == 'interface':
                i = self.skip_generics(i)
                brace = self.structure.find('{', i)
                if brace < 0:
                    continue
                header = self.structure[i:brace].strip()
                extends = []
                if header.startswith('extends'):
                    extends = [re.sub(r'\s+', ' ', part).strip() for part in self.split_top(self.clean[i:brace].strip()[len('extends'):])]
                    extends = [e for e in extends if e]
                elif header:
                    raise TypeScriptError(f'Line {line_of(self.body, match.start())}: the interface {name} has text before its braces that is not `extends`: {header[:40]!r}')
            else:
                i = self.skip_generics(i)
                equals = re.match(r'\s*=\s*', self.structure[i:])
                if not equals or self.structure[i + equals.end():i + equals.end() + 1] != '{':
                    continue
                brace, extends = i + equals.end(), []
            self.members(name, extends, brace + 1, matching(self.structure, brace), '', 1)
            found += 1
        if not found:
            raise TypeScriptError('The file holds no interface and no object type')
        return self.fields

    def skip_generics(self, i):
        s = self.structure
        j = i
        while s[j:j + 1] in (' ', '\t'):
            j += 1
        if s[j:j + 1] == '<':
            return matching(s, j, '<', '>') + 1
        return i

    @staticmethod
    def split_top(text):
        parts, depth, start = [], 0, 0
        for i, char in enumerate(text):
            if char in OPENING:
                depth += 1
            elif char in CLOSING:
                depth -= 1
            elif char == ',' and depth == 0:
                parts.append(text[start:i])
                start = i + 1
        parts.append(text[start:])
        return parts


def read(body):
    """The field records of the type declarations, in file order, and whether the field limit cut them."""
    fields = Reader(body).read()
    return fields[:MAX_FIELDS], len(fields) > MAX_FIELDS
