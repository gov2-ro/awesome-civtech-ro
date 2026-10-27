"""Offline checks for the reader of pasted Eurostat extractions (`html-tabele-eurostat`). The fixture `fixtures/text/tabele-eurostat.html` is a small page made by hand with
the structure of the data pages of monitorsocial.ro (read on 2026-10-27): a heading with the data set code above each pasted table, metadata rows, dimension rows and data
rows. Its numbers are invented."""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, parse_source
from inventory_eurostat import headings, read
from inventory_text import READERS, parse_tables, sample_type

FIXTURE = Path(__file__).parent / 'fixtures/text/tabele-eurostat.html'
URL = 'https://example.org/data/consum/'


class Extractions(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()
        self.tables = parse_tables(self.body)
        self.fields, self.complete = read(self.body, self.tables, sample_type)
        self.by_path = {f['cale']: f for f in self.fields}

    def test_only_a_table_that_starts_with_the_extraction_line_is_read(self):
        self.assertEqual(len(self.tables), 6)
        self.assertEqual(sorted({f['pointer'].split('/')[2] for f in self.fields}), ['1', '2', '4', '5', '6'], 'the table with a header row of other cells (3) is not an extraction')

    def test_the_measure_has_the_title_the_code_the_unit_and_the_written_form_of_the_cells_and_no_type(self):
        measure = self.by_path['hbs_exp_t000__custom_1000001']
        self.assertEqual((measure['nume'], measure['rol'], measure['unitate'], measure['tip_declarat']),
                         ('Mean consumption expenditure per household and per adult equivalent0', 'masura', 'Euro per adult equivalent', None))
        self.assertEqual((measure['cod_set'], measure['sursa_declarata'], measure['extras_la'], measure['actualizat_declarat'], measure['extractii_in_pagina']),
                         ('hbs_exp_t000__custom_1000001', 'ESTAT', '16/11/2023 14:14:55', '20/10/2023 23:00', 1))
        self.assertEqual(measure['tipuri_observate'], ['forma-numerica', 'text'], 'the missing-value mark is text; the reader gives no storage type')
        self.assertEqual(self.tables[0]['rows'][int(measure['pointer'].rsplit('/', 1)[1])][0], 'Unit of measure')

    def test_the_unit_is_the_first_value_of_its_row_wherever_the_cell_is(self):
        self.assertEqual(self.by_path['hbs_str_t000__custom_1000002']['unitate'], 'Per mille')

    def test_a_dimension_row_says_how_many_values_the_table_shows_and_copies_none(self):
        counts = {f['nume']: f['valori_in_tabel'] for f in self.fields if f['rol'] == 'dimensiune' and f['cale'].startswith('hbs_exp_t000')}
        self.assertEqual(counts, {'Time frequency': 1, 'TIME': 3, 'GEO': 0}, 'the dimension of the rows has no value in its own row')
        counts = {f['nume']: f['valori_in_tabel'] for f in self.fields if f['rol'] == 'dimensiune' and f['cale'].startswith('hbs_str_t000')}
        self.assertEqual(counts, {'Time frequency': 1, 'Time': 1, 'COICOP': 2, 'QUANTILE': 0}, 'the data rows start after the (Labels) rows that follow each other')
        text = json.dumps(self.fields, ensure_ascii=False)
        for value in ('Belgium', 'Bulgaria', 'First quintile', 'Annual', 'Food', '2005'):
            self.assertNotIn(value, text, 'a table value is not a field')

    def test_metadata_rows_are_not_dimensions_and_the_label_suffix_is_cut_from_the_name(self):
        names = {f['nume'] for f in self.fields if f['rol'] == 'dimensiune'}
        self.assertFalse(names & {'Unit of measure', 'Last updated:', 'Dataset:'})
        self.assertIn('GEO', names)
        self.assertNotIn('GEO (Labels)', names)

    def test_a_row_dimension_that_the_extraction_does_not_name_is_not_invented(self):
        self.assertFalse([f for f in self.fields if f['cale'].startswith('hbs_str_t000') and f['nume'] in ('GEO', 'Country', 'Geopolitical entity (reporting)')],
                         'the countries in the first column have no heading: the page does not say which dimension they are')

    def test_a_title_row_may_carry_the_code_and_the_extraction_line_and_the_unit_may_be_in_any_column(self):
        measure = self.by_path['TEST_EMP__custom_2000001']
        self.assertEqual((measure['nume'], measure['unitate'], measure['sursa_declarata'], measure['extras_la']),
                         ('Employment (invented) – annual data', 'Procent din populație', 'ESTAT', '08/09/2023 18:49:38'), 'Date extrase la is the Romanian form of the line')
        self.assertEqual(self.by_path['TEST_PERM__custom_2000002']['unitate'], 'Person', 'the value is in the third cell of its row')

    def test_the_same_code_twice_in_a_table_is_one_data_set_listed_once(self):
        self.assertEqual(self.by_path['TEST_EMP__custom_2000001']['extractii_in_pagina'], 2)
        paths = [f['cale'] for f in self.fields]
        self.assertEqual(len(paths), len(set(paths)), 'no field is listed twice')
        self.assertEqual(sum(1 for f in self.fields if f['rol'] == 'masura' and f['cale'].startswith('TEST_EMP')), 1)

    def test_an_extraction_without_a_labels_row_ends_its_block_at_the_time_row_and_a_label_of_a_pasted_table_is_not_a_dimension(self):
        names = [f['nume'] for f in self.fields if f['cale'].startswith('TEST_PERM__custom_2000002.')]
        self.assertEqual(names, ['Reason', 'TIME'], 'the row `Tabel 1` is a label, and the country below the TIME row is a data row')

    def test_an_extraction_that_cannot_be_split_is_left_out_and_the_source_says_it_is_partial(self):
        self.assertFalse(self.complete)
        self.assertFalse([f for f in self.fields if 'ORPHAN' in f['cale']])

    def test_the_first_row_of_th_cells_is_the_extraction_line_too(self):
        self.assertEqual(self.by_path['tabel5']['unitate'], 'Index')
        self.assertEqual(self.tables[4]['header'][0], 'Data extracted on 02/02/2024 11:00:00 from [ESTAT]', 'the parser keeps a row of th cells as the header')

    def test_an_extraction_without_a_unit_row_has_no_unit_and_points_at_its_first_row(self):
        for text, pointer in (('<table><tr><td>Data extracted on 01/01/2024 10:00:00 from [ESTAT]</td></tr><tr><td>GEO (Labels)</td></tr><tr><td>Romania</td></tr></table>', '/tabele/1/randuri/0'),
                              ('<table><tr><th>Data extracted on 01/01/2024 10:00:00 from [ESTAT]</th></tr><tr><td>GEO (Labels)</td></tr><tr><td>Romania</td></tr></table>', '/tabele/1/antet/0')):
            measure = read(text, parse_tables(text), sample_type)[0][0]
            self.assertEqual((measure['unitate'], measure['pointer'], measure['actualizat_declarat']), (None, pointer, None))

    def test_an_extraction_without_a_heading_gets_a_table_path_and_no_code(self):
        measure = self.by_path['tabel4']
        self.assertEqual((measure['nume'], measure['unitate'], 'cod_set' in measure), ('Tabel 4', 'Percentage', False))
        self.assertIn('tabel4.GEO', self.by_path)

    def test_the_heading_above_a_table_is_found_through_empty_paragraphs_and_line_breaks(self):
        titles = headings(self.body)
        self.assertEqual(sorted(titles), [1, 2])
        self.assertEqual(titles[2], 'Structure of consumption expenditure by COICOP consumption purpose [hbs_str_t000__custom_1000002]')

    def test_every_locator_names_a_row_of_its_table_that_holds_the_text_of_the_field(self):
        for field in self.fields:
            _, _, table, _, row = field['pointer'].split('/')
            cells = self.tables[int(table) - 1]['rows'][int(row)]
            if field['rol'] == 'dimensiune':
                self.assertEqual(cells[0].replace(' (Labels)', ''), field['nume'])
            else:
                self.assertIn(cells[0], ('Unit of measure', 'Unitate de măsură'))

    def test_a_table_without_a_labels_row_and_a_page_without_an_extraction_are_errors(self):
        broken = self.body.replace('GEO (Labels)', 'GEO').replace('COICOP (Labels)', 'COICOP')
        fields, complete = read(broken, parse_tables(broken), sample_type)
        self.assertEqual({f['cale'].split('.')[0] for f in fields}, {'hbs_exp_t000__custom_1000001', 'hbs_str_t000__custom_1000002', 'TEST_EMP__custom_2000001', 'TEST_PERM__custom_2000002'},
                         'tables 4 and 5 have no (Labels) row and no TIME row left: they are left out, the others stay (the TIME row ends their block)')
        self.assertFalse(complete)
        only = '<table><tr><td>Data extracted on 01/01/2024 10:00:00 from [ESTAT]</td></tr><tr><td>Sex</td><td>Total</td></tr><tr><td>Romania</td><td>5</td></tr></table>'
        with self.assertRaises(ValueError):
            read(only, parse_tables(only), sample_type)
        plain = '<html><table><tr><td>a</td><td>b</td></tr></table></html>'
        with self.assertRaises(ValueError):
            read(plain, parse_tables(plain), sample_type)

    def test_the_hint_selects_the_reader_and_the_source_record_is_documentation_not_a_schema(self):
        self.assertIn('html-tabele-eurostat', READERS)
        fmt, fields, truncated = parse_source(self.body, URL, 'text/html', 'html-tabele-eurostat')
        self.assertEqual((fmt, fields, truncated), ('html-tabele-eurostat', self.fields, True), 'an extraction that was left out makes the source partial')
        record = analyse_source({'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/html', 'body': self.body}, 'html-tabele-eurostat')
        self.assertEqual((record['format'], record['baza_tipului'], record['stare']), ('html-tabele-eurostat', 'cod-sau-documentatie', 'analizat'))

    def test_the_evidence_check_reads_the_retained_body_again(self):
        response = {'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/html', 'body': self.body}
        record = analyse_source(response, 'html-tabele-eurostat')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            path = out / 'seturi-date.json'
            path.write_text(json.dumps({'surse': [record]}))
            report = check_report(out, out)
            self.assertEqual((report['errors'], report['verified']), ([], 1))
            record['campuri'][0]['unitate'] = 'Euro'
            path.write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']))


if __name__ == '__main__':
    unittest.main()
