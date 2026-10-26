"""Offline checks for the reader of a Datasette database listing (`baza-datasette`) and for its use in an inventory run.

The fixture `fixtures/datasette/banipartide-lista.json` is a trimmed copy of the listing that the owner saved from https://db.banipartide.ro/banipartide.json
on 2026-10-26: six of the 38 tables (four visible, two hidden full-text tables), the four views, and the source and licence members. The file is ASCII with
`\\u` escapes, as the server wrote it. It holds column names and row counts only, and no row.
Every network call here is a fake or is absent. The reader never requests a table, and a test proves it.
"""
import csv
import hashlib
import json
import shutil
import socket
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from common import forbidden
from inventory import analyse_source, check_report, import_saved, parse_source, pointer_value
from inventory_concepts import selector_matches
from inventory_datasette import database, is_listing, read
from inventory_site import source_licence
from inventory_state import source_id
from test_inventory_state import Workspace, docs_for, entry

FIXTURE = Path(__file__).parent / 'fixtures/datasette/banipartide-lista.json'
URL = 'https://db.example/base.json'
SAVED_AT = '2026-10-26T20:30:00+02:00'
NOW = datetime(2026, 10, 26, 19, 0, tzinfo=timezone.utc)


def table(name, columns, count=3, hidden=False):
    return {'name': name, 'columns': columns, 'primary_keys': [], 'count': count, 'hidden': hidden, 'fts_table': None,
            'foreign_keys': {'incoming': [], 'outgoing': []}, 'private': False}


def listing(**more):
    return {'database': 'd', 'tables': [table('A', ['x', 'y'])], 'hidden_count': 0, 'views': [], **more}


