"""Offline checks for the CSV header options (`{"tip": "csv", "rand_antet": N, "coloane_fara_nume": "omise"}`) of the export of a spreadsheet tab.

The bodies are small invented tables with the shapes that two real tabs have: a title row above the header, and a header with empty cells.
Every network call is a fake.
"""
import json
import unittest

from inventory import analyse_source, check_report, has_csv_options, parse_source
from inventory_sheet import cell, column_letters, header_facts, read, read_rows, settings
from test_inventory_state import Workspace, docs_for, entry

URL = 'https://docs.google.com/spreadsheets/d/AAA/export?format=csv&gid=7'
TITLED = 'Stabilire de domiciliu în perioada 01.04 - 11.06.2016,,,\nJudeţ,Localitate,Judeţ de provenienţă,Nr. persoane\nAlba,Com.Albac,Alba,15\n'
UNNAMED = ',Document,Data Document,Beneficiar,Plati,,,,\n1,OP 1,31.05.2021,A SRL,"21363,51",,,,\n'
PLAIN = 'SIRUTA,UAT,judet\n1017,ALBA IULIA,ALBA\n'


def response(body, url=URL, content_type='text/csv'):
    return {'url': url, 'final_url': 'https://doc-0g-sheets.googleusercontent.com/export/x', 'state': 'ok', 'http_status': 200,
            'content_type': content_type, 'body': body, 'fetched_at': '2026-10-26T19:00:00+00:00'}


class Net:
    def __init__(self, bodies):
        self.bodies, self.calls = bodies, []

    def __call__(self, url, sample=None):
        self.calls.append(url)
        return response(self.bodies[url], url)


class Columns(unittest.TestCase):
    def test_spreadsheet_notation(self):
        self.assertEqual([column_letters(i) for i in (0, 1, 25, 26, 27, 51, 52, 701, 702)], ['A', 'B', 'Z', 'AA', 'AB', 'AZ', 'BA', 'ZZ', 'AAA'])
        self.assertEqual(cell(3, 12), 'D12')


class HeaderRow(unittest.TestCase):
    def test_without_an_option_a_title_row_and_empty_header_cells_stay_errors(self):
        with self.assertRaises(ValueError):
            parse_source(UNNAMED, URL, 'text/csv')
        with self.assertRaises(ValueError):
            parse_source(TITLED, URL, 'text/csv')
        self.assertTrue(has_csv_options({'tip': 'csv', 'rand_antet': 2}))
        self.assertFalse(has_csv_options({'tip': 'csv'}) or has_csv_options('csv') or has_csv_options(None))

    def test_the_header_can_be_the_second_row_and_the_title_above_it_is_kept_as_a_fact(self):
        fmt, fields, limited = parse_source(TITLED, URL, 'text/csv', {'tip': 'csv', 'rand_antet': 2})
        self.assertEqual((fmt, limited), ('csv', False))
        self.assertEqual([f['nume'] for f in fields], ['Judeţ', 'Localitate', 'Judeţ de provenienţă', 'Nr. persoane'])
        self.assertEqual([f['pointer'] for f in fields], ['celula:A2', 'celula:B2', 'celula:C2', 'celula:D2'])
        self.assertTrue(all(f['tip_declarat'] is None and f['stare_tip'] == 'neprecizat-in-antet-csv' for f in fields))
        self.assertEqual(header_facts(TITLED, {'tip': 'csv', 'rand_antet': 2}),
                         {'rand_antet': 2, 'randuri_deasupra': [{'rand': 1, 'celule': [{'celula': 'A1', 'valoare': 'Stabilire de domiciliu în perioada 01.04 - 11.06.2016'}]}],
                          'celule_antet_goale': []})

    def test_empty_header_cells_are_left_out_only_when_the_option_says_so_and_they_are_listed(self):
        with self.assertRaises(ValueError):
            read(UNNAMED, {'tip': 'csv', 'rand_antet': 1})
        fields = read(UNNAMED, {'tip': 'csv', 'coloane_fara_nume': 'omise'})
        self.assertEqual([f['nume'] for f in fields], ['Document', 'Data Document', 'Beneficiar', 'Plati'])
        self.assertEqual([f['coloana_csv'] for f in fields], [1, 2, 3, 4], 'the column number is the position in the sheet')
        facts = header_facts(UNNAMED, {'tip': 'csv', 'coloane_fara_nume': 'omise'})
        self.assertEqual((facts['celule_antet_goale'], facts['randuri_deasupra']), (['A1', 'F1', 'G1', 'H1', 'I1'], []))

    def test_the_name_is_the_text_of_the_cell_with_its_line_breaks_and_spaces(self):
        fields = read('"Partidul Politic „Șor”\n",Total \n1,2\n', {'tip': 'csv', 'rand_antet': 1})
        self.assertEqual([f['nume'] for f in fields], ['Partidul Politic „Șor”\n', 'Total '])

    def test_a_repeated_name_is_still_an_error_after_the_empty_cells_are_left_out(self):
        with self.assertRaises(ValueError):
            read('a,,a\n1,2,3\n', {'tip': 'csv', 'coloane_fara_nume': 'omise'})
        with self.assertRaises(ValueError):
            read(',,\n1,2,3\n', {'tip': 'csv', 'coloane_fara_nume': 'omise'})

    def test_wrong_options_and_a_missing_row_are_errors(self):
        for bad in ({'rand_antet': 0}, {'rand_antet': '2'}, {'rand_antet': True}, {'rand_antet': 1.5}, {'coloane_fara_nume': 'da'}, {'separator': ';'}):
            with self.assertRaises(ValueError, msg=str(bad)):
                settings({'tip': 'csv', **bad})
        with self.assertRaises(ValueError):
            read_rows('a,b\n', 3)
        with self.assertRaises(ValueError):
            read_rows('a,b\n', 2)

    def test_a_row_above_the_header_keeps_its_non_empty_cells_and_cuts_a_long_cell(self):
        above, header = read_rows(',Title,,' + 'x' * 400 + '\nA,B,C,D\n1,2,3,4\n', 2)
        self.assertEqual(header, ['A', 'B', 'C', 'D'])
        self.assertEqual([c['celula'] for c in above[0]['celule']], ['B1', 'D1'])
        self.assertEqual(len(above[0]['celule'][1]['valoare']), 300)


