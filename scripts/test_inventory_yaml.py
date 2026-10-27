"""Offline checks for the YAML reader (`inventory_yaml`, reader name `openapi-yaml`).

The reader gives the Python values that `json.loads` gives for the same document, so that a contract served as YAML reads like a contract served as JSON.
The fixture `fixtures/text/contract-mic.yaml` is written by hand for the tests; its parse was compared once with PyYAML (a tool outside the repository, not needed here).
No network call and no file outside the repository.
"""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, openapi_fields, parse_source, pointer_value
from inventory_yaml import YamlError, load, pointer_part, resolve

FIXTURE = Path(__file__).parent / 'fixtures/text/contract-mic.yaml'
URL = 'https://api.example/v1/openapi'


def parsed(text):
    return load(text)[0]


class Structure(unittest.TestCase):
    def test_nested_mappings_and_sequences_in_the_three_layouts_of_a_sequence(self):
        text = ('a:\n  - 1\n  - two\nb:\n- x\n- y\nc:\n  -\n    k: v\n  - - p\n    - q\n  - name: n\n    in: path\n    nested:\n      z: 1\nd: {}\ne: []\n')
        self.assertEqual(parsed(text), {'a': [1, 'two'], 'b': ['x', 'y'], 'c': [{'k': 'v'}, ['p', 'q'], {'name': 'n', 'in': 'path', 'nested': {'z': 1}}], 'd': {}, 'e': []})

    def test_a_compact_mapping_starts_at_the_column_of_its_first_key_whatever_the_spaces_after_the_dash(self):
        self.assertEqual(parsed('a:\n  -   k: 1\n      m: 2\n  - n: 3\n    o: 4\n'), {'a': [{'k': 1, 'm': 2}, {'n': 3, 'o': 4}]})
        with self.assertRaises(YamlError):  # the second key sits left of the first one
            parsed('a:\n  -   k: 1\n    m: 2\n')

    def test_text_after_the_document_at_the_indent_of_a_root_sequence_is_an_error(self):
        for bad in ('- a\nb: 1\n', '- a\n- b\nc\n'):
            with self.assertRaises(YamlError, msg=bad):
                parsed(bad)

    def test_a_key_without_a_value_is_null_and_a_quoted_key_keeps_its_text(self):
        self.assertEqual(parsed('a:\nb:\n  c:\n"200":\n  x: 1\n\'key: with colon\': 2\n/v1/p/{id}: 3\n'),
                         {'a': None, 'b': {'c': None}, '200': {'x': 1}, 'key: with colon': 2, '/v1/p/{id}': 3})

    def test_a_comment_ends_a_plain_scalar_and_is_text_inside_quotes_or_without_a_space(self):
        text = '# first\na: 1 # trailing\nb: "x # y"  # after\nc: a#b\nd: [1, 2] # list\n# last\ne: |\n  # kept\n  text\n'
        self.assertEqual(parsed(text), {'a': 1, 'b': 'x # y', 'c': 'a#b', 'd': [1, 2], 'e': '# kept\ntext\n'})

    def test_a_document_marker_at_the_top_is_allowed_and_a_second_document_is_not(self):
        self.assertEqual(parsed('---\na: 1\n'), {'a': 1})
        self.assertEqual(parsed('a: 1\n...\n'), {'a': 1})
        with self.assertRaises(YamlError):
            parsed('a: 1\n---\nb: 2\n')
        with self.assertRaises(YamlError):
            parsed('--- a: 1\n')

    def test_line_ends_of_windows_and_a_byte_order_mark_do_not_change_the_result(self):
        self.assertEqual(parsed('\ufeffa:\r\n  - 1\r\n  - "x\r\n    y"\r\n'), {'a': [1, 'x y']})


