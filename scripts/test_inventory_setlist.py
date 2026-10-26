"""Offline checks for the reader of a page that lists data sets and links each one to an external file (`html-lista-seturi`).

The fixture `fixtures/text/expertforum-date.html` is the page https://data.expertforum.ro/ as the owner saved it from their browser on
2026-10-26, with the tag-manager script and the contact sentence (a person's e-mail address) removed. The markup of the rest is unchanged.
Every network call is a fake. The reader never requests a link, and a test proves it.
"""
import csv
import hashlib
import json
import re
import socket
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from common import forbidden
from inventory import analyse_source, check_report, import_saved, parse_source
from inventory_state import source_id
from inventory_setlist import kind_of, list_datasets, read, text_of, unwrap
from test_inventory_state import Workspace, docs_for, entry

FIXTURES = Path(__file__).parent / 'fixtures/text'
PAGE = 'https://p.example/'
SAVED_AT = '2026-10-26T20:23:00+02:00'
NOW = datetime(2026, 10, 26, 19, 0, tzinfo=timezone.utc)
SHEET = 'https://docs.google.com/spreadsheets/d/{}/export?format=csv&gid={}'


def export(ident, gid):
    return SHEET.format(ident, gid)


class SheetNet:
    """A fake network for Google Sheets exports: URL -> CSV text. It answers like the export endpoint: `text/csv`."""

    def __init__(self, bodies):
        self.bodies, self.calls = dict(bodies), []

    def __call__(self, url, sample=None):
        self.calls.append(url)
        base = {'url': url, 'final_url': 'https://doc-0g-sheets.googleusercontent.com/export/x', 'fetched_at': '2026-10-26T19:00:00+00:00'}
        if url not in self.bodies:
            return {**base, 'http_status': 404, 'state': 'eroare-http', 'error': 'HTTP Error 404'}
        return {**base, 'http_status': 200, 'content_type': 'text/csv', 'state': 'ok', 'body': self.bodies[url]}


