"""Reader for the Django models of a Python file. Stdlib only.

Format name: `django-modele` (the extension `.py` selects it). A Django project declares the shape of its stored data as classes of model fields:
`name = models.CharField(max_length=100, null=True)`. The reader parses the file with `ast` (it never imports or runs it) and keeps what the text states:

- A class gives fields when its body assigns a call to a field class: `models.XField(...)`, `models.ForeignKey(...)`, `models.OneToOneField(...)`,
  `models.ManyToManyField(...)`, or a bare name that ends in `Field`, `ForeignKey` or `OneToOneField`. Other assignments, methods, managers and `Meta` give none.
- `nume` is the attribute name, `cale` is `Class.attribute`, `grup` is the class. `tip_declarat` is the field class (`CharField`, `ForeignKey`).
  It is a type of the code, not of a stored value.
- `obligatoriu` is false when the call states `null=True`; it is true otherwise. `blank` and `default` are not read as meanings of the value.
- `relatie` is the target of a relation as written (`"Ngo"`, `Donor`, `settings.AUTH_USER_MODEL`).
- `descriere` is the `help_text` or `verbose_name` when it is a plain string (also inside `_("...")`). Any other expression gives no description.
- A file with a syntax error, or with no model field, is an error (state `eroare-parsare`). The same path twice is an error.

The locator `char:START-END` covers the assignment in the retained body, so `inventory.py --check` finds it again. The field limit is 2,000 (`MAX_FIELDS`).
"""
from __future__ import annotations

import ast

FORMAT = 'django-modele'
MAX_FIELDS = 2000
RELATIONS = ('ForeignKey', 'OneToOneField', 'ManyToManyField')


def called_name(call):
    function = call.func
    if isinstance(function, ast.Attribute):
        return function.attr
    if isinstance(function, ast.Name):
        return function.id
    return None


def is_field(name):
    return bool(name) and (name.endswith('Field') or name in RELATIONS)


def text_of(node):
    """A plain string, or `_("string")`. Anything else is None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords and called_name(node) in ('_', 'gettext_lazy', 'gettext'):
        return text_of(node.args[0])
    return None


def keyword(call, name):
    return next((k.value for k in call.keywords if k.arg == name), None)


def as_written(node):
    return ast.unparse(node) if node is not None else None


def offsets(body):
    starts, position = [], 0
    for line in body.split('\n'):
        starts.append(position)
        position += len(line) + 1
    return starts


def position(body, starts, line, column):
    """Character offset of an `ast` position. `col_offset` counts UTF-8 bytes."""
    text = body.split('\n')[line - 1]
    return starts[line - 1] + len(text.encode('utf-8')[:column].decode('utf-8', 'ignore'))


def read(body):
    """(fields, cut). Raises ValueError for a syntax error or a file without a model field."""
    try:
        tree = ast.parse(body)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f'The Python file does not parse: {exc}') from exc
    starts, fields, seen = offsets(body), [], set()
    for owner in ast.walk(tree):
        if not isinstance(owner, ast.ClassDef):
            continue
        for statement in owner.body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                name, value = statement.targets[0].id, statement.value
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
                name, value = statement.target.id, statement.value
            else:
                continue
            kind = called_name(value) if isinstance(value, ast.Call) else None
            if not is_field(kind):
                continue
            path = f'{owner.name}.{name}'
            if path in seen:
                raise ValueError(f'The field {path} is declared twice')
            seen.add(path)
            null = keyword(value, 'null')
            record = {'nume': name, 'cale': path, 'tip_declarat': kind, 'stare_tip': 'declarat-in-cod-sursa', 'rol': 'camp-model', 'grup': owner.name,
                      'obligatoriu': not (isinstance(null, ast.Constant) and null.value is True),
                      'pointer': 'char:{}-{}'.format(position(body, starts, statement.lineno, statement.col_offset),
                                                      position(body, starts, statement.end_lineno, statement.end_col_offset)),
                      'linie': statement.lineno}
            if kind in RELATIONS and value.args:
                record['relatie'] = as_written(value.args[0])
            elif kind in RELATIONS and keyword(value, 'to') is not None:
                record['relatie'] = as_written(keyword(value, 'to'))
            for source in ('help_text', 'verbose_name'):
                description = text_of(keyword(value, source))
                if description:
                    record['descriere'] = description
                    break
            fields.append(record)
    if not fields:
        raise ValueError('The Python file declares no model field')
    return fields[:MAX_FIELDS], len(fields) > MAX_FIELDS
