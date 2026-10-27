"""Reader for a JSON document that a bounded read cut short. Stdlib only.

Format name: `json-esantion`. The input is the body of a range read (`inventory.py --probe --sample-bytes N`) of a JSON or GeoJSON file that is
too large to read whole. A cut document is not valid JSON, so the plain reader refuses it. This reader keeps what is complete and leaves the rest.

- Complete members of every object and complete elements of every array are kept. The element or the member that the cut ended is dropped,
  also when most of it was read: a field list built from half a record would show a missing field as absent.
  One exception: an object that the cut ended keeps its complete members when it is a keyed collection (`inventory_literals.keyed_collection`: companies keyed by CUI,
  years, 100 members or more). Each member is a whole record, and the keys are values, not field names, so no field can look absent. The member that the cut ended is dropped.
- A document that parses whole is read whole. The reader then gives the same fields as the plain JSON reader.
- Fields come from the plain observed-fields walk of `inventory.observed_fields` (bounds: 25 elements, seven levels, 2,000 fields) on the recovered
  document. Their pointers address the recovered document, which is the retained body up to the cut. `stare_tip` is `observat-in-esantion-json`.
- `elemente_citite` counts the complete elements of the first array that the walk reaches in each list. The reader does not guess the size of the file:
  the number of records that the file holds is unknown, because the read stopped.

A body with no complete value, a value that is not an object or an array, and a nesting deeper than `MAX_NESTING` are errors (state `eroare-parsare`).
The reader never guesses a missing closing bracket, and it never repairs a string or a number that the cut ended.
"""
from __future__ import annotations

import json
import re

from inventory_literals import keyed_object

FORMAT = 'json-esantion'
MAX_NESTING = 60
WHITESPACE = ' \t\r\n'
MISSING = object()
TOKEN = re.compile(r'[-+0-9.eE]+|[A-Za-z]+')


def string_end(text, start):
    """Index after the closing quote of the string that starts at `start`, or -1 when the text ends inside the string."""
    i = start + 1
    while i < len(text):
        if text[i] == '\\':
            i += 2
        elif text[i] == '"':
            return i + 1
        else:
            i += 1
    return -1


class Cut(Exception):
    """The text ended inside a value. `partial` is the part that is complete (a list or a dict), or MISSING."""

    def __init__(self, partial=MISSING):
        super().__init__('cut')
        self.partial = partial


class Recover:
    def __init__(self, text):
        self.text, self.decoder = text, json.JSONDecoder()

    def space(self, i):
        while i < len(self.text) and self.text[i] in WHITESPACE:
            i += 1
        return i

    def value(self, i, depth=0):
        """(value, next index). Raises Cut when the text ends inside the value, ValueError for text that is not JSON."""
        if depth > MAX_NESTING:
            raise ValueError('JSON nested deeper than ' + str(MAX_NESTING) + ' levels')
        i = self.space(i)
        if i >= len(self.text):
            raise Cut()
        if self.text[i] == '{':
            return self.members(i, depth)
        if self.text[i] == '[':
            return self.elements(i, depth)
        if self.text[i] == '"':
            end = string_end(self.text, i)
            if end < 0:
                raise Cut()
        else:
            token = TOKEN.match(self.text, i)
            if token and token.end() >= len(self.text):
                raise Cut()  # a number or a word at the very end may be the start of a longer one
        try:
            return self.decoder.raw_decode(self.text, i)
        except json.JSONDecodeError as exc:
            raise ValueError('Not JSON at character ' + str(exc.pos)) from exc

    def elements(self, i, depth):
        items, i = [], i + 1
        while True:
            i = self.space(i)
            if i >= len(self.text):
                raise Cut(items)
            if self.text[i] == ']':
                return items, i + 1
            try:
                item, i = self.value(i, depth + 1)
            except Cut as cut:
                raise Cut(items) from cut  # the element that the cut ended is not a whole record
            items.append(item)
            i = self.space(i)
            if i >= len(self.text):
                raise Cut(items)
            if self.text[i] == ',':
                i += 1
            elif self.text[i] != ']':
                raise ValueError('Expected "," or "]" at character ' + str(i))

    def members(self, i, depth):
        found, i = {}, i + 1
        while True:
            i = self.space(i)
            if i >= len(self.text):
                raise Cut(found)
            if self.text[i] == '}':
                return found, i + 1
            if self.text[i] != '"':
                raise ValueError('Expected a member name at character ' + str(i))
            try:
                key, i = self.decoder.raw_decode(self.text, i)
            except json.JSONDecodeError as cut:
                raise Cut(found) from cut
            i = self.space(i)
            if i >= len(self.text):
                raise Cut(found)
            if self.text[i] != ':':
                raise ValueError('Expected ":" at character ' + str(i))
            try:
                item, i = self.value(i + 1, depth + 1)
            except Cut as cut:
                if isinstance(cut.partial, list):  # a list keeps its complete elements; a half object is dropped
                    found[key] = cut.partial
                elif isinstance(cut.partial, dict) and keyed_object(cut.partial):  # a keyed collection keeps the members that are whole records
                    found[key] = cut.partial
                raise Cut(found) from cut
            found[key] = item
            i = self.space(i)
            if i >= len(self.text):
                raise Cut(found)
            if self.text[i] == ',':
                i += 1
            elif self.text[i] != '}':
                raise ValueError('Expected "," or "}" at character ' + str(i))


def recover(body):
    """(document, complete). `document` is what the body holds in full; `complete` is true when the body is a whole JSON document."""
    text = body.lstrip('﻿')
    try:
        whole = json.loads(text)
    except json.JSONDecodeError:
        whole = MISSING
    if whole is not MISSING:
        if not isinstance(whole, (dict, list)) or not whole:
            raise ValueError('The body holds no JSON object or array with a member or an element')
        return whole, True
    reader = Recover(text)
    try:
        value, _ = reader.value(0)
    except Cut as cut:
        value = cut.partial
    if not isinstance(value, (dict, list)):
        raise ValueError('The body holds no complete JSON object or array')
    if not value:
        raise ValueError('The body holds no complete member or element')
    return value, False


def list_sizes(document):
    """How many complete elements each list of the recovered document has, by path: `{"$.features": 12}`. Lists nested in elements are not listed."""
    sizes = {}

    def walk(value, path, depth):
        if depth > 3:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f'{path}.{key}', depth + 1)
        elif isinstance(value, list):
            sizes[path] = len(value)

    walk(document, '$', 0)
    return sizes