class SetList(unittest.TestCase):
    def setUp(self):
        self.body = (FIXTURES / 'expertforum-date.html').read_text()
        self.datasets = read(self.body)

    def cut(self, fact):
        start, end = fact['pointer'].split(':')[1].split('-')
        return self.body[int(start):int(end)]

    def test_each_table_row_is_a_data_set_in_page_order_under_its_heading(self):
        self.assertEqual(len(self.datasets), 15)
        counts = {}
        for item in self.datasets:
            counts[item['categorie']['valoare']] = counts.get(item['categorie']['valoare'], 0) + 1
        self.assertEqual(counts, {'Electoral': 4, 'Finanțare politică': 1, 'Infrastructură': 6, 'Media': 1, 'Sănătate': 3})
        self.assertEqual(self.datasets[0]['titlu']['valoare'], 'Genul candidaților la alegerile parlamentare 2020')
        self.assertEqual(self.datasets[0]['subcategorie']['valoare'], 'Gen în alegeri')
        self.assertEqual(self.datasets[0]['descriere']['valoare'], 'Genul candidaților la alegerile parlamentare din 2020, calculele EFOR')

    def test_the_header_row_and_the_page_text_around_the_tables_are_not_data_sets(self):
        titles = [d['titlu']['valoare'] for d in self.datasets]
        self.assertNotIn('Baza de date', titles)
        self.assertNotIn('Descrierea setului', ' '.join(titles))
        self.assertTrue(all(d['categorie']['valoare'] != 'Categoria secundară' for d in self.datasets))

    def test_every_fact_has_an_exact_interval_of_the_retained_body_and_the_basis_of_the_page(self):
        for item in self.datasets:
            for key in ('categorie', 'subcategorie', 'titlu', 'descriere'):
                fact = item[key]
                self.assertEqual(fact['baza'], 'declarat-in-pagina')
                self.assertEqual(text_of(self.cut(fact)), fact['valoare'], key)
            for report in item['rapoarte']:
                self.assertEqual(text_of(self.cut(report['text'])), report['text']['valoare'])
            for link in item['legaturi']:
                self.assertEqual(text_of(self.cut(link['eticheta'])), link['eticheta']['valoare'])
            row = item['pointer'].split(':')[1].split('-')
            self.assertTrue(self.body[int(row[0]):int(row[1])].startswith('<tr'))

    def test_an_entity_in_the_page_is_decoded_in_the_value_and_kept_in_the_interval(self):
        media = next(d for d in self.datasets if d['categorie']['valoare'] == 'Media')
        self.assertEqual(media['titlu']['valoare'], 'Alocări și plăți pentru mass media în 2020, pentru programul de promovare COVID')
        self.assertIn('&icirc;n 2020', self.cut(media['titlu']))
        sanatate = next(d for d in self.datasets if d['categorie']['valoare'] == 'Sănătate')
        self.assertIn('metodologie din raport', sanatate['descriere']['valoare'], 'a no-break space is a space')

    def test_a_wrapped_google_link_gives_its_target_and_keeps_the_text_of_the_page(self):
        first = self.datasets[0]['legaturi'][0]
        address = first['adresa']
        self.assertEqual(address['valoare'], 'https://docs.google.com/spreadsheets/d/1ZdnysGyGRAlRQM651SIqsCeUGlO1Ivd8/edit#gid=1547605917')
        self.assertEqual(address['transformare'], 'legatura-google-desfacuta')
        self.assertTrue(address['legatura'].startswith('https://www.google.com/url?q=https://docs.google.com/spreadsheets/d/1Zdnys'))
        self.assertIn('edit%23gid%3D1547605917', self.cut(address), 'the interval is the href as the page writes it')
        self.assertEqual((first['tip'], first['id_document'], first['gid']), ('foaie-google', '1ZdnysGyGRAlRQM651SIqsCeUGlO1Ivd8', '1547605917'))
        plain = next(l for d in self.datasets for l in d['legaturi'] if l['id_document'] == '1uHjx7STb9E97Da4vnUA3Z3oqDurRo220ZpwUCyM2Mm8')
        self.assertNotIn('legatura', plain['adresa'])
        self.assertNotIn('transformare', plain['adresa'])
        self.assertEqual(plain['gid'], '0', 'gid 0 is a sheet number, not a missing value')

    def test_the_reader_makes_no_network_call_not_even_to_google(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('the reader opened a socket')), \
                patch.object(socket, 'create_connection', side_effect=AssertionError('the reader opened a connection')):
            self.assertEqual(len(read(self.body)), 15)

    def test_the_kind_of_a_link_comes_from_its_address_only(self):
        kinds = [link['tip'] for d in self.datasets for link in d['legaturi']]
        self.assertEqual({k: kinds.count(k) for k in set(kinds)}, {'foaie-google': 14, 'fisier-drive': 1, 'dosar-drive': 3})
        drive = next(d for d in self.datasets if d['categorie']['valoare'] == 'Finanțare politică')['legaturi'][0]
        self.assertEqual((drive['tip'], drive['id_document'], drive['gid']), ('fisier-drive', '1-YWEDLrSBv_W40b1bpFx9eIfLlc1U3r1', None))
        self.assertEqual(kind_of('https://example.org/file.csv'), ('alta-legatura', None, None))
        self.assertEqual(kind_of('https://drive.google.com/drive/folders/abc_1')[:2], ('dosar-drive', 'abc_1'))

    def test_the_text_next_to_a_link_is_kept_and_a_bare_separator_is_not(self):
        reserve = next(d for d in self.datasets if d['titlu']['valoare'] == 'Alocări Fondul de rezervă')
        self.assertEqual([l['text_dupa']['valoare'] for l in reserve['legaturi']], ['HG 1088/2021 (Citu)', 'HG 1264/2021 (Ciucă)'])
        for link in reserve['legaturi']:
            self.assertEqual(text_of(self.cut(link['text_dupa'])), link['text_dupa']['valoare'])
        roads = next(d for d in self.datasets if d['titlu']['valoare'].startswith('Alocări fonduri pentru programul Drumuri Bune'))
        self.assertEqual([l['eticheta']['valoare'] for l in roads['legaturi']], ['Deschide 1', 'Deschide 2'])
        self.assertEqual([l['text_dupa'] for l in roads['legaturi']], [None, None])
        media = next(d for d in self.datasets if d['categorie']['valoare'] == 'Media')
        self.assertEqual([l['eticheta']['valoare'] for l in media['legaturi']], ['Deconturi', 'Plăți'])

    def test_related_reports_keep_their_text_and_their_target_and_an_empty_cell_gives_no_report(self):
        reserve = next(d for d in self.datasets if d['titlu']['valoare'] == 'Alocări Fondul de rezervă')
        self.assertEqual([r['adresa']['valoare'] for r in reserve['rapoarte']],
                         ['https://expertforum.ro/clientelism-fara-rezerve/', 'https://expertforum.ro/bani-fondul-rezerva-decembrie-2021/'])
        pndl = next(d for d in self.datasets if d['titlu']['valoare'] == 'Implementare PNDL 2015-2023')
        self.assertEqual((pndl['rapoarte'][0]['text']['valoare'], pndl['rapoarte'][0]['adresa']['valoare']),
                         ('www.expertforum.ro/pndl-in-2022//', 'https://expertforum.ro/pndl-in-2022/'), 'the text and the target of a link can differ')
        self.assertEqual([d['rapoarte'] for d in self.datasets if d['categorie']['valoare'] == 'Sănătate'], [[], [], []])

    def test_a_report_link_to_another_project_is_a_report_and_not_a_file(self):
        finance = next(d for d in self.datasets if d['categorie']['valoare'] == 'Finanțare politică')
        self.assertEqual([r['adresa']['valoare'] for r in finance['rapoarte']], ['https://www.banipartide.ro/'])
        self.assertEqual([l['tip'] for l in finance['legaturi']], ['fisier-drive'])

    def test_the_three_health_data_sets_share_one_folder_and_stay_three_records(self):
        health = [d for d in self.datasets if d['categorie']['valoare'] == 'Sănătate']
        self.assertEqual(len(health), 3)
        self.assertEqual({l['id_document'] for d in health for l in d['legaturi']}, {'1aeDYrKQBwm_L0Wg0qaCprylFUehmOEEu'})

    def test_a_google_link_without_a_target_a_page_without_the_table_and_a_short_row_are_errors(self):
        with self.assertRaises(ValueError):
            unwrap('https://www.google.com/url?sa=D')
        self.assertEqual(unwrap('https://example.org/a?q=1'), ('https://example.org/a?q=1', False))
        with self.assertRaises(ValueError):
            read('<html><body><h3>A</h3><table><tr><th>Nume</th></tr><tr><td>x</td></tr></table></body></html>')
        short = self.body.replace('<td>&nbsp;</td>\n\t\t\t<td><a class="btn btn-primary btn-sm" href="https://drive.google.com/drive/u/0/folders/1aeDYrKQBwm_L0Wg0qaCprylFUehmOEEu">Deschide</a></td>',
                                  '<td>&nbsp;</td>', 1)
        self.assertNotEqual(short, self.body)
        with self.assertRaises(ValueError):
            read(short)

    def test_the_same_data_set_twice_is_an_error(self):
        start = self.body.index('<tr>\n\t\t\t<td>Gen &icirc;n alegeri</td>')
        end = self.body.index('</tr>', start) + len('</tr>')
        doubled = self.body[:end] + self.body[start:end] + self.body[end:]
        with self.assertRaises(ValueError):
            read(doubled)

    def test_the_reader_lists_no_field_and_the_source_key_holds_the_data_sets(self):
        fmt, fields, limited = parse_source(self.body, PAGE, 'text/html', {'tip': 'html-lista-seturi'})
        self.assertEqual((fmt, fields, limited), ('html-lista-seturi', [], False))
        metadata = analyse_source({'url': PAGE, 'final_url': PAGE, 'state': 'ok', 'http_status': 200, 'content_type': 'text/html', 'body': self.body,
                                   'fetched_at': '2026-10-26T19:00:00+00:00'}, {'tip': 'html-lista-seturi'})
        self.assertEqual((metadata['stare'], metadata['format'], metadata['campuri']), ('analizat', 'html-lista-seturi', []))
        self.assertEqual(metadata['seturi'], list_datasets(self.body))
        self.assertEqual(metadata['baza_tipului'], 'cod-sau-documentatie')