class Source(unittest.TestCase):
    def setUp(self):
        self.hint = {'tip': 'csv', 'rand_antet': 2}

    def test_a_source_with_options_keeps_the_reader_and_the_header_facts_and_a_plain_one_keeps_neither(self):
        source = analyse_source(response(TITLED), self.hint)
        self.assertEqual((source['stare'], source['format'], source['baza_tipului']), ('analizat', 'csv', 'antet-fara-tipuri'))
        self.assertEqual((source['citire'], source['antet']['rand_antet']), (self.hint, 2))
        plain = analyse_source(response(PLAIN, URL + '&p=1'), None)
        self.assertEqual((plain['stare'], plain['format']), ('analizat', 'csv'))
        self.assertNotIn('antet', plain)
        self.assertNotIn('citire', plain)

    def test_the_title_row_as_a_header_fails_the_plain_reader_cleanly_and_the_option_reads_it(self):
        plain = analyse_source(response(UNNAMED), None)
        self.assertEqual(plain['stare'], 'eroare-parsare')
        option = analyse_source(response(UNNAMED), {'tip': 'csv', 'coloane_fara_nume': 'omise'})
        self.assertEqual((option['stare'], len(option['campuri'])), ('analizat', 4))

    def run_workspace(self):
        work = Workspace(self)
        entries = [entry('p', 'https://p.example/')]
        docs = {'p': docs_for('p', 'https://p.example/', [])}
        net = Net({URL: TITLED, URL + '&p=1': PLAIN})
        additions = [('p', {'url': URL, 'citire': self.hint}), ('p', {'url': URL + '&p=1'})]
        work.run(entries, docs, net, add_sources=additions)
        return work, entries, docs, additions

    def test_a_run_reads_both_kinds_and_a_replay_from_the_cache_gives_the_same_bytes(self):
        work, entries, docs, additions = self.run_workspace()
        sources = work.sources()
        self.assertEqual([f['nume'] for f in sources[URL]['campuri']], ['Judeţ', 'Localitate', 'Judeţ de provenienţă', 'Nr. persoane'])
        self.assertEqual([f['nume'] for f in sources[URL + '&p=1']['campuri']], ['SIRUTA', 'UAT', 'judet'])
        before = work.files()
        work.run(entries, docs, None, offline=True, add_sources=additions)
        self.assertEqual(work.files(), before)
        rows = [line for line in (work.out / 'campuri.csv').read_text().splitlines() if 'celula:' in line]
        self.assertEqual(len(rows), 4, 'the pointer column holds the header cell of the option reader')

    def test_the_evidence_check_verifies_the_fields_and_the_header_facts(self):
        work, _, _, _ = self.run_workspace()
        obs = work.out.parent
        self.assertEqual(check_report(work.out, obs)['errors'], [])
        path = work.out / 'seturi-date.json'
        state = json.loads(path.read_text())
        source = next(s for s in state['surse'] if s['url'] == URL)
        source['antet']['randuri_deasupra'][0]['celule'][0]['valoare'] = 'Another title'
        path.write_text(json.dumps(state))
        self.assertTrue(any('CSV header facts differ' in e for e in check_report(work.out, obs)['errors']))
        source['antet']['randuri_deasupra'][0]['celule'][0]['valoare'] = 'Stabilire de domiciliu în perioada 01.04 - 11.06.2016'
        source['campuri'][0]['pointer'] = 'celula:Z9'
        path.write_text(json.dumps(state))
        self.assertTrue(any('CSV header facts differ' in e for e in check_report(work.out, obs)['errors']))


if __name__ == '__main__':
    unittest.main()
