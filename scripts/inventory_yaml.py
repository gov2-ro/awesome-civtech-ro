"""A reader of the YAML subset that an OpenAPI file uses. Stdlib only.

Reader name (`citire`): `openapi-yaml`. The standard library has no YAML parser, and an API can serve its contract as YAML (SICAP.ai, 2026-10-27). The reader
parses the text into the same Python values that `json.loads` gives for the same document (dictionaries with text keys, lists, text, numbers, booleans,
`None`). `inventory.parse_source` then reads the contract with the OpenAPI reader, so a YAML contract and a JSON contract give the same field records.

It reads what an OpenAPI file uses and refuses the rest. It never guesses: a construct that it does not read is an error with the line number.

- Block mappings and block sequences, nested by spaces. A sequence may sit at the indent of its key. A compact mapping in a sequence item (`- name: a`) works.
- Plain scalars, also over several lines (a line break becomes a space, a blank line becomes a line break). A plain scalar that holds `: ` is an error.
- Double-quoted scalars (all escapes of the YAML 1.2 specification) and single-quoted scalars, also over several lines.
- Block scalars `|` and `>` with the chomping marks `-` and `+`. An explicit indentation digit is an error.
- Flow sequences and flow mappings (`[a, b]`, `{a: 1}`, `[]`, `{}`), also over several lines. A flow mapping needs a value for each key.
- Comments (`# …` after a space, or on a line of their own). A `---` at the top is allowed; a second document is an error.
- Types follow the core schema of YAML 1.2: `null`, `~` and the empty value are `None`; `true` and `false` (three spellings) are booleans; a decimal integer is an
  `int`; a decimal number with a point or an exponent is a `float`; `.inf` and `.nan` are floats. Everything else is text. A date or a time (`2024-03-15T10:30:00Z`) stays
  text, and `yes`, `no`, `on`, `off` stay text (YAML 1.1 reads them as booleans). An integer with a leading zero (`007`) stays text: YAML 1.1 reads it as octal, YAML 1.2 as
  decimal, and the reader does not choose. Hexadecimal and octal integers (`0x1F`, `0o17`) stay text. Keys are always text, written as in the file.
- Not read, so an error: anchors (`&a`), aliases (`*a`), tags (`!!str`), merge keys (`<<`), complex keys (`? `), directives (`%YAML`), a tab in the indent, a duplicate key,
  and a document that is not a mapping or a sequence.

`load(text)` returns `(document, lines)`. `lines` maps the JSON pointer of each mapping key and sequence item (`/paths/~1v1~1health/get`) to its 1-based line in the text.
A field record of an OpenAPI source keeps that line as `linie`, because the JSON pointer of a record names the parsed document and a person looks for it in the file.
"""
from __future__ import annotations

import re

MAX_DEPTH = 60
FORBIDDEN_START = set(',[]{}#&*!|>\'"%@`')
ESCAPES = {'0': '\0', 'a': '\a', 'b': '\b', 't': '\t', '\t': '\t', 'n': '\n', 'v': '\v', 'f': '\f', 'r': '\r', 'e': '\x1b', ' ': ' ', '"': '"', '/': '/',
           '\\': '\\', 'N': '\x85', '_': '\xa0', 'L': ' ', 'P': ' '}
HEX_ESCAPES = {'x': 2, 'u': 4, 'U': 8}
INTEGER = re.compile(r'[-+]?[0-9]+$')
LEADING_ZERO = re.compile(r'[-+]?0[0-9]+$')
DECIMAL = re.compile(r'[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?$')
SPECIAL_FLOATS = {'.inf': float('inf'), '.Inf': float('inf'), '.INF': float('inf'), '+.inf': float('inf'), '+.Inf': float('inf'), '+.INF': float('inf'),
                  '-.inf': float('-inf'), '-.Inf': float('-inf'), '-.INF': float('-inf'), '.nan': float('nan'), '.NaN': float('nan'), '.NAN': float('nan')}
WORDS = {'': None, '~': None, 'null': None, 'Null': None, 'NULL': None, 'true': True, 'True': True, 'TRUE': True, 'false': False, 'False': False, 'FALSE': False}


def pointer_part(value):
    """One part of a JSON pointer (RFC 6901): `~` and `/` are escaped."""
    return str(value).replace('~', '~0').replace('/', '~1')


class YamlError(ValueError):
    pass


class _Unterminated(Exception):
    """A quoted scalar or a flow collection that the text ends before it closes: the caller can add the next line."""


def resolve(text):
    """The value of a plain scalar (core schema of YAML 1.2, without the readings that need a choice)."""
    if text in WORDS:
        return WORDS[text]
    if text in SPECIAL_FLOATS:
        return SPECIAL_FLOATS[text]
    if LEADING_ZERO.match(text):
        return text
    if INTEGER.match(text):
        return int(text)
    if DECIMAL.match(text):
        return float(text)
    return text