class Reader(unittest.TestCase):
    def setUp(self):
        self.body = FIXTURE.read_text()
        self.doc = json.loads(self.body)
        self.fields, self.truncated = read(self.doc)

    def test_each_column_of_a_visible_table_is_a_field_in_table_order_and_a_hidden_table_has_none(self):
        self.assertFalse(self.truncated)
        groups = []
        for field in self.fields:
            if field['grup'] not in groups:
                groups.append(field['grup'])
        self.assertEqual(groups, ['Contributii campanie', 'Legenda partide', 'Subvenții', 'news'])
        self.assertEqual({g: sum(f['grup'] == g for f in self.fields) for g in groups},
                         {'Contributii campanie': 11, 'Legenda partide': 14, 'Subvenții': 5, 'news': 5})
        self.assertFalse([f for f in self.fields if '_fts' in f['grup']], 'the full-text tables are hidden and hold no variable')
        self.assertFalse([f for f in self.fields if f['nume'] in ('rank', 'k', 'v')])

    def test_a_field_has_the_path_table_dot_column_the_role_and_no_type(self):
        field = next(f for f in self.fields if f['cale'] == 'Subvenții.Suma')
        self.assertEqual((field['nume'], field['grup'], field['rol'], field['tip_declarat']), ('Suma', 'Subvenții', 'coloana-sql', None))
        self.assertEqual(field['stare_tip'], 'declarat-in-lista-baza')
        self.assertEqual(len({f['cale'] for f in self.fields}), len(self.fields), 'a column name that two tables share is two fields')
        self.assertGreater(sum(f['nume'] == 'Partid' for f in self.fields) + sum(f['nume'] == 'An' for f in self.fields), 0)
        for extra in ('descriere', 'unitate', 'tipuri_observate', 'perioada_declarata'):
            self.assertTrue(all(extra not in f for f in self.fields), extra + ': the listing declares no such fact')

    def test_a_name_stays_as_written_and_the_pointer_addresses_the_name(self):
        legend = [f for f in self.fields if f['grup'] == 'Legenda partide']
        self.assertIn('Sediul social ', [f['nume'] for f in legend], 'a trailing space is part of the name')
        self.assertIn('Președinte', [f['nume'] for f in legend])
        for field in self.fields:
            self.assertEqual(pointer_value(self.doc, field['pointer']), field['nume'], field['cale'])
            self.assertEqual(pointer_value(self.doc, field['pointer'].rsplit('/columns/', 1)[0] + '/name'), field['grup'])

    def test_the_row_count_is_a_fact_that_the_server_computed_and_a_missing_count_stays_empty(self):
        self.assertEqual({f['grup']: f['randuri_tabel'] for f in self.fields},
                         {'Contributii campanie': 49697, 'Legenda partide': 320, 'Subvenții': 1200, 'news': 2})
        base = database(self.doc)
        rows = {t['nume']['valoare']: t['randuri'] for t in base['tabele']}
        self.assertEqual(rows['Subvenții'], {'valoare': 1200, 'pointer': '/tables/2/count', 'baza': 'calculat-de-server'})
        for item in base['tabele']:
            self.assertEqual(pointer_value(self.doc, item['randuri']['pointer']), item['randuri']['valoare'])
        unknown = listing(tables=[table('A', ['x'], count=None), table('B', ['y'], count=True)])
        fields, _ = read(unknown)
        self.assertTrue(all('randuri_tabel' not in f for f in fields), 'a null or boolean count is not a count')
        self.assertEqual([t['randuri'] for t in database(unknown)['tabele']], [None, None])

    def test_a_view_is_named_and_has_no_column_and_the_hidden_tables_are_only_counted(self):
        base = database(self.doc)
        self.assertEqual([v['nume']['valoare'] for v in base['vederi']], ['Alegeri extra', 'Subvenții anuale', 'Venituri cheltuieli alegeri', 'Venituri cheltuieli alegeri - total'])
        self.assertTrue(all(set(v) == {'nume', 'pointer'} for v in base['vederi']))
        self.assertFalse([f for f in self.fields if f['grup'] in {v['nume']['valoare'] for v in base['vederi']}])
        self.assertEqual((base['tabele_ascunse']['valoare'], base['ascunse_in_lista']), (2, 2))
        self.assertEqual([t['nume']['valoare'] for t in base['tabele']], ['Contributii campanie', 'Legenda partide', 'Subvenții', 'news'])
        self.assertEqual(base['tabele'][2]['coloane'], ['Partid', 'Suma', 'An', 'Luna', 'Luna-nr'])

    def test_the_source_and_the_licence_are_declared_facts_with_pointers_into_the_listing(self):
        base = database(self.doc)
        self.assertEqual((base['nume']['valoare'], base['sursa']['valoare'], base['adresa_sursa']['valoare']),
                         ('banipartide', 'Expert Forum', 'https://expertforum.ro/tag/finantare-politica/'))
        self.assertEqual(base['marime_octeti'], {'valoare': 46718976, 'pointer': '/size', 'baza': 'calculat-de-server'})
        licence = base['licenta']
        self.assertEqual((licence['valoare'], licence['acopera'], licence['baza']), ('CC Attribution 4.0 License', 'tabelele-bazei', 'declarat-in-metadate'))
        self.assertEqual(licence['url']['valoare'], 'http://creativecommons.org/licenses/by/4.0/', 'the address stays as the server wrote it')
        self.assertEqual(licence['atribuire'], base['sursa'], 'the attribution is the declared source, word for word')
        for fact in (base['nume'], base['sursa'], base['adresa_sursa'], licence, licence['url'], licence['atribuire'], base['tabele_ascunse']):
            self.assertEqual(pointer_value(self.doc, fact['pointer']), fact['valoare'])

    def test_a_listing_without_source_or_licence_declares_none_and_never_borrows_one(self):
        base = database(listing())
        self.assertEqual((base['sursa'], base['adresa_sursa'], base['licenta'], base['marime_octeti']), (None, None, None, None))
        self.assertEqual(base['tabele_ascunse']['valoare'], 0)
        only_url = database(listing(license_url='http://example.org/l'))
        self.assertIsNone(only_url['licenta'], 'a licence address with no licence name is not a licence')
        no_source = database(listing(license='CC0'))
        self.assertEqual((no_source['licenta']['valoare'], 'url' in no_source['licenta'], 'atribuire' in no_source['licenta']), ('CC0', False, False))

    def test_a_listing_that_is_not_valid_is_an_error_and_never_a_guess(self):
        bad = {
            'a table with no name': listing(tables=[{**table('A', ['x']), 'name': ''}]),
            'a table with no hidden flag': listing(tables=[{k: v for k, v in table('A', ['x']).items() if k != 'hidden'}]),
            'a table with no column list': listing(tables=[{**table('A', ['x']), 'columns': 'x'}]),
            'a table twice': listing(tables=[table('A', ['x']), table('A', ['y'])]),
            'a column twice': listing(tables=[table('A', ['x', 'x'])]),
            'a column with no name': listing(tables=[table('A', ['x', ''])]),
            'a view with no name': listing(views=[{'private': False}]),
            'a source that is not text': listing(source=3),
        }
        for label, doc in bad.items():
            with self.subTest(label):
                self.assertTrue(is_listing(doc))
                with self.assertRaises(ValueError):
                    read(doc)
                    database(doc)
        hidden_twice = listing(tables=[table('A', ['x', 'x'], hidden=True)])
        self.assertEqual(read(hidden_twice), ([], False), 'a hidden table is not read, so its columns are not checked')

    def test_a_document_that_is_not_a_listing_is_not_taken_for_one(self):
        for doc in ({'database': 'd', 'tables': []}, {'tables': [], 'views': []}, {'database': 3, 'tables': [], 'views': []}, [], 'x'):
            self.assertFalse(is_listing(doc), doc)
        self.assertTrue(is_listing(listing()))

    def test_the_reader_makes_no_network_call(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('the reader opened a socket')), \
                patch.object(socket, 'create_connection', side_effect=AssertionError('the reader opened a connection')):
            self.assertEqual(len(read(self.doc)[0]), 35)
            self.assertEqual(len(database(self.doc)['tabele']), 4)


