"""Offline checks for the glossary reader (`html-glosar`). The fixture `fixtures/text/glosar.html` is a small page made by hand with the structure of the
structure page of verificapsiholog.ro (read on 2026-10-27): headings `Label (name)`, a definition paragraph, an example in a `<small>` that the reader must not copy,
and headings that are not fields."""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, parse_source
from inventory_glossary import read
from inventory_text import READERS

FIXTURE = Path(__file__).parent / 'fixtures/text/glosar.html'
URL = 'https://example.org/structura-datelor'


class Glossary(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()
        self.fields = read(self.body)
        self.by_name = {f['nume']: f for f in self.fields}

    def test_a_heading_with_a_name_in_brackets_is_a_field_and_a_plain_heading_is_not(self):
        self.assertEqual([f['nume'] for f in self.fields], ['personalCode', 'issuanceDate', 'is_suspended2', 'branch'])
        for plain in ('Ontologie', 'RUP Partea I', 'practice regime'):
            self.assertNotIn(plain, self.by_name, 'a capital letter or several words in the brackets is not a field name')
        self.assertEqual(self.by_name['issuanceDate']['eticheta'], 'Data (re)emiterii', 'the label keeps its own brackets')

    def test_the_definition_is_the_first_paragraph_below_the_heading_and_a_heading_without_one_has_none(self):
        self.assertEqual(self.by_name['personalCode']['descriere'], 'Identificatorul unic al persoanei în registru. Codul este atribuit de organizație.')
        self.assertEqual(self.by_name['issuanceDate']['descriere'], 'Data când certificatul a fost emis & reemis.', 'entities are decoded')
        self.assertEqual(self.by_name['is_suspended2']['descriere'], '', 'the next heading comes before any paragraph: the field has no definition')
        self.assertEqual(self.by_name['branch']['descriere'], 'Filiala teritorială.')

    def test_an_example_and_a_later_paragraph_are_never_copied(self):
        text = json.dumps(self.fields, ensure_ascii=False)
        self.assertNotIn('Popescu Test Ana', text, 'an example on such a page can name a real person')
        self.assertNotIn('al doilea paragraf', text)

    def test_a_field_states_what_the_page_says_and_no_type(self):
        for field in self.fields:
            self.assertEqual((field['tip_declarat'], field['stare_tip'], field['rol'], field['cale']), (None, 'declarat-in-text-documentatie', 'camp-dictionar', field['nume']))

    def test_the_locator_covers_the_heading_and_its_paragraph_in_the_retained_body(self):
        for field in self.fields:
            start, end = (int(n) for n in field['pointer'].split(':')[1].split('-'))
            cut = self.body[start:end]
            self.assertTrue(cut.startswith('<h'), field['nume'])
            self.assertIn(f'({field["nume"]})', cut)
            self.assertEqual(cut.count('<p'), 1 if field['descriere'] else 0, field['nume'])
            self.assertEqual(field['linie'], self.body.count('\n', 0, start) + 1)
        self.assertTrue(self.body[int(self.by_name['personalCode']['pointer'].split('-')[1]) - 4:].startswith('</p>'), 'the locator ends after the closing tag of the paragraph')

    def test_the_same_name_under_two_headings_and_a_page_without_a_field_are_errors(self):
        with self.assertRaises(ValueError):
            read(self.body.replace('Filiala (branch)', 'Filiala (personalCode)'))
        with self.assertRaises(ValueError):
            read('<html><h2>Titlu</h2><p>text</p></html>')

    def test_the_hint_selects_the_reader_and_the_source_record_says_it_is_documentation(self):
        self.assertIn('html-glosar', READERS)
        fmt, fields, truncated = parse_source(self.body, URL, 'text/html', 'html-glosar')
        self.assertEqual((fmt, fields, truncated), ('html-glosar', self.fields, False))
        with self.assertRaises(ValueError):
            parse_source(self.body, URL, 'text/html')  # HTML at a data address is an error unless a reader is named
        record = analyse_source({'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/html', 'body': self.body}, 'html-glosar')
        self.assertEqual((record['format'], record['baza_tipului'], record['stare'], len(record['campuri'])), ('html-glosar', 'cod-sau-documentatie', 'analizat', 4))

    def test_the_evidence_check_reads_the_retained_body_again(self):
        response = {'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/html', 'body': self.body}
        record = analyse_source(response, 'html-glosar')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            path = out / 'seturi-date.json'
            path.write_text(json.dumps({'surse': [record]}))
            report = check_report(out, out)
            self.assertEqual((report['errors'], report['verified']), ([], 1))
            record['campuri'][0]['descriere'] = 'Alt text'
            path.write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']))


if __name__ == '__main__':
    unittest.main()
