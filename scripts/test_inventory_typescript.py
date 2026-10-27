"""Offline checks for the TypeScript reader (`inventory_typescript`, format `typescript`).

The fixture `fixtures/text/tipuri-mic.ts` is written by hand with the constructs of a file of type declarations (the documents of a search index and the filters of a
query), and with code around the declarations that the reader must not read. No network call.
"""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, parse_source
from inventory_text import EXTENSIONS, READERS
from inventory_typescript import MAX_FIELDS, TypeScriptError, read

FIXTURE = Path(__file__).parent / 'fixtures/text/tipuri-mic.ts'
URL = 'https://raw.githubusercontent.com/example/project/0123456789abcdef0123456789abcdef01234567/src/types.ts'


def fields_of(body):
    return read(body)[0]


def paths(fields):
    return [f['cale'] for f in fields]


def one(body, path):
    found = [f for f in fields_of(body) if f['cale'] == path]
    assert len(found) == 1, (path, paths(fields_of(body)))
    return found[0]


def interval(field):
    start, end = field['pointer'].split(':')[1].split('-')
    return int(start), int(end)


class Declarations(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()
        self.fields = fields_of(self.body)

    def test_interfaces_and_object_types_give_fields_and_nothing_else_does(self):
        self.assertEqual(sorted({f['grup'] for f in self.fields}), ['Alias', 'Declared', 'Filters', 'Item'])
        self.assertNotIn('Empty', {f['grup'] for f in self.fields}, 'an interface with no member has no field')
        text = json.dumps(self.fields)
        for ignored in ('NotADeclaration', 'Nope', 'LIMITS', 'IndexName.', 'Id.', 'Kind', 'build'):
            self.assertNotIn(ignored, text)

    def test_a_field_has_the_name_the_path_the_type_as_written_and_whether_it_is_required(self):
        db = one(self.body, 'Filters.db')
        self.assertEqual((db['nume'], db['tip_declarat'], db['obligatoriu'], db['grup'], db['rol'], db['stare_tip']),
                         ('db', 'IndexName[]', False, 'Filters', 'camp-model', 'declarat-in-cod-sursa'))
        self.assertEqual(one(self.body, 'Filters.cpv')['obligatoriu'], True)
        self.assertEqual(one(self.body, 'Filters.callback')['tip_declarat'], '(a: number, b: Map<string, number>) => void')
        self.assertEqual(one(self.body, 'Filters.kind')['tip_declarat'], '"licitatii" | "achizitii" | "offline"', 'a union over several lines, with the leading bar cut and the literals intact')

    def test_a_type_that_can_be_null_is_still_required_and_a_readonly_or_quoted_member_keeps_its_name(self):
        nullable = one(self.body, 'Filters.euFunds')
        self.assertEqual((nullable['tip_declarat'], nullable['obligatoriu']), ('boolean | null', True))
        self.assertEqual(one(self.body, 'Filters.x-county')['nume'], 'x-county')

    def test_methods_are_not_fields_and_do_not_end_the_reading_of_the_members_after_them(self):
        self.assertNotIn('Filters.run', paths(self.fields))
        self.assertNotIn('Filters.go', paths(self.fields))
        self.assertIn('Filters.callback', paths(self.fields), 'a member with a function type is a field')
        self.assertIn('Filters.kind', paths(self.fields))

    def test_an_interface_names_what_it_extends_and_its_fields_are_not_repeated_from_the_base(self):
        item = one(self.body, 'Item.id')
        self.assertEqual(item['extinde'], ['Base', 'Mixin<Id>'])
        self.assertNotIn('extinde', one(self.body, 'Filters.db'))
        self.assertEqual([f for f in paths(self.fields) if f.startswith('Empty')], [])

    def test_a_declaration_with_declare_and_an_object_type_alias_are_read(self):
        self.assertEqual(paths([f for f in self.fields if f['grup'] in ('Alias', 'Declared')]), ['Alias.an', 'Alias.caen', 'Declared.flag'])
        self.assertEqual(one(self.body, 'Alias.caen')['obligatoriu'], False)

    def test_the_fields_come_in_file_order_with_the_members_of_an_inline_object_after_their_parent(self):
        starts = [interval(f)[0] for f in self.fields]
        self.assertEqual(starts, sorted(starts))
        order = paths(self.fields)
        self.assertLess(order.index('Item.supplier'), order.index('Item.supplier.fiscalNumber'))
        self.assertLess(order.index('Item.supplier.address.city'), order.index('Item.lots'))


class Nesting(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()

    def test_an_inline_object_is_a_member_of_type_object_and_its_members_follow_with_a_dotted_path(self):
        self.assertEqual(one(self.body, 'Item.supplier')['tip_declarat'], 'object')
        self.assertEqual(one(self.body, 'Item.supplier.address.county')['tip_declarat'], 'string')
        self.assertEqual(one(self.body, 'Item.supplier.address.city')['obligatoriu'], False)

    def test_an_array_of_inline_objects_has_the_brackets_in_the_path_and_in_the_type(self):
        self.assertEqual(one(self.body, 'Item.lots')['tip_declarat'], 'object[]')
        self.assertEqual(one(self.body, 'Item.lots[].number')['tip_declarat'], 'number')
        self.assertEqual(one(self.body, 'Item.lots[].rows')['tip_declarat'], 'object[]')
        self.assertEqual(one(self.body, 'Item.lots[].rows[].value')['tip_declarat'], 'number', 'two levels of arrays of objects')

    def test_an_object_next_to_null_is_expanded_and_an_object_inside_a_generic_is_kept_as_written(self):
        self.assertEqual(one(self.body, 'Item.winner')['tip_declarat'], 'object | null')
        self.assertEqual(one(self.body, 'Item.winner.id')['tip_declarat'], 'number')
        self.assertEqual(one(self.body, 'Item.extra')['tip_declarat'], 'Array<{ ignored: true }>')
        self.assertEqual(one(self.body, 'Item.history')['tip_declarat'], 'Record<string, { a: number }>')
        self.assertNotIn('Item.extra.ignored', paths(fields_of(self.body)))
        self.assertNotIn('Item.history.a', paths(fields_of(self.body)))

    def test_an_object_nested_too_deep_is_an_error(self):
        deep = 'export interface D {\n' + ''.join(f'a{n}: {{\n' for n in range(40)) + 'z: string;\n' + '};\n' * 40 + '}\n'
        with self.assertRaises(TypeScriptError):
            read(deep)


class Comments(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()

    def test_the_comment_above_a_member_is_its_description_and_a_block_of_lines_is_joined(self):
        self.assertEqual(one(self.body, 'Filters.dateFrom')['descriere'], 'First day of the period, ISO 8601.')
        self.assertEqual(one(self.body, 'Filters.valueFrom')['descriere'], 'Lowest value, in lei.')

    def test_the_comment_at_the_end_of_the_line_describes_that_member_and_not_the_next_one(self):
        self.assertEqual(one(self.body, 'Filters.authority')['descriere'], 'the contracting authority')
        self.assertNotIn('descriere', one(self.body, 'Filters.cpv'), 'the comment at the end of the line above belongs to the line above')
        self.assertEqual(one(self.body, 'Item.supplier.address.county')['descriere'], 'the county of the supplier')
        self.assertEqual(one(self.body, 'Filters.kind')['descriere'], 'the dataset')

    def test_a_comment_cut_off_by_a_blank_line_and_the_comment_of_a_declaration_describe_no_member(self):
        text = json.dumps(fields_of(self.body))
        self.assertNotIn('cut off', text)
        self.assertNotIn('filters of a query', text)
        self.assertNotIn('descriere', one(self.body, 'Filters.db'), 'the comment above the declaration is not the description of its first member')

    def test_a_block_comment_loses_its_stars(self):
        body = 'interface A {\n  /**\n   * First line\n   * second line\n   */\n  a: string;\n}\n'
        self.assertEqual(one(body, 'A.a')['descriere'], 'First line second line')


class Locators(unittest.TestCase):
    def test_the_interval_covers_the_member_from_its_name_to_the_end_of_its_type(self):
        body = FIXTURE.read_text()
        for field in fields_of(body):
            start, end = interval(field)
            cut = body[start:end]
            self.assertTrue(cut.lstrip('"').startswith(field['nume']), field['cale'])
            self.assertNotIn(cut[-1:], (';', ',', ' ', '\n'), field['cale'])
            self.assertEqual(field['linie'], body.count('\n', 0, start) + 1, field['cale'])
        self.assertEqual(body[slice(*interval(one(body, 'Filters.db')))], 'db?: IndexName[]')
        self.assertTrue(body[slice(*interval(one(body, 'Item.supplier')))].endswith('}'))

    def test_a_replay_of_the_same_body_gives_the_same_fields(self):
        body = FIXTURE.read_text()
        self.assertEqual(fields_of(body), fields_of(body))


class Strictness(unittest.TestCase):
    def test_what_the_reader_cannot_state_without_a_guess_is_an_error(self):
        cases = {'index signature': 'interface A { [key: string]: number; }', 'mapped type': 'type A = { [K in Keys]: string };',
                 'accessor': 'interface A { get foo(): string; }', 'unclosed': 'interface A { a: string;', 'nothing to read': 'export const a = 1;\ntype Id = string;\n',
                 'repeated member': 'interface A { a: string; a: number; }', 'same path twice': 'interface A { a: string; }\ninterface A { a: string; }\n'}
        for name, text in cases.items():
            with self.assertRaises(TypeScriptError, msg=name):
                read(text)

    def test_two_declarations_of_one_name_with_different_members_are_both_read(self):
        found = fields_of('interface A { a: string; }\ninterface A { b: string; }\n')
        self.assertEqual(paths(found), ['A.a', 'A.b'])

    def test_a_member_without_a_type_has_no_declared_type(self):
        self.assertIsNone(one('interface A { a; b: string }', 'A.a')['tip_declarat'])

    def test_braces_in_strings_and_comments_do_not_end_a_declaration(self):
        body = 'interface A {\n  a: "}" | "{";\n  // a } in a comment\n  b: string; /* and } here */\n  c: `x{y`;\n}\ninterface B { z: number }\n'
        self.assertEqual(paths(fields_of(body)), ['A.a', 'A.b', 'A.c', 'B.z'])
        self.assertEqual(one(body, 'A.a')['tip_declarat'], '"}" | "{"')

    def test_the_last_member_may_end_without_a_semicolon_and_members_may_be_separated_by_commas(self):
        self.assertEqual(paths(fields_of('type A = { a: string, b: number\n c: boolean }')), ['A.a', 'A.b', 'A.c'])

    def test_the_field_bound_is_two_thousand(self):
        self.assertEqual(MAX_FIELDS, 2000)

    def test_a_quote_that_is_not_closed_ends_at_the_line_end_and_hides_no_later_declaration(self):
        self.assertEqual(paths(fields_of('export const s = "oops;\nconst t = \'x;\ninterface A { z: number; }\n')), ['A.z'])

    def test_two_members_on_one_line_do_not_share_the_comment_at_its_end(self):
        body = 'interface A { a: string; b: number; // about b\n}\n'
        self.assertNotIn('descriere', one(body, 'A.a'))
        self.assertEqual(one(body, 'A.b')['descriere'], 'about b')

    def test_the_extends_list_keeps_the_text_of_each_base_with_collapsed_spaces(self):
        self.assertEqual(one('interface B extends A<\n  C\n>, D { x: string }', 'B.x')['extinde'], ['A< C >', 'D'])

    def test_text_before_the_braces_that_is_not_extends_is_an_error(self):
        with self.assertRaises(TypeScriptError):
            read('interface A implements B { a: string }')

    def test_a_file_with_more_fields_than_the_bound_is_cut_and_says_so(self):
        body = 'interface Big {\n' + ''.join(f'  m{n}: string;\n' for n in range(MAX_FIELDS + 50)) + '}\n'
        fields, cut = read(body)
        self.assertEqual((len(fields), cut), (MAX_FIELDS, True))
        self.assertEqual(read('interface Small { a: string }')[1], False)


class Integration(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()
        self.response = {'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/plain', 'body': self.body}

    def test_the_extension_selects_the_reader_and_the_hint_does_too(self):
        self.assertEqual(EXTENSIONS['.ts'], 'typescript')
        self.assertIn('typescript', READERS)
        by_extension = parse_source(self.body, URL, 'text/plain')
        by_hint = parse_source(self.body, 'https://example.org/data', 'text/plain', 'typescript')
        self.assertEqual(by_extension[0], 'typescript')
        self.assertEqual(by_extension, by_hint)
        self.assertEqual((by_extension[1], by_extension[2]), (fields_of(self.body), False))

    def test_the_source_record_says_that_the_types_come_from_code(self):
        record = analyse_source(self.response)
        self.assertEqual((record['format'], record['baza_tipului'], record['stare'], len(record['campuri'])), ('typescript', 'cod-sau-documentatie', 'analizat', len(fields_of(self.body))))

    def test_a_body_with_no_declaration_is_a_parse_error_and_not_a_silent_empty_source(self):
        record = analyse_source({**self.response, 'body': 'export const a = 1;\n'})
        self.assertEqual((record['stare'], record['campuri']), ('eroare-parsare', []))

    def test_the_evidence_check_reads_the_retained_body_again(self):
        record = analyse_source(self.response)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps(self.response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            path = out / 'seturi-date.json'
            path.write_text(json.dumps({'surse': [record]}))
            report = check_report(out, out)
            self.assertEqual((report['errors'], report['verified']), ([], 1))
            record['campuri'][0]['tip_declarat'] = 'number'
            path.write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']))


if __name__ == '__main__':
    unittest.main()