class InSource(unittest.TestCase):
    """The listing as a source of the inventory: the format is detected from its shape, and `--check` reads the retained body again."""

    def setUp(self):
        self.body = FIXTURE.read_text()
        self.response = {'url': URL, 'final_url': URL, 'state': 'ok', 'http_status': 200, 'content_type': 'application/json', 'body': self.body,
                         'fetched_at': '2026-10-26T19:00:00+00:00'}

    def test_the_format_comes_from_the_shape_of_the_document(self):
        fmt, fields, truncated = parse_source(self.body, URL, 'application/json')
        self.assertEqual((fmt, len(fields), truncated), ('baza-datasette', 35, False))
        metadata = analyse_source(self.response)
        self.assertEqual((metadata['stare'], metadata['format'], metadata['baza_tipului']), ('analizat', 'baza-datasette', 'lista-fara-tipuri'))
        self.assertEqual(metadata['baza'], database(json.loads(self.body)))
        self.assertEqual(metadata['campuri'], fields)

    def test_another_json_document_with_the_same_member_names_stays_sampled_json(self):
        other = json.dumps({'tables': [{'name': 'a'}], 'views': []})
        self.assertEqual(parse_source(other, URL, 'application/json')[0], 'json')

    def test_a_malformed_listing_gives_a_parse_error_and_no_field(self):
        broken = json.loads(self.body)
        broken['tables'][0]['columns'].append(broken['tables'][0]['columns'][0])
        metadata = analyse_source({**self.response, 'body': json.dumps(broken)})
        self.assertEqual((metadata['stare'], metadata['campuri']), ('eroare-parsare', []))
        self.assertIn('twice', metadata['error'])