def cut_comment(text):
    """The text without a trailing comment (`#` after a space or a tab), and without trailing spaces."""
    match = re.search(r'[ \t]#', text)
    return (text[:match.start()] if match else text).rstrip()


def scan_quoted(text, start, quote):
    """The value of the quoted scalar whose opening quote is at `start`, and the index after the closing quote. A line break inside the scalar folds:
    the spaces around it go, one break becomes a space, and each blank line becomes a line break. `\\` before a line break (double quotes) joins the lines."""
    out, protected, i = [], 0, start + 1
    while i < len(text):
        char = text[i]
        if char == quote:
            if quote == "'" and text[i + 1:i + 2] == "'":
                out.append("'")
                protected = len(out)
                i += 2
                continue
            return ''.join(out), i + 1
        if char == '\\' and quote == '"':
            following = text[i + 1:i + 2]
            if following == '\n':
                i += 2
                while i < len(text) and text[i] in ' \t':
                    i += 1
                continue
            if following in HEX_ESCAPES:
                width = HEX_ESCAPES[following]
                digits = text[i + 2:i + 2 + width]
                if len(digits) < width or not re.fullmatch(r'[0-9A-Fa-f]+', digits):
                    raise YamlError(f'A bad escape in a double-quoted scalar: \\{following}{digits}')
                out.append(chr(int(digits, 16)))
                i += 2 + width
            elif following in ESCAPES:
                out.append(ESCAPES[following])
                i += 2
            elif following == '':
                break
            else:
                raise YamlError(f'An unknown escape in a double-quoted scalar: \\{following}')
            protected = len(out)
            continue
        if char == '\n':
            while len(out) > protected and out[-1] in ' \t':
                out.pop()
            breaks = 0
            while True:
                i += 1
                end = text.find('\n', i)
                line = text[i:] if end < 0 else text[i:end]
                if line.strip(' \t') == '' and end >= 0:
                    breaks += 1
                    i = end
                    continue
                break
            out.append('\n' * breaks if breaks else ' ')
            protected = len(out)
            while i < len(text) and text[i] in ' \t':
                i += 1
            continue
        out.append(char)
        i += 1
    raise _Unterminated()


def skip_flow(text, i):
    """The index of the next character that is not a space, a line break or a comment."""
    while i < len(text):
        if text[i] in ' \t\n':
            i += 1
        elif text[i] == '#' and (i == 0 or text[i - 1] in ' \t\n'):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
        else:
            break
    return i


def flow_plain(text, i, in_key):
    """A plain scalar inside a flow collection: it ends at `,`, `]`, `}`, a comment, a line break, or (for a key) `: `."""
    start = i
    while i < len(text):
        char = text[i]
        if char in ',]}\n' or (char == '#' and i > start and text[i - 1] in ' \t'):
            break
        if char == ':' and (text[i + 1:i + 2] in ('', ' ', '\t', '\n', ',', ']', '}')):
            if in_key:
                break
            raise YamlError(f'A plain scalar in a flow collection holds ": ": {text[start:i + 1]!r}')
        i += 1
    return text[start:i].strip(' \t'), i


def flow_value(text, i, depth):
    if depth > MAX_DEPTH:
        raise YamlError('The document is nested too deep')
    i = skip_flow(text, i)
    if i >= len(text):
        raise _Unterminated()
    char = text[i]
    if char == '[':
        items, i = [], i + 1
        while True:
            i = skip_flow(text, i)
            if i >= len(text):
                raise _Unterminated()
            if text[i] == ']':
                return items, i + 1
            value, i = flow_value(text, i, depth + 1)
            i = skip_flow(text, i)
            if i >= len(text):
                raise _Unterminated()
            if text[i] == ',':
                items.append(value)
                i += 1
            elif text[i] == ']':
                items.append(value)
            else:
                raise YamlError(f'A flow sequence needs "," or "]" after an item, not {text[i]!r}')
    if char == '{':
        result, i = {}, i + 1
        while True:
            i = skip_flow(text, i)
            if i >= len(text):
                raise _Unterminated()
            if text[i] == '}':
                return result, i + 1
            if text[i] in '"\'':
                key, i = scan_quoted(text, i, text[i])
            else:
                key, i = flow_plain(text, i, True)
                if key == '' or key[0] in '&*!|>%@`[{':
                    raise YamlError(f'A flow mapping key that is not read: {key!r}')
            i = skip_flow(text, i)
            if i >= len(text):
                raise _Unterminated()
            if text[i] != ':':
                raise YamlError(f'A flow mapping needs a value for the key {key!r}')
            if key in result:
                raise YamlError(f'The key {key!r} occurs twice in a flow mapping')
            value, i = flow_value(text, i + 1, depth + 1)
            result[key] = value
            i = skip_flow(text, i)
            if i >= len(text):
                raise _Unterminated()
            if text[i] == ',':
                i += 1
            elif text[i] != '}':
                raise YamlError(f'A flow mapping needs "," or "}}" after a value, not {text[i]!r}')
    if char in '"\'':
        return scan_quoted(text, i, char)
    if char in '&*!|>%@`':
        raise YamlError(f'A flow value that starts with {char!r} is not read (anchors, aliases, tags and block scalars are not)')
    raw, i = flow_plain(text, i, False)
    if raw == '':
        raise YamlError('An empty item in a flow collection')
    return resolve(raw), i


