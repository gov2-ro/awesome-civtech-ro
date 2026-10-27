"""Offline checks for the reader of position names in a page script (`js-pozitii`). The fixture `fixtures/text/script-pozitii.js` is a short script made by hand with the
shape of the decoder in cat-de-tare/assets/app.js (read on 2026-10-27): a regular expression that holds a quote, a division, strings and comments with braces, and objects
that index an array."""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, parse_source
from inventory_positions import MIN_POSITIONS, objects, read, regex_allowed
from inventory_text import READERS

FIXTURE = Path(__file__).parent / 'fixtures/text/script-pozitii.js'
URL = 'https://example.org/assets/app.js'


class Positions(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()
        self.fields = read(self.body)
        self.by_path = {f['cale']: f for f in self.fields}

    def test_each_name_of_the_decoder_is_a_field_with_its_position_and_the_variable(self):
        decoder = [f for f in self.fields if f['cale'].startswith('a[')]
        self.assertEqual([(f['pozitie'], f['nume']) for f in decoder], [(0, 'name'), (1, 'county'), (2, 'kind'), (3, 'pop'), (4, 'x'), (5, 'bb')])
        for field in self.fields:
            self.assertEqual((field['tip_declarat'], field['stare_tip'], field['rol']), (None, 'utilizat-in-cod-pagina', 'camp-folosit-de-pagina'))
            self.assertEqual(field['cale'].replace('#2', '').split('[')[0], field['indice_in'])

    def test_a_member_that_is_not_a_plain_index_is_not_a_position(self):
        names = {f['nume'] for f in self.fields}
        self.assertNotIn('i', names, '`i: i` is no position')
        self.assertNotIn('key', names, '`key: fold(a[0])` names a computed value, not a position')
        self.assertNotIn('pair', names, 'an array of indexes is not one position')

    def test_the_expression_after_the_index_is_kept_as_written_and_never_run(self):
        self.assertEqual((self.by_path['a[4]']['expresie'], self.by_path['a[5]']['expresie']), ('/ 10', '.map(function (b) { return b / 10; })'))
        self.assertIsNone(self.by_path['a[0]']['expresie'])

    def test_an_object_needs_three_positions_of_one_variable(self):
        self.assertEqual(MIN_POSITIONS, 3)
        self.assertNotIn('first', {f['nume'] for f in self.fields}, 'two positions are not a decoder')
        self.assertEqual([f['nume'] for f in self.fields if f['indice_in'] == 'r'], ['id', 'label', 'size'], 'another variable gets its own fields')

    def test_a_second_decoder_on_the_same_variable_keeps_its_own_paths(self):
        second = [(f['pozitie'], f['nume']) for f in self.fields if f['cale'].startswith('a#2[')]
        self.assertEqual(second, [(0, 'title'), (1, 'count'), (2, 'share')])
        self.assertEqual(len({f['cale'] for f in self.fields}), len(self.fields), 'no two fields share a path')

    def test_a_regular_expression_with_a_quote_does_not_break_the_scan(self):
        # The script has /[&<>"]/g before the decoder. Read as a string, the quote would swallow the rest of the file and no decoder would be found.
        self.assertTrue(self.fields)
        self.assertTrue(regex_allowed('x = /a"/', 4))
        self.assertTrue(regex_allowed('return /a"/', 7))
        self.assertFalse(regex_allowed('total / 2 / 3', 6), 'a division after an identifier')
        self.assertFalse(regex_allowed('(a + b) / 2', 8), 'a division after a bracket that closes')

    def test_braces_in_strings_comments_and_template_strings_are_not_objects(self):
        spans = objects(self.body)
        for start, end in spans:
            self.assertEqual((self.body[start], self.body[end - 1]), ('{', '}'))
            self.assertNotIn(self.body[start:start + 3], ('{n}', '{y}'))
        self.assertFalse([s for s in spans if self.body[s[0]:s[1]] in ('{n}', '{y}', '{ that must not open an object')])

    def test_the_locator_cuts_the_member_and_the_line_is_its_line(self):
        for field in self.fields:
            start, end = (int(n) for n in field['pointer'].split(':')[1].split('-'))
            self.assertRegex(self.body[start:end], rf'^{field["nume"]}\s*:\s*{field["indice_in"]}\[{field["pozitie"]}\]', field['cale'])
            self.assertEqual(field['linie'], self.body.count('\n', 0, start) + 1)

    def test_a_script_with_no_decoder_is_an_error(self):
        with self.assertRaises(ValueError):
            read('var a = { x: b[0], y: b[1] }; var c = [1, 2, 3];')

    def test_the_hint_selects_the_reader_and_the_check_reads_the_retained_body_again(self):
        self.assertIn('js-pozitii', READERS)
        fmt, fields, truncated = parse_source(self.body, URL, 'text/javascript', 'js-pozitii')
        self.assertEqual((fmt, fields, truncated), ('js-pozitii', self.fields, False))
        response = {'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/javascript', 'body': self.body}
        record = analyse_source(response, 'js-pozitii')
        self.assertEqual((record['format'], record['baza_tipului'], record['stare']), ('js-pozitii', 'cod-sau-documentatie', 'analizat'))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            path = out / 'seturi-date.json'
            path.write_text(json.dumps({'surse': [record]}))
            report = check_report(out, out)
            self.assertEqual((report['errors'], report['verified']), ([], 1))
            record['campuri'][1]['nume'] = 'region'
            path.write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']))


if __name__ == '__main__':
    unittest.main()