class Run(unittest.TestCase):
    """The owner's copy in a run: no request, the locator in the copy itself, a replay with the same bytes, and the evidence check."""

    def setUp(self):
        self.work = Workspace(self)
        self.entries = [entry('p', 'https://example.org/')]
        self.docs = {'p': docs_for('p', 'https://example.org/', [])}
        self.raw = FIXTURE.read_bytes()
        self.body = self.raw.decode()
        import_saved(self.work.out / 'surse', URL, self.raw, SAVED_AT, 'banipartide.json', None, now=NOW)
        fragment = '"source": "Expert Forum"'
        start = self.body.index(fragment)
        self.spec = {'url': URL, 'metoda': 'adaugat-explicit',
                     'dovada': {'url': URL, 'sha256': hashlib.sha256(self.body.encode()).hexdigest(), 'pointer': '/body', 'interval': [start, start + len(fragment)],
                                'fragment': fragment, 'snapshot': 'inventare/surse/' + source_id(URL) + '.json'}}
        self.state = self.work.run(self.entries, self.docs, None, add_sources=[('p', self.spec)], offline=True)

    def test_the_copy_gives_one_source_with_its_fields_and_database_facts_and_no_request(self):
        source = self.work.sources()[URL]
        self.assertEqual((source['origine'], source['http_status'], source['format'], source['stare']), ('copie-salvata-de-proprietar', None, 'baza-datasette', 'analizat'))
        self.assertEqual(len(source['campuri']), 35)
        self.assertEqual(self.work.profile('p')['campuri_din_surse'], 35)
        self.assertEqual(source['baza']['licenta']['valoare'], 'CC Attribution 4.0 License')
        self.assertTrue(forbidden('https://db.banipartide.ro/banipartide.json'), 'the host stays on the list of hosts that no script requests')

    def test_the_inventory_keeps_names_and_counts_and_never_a_row(self):
        allowed = {'nume', 'cale', 'grup', 'rol', 'tip_declarat', 'stare_tip', 'pointer', 'randuri_tabel'}
        self.assertTrue(all(set(f) <= allowed for f in self.work.sources()[URL]['campuri']))

    def test_the_locator_of_the_discovery_is_a_fragment_of_the_copy_and_the_check_verifies_it(self):
        record = next(r for r in self.work.registry() if r['url'] == URL)
        self.assertEqual((record['locator_stare'], record['dovada']['pointer']), ('cunoscut', '/body'))
        start, end = record['dovada']['interval']
        self.assertEqual(self.body[start:end], record['dovada']['fragment'])
        report = check_report(self.work.out, self.work.out.parent)
        self.assertEqual((report['errors'], report['verified']), ([], 1))
        self.assertEqual(report['saved'], {'total': 1, 'verified': 1, 'unavailable': 0})

    def test_a_replay_from_the_cache_gives_the_same_bytes(self):
        before = self.work.files()
        self.work.run(self.entries, self.docs, None, add_sources=[('p', self.spec)], offline=True)
        self.assertEqual(self.work.files(), before)

    def test_the_evidence_check_catches_a_changed_field_and_a_changed_database_fact(self):
        for label, change in (('a field', lambda s: s['campuri'][0].update(nume='Other')),
                              ('the licence', lambda s: s['baza']['licenta'].update(valoare='CC0'))):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / 'inventare'
                shutil.copytree(self.work.out, out)
                state = json.loads((out / 'seturi-date.json').read_text())
                change(next(s for s in state['surse'] if s['url'] == URL))
                (out / 'seturi-date.json').write_text(json.dumps(state))
                self.assertTrue(any('differ from the retained body' in e for e in check_report(out, Path(tmp))['errors']))