class Scalars(unittest.TestCase):
    def test_the_core_schema_of_yaml_12_with_the_readings_that_need_no_choice(self):
        expected = {'': None, '~': None, 'null': None, 'Null': None, 'NULL': None, 'true': True, 'True': True, 'TRUE': True, 'false': False, 'False': False,
                    '0': 0, '-12': -12, '+7': 7, '20': 20, '1.5': 1.5, '.5': 0.5, '2.': 2.0, '1e3': 1000.0, '-1.5E-2': -0.015, '.inf': float('inf'), '-.inf': float('-inf'),
                    # a choice between YAML 1.1 and 1.2, or no number: the text stays
                    'yes': 'yes', 'no': 'no', 'on': 'on', 'off': 'off', 'y': 'y', '007': '007', '0x1F': '0x1F', '0o17': '0o17', '1_000': '1_000',
                    '2024-03-15T10:30:00Z': '2024-03-15T10:30:00Z', '2024-03-15': '2024-03-15', '3.0.3': '3.0.3', '1.2.0': '1.2.0', 'nullish': 'nullish'}
        for text, value in expected.items():
            self.assertEqual(resolve(text), value, text)
            self.assertIs(type(resolve(text)), type(value), text)
        self.assertNotEqual(resolve('.nan'), resolve('.nan'))  # NaN

    def test_a_plain_scalar_over_several_lines_folds_and_a_blank_line_is_a_line_break(self):
        text = 'a: one two\n  three\n\n  four\nb: x\n'
        self.assertEqual(parsed(text), {'a': 'one two three\nfour', 'b': 'x'})

    def test_a_comment_ends_a_plain_scalar_over_several_lines(self):
        for bad in ('a: x\n  # note\n  y\n', 'a: x\n  y # note\n  z\n', 'a: x # note\n  y\n'):
            with self.assertRaises(YamlError, msg=bad):
                parsed(bad)
        self.assertEqual(parsed('a: x\n  y # note\nb: 1\n'), {'a': 'x y', 'b': 1})

    def test_a_plain_scalar_that_holds_a_colon_and_a_space_is_an_error(self):
        for text in ('a: b: c\n', 'a: b\n  c: d\n', 'a: x:\n', '- a: b: c\n'):
            with self.assertRaises(YamlError, msg=text):
                parsed(text)
        self.assertEqual(parsed('u: https://a.example/x?y=1:2\n'), {'u': 'https://a.example/x?y=1:2'})

    def test_double_quoted_scalars_read_the_escapes_of_the_specification(self):
        text = 'a: "x\\ty\\n\\"q\\" \\\\ \\u00e9 \\x41 \\/ \\_ \\0"\n'
        self.assertEqual(parsed(text), {'a': 'x\ty\n"q" \\ é A / \xa0 \0'})
        for bad in ('a: "\\q"\n', 'a: "\\u12"\n', 'a: "\\xZZ"\n'):
            with self.assertRaises(YamlError, msg=bad):
                parsed(bad)

    def test_quoted_scalars_over_several_lines_fold_like_plain_ones(self):
        self.assertEqual(parsed('a: "one   \n      two\n\n    three \\\n    four"\nb: \'it\'\'s\n  here\'\n'), {'a': 'one two\nthree four', 'b': "it's here"})

    def test_the_spaces_at_a_line_break_inside_quotes_go_but_an_escaped_space_stays(self):
        self.assertEqual(parsed('a: "one\n  two   \n  three"\n'), {'a': 'one two three'})
        self.assertEqual(parsed('a: "one\\ \n  two"\n'), {'a': 'one  two'})

    def test_a_quoted_scalar_that_is_not_closed_or_has_text_after_it_is_an_error(self):
        for bad in ('a: "x\nb: 1\n', "a: 'x\n", 'a: "x" y\n', "a: 'x' 'y'\n"):
            with self.assertRaises(YamlError, msg=bad):
                parsed(bad)


class BlockScalars(unittest.TestCase):
    def test_literal_and_folded_keep_or_fold_the_line_breaks(self):
        text = 'a: |\n  one\n   two\n\n  three\nb: >\n  one\n  two\n\n  three\n\n\n  four\n   more\n  five\nc: x\n'
        self.assertEqual(parsed(text), {'a': 'one\n two\n\nthree\n', 'b': 'one two\nthree\n\nfour\n more\nfive\n', 'c': 'x'})

    def test_the_chomping_marks_decide_the_final_line_breaks(self):
        body = '  text\n\n\n'
        self.assertEqual(parsed('a: |\n' + body + 'b: 1\n'), {'a': 'text\n', 'b': 1})
        self.assertEqual(parsed('a: |-\n' + body + 'b: 1\n'), {'a': 'text', 'b': 1})
        self.assertEqual(parsed('a: |+\n' + body + 'b: 1\n'), {'a': 'text\n\n\n', 'b': 1})
        self.assertEqual(parsed('a: >-\n  x\n  y\nb: 1\n'), {'a': 'x y', 'b': 1})
        self.assertEqual(parsed('a: |\nb: 1\n'), {'a': '', 'b': 1})

    def test_a_block_scalar_in_a_sequence_ends_at_the_next_item_and_reads_keys_as_text(self):
        text = '- |\n  k: v\n  - not an item\n- >-\n  a\n  b\n- last\n'
        self.assertEqual(parsed(text), ['k: v\n- not an item\n', 'a b', 'last'])

    def test_an_indentation_digit_is_an_error(self):
        with self.assertRaises(YamlError):
            parsed('a: |2\n    x\n')


