"""Reader for a page that documents its fields as a glossary of headings. Stdlib only.

Format name: `html-glosar`. A heading (`<h2>` to `<h6>`) reads `Label (name)`: a text in the page's language, then the name of a field in brackets. The name is
written the way code writes it: a lowercase first letter, then letters, digits and underscores (`personalCode`, `isSuspended`). The definition of the field is the
first paragraph (`<p>`) between that heading and the next heading of any level. A heading that has no name in brackets, a name that starts with a capital letter
(`Ontologie`, `RUP Partea I`) and a bracket with several words are not fields: the page uses them as plain headings.

The reader keeps what the page states and nothing else:

- `nume` and `cale` are the name in brackets; `eticheta` is the label as the page writes it; `descriere` is the text of the paragraph, tags removed and entities decoded;
- the page declares no type in a place that a reader can trust, so `tip_declarat` is null. Prose such as „Format: număr întreg” stays unread;
- an example in a `<small>` or in a later paragraph is never copied (examples on such pages can name a real person);
- the same name under two headings is an error: the reader does not choose between two definitions.

It makes no request and runs no script. The locator `char:START-END` covers the heading and its paragraph in the retained body, so `inventory.py --check` finds them again.
"""
from __future__ import annotations

import html
import re

STATE = 'declarat-in-text-documentatie'
ROLE = 'camp-dictionar'
HEADING = re.compile(r'<h([2-6])\b[^>]*>(.*?)</h\1\s*>', re.S)
ANY_HEADING = re.compile(r'<h[1-6]\b')
PARAGRAPH = re.compile(r'<p\b[^>]*>(.*?)</p\s*>', re.S)
LABELLED = re.compile(r'^(?P<label>.*\S)\s*\((?P<name>[a-z][A-Za-z0-9_]*)\)$')


def text_of(raw):
    """Visible text of an HTML fragment: tags removed, entities decoded, spaces collapsed."""
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', raw))).strip()


def read(body):
    """The field records of the glossary, in page order. An empty glossary is an error: the page is not one."""
    fields, seen = [], {}
    for heading in HEADING.finditer(body):
        labelled = LABELLED.match(text_of(heading.group(2)))
        if not labelled:
            continue
        name = labelled.group('name')
        if name in seen:
            raise ValueError(f'The glossary names the field {name} under two headings')
        following = ANY_HEADING.search(body, heading.end())
        limit = following.start() if following else len(body)
        paragraph = PARAGRAPH.search(body, heading.end(), limit)
        end = paragraph.end() if paragraph else heading.end()
        field = {'nume': name, 'cale': name, 'tip_declarat': None, 'stare_tip': STATE, 'rol': ROLE,
                 'eticheta': labelled.group('label'), 'descriere': text_of(paragraph.group(1)) if paragraph else '',
                 'pointer': f'char:{heading.start()}-{end}', 'linie': body.count('\n', 0, heading.start()) + 1}
        seen[name] = field
        fields.append(field)
    if not fields:
        raise ValueError('The page has no heading of the form `Label (name)`')
    return fields


def glossary(body, options=None):
    """The reader of `citire: html-glosar`: field records in the shape of inventory.parse_source."""
    return 'html-glosar', read(body), False