class TrackedBaniPartide(unittest.TestCase):
    """The tracked inventory of bani-partide (lot C2, part 3). It reads the tracked files only, never the retained bodies, and pins no review state."""
    ROOT = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2'
    URL = 'https://db.banipartide.ro/banipartide.json'

    @classmethod
    def setUpClass(cls):
        inv = cls.ROOT / 'observatii/inventare'
        cls.source = next(s for s in json.loads((inv / 'seturi-date.json').read_text())['surse'] if s['url'] == cls.URL)
        cls.registry = [r for r in json.loads((inv / 'descoperiri.json').read_text())['descoperiri'] if r['proiect'] == 'bani-partide']
        cls.log = list(csv.DictReader((inv / 'jurnal-cereri.csv').open(newline='')))
        cls.concepts = json.loads((cls.ROOT / 'inventar-concepte.json').read_text())['concepte']
        cls.notes = json.loads((cls.ROOT / 'inventar-note.json').read_text())
        cls.fields = [({'name': f['nume'], 'path': f['cale'], 'role': f['rol']}, cls.URL) for f in cls.source['campuri']]

    def test_the_source_is_the_owners_copy_with_one_field_for_each_column_of_the_18_visible_tables(self):
        source = self.source
        self.assertEqual((source['origine'], source['http_status'], source['format'], source['stare']), ('copie-salvata-de-proprietar', None, 'baza-datasette', 'analizat'))
        self.assertEqual(source['salvat_la'], '2026-10-26T20:30:00+02:00')
        base = source['baza']
        self.assertEqual((len(base['tabele']), len(source['campuri']), len(base['vederi'])), (18, 172, 4))
        self.assertEqual((base['tabele_ascunse']['valoare'], base['ascunse_in_lista']), (20, 20), 'the hidden full-text tables get no field')
        self.assertEqual(sum(len(t['coloane']) for t in base['tabele']), len(source['campuri']))
        self.assertFalse([f for f in source['campuri'] if '_fts' in f['grup']])
        self.assertEqual({r['url'] for r in self.registry if r['stare'] == 'activ'}, {self.URL})

    def test_the_declared_licence_and_source_are_kept_for_the_field_browser(self):
        base = self.source['baza']
        self.assertEqual((base['licenta']['valoare'], base['licenta']['url']['valoare']), ('CC Attribution 4.0 License', 'http://creativecommons.org/licenses/by/4.0/'))
        self.assertEqual((base['sursa']['valoare'], base['adresa_sursa']['valoare']), ('Expert Forum', 'https://expertforum.ro/tag/finantare-politica/'))
        credit = source_licence(self.source)
        self.assertEqual((credit['name'], credit['attribution']), ('CC Attribution 4.0 License', 'Sursa: Expert Forum'))

    def test_no_request_was_made_to_a_listed_host_and_the_inventory_keeps_no_value_of_a_row(self):
        self.assertFalse([r for r in self.log if 'db.banipartide.ro' in r['url']], 'the database host was never requested')
        listed = [r for r in self.log if forbidden(r['url'])]
        self.assertTrue(listed and all(r['http_status'] == '403' for r in listed), 'the only requests to listed hosts are the refusals that came before the list')
        self.assertIsNotNone(forbidden(self.URL))
        self.assertIsNotNone(forbidden('https://banipartide.ro/'))
        allowed = {'nume', 'cale', 'grup', 'rol', 'tip_declarat', 'stare_tip', 'pointer', 'randuri_tabel'}
        self.assertTrue(all(set(f) <= allowed and f['tip_declarat'] is None for f in self.source['campuri']))
        for table in self.source['baza']['tabele']:
            self.assertEqual(set(table), {'nume', 'randuri', 'coloane', 'pointer'})

    def test_the_discovery_locator_is_a_fragment_of_the_copy(self):
        record = next(r for r in self.registry if r['url'] == self.URL)
        self.assertEqual((record['locator_stare'], record['dovada']['pointer'], record['dovada']['sha256']), ('cunoscut', '/body', self.source['sha256']))
        self.assertEqual({e['rol'] for e in record['dovezi_suplimentare']}, {'adresa-sursa-declarata', 'licenta-declarata', 'adresa-licenta-declarata'})

    def test_each_selector_of_this_part_matches_the_fields_that_its_context_names(self):
        groups = {c['id']: c for c in self.concepts}
        def matched(group):
            return [f for f, url in self.fields if any(selector_matches(s, 'bani-partide', f, url) for s in groups[group]['selectors'])]
        self.assertEqual(sorted(f['path'] for f in matched('subventie-partid')), ['Subvenții.Suma'])
        self.assertEqual(len(matched('donatie-partid')), 3)
        self.assertEqual(len([f for f in matched('partid-politic') if f['name'] == 'Partid']), 12)
        self.assertEqual([f['path'] for f in matched('uat')], ['Legenda partide.UAT'])
        for group in ('subventie-partid', 'donatie-partid'):
            self.assertEqual((groups[group]['categorie'], groups[group]['familie']), ('masura', 'alegeri'))
            facts = [x['cheie'] for s in groups[group]['selectors'] for x in s.get('fapte', [])]
            self.assertNotIn('unitate', facts, 'the listing declares no unit')

    def test_the_candidate_selectors_for_reviewed_groups_match_fields_and_no_donor_column_enters_a_group_by_its_name_alone(self):
        candidates = [c for c in self.notes['selectori_candidati'] if 'bani-partide' in c['selector']['projects']]
        self.assertEqual(sorted(c['grup'] for c in candidates), ['cui', 'cui', 'cui', 'judet', 'judet', 'perioada-de-referinta'])
        for item in candidates:
            hits = [f for f, url in self.fields if selector_matches(item['selector'], 'bani-partide', f, url)]
            self.assertEqual(len(hits), len(item['selector']['path']), item['selector']['context'])
        groups = {c['id']: c for c in self.concepts}
        for gid in ('donatie-partid', 'subventie-partid', 'partid-politic', 'uat'):
            for selector in groups[gid]['selectors']:
                self.assertFalse({'CNP', 'Nume donator'} & set(selector.get('names') or []), 'a column that names a person is in no group')


if __name__ == '__main__':
    unittest.main()