class Flow(unittest.TestCase):
    def test_flow_sequences_and_mappings_nest_and_take_quoted_and_plain_items(self):
        self.assertEqual(parsed('a: [x, 1, "y, z", \'w\', [2, 3], {k: v}, https://a.example/p]\nb: {a: 1, "b c": [true, null], d: {}}\n'),
                         {'a': ['x', 1, 'y, z', 'w', [2, 3], {'k': 'v'}, 'https://a.example/p'], 'b': {'a': 1, 'b c': [True, None], 'd': {}}})

    def test_a_flow_collection_may_span_lines_and_hold_comments(self):
        self.assertEqual(parsed('a: [x,\n  y, # note\n  z]\nb: {k: 1,\n  m: 2}\nc: 3\n'), {'a': ['x', 'y', 'z'], 'b': {'k': 1, 'm': 2}, 'c': 3})

    def test_what_a_flow_collection_cannot_say_without_a_guess_is_an_error(self):
        for bad in ('a: [x, y\n', 'a: {k: 1\n', 'a: [x y: z]\n', 'a: [a: b]\n', 'a: {k}\n', 'a: {k: 1, k: 2}\n', 'a: [x, , y]\n', 'a: [*b]\n', 'a: [x] y\n', 'a: {k: 1} {m: 2}\n'):
            with self.assertRaises(YamlError, msg=bad):
                parsed(bad)


class Refusals(unittest.TestCase):
    def test_constructs_that_the_reader_does_not_read_are_errors(self):
        cases = {'anchor': 'a: &x 1\n', 'alias': 'a: *x\n', 'tag': 'a: !!str 1\n', 'merge key': 'a:\n  <<: {b: 1}\n', 'directive': '%YAML 1.2\na: 1\n',
                 'reserved indicator': 'a: @x\n', 'tab in the indent': 'a:\n\tb: 1\n', 'duplicate key': 'a: 1\nb: 2\na: 3\n',
                 'duplicate key in an item': '- k: 1\n  k: 2\n', 'a line with no key': 'a: 1\nstray\n', 'item after a key with a value': 'a: 1\n- b\n',
                 'indent after a scalar': 'a: 1\n    b: 2\n', 'indent that does not match': 'a:\n    b: 1\n  c: 2\n'}
        for name, text in cases.items():
            with self.assertRaises(YamlError, msg=name):
                parsed(text)

    def test_a_document_that_is_not_a_mapping_or_a_sequence_is_an_error(self):
        for text in ('', '# only a comment\n', 'just text\n', '"quoted"\n', '42\n'):
            with self.assertRaises(YamlError, msg=text):
                parsed(text)

    def test_a_document_nested_too_deep_is_an_error_and_not_a_crash(self):
        deep = ''.join('  ' * n + 'k:\n' for n in range(200)) + '  ' * 200 + 'v: 1\n'
        with self.assertRaises(YamlError):
            parsed(deep)
        with self.assertRaises(YamlError):
            parsed('a: ' + '[' * 200 + ']' * 200 + '\n')

    def test_the_error_names_the_line(self):
        with self.assertRaises(YamlError) as caught:
            parsed('a: 1\nb: 2\nc: x: y\n')
        self.assertIn('Line 3', str(caught.exception))