def key_split(content):
    """`(key, rest)` when the line is a mapping entry (`key: value`, `"key": value`, `key:`), else None. `rest` is the text after the colon, stripped."""
    first = content[0]
    if first in '"\'':
        try:
            key, end = scan_quoted(content, 0, first)
        except _Unterminated:
            return None
        after = content[end:].lstrip(' \t')
        if after.startswith(':') and after[1:2] in ('', ' ', '\t'):
            return key, after[1:].strip(' \t')
        return None
    if first in FORBIDDEN_START or (first in '-?:' and content[1:2] in ('', ' ', '\t')):
        return None
    for i, char in enumerate(content):
        if char == ':' and content[i + 1:i + 2] in ('', ' ', '\t'):
            return content[:i].rstrip(' \t'), content[i + 1:].strip(' \t')
        if char == '#' and i > 0 and content[i - 1] in ' \t':
            return None
    return None


def is_item(content):
    return content == '-' or content.startswith(('- ', '-\t'))


class _Parser:
    def __init__(self, text):
        text = text.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n')
        self.lines = text.split('\n')
        self.pos = 0
        self.index = {}
        self.started = False

    def fail(self, message, line=None):
        raise YamlError(f'Line {(self.pos if line is None else line) + 1}: {message}')

    def peek(self):
        """The next line that is not blank and not a comment: `(indent, content)`, or None at the end. It moves to that line."""
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            stripped = line.strip(' \t')
            if stripped == '' or stripped.startswith('#'):
                self.pos += 1
                continue
            lead = line[:len(line) - len(line.lstrip(' \t'))]
            if '\t' in lead:
                self.fail('A tab in the indent is not read')
            if line.startswith('---') and line[3:4] in ('', ' ', '\t'):
                if self.started:
                    self.fail('A second document (---) is not read')
                if stripped[3:].strip(' \t') not in ('', ) and not stripped[3:].strip(' \t').startswith('#'):
                    self.fail('Content after --- is not read')
                self.pos += 1
                self.started = True
                continue
            if line.startswith('...') and line[3:4] in ('', ' ', '\t'):
                self.pos = len(self.lines)
                return None
            if line.startswith('%'):
                self.fail('A directive (%) is not read')
            self.started = True
            return len(lead), line[len(lead):].rstrip()
        return None

    def record(self, path):
        self.index['/' + '/'.join(pointer_part(part) for part in path)] = self.pos + 1

    def block(self, parent, path, depth):
        """The node that starts on the next significant line when its indent is above `parent`; None when the next line is not deeper."""
        if depth > MAX_DEPTH:
            self.fail('The document is nested too deep')
        line = self.peek()
        if line is None or line[0] <= parent:
            return None
        indent, content = line
        if is_item(content):
            return self.sequence(indent, path, depth)
        if key_split(content) is not None:
            return self.mapping(indent, path, depth)
        return self.inline(content, parent, path)

    def mapping(self, indent, path, depth):
        result = {}
        while True:
            line = self.peek()
            if line is None or line[0] < indent:
                return result
            if line[0] > indent:
                self.fail('Unexpected indent')
            split = key_split(line[1])
            if split is None:
                self.fail('A mapping entry needs "key: value"' if not is_item(line[1]) else 'A sequence item inside a mapping')
            key, rest = split
            if key == '<<':
                self.fail('A merge key (<<) is not read')
            if key in result:
                self.fail(f'The key {key!r} occurs twice')
            item_path = path + [key]
            self.record(item_path)
            if rest == '' or rest.startswith('#'):
                self.pos += 1
                following = self.peek()
                if following and following[0] == indent and is_item(following[1]):
                    result[key] = self.sequence(indent, item_path, depth + 1)
                else:
                    result[key] = self.block(indent, item_path, depth + 1)
            else:
                result[key] = self.inline(rest, indent, item_path)

    def sequence(self, indent, path, depth):
        result = []
        while True:
            line = self.peek()
            if line is None or line[0] < indent or (line[0] == indent and not is_item(line[1])):
                return result
            if line[0] > indent:
                self.fail('Unexpected indent')
            item_path = path + [str(len(result))]
            self.record(item_path)
            after = line[1][1:]
            rest = after.lstrip(' \t')
            if rest == '' or rest.startswith('#'):
                self.pos += 1
                result.append(self.block(indent, item_path, depth + 1))
            else:
                # Move the content to its own column, so that a compact mapping or a nested sequence reads like a block at that indent.
                column = indent + 1 + len(after) - len(rest)
                self.lines[self.pos] = ' ' * column + rest
                result.append(self.block(indent, item_path, depth + 1))

    def inline(self, text, parent, path):
        """The value that starts in `text` (the rest of the current line), and the lines that it continues on. `parent` is the indent of the key or the dash."""
        first = text[0]
        start = self.pos
        if first in '|>':
            return self.block_scalar(text, parent)
        if first in '&*!':
            self.fail('An anchor, an alias or a tag is not read')
        if first in '%@`':
            self.fail(f'A value that starts with {first!r} is not read')
        if first in '"\'[{':
            line = self.lines[self.pos]
            joined = text + line[len(line.rstrip(' \t')):]  # a trailing space can be an escaped one (`\\ `): the first line keeps it
            while True:
                try:
                    if first in '"\'':
                        value, end = scan_quoted(joined, 0, first)
                    else:
                        value, end = flow_value(joined, 0, 0)
                    break
                except _Unterminated:
                    self.pos += 1
                    if self.pos >= len(self.lines):
                        self.fail('A quoted scalar or a flow collection is not closed', start)
                    joined += '\n' + self.lines[self.pos]
                except YamlError as exc:
                    self.fail(str(exc), start)
            tail = joined[end:]
            if skip_flow(tail, 0) != len(tail):
                self.fail('Text after a quoted scalar or a flow collection', start)
            self.pos += 1
            return value
        return self.plain(text, parent)

    def plain(self, text, parent):
        start = self.pos
        pieces = [cut_comment(text)]
        ended = pieces[0] != text.rstrip()
        self.pos += 1
        breaks = 0
        while not ended and self.pos < len(self.lines):
            line = self.lines[self.pos]
            stripped = line.strip(' \t')
            if stripped == '':
                breaks += 1
                self.pos += 1
                continue
            if stripped.startswith('#') or len(line) - len(line.lstrip(' ')) <= parent or '\t' in line[:len(line) - len(line.lstrip(' \t'))]:
                break
            piece = cut_comment(stripped)
            ended = piece != stripped
            pieces.append('\n' * breaks if breaks else ' ')
            pieces.append(piece)
            breaks = 0
            self.pos += 1
        value = ''.join(pieces)
        if re.search(r':(?:[ \t]|$)', value):
            self.fail('A plain scalar that holds ": " (quote it)', start)
        return resolve(value) if len(pieces) == 1 else value

    def block_scalar(self, header, parent):
        start = self.pos
        match = re.fullmatch(r'([|>])([-+]?)(?:[ \t]+#.*)?', header)
        if not match:
            self.fail('A block scalar header with an indentation digit is not read', start)
        style, chomp = match.group(1), match.group(2)
        self.pos += 1
        raw = []
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            if line.strip(' \t') == '':
                raw.append('')
                self.pos += 1
                continue
            if len(line) - len(line.lstrip(' ')) <= parent:
                break
            raw.append(line)
            self.pos += 1
        trailing = 0
        while raw and raw[-1] == '':
            raw.pop()
            trailing += 1
        content = [line for line in raw if line]
        if not content:
            return '\n' * trailing if chomp == '+' else ''
        width = min(len(line) - len(line.lstrip(' ')) for line in content)
        lines = [line[width:] if line else '' for line in raw]
        if style == '|':
            text = '\n'.join(lines)
        else:
            out, previous, pending = [], None, 0
            for line in lines:
                if line == '':
                    pending += 1
                    continue
                more = line[0] in ' \t'
                if previous is None:
                    out.append('\n' * pending)
                elif previous == 'text' and not more:
                    out.append('\n' * pending if pending else ' ')
                else:
                    out.append('\n' * (pending + 1))
                out.append(line)
                previous, pending = ('more' if more else 'text'), 0
            text = ''.join(out)
        if chomp == '-':
            return text
        return text + '\n' + ('\n' * trailing if chomp == '+' else '')


def load(text):
    """`(document, lines)`: the parsed document and the line of each pointer. A document that is not a mapping or a sequence is an error."""
    parser = _Parser(text)
    document = parser.block(-1, [], 0)
    if parser.peek() is not None:
        parser.fail('Unexpected indent or text after the document')
    if not isinstance(document, (dict, list)):
        raise YamlError('The document is not a mapping or a sequence')
    return document, parser.index