class SetListRun(unittest.TestCase):
    """The saved page and two of its sheets in one run: the page by `--import-saved`, the sheets by an explicit addition and a fake network."""

    def setUp(self):
        self.work = Workspace(self)
        self.entries = [entry('p', PAGE)]
        self.docs = {'p': docs_for('p', PAGE, [])}
        self.raw = (FIXTURES / 'expertforum-date.html').read_bytes()
        self.body = self.raw.decode()
        self.first = export('1ZdnysGyGRAlRQM651SIqsCeUGlO1Ivd8', '1547605917')
        self.second = export('1-gauuhQ731-q3ZD6fhCM_sNSXQ8QD6e5', '1272308734')
        self.csv = {self.first: 'SIRUTA,UAT,judet,gen\n1017,ALBA IULIA,ALBA,F\n', self.second: 'SIRUTA,UAT,judet,partid\n1017,ALBA IULIA,ALBA,PNL\n'}
        import_saved(self.work.out / 'surse', PAGE, self.raw, SAVED_AT, 'saved.html', None, now=NOW)
        self.page = {'url': PAGE, 'citire': {'tip': 'html-lista-seturi'}}
        self.sheet = lambda url, fragment: {'url': url, 'metoda': 'adaugat-explicit', 'parinte': PAGE,
                                            'dovada': {'url': PAGE, 'sha256': hashlib.sha256(self.body.encode()).hexdigest(), 'pointer': '/body',
                                                       'interval': [self.body.index(fragment), self.body.index(fragment) + len(fragment)],
                                                       'fragment': fragment, 'snapshot': 'inventare/surse/' + source_id(PAGE) + '.json'}}
        self.additions = [('p', self.page),
                          ('p', self.sheet(self.first, 'https://docs.google.com/spreadsheets/d/1ZdnysGyGRAlRQM651SIqsCeUGlO1Ivd8/edit%23gid%3D1547605917')),
                          ('p', self.sheet(self.second, 'https://docs.google.com/spreadsheets/d/1-gauuhQ731-q3ZD6fhCM_sNSXQ8QD6e5/edit%23gid%3D1272308734'))]
        self.net = SheetNet(self.csv)
        self.state = self.work.run(self.entries, self.docs, self.net, add_sources=self.additions)

    def test_a_sheet_export_is_read_as_a_csv_with_its_header_as_fields_and_the_page_as_a_list_of_data_sets(self):
        sources = self.work.sources()
        self.assertEqual(sorted(self.net.calls), sorted([self.first, self.second]), 'one request for each sheet and none for the saved page')
        self.assertEqual([f['nume'] for f in sources[self.first]['campuri']], ['SIRUTA', 'UAT', 'judet', 'gen'])
        self.assertEqual(sources[self.first]['format'], 'csv')
        self.assertTrue(all(f['stare_tip'] == 'neprecizat-in-antet-csv' and f['tip_declarat'] is None for f in sources[self.first]['campuri']))
        self.assertEqual(sources[PAGE]['format'], 'html-lista-seturi')
        self.assertEqual((sources[PAGE]['campuri'], len(sources[PAGE]['seturi'])), ([], 15))
        self.assertEqual(self.work.profile('p')['campuri_din_surse'], 8, 'the page adds no field')

    def test_the_header_is_the_only_data_that_the_inventory_keeps_of_a_sheet(self):
        text = json.dumps(self.work.sources()[self.first], ensure_ascii=False)
        self.assertNotIn('ALBA IULIA', text)
        for name in ('campuri.csv', 'seturi-date.json'):
            self.assertNotIn('ALBA IULIA', (self.work.out / name).read_text())

    def test_the_discovery_locator_of_a_sheet_is_the_link_in_the_saved_page(self):
        record = next(r for r in self.work.registry() if r['url'] == self.first)
        self.assertEqual((record['locator_stare'], record['dovada']['pointer']), ('cunoscut', '/body'))
        start, end = record['dovada']['interval']
        self.assertEqual(self.body[start:end], record['dovada']['fragment'])

    def test_a_replay_from_the_cache_gives_the_same_bytes_and_makes_no_request(self):
        before = self.work.files()
        net = SheetNet({})
        self.work.run(self.entries, self.docs, net, add_sources=self.additions)
        self.assertEqual(net.calls, [])
        self.assertEqual(self.work.files(), before)

    def test_the_evidence_check_verifies_the_page_the_sheets_and_the_locators_and_catches_a_changed_data_set(self):
        obs = self.work.out.parent
        report = check_report(self.work.out, obs)
        self.assertEqual((report['errors'], report['verified']), ([], 3))
        self.assertEqual(report['saved'], {'total': 1, 'verified': 1, 'unavailable': 0})
        path = self.work.out / 'seturi-date.json'
        state = json.loads(path.read_text())
        page = next(s for s in state['surse'] if s['url'] == PAGE)
        page['seturi'][0]['titlu']['valoare'] = 'Another title'
        path.write_text(json.dumps(state))
        self.assertTrue(any('Datasets differ from the retained body' in e for e in check_report(self.work.out, obs)['errors']))

    def test_a_failed_sheet_keeps_a_record_without_fields_and_the_other_sheet_is_unaffected(self):
        work = Workspace(self)
        import_saved(work.out / 'surse', PAGE, self.raw, SAVED_AT, 'saved.html', None, now=NOW)
        net = SheetNet({self.second: self.csv[self.second]})
        work.run(self.entries, self.docs, net, add_sources=self.additions)
        sources = work.sources()
        self.assertEqual((sources[self.first]['state'], sources[self.first]['http_status']), ('eroare-http', 404))
        self.assertNotEqual(sources[self.first].get('stare'), 'analizat')
        self.assertEqual(sources[self.first]['campuri'], [])
        self.assertEqual([f['nume'] for f in sources[self.second]['campuri']], ['SIRUTA', 'UAT', 'judet', 'partid'])
        self.assertEqual(net.calls.count(self.first), 1, 'no retry')