class Pointers(unittest.TestCase):
    def test_every_key_and_item_has_its_line_under_its_json_pointer(self):
        text = 'paths:\n  /v1/a~b:\n    get:\n      parameters:\n        - name: x\n          in: path\n        - name: y\n'
        document, lines = load(text)
        self.assertEqual(lines, {'/paths': 1, '/paths/~1v1~1a~0b': 2, '/paths/~1v1~1a~0b/get': 3, '/paths/~1v1~1a~0b/get/parameters': 4,
                                 '/paths/~1v1~1a~0b/get/parameters/0': 5, '/paths/~1v1~1a~0b/get/parameters/0/name': 5, '/paths/~1v1~1a~0b/get/parameters/0/in': 6,
                                 '/paths/~1v1~1a~0b/get/parameters/1': 7, '/paths/~1v1~1a~0b/get/parameters/1/name': 7})
        self.assertEqual(pointer_part('a/b~c'), 'a~1b~0c')
        self.assertEqual(document['paths']['/v1/a~b']['get']['parameters'][1], {'name': 'y'})

    def test_the_lines_of_the_fixture_are_the_lines_of_the_text(self):
        text = FIXTURE.read_text()
        document, lines = load(text)
        rows = text.split('\n')
        for pointer, line in lines.items():
            key = pointer.rsplit('/', 1)[1].replace('~1', '/').replace('~0', '~')
            if isinstance(pointer_value(document, pointer.rsplit('/', 1)[0]), list):
                self.assertTrue(rows[line - 1].lstrip().startswith('-'), pointer)
            else:
                self.assertTrue(rows[line - 1].lstrip().lstrip('- ').lstrip('"').startswith(key), (pointer, rows[line - 1]))


class Contract(unittest.TestCase):
    """The reader name `openapi-yaml` makes `inventory.parse_source` read a contract that is written as YAML."""

    def setUp(self):
        self.text = FIXTURE.read_text()
        self.document = parsed(self.text)
        self.fmt, self.fields, self.truncated = parse_source(self.text, URL, 'text/plain', 'openapi-yaml')
        self.by = {(f['rol'], f['operatie'], f['cale']): f for f in self.fields}

    def test_the_fixture_parses_to_the_expected_values(self):
        d = self.document
        self.assertEqual((d['openapi'], d['info']['version'], d['components']['schemas'], d['paths']['/v1/health']['get']['tags']), ('3.0.3', '1.2.0', {}, []))
        self.assertEqual(d['info']['description'], 'Prima propoziție a descrierii, continuată pe a doua linie.\n\n**Un paragraf nou**, după două rânduri goale.\n')
        operation = d['paths']['/v1/autoritate/{cif}/contracte']['get']
        self.assertEqual(operation['description'], 'Obține contractele unei autorități contractante, după codul ei fiscal')
        self.assertEqual(operation['responses']['200']['description'], 'Răspuns (ex: o listă de contracte) scris pe două rânduri')
        self.assertEqual(operation['parameters'][2]['schema']['enum'], ['achizitii-directe', 'licitatii-publice'])
        self.assertEqual(operation['parameters'][0]['required'], True)
        self.assertEqual(operation['parameters'][1]['schema']['default'], 20)
        self.assertEqual(operation['responses']['200']['content']['application/json']['schema']['required'], ['cif', 'contracte'])

    def test_the_fields_are_the_fields_that_the_same_contract_gives_as_json(self):
        fmt, as_json, truncated = parse_source(json.dumps(self.document), URL, 'application/json')
        self.assertEqual((self.fmt, self.truncated), (fmt, truncated))
        self.assertEqual(len(self.fields), len(as_json))
        for yaml_field, json_field in zip(self.fields, as_json):
            self.assertEqual({k: v for k, v in yaml_field.items() if k != 'linie'}, json_field)

    def test_the_parameters_and_the_response_members_are_fields_with_their_declared_types(self):
        self.assertEqual(self.fmt, 'openapi')
        self.assertEqual(sorted(f['cale'] for f in self.fields if f['rol'] == 'parametru-api'), ['cif', 'limit', 'sursa'])
        cif = self.by[('parametru-api', 'GET /v1/autoritate/{cif}/contracte', 'cif')]
        self.assertEqual((cif['loc'], cif['tip_declarat'], cif['obligatoriu'], cif['stare_tip']), ('path', 'string', True, 'declarat-in-schema'))
        value = self.by[('camp-raspuns', 'GET /v1/autoritate/{cif}/contracte', '$.contracte[].valoare')]
        self.assertEqual((value['tip_declarat'], value['descriere'], value['status_raspuns']), ('number', 'Valoarea în RON', '200'))
        self.assertEqual(self.by[('camp-raspuns', 'GET /v1/health', '$.status')]['descriere'], 'Starea serviciului')
        union = self.by[('camp-raspuns', 'GET /v1/autoritate/{cif}/contracte', '$.contracte[].furnizor')]
        self.assertIsNone(union['tip_declarat'], 'a union type is not turned into one type')

    def test_a_parameter_takes_its_definition_from_its_schema_when_it_has_none_of_its_own(self):
        text = {'openapi': '3.0.3', 'paths': {'/a': {'get': {'parameters': [
            {'name': 'x', 'in': 'query', 'schema': {'type': 'string', 'description': 'from the schema'}},
            {'name': 'y', 'in': 'query', 'description': 'of the parameter', 'schema': {'type': 'string', 'description': 'from the schema'}},
            {'name': 'z', 'in': 'query', 'schema': {'type': 'string'}}]}}}}
        _, fields, _ = parse_source(json.dumps(text), URL, 'application/json')
        self.assertEqual([f['descriere'] for f in fields], ['from the schema', 'of the parameter', ''])

    def test_each_field_names_the_line_of_its_declaration_in_the_file(self):
        rows = self.text.split('\n')
        for field in self.fields:
            self.assertIn('linie', field)
            row = rows[field['linie'] - 1].strip()
            if field['rol'] == 'parametru-api':
                self.assertEqual(row, f'- name: {field["nume"]}', field['cale'])
            else:
                self.assertTrue(row.startswith(field['nume'] + ':'), (field['cale'], row))
        # a JSON document has no line
        self.assertFalse(any('linie' in f for f in parse_source(json.dumps(self.document), URL, 'application/json')[1]))

    def test_a_document_that_is_not_a_contract_is_an_error_and_a_source_with_it_is_not_analysed(self):
        for text in ('a: 1\n', '- 1\n- 2\n', 'openapi: yes\npaths: {}\n', 'openapi: [3, 0]\n'):
            with self.assertRaises(ValueError, msg=text):
                parse_source(text, URL, 'text/plain', 'openapi-yaml')
        record = analyse_source({'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/plain', 'body': 'a: 1\n'}, 'openapi-yaml')
        self.assertEqual((record['stare'], record['campuri']), ('eroare-parsare', []))
        self.assertIn('not an OpenAPI contract', record['error'])
        record = analyse_source({'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/plain', 'body': 'a: [1\n'}, 'openapi-yaml')
        self.assertEqual(record['stare'], 'eroare-parsare')

    def test_without_the_reader_name_a_yaml_body_is_not_guessed(self):
        with self.assertRaises(ValueError):
            parse_source(self.text, URL, 'text/plain')

    def test_the_source_record_keeps_the_reader_and_says_that_the_types_are_declared(self):
        record = analyse_source({'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/plain', 'body': self.text}, 'openapi-yaml')
        self.assertEqual((record['format'], record['citire'], record['baza_tipului'], record['stare'], len(record['campuri'])),
                         ('openapi', 'openapi-yaml', 'schema-declarata', 'analizat', len(self.fields)))

    def test_the_evidence_check_reads_the_retained_body_again(self):
        response = {'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/plain', 'body': self.text}
        record = analyse_source(response, 'openapi-yaml')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            path = out / 'seturi-date.json'
            path.write_text(json.dumps({'surse': [record]}))
            report = check_report(out, out)
            self.assertEqual((report['errors'], report['verified']), ([], 1))
            record['campuri'][1]['descriere'] = 'Alt text'
            path.write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']))
            record['campuri'][1]['descriere'] = self.fields[1]['descriere']
            record['campuri'][1]['pointer'] = '/paths/nu-exista'
            path.write_text(json.dumps({'surse': [record]}))
            self.assertTrue(check_report(out, out)['errors'])

    def test_a_contract_with_more_fields_than_the_bound_says_that_the_bound_was_reached(self):
        members = ''.join(f'                  m{n}:\n                    type: string\n' for n in range(2100))
        text = ('openapi: 3.0.3\npaths:\n  /a:\n    get:\n      responses:\n        "200":\n          content:\n            application/json:\n'
                '              schema:\n                type: object\n                properties:\n' + members)
        fmt, fields, truncated = parse_source(text, URL, 'text/plain', 'openapi-yaml')
        self.assertEqual((fmt, len(fields), truncated), ('openapi', 2000, True))
        self.assertFalse(self.truncated)

    def test_openapi_fields_without_lines_give_the_same_fields_as_before(self):
        self.assertEqual(openapi_fields(self.document), [{k: v for k, v in f.items() if k != 'linie'} for f in self.fields])


if __name__ == '__main__':
    unittest.main()