class TrackedExpertForum(unittest.TestCase):
    """The tracked inventory of data-expertforum (lot C2, part 2). It reads the tracked files only, never the retained bodies."""
    ROOT = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2/observatii/inventare'
    PAGE = 'https://data.expertforum.ro/'
    TAB = re.compile(r'^https://docs\.google\.com/spreadsheets/d/([\w-]+)/export\?format=csv&gid=(\d+)$')

    @classmethod
    def setUpClass(cls):
        cls.sources = {s['url']: s for s in json.loads((cls.ROOT / 'seturi-date.json').read_text())['surse']}
        cls.registry = [r for r in json.loads((cls.ROOT / 'descoperiri.json').read_text())['descoperiri'] if r['proiect'] == 'data-expertforum']
        cls.log = list(csv.DictReader((cls.ROOT / 'jurnal-cereri.csv').open(newline='')))
        cls.datasets = cls.sources[cls.PAGE]['seturi']
        cls.links = [link for d in cls.datasets for link in d['legaturi']]

    def test_the_page_is_the_owners_copy_and_never_a_fetched_page(self):
        page = self.sources[self.PAGE]
        self.assertEqual((page['origine'], page['http_status'], page['format'], len(self.datasets)), ('copie-salvata-de-proprietar', None, 'html-lista-seturi', 15))
        self.assertTrue(all(r['stare'] == 'activ' for r in self.registry))

    def test_each_tab_source_is_the_export_of_a_sheet_link_of_the_page_and_each_sheet_link_has_a_source(self):
        tabs = {r['url'] for r in self.registry if r['url'] != self.PAGE}
        wanted = {f"https://docs.google.com/spreadsheets/d/{l['id_document']}/export?format=csv&gid={l['gid']}" for l in self.links if l['tip'] == 'foaie-google'}
        self.assertEqual(tabs, wanted)
        self.assertEqual(len(tabs), 14)
        self.assertTrue(all(self.TAB.match(url) for url in tabs))

    def test_a_drive_file_and_a_drive_folder_are_listed_by_the_page_and_never_a_source_or_a_request(self):
        self.assertEqual(sorted({l['tip'] for l in self.links}), ['dosar-drive', 'fisier-drive', 'foaie-google'])
        for record in self.registry:
            self.assertNotIn('drive.google.com', record['url'])
        self.assertFalse([r for r in self.log if 'drive.google.com' in r['url'] or 'www.google.com' in r['url']])

    def test_every_tab_was_requested_once_at_docs_google_com_and_no_forbidden_host_was_asked_for_it(self):
        rows = [r for r in self.log if self.TAB.match(r['url'])]
        self.assertEqual(sorted(r['url'] for r in rows), sorted(r['url'] for r in self.registry if r['url'] != self.PAGE), 'one request for each tab, none twice')
        self.assertLessEqual(len(rows), 30)
        self.assertTrue(all(r['metoda'] == 'GET' and r['cache'] == 'nu' and r['lot'] == 'C2' for r in rows))
        self.assertTrue(all(forbidden(r['url']) is None for r in rows))

    def test_the_inventory_keeps_header_names_and_never_a_value_of_a_row(self):
        allowed = {'nume', 'cale', 'tip_declarat', 'stare_tip', 'rol', 'coloana_csv', 'pointer'}
        parsed = [s for s in (self.sources[r['url']] for r in self.registry if r['url'] != self.PAGE) if s.get('stare') == 'analizat']
        self.assertEqual(len(parsed), 10)
        for source in parsed:
            self.assertEqual(source['format'], 'csv')
            for field in source['campuri']:
                self.assertLessEqual(set(field), allowed, field)
                self.assertIsNone(field['tip_declarat'])
        titled = [s for s in parsed if s.get('antet', {}).get('randuri_deasupra')]
        self.assertEqual(len(titled), 1, 'one tab has a title row above its header; it is the only row text kept')
        self.assertEqual(titled[0]['antet']['randuri_deasupra'][0]['celule'][0]['celula'], 'A1')

    def test_a_response_over_the_size_limit_is_recorded_and_not_parsed(self):
        refused = [self.sources[r['url']] for r in self.registry if self.sources[r['url']].get('state') == 'raspuns-prea-mare']
        self.assertGreaterEqual(len(refused), 1)
        for source in refused:
            self.assertEqual((source['campuri'], source.get('sha256')), ([], None))
        rows = {r['url']: r for r in self.log if r['stare'] == 'raspuns-prea-mare'}
        self.assertTrue(all(source['url'] in rows and rows[source['url']]['octeti'] == '2000001' for source in refused))


if __name__ == '__main__':
    unittest.main()
