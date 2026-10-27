"""Offline checks for the mark `persoane` (module `inventory_persons`): sources whose body holds records about natural persons.

Every person in these fixtures is invented. Every network call is a fake. The tests that read the tracked files need no retained body, except the one
that searches the tracked files for the values of the bodies; it says so and is skipped where the bodies are absent.
"""
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import render_pages
from common import PUBLIC_ROOT
from inventory import analyse_source, check_persons, check_report, header_of, resolve_spec, update_inventory
from inventory_persons import (FIELD_KEYS, MARK, body_values, candidates, identifies, is_marked, leaks, mark_errors, occurs, problems, safe_fields, safe_header,
                               scope_files)
from inventory_state import StateError, load_previous, new_discovery, source_id, validate_state
from test_forbidden_hosts import Browser, Isolated, SyncPage, fake_sync_playwright
from test_inventory_state import Net, Workspace, docs_for, entry

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / 'data/taxonomy-v2'
SITE = 'https://people.example/'
PEOPLE = SITE + 'people.json'
TABLE = SITE + 'table.tsv'
# One record about an invented person: a name, an address, a birth date with a time, an e-mail address, a phone number, a role and a country.
RECORD = {'name': 'Ana Exemplu', 'street': 'Strada Fictiva 12', 'born': '1980-01-01T00:00:00.000000Z', 'email': 'ana.exemplu@example.org',
          'phone': '0721000111', 'role': 'Administrator', 'country': 'Romania', 'badge': 'x1'}
BODY = json.dumps({'total': 2, 'people': [RECORD, {**RECORD, 'name': 'Ion Fictiv', 'role': 'Administrator'}], 'notes': [], 'meta': {}})
TSV = 'type\tname\tscore\nauthority\tNume si prenume\tScor\ncourt\tCurtea de Apel Fictiva\t0.83\nfirst\tIon Fictiv\t0.5\n'
VALUES = ('Ana Exemplu', 'Strada Fictiva 12', '1980-01-01T00:00:00.000000Z', 'ana.exemplu@example.org', 'Ion Fictiv')


def everything(work):
    """The text of every file that a run wrote in the inventory folder."""
    return '\n'.join(data.decode() for data in work.files().values())


def spec(url=PEOPLE, **extra):
    return {'url': url, 'metoda': 'adaugat-explicit', 'parinte': SITE, 'nota': 'Invented people.', **extra}


class Tree(Workspace):
    """A workspace with the folders of the real tree (`data/taxonomy-v2/observatii/inventare`), so that the scope of the search finds its files."""

    def __init__(self, test):
        super().__init__(test)
        self.taxonomy = Path(self.tmp.name) / 'data/taxonomy-v2'
        self.obs = self.taxonomy / 'observatii'
        self.out = self.obs / 'inventare'

    def entries(self):
        return [entry('p', SITE)]

    def docs(self):
        return {'p': docs_for('p', SITE, [])}

    def add(self, name, text):
        """A file of the scope (or of another folder) with the text of an editor's note."""
        path = self.taxonomy / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def check(self):
        return check_report(self.out, self.obs)

    def leaks(self):
        return [e for e in self.check()['errors'] if 'source with persons' in e]


class Mark(unittest.TestCase):
    def test_only_true_is_a_mark_and_any_other_value_is_an_error(self):
        self.assertEqual(mark_errors({'url': 'u'}, 'x'), [])
        self.assertEqual(mark_errors({MARK: True}, 'x'), [])
        for value in (False, None, 'true', 1, 0, [], [True], {'a': 1}, 'da'):
            with self.subTest(value=value):
                self.assertEqual(len(mark_errors({MARK: value}, 'x')), 1)
                self.assertFalse(is_marked({MARK: value}))
        self.assertTrue(is_marked({MARK: True}))

    def test_a_specification_with_another_value_stops_the_run_before_it_writes(self):
        work = Tree(self)
        for value in (False, 'true', 1):
            with self.subTest(value=value), self.assertRaises(StateError):
                work.run(work.entries(), work.docs(), Net({PEOPLE: BODY}), add_sources=[('p', spec(**{MARK: value}))])
        self.assertFalse(work.out.exists() and (work.out / 'proiecte.json').exists())

    def test_the_state_check_refuses_a_registry_record_with_another_value(self):
        record = new_discovery('p', PEOPLE, 'adaugat-explicit', state='activ')
        record[MARK] = 'true'
        errors = validate_state([], [], {('p', PEOPLE): record})
        self.assertTrue(any(MARK in e and 'true' in e for e in errors), errors)

    def test_the_registry_the_source_and_the_state_check_carry_the_mark(self):
        work = Tree(self)
        work.run(work.entries(), work.docs(), Net({PEOPLE: BODY}), add_sources=[('p', spec(**{MARK: True}))])
        record = next(d for d in work.registry() if d['url'] == PEOPLE)
        self.assertIs(record[MARK], True)
        self.assertEqual([e['eveniment'] for e in record['istoric']], ['adaugat'])
        self.assertIs(work.sources()[PEOPLE][MARK], True)
        self.assertEqual(work.check()['errors'], [])
        # The mark is not in a record of a source that has none.
        work2 = Tree(self)
        work2.run(work2.entries(), work2.docs(), Net({PEOPLE: BODY}), add_sources=[('p', spec())])
        self.assertNotIn(MARK, work2.registry()[0])
        self.assertNotIn(MARK, work2.sources()[PEOPLE])

    def test_a_specification_file_with_a_wrong_mark_or_a_mark_that_the_registry_lacks_fails_the_check(self):
        work = Tree(self)
        work.run(work.entries(), work.docs(), Net({PEOPLE: BODY}), add_sources=[('p', spec())])
        folder = work.out / 'adaugari'
        folder.mkdir()
        (folder / 'a.json').write_text(json.dumps([{'proiect': 'p', **spec(**{MARK: True})}]))
        errors = work.check()['errors']
        self.assertTrue(any('not in the registry' in e for e in errors), errors)
        (folder / 'a.json').write_text(json.dumps([{'proiect': 'p', **spec(**{MARK: 'yes'})}]))
        self.assertTrue(any('accepts only the value true' in e for e in work.check()['errors']))
        (folder / 'a.json').write_text(json.dumps([{'proiect': 'p', **spec()}]))
        self.assertEqual(work.check()['errors'], [])

    def test_the_mark_is_added_to_a_registered_source_and_a_later_specification_without_it_never_takes_it_back(self):
        work = Tree(self)
        work.run(work.entries(), work.docs(), Net({PEOPLE: BODY}), add_sources=[('p', spec(nota='Quotes Ana Exemplu.'))])
        self.assertIn('Quotes Ana Exemplu.', json.dumps(work.registry()))
        self.assertNotIn(MARK, work.sources()[PEOPLE])
        # The marked specification replaces the note, and the source is read again with the rule.
        work.run(work.entries(), work.docs(), None, add_sources=[('p', spec(**{MARK: True, 'nota': 'Invented people; no value.'}))], offline=True)
        record = next(d for d in work.registry() if d['url'] == PEOPLE)
        self.assertEqual((record[MARK], record['nota']), (True, 'Invented people; no value.'))
        self.assertEqual([e['eveniment'] for e in record['istoric']], ['adaugat', 'marcat-persoane', 'nota-inlocuita'])
        self.assertNotIn('Ana Exemplu', json.dumps(work.registry()))
        self.assertIs(work.sources()[PEOPLE][MARK], True)
        work.run(work.entries(), work.docs(), None, add_sources=[('p', spec())], offline=True)
        self.assertIs(next(d for d in work.registry() if d['url'] == PEOPLE)[MARK], True)
        # The same note again adds no event.
        work.run(work.entries(), work.docs(), None, add_sources=[('p', spec(**{MARK: True, 'nota': 'Invented people; no value.'}))], offline=True)
        self.assertEqual(len(next(d for d in work.registry() if d['url'] == PEOPLE)['istoric']), 3)

    def test_a_replay_from_the_cache_gives_the_same_bytes(self):
        work = Tree(self)
        marked = [('p', spec(**{MARK: True}))]
        work.run(work.entries(), work.docs(), Net({PEOPLE: BODY}), add_sources=marked)
        before = work.files()
        work.run(work.entries(), work.docs(), None, add_sources=marked, offline=True)
        self.assertEqual(work.files(), before)


class Readers(unittest.TestCase):
    def marked(self, url, body, **extra):
        work = Tree(self)
        work.run(work.entries(), work.docs(), Net({url: body}), add_sources=[('p', spec(url, **{MARK: True}, **extra))])
        return work, work.sources()[url]

    def test_a_marked_json_source_keeps_key_names_paths_types_and_counts_and_no_value(self):
        work, source = self.marked(PEOPLE, BODY)
        self.assertEqual((source['format'], source['stare']), ('json', 'analizat'))
        for field in source['campuri']:
            self.assertLessEqual(set(field), FIELD_KEYS, field['cale'])
        self.assertEqual(problems(source), [])
        text = everything(work)
        for value in (*VALUES, 'Administrator', 'Romania', '0721000111', 'Strada'):
            self.assertNotIn(value, text, 'no file of the inventory holds a value of the body')
        paths = {f['cale']: f for f in source['campuri']}
        self.assertEqual(paths['$.people[].name']['tipuri_observate'], ['string'])
        self.assertEqual((paths['$.notes']['tipuri_observate'], paths['$.notes']['numar_elemente']), (['array'], 0))
        self.assertEqual(paths['$.meta']['numar_elemente'], 0)

    def test_the_record_of_an_unmarked_source_is_what_it_was(self):
        work = Tree(self)
        work.run(work.entries(), work.docs(), Net({PEOPLE: BODY}), add_sources=[('p', spec())])
        source = work.sources()[PEOPLE]
        self.assertNotIn(MARK, source)
        self.assertEqual(source['campuri'], analyse_source({'url': PEOPLE, 'final_url': PEOPLE, 'state': 'ok', 'body': BODY})['campuri'])
        self.assertEqual(safe_fields(source['campuri']), source['campuri'], 'the fields of this reader already hold the allowed keys only')

    def test_a_field_record_loses_every_key_that_is_not_allowed(self):
        field = {'nume': 'a', 'cale': '$.a', 'tipuri_observate': ['string'], 'stare_tip': 'x', 'rol': 'camp-date', 'pointer': '/a', 'valori_enum': ['Ana'],
                 'descriere': 'Ana Exemplu', 'valoare': 'Ana', 'exemplu': 'Ana', 'chei_exemplu': ['Ana'], 'unitate': 'lei', 'numar_elemente': 0}
        self.assertEqual(set(safe_fields([field])[0]), {'nume', 'cale', 'tipuri_observate', 'stare_tip', 'rol', 'pointer', 'numar_elemente'})

    def test_a_reader_that_adds_a_key_to_a_field_of_a_marked_source_cannot_put_it_in_the_record_or_in_the_check(self):
        def reader(body, url, content_type='', hint=None):
            return 'json', [{'nume': 'a', 'cale': '$.a', 'tipuri_observate': ['string'], 'stare_tip': 'observat-in-esantion-json', 'rol': 'camp-date', 'pointer': '/a',
                             'valori_enum': ['Ana Exemplu'], 'descriere': 'Ana Exemplu'}], False
        response = {'url': PEOPLE, 'final_url': PEOPLE, 'state': 'ok', 'body': BODY}
        with mock.patch('inventory.parse_source', reader):
            marked = analyse_source(response, persons=True)
            plain = analyse_source(response)
        self.assertEqual(set(marked['campuri'][0]), set(FIELD_KEYS) & set(plain['campuri'][0]))
        self.assertIn('valori_enum', plain['campuri'][0], 'the mark is what removes the keys')
        # The evidence check re-reads a marked body with the same rule, so a body that still reads the same gives no error.
        work, source = self.marked(PEOPLE, BODY)
        with mock.patch('inventory.parse_source', side_effect=lambda *a, **k: ('json', [{**f, 'valori_enum': ['x']} for f in source['campuri']], False)):
            self.assertEqual([e for e in work.check()['errors'] if 'differ' in e], [])

    def test_a_marked_source_read_as_text_is_refused_because_those_readers_copy_text(self):
        # A JSON Schema holds enumerations and descriptions: the reader of schemas copies them, so a marked source cannot be one.
        schema = json.dumps({'type': 'object', 'properties': {'role': {'type': 'string', 'enum': ['Administrator', 'Ana Exemplu'], 'description': 'Ana Exemplu is one'}}})
        work, source = self.marked(SITE + 'schema.json', schema)
        self.assertEqual((source['stare'], source['campuri']), ('eroare-parsare', []))
        self.assertIn('copy text', source['error'])
        self.assertNotIn('Ana Exemplu', everything(work))
        # A reader that is named in `citire` and copies text is refused too.
        markdown = '| name | description |\n| --- | --- |\n| role | Ana Exemplu is the contact |\n'
        _, record = self.marked(SITE + 'doc.md', markdown, citire='markdown')
        self.assertEqual((record['stare'], record['campuri']), ('eroare-parsare', []))
        self.assertNotIn('Ana Exemplu', json.dumps(record))

    def test_a_marked_csv_keeps_the_header_cells_and_the_machine_names_above_it_and_drops_a_title(self):
        titled = 'Scores of Ana Exemplu\nname\tscore\nNume\tScor\nIon Fictiv\t5\n'
        work, source = self.marked(TABLE, titled, citire={'tip': 'csv', 'delimitator': 'tab', 'rand_antet': 3})
        self.assertEqual([f['nume'] for f in source['campuri']], ['Nume', 'Scor'])
        rows = source['antet']['randuri_deasupra']
        self.assertEqual([c['celula'] for c in rows[0]['celule']], ['A1'], 'the cell of the title stays as an address')
        self.assertEqual([c.get('valoare') for c in rows[0]['celule']], [None], 'and its text does not')
        self.assertEqual([c['valoare'] for c in rows[1]['celule']], ['name', 'score'], 'a machine name is a key name')
        self.assertNotIn('Ana Exemplu', everything(work))
        self.assertNotIn('Ion Fictiv', everything(work))
        self.assertEqual(work.check()['errors'], [])
        # The same file without the mark keeps the title, as before.
        plain = Tree(self)
        plain.run(plain.entries(), plain.docs(), Net({TABLE: titled}), add_sources=[('p', spec(TABLE, citire={'tip': 'csv', 'delimitator': 'tab', 'rand_antet': 3}))])
        self.assertEqual(plain.sources()[TABLE]['antet']['randuri_deasupra'][0]['celule'][0]['valoare'], 'Scores of Ana Exemplu')

    def test_the_header_facts_of_a_marked_source_follow_the_same_rule_in_the_check(self):
        titled = 'Scores of Ana Exemplu\nname\tscore\n'
        hint = {'tip': 'csv', 'delimitator': 'tab', 'rand_antet': 2}
        facts = header_of(titled, hint, True)
        self.assertEqual(facts, safe_header(header_of(titled, hint)))
        self.assertNotEqual(facts, header_of(titled, hint))
        work, _ = self.marked(TABLE, titled, citire=hint)
        path = work.out / 'seturi-date.json'
        state = json.loads(path.read_text())
        state['surse'][0]['antet'] = header_of(titled, hint)  # the text of the title came back
        path.write_text(json.dumps(state))
        errors = work.check()['errors']
        self.assertTrue(any('keeps the text of cell A1' in e for e in errors), errors)
        self.assertNotIn('Ana Exemplu', ' '.join(errors))

    def test_the_form_check_names_a_forbidden_key_and_a_wrong_reader_and_never_a_value(self):
        source = {'url': PEOPLE, 'format': 'json', 'stare': 'analizat', 'persoane': True, 'campuri': [{'nume': 'a', 'cale': '$.a', 'valori_enum': ['Ana Exemplu']}],
                  'valoare_esantion': 'Ana Exemplu'}
        found = problems(source)
        self.assertEqual(len(found), 2)
        self.assertTrue(any('valoare_esantion' in f for f in found) and any('valori_enum' in f for f in found))
        self.assertNotIn('Ana Exemplu', ' '.join(found))
        self.assertEqual(len(problems({'url': PEOPLE, 'format': 'php', 'stare': 'analizat', 'persoane': True, 'campuri': []})), 1)
        self.assertEqual(problems({'url': PEOPLE, 'format': 'json-esantion', 'stare': 'analizat', 'persoane': True, 'campuri': [], 'esantion': {}}), [])

    def test_a_marked_source_that_the_registry_marks_but_the_record_lacks_fails_the_state_check(self):
        work, source = self.marked(PEOPLE, BODY)
        record = work.registry()[0]
        source = {k: v for k, v in source.items() if k != MARK}
        errors = validate_state([], [source], {('p', PEOPLE): record})
        self.assertTrue(any('no mark in its record' in e for e in errors), errors)

    def test_a_specification_never_quotes_the_body_of_a_marked_source(self):
        work, _ = self.marked(PEOPLE, BODY)
        request = {'url': SITE + 'other.json', 'metoda': 'adaugat-explicit', 'locate': {'pagina': PEOPLE, 'text': '"total"', 'cache': True}}
        with self.assertRaises(StateError) as caught:
            resolve_spec({}, 'p', request, work.out / 'surse', {PEOPLE})
        self.assertIn('never quoted', str(caught.exception))
        # The same request for a body that is not marked finds its fragment.
        found = resolve_spec({}, 'p', request, work.out / 'surse', set())
        self.assertEqual(found['dovada']['fragment'], '"total"')
        extra = {'url': SITE + 'other.json', 'metoda': 'adaugat-explicit', 'dovezi': [{'pagina': PEOPLE, 'text': '"total"', 'cache': True, 'rol': 'x'}]}
        with self.assertRaises(StateError):
            resolve_spec({}, 'p', extra, work.out / 'surse', {PEOPLE})

    def test_the_command_refuses_persons_without_a_source_to_mark(self):
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/inventory.py'), '--persons'], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(run.returncode, 2)
        self.assertIn('--persons belongs to --add-source or --import-saved', run.stderr)


class Search(unittest.TestCase):
    """`check_report` looks for the identifying values of each marked body in the files that the inventory writes. The answer names a file and a fingerprint."""

    def setUp(self):
        self.work = Tree(self)
        self.work.run(self.work.entries(), self.work.docs(), Net({PEOPLE: BODY, SITE + 'county.json': json.dumps({'counties': ['Alba Iulia', 'Strada Fictiva 12']})}),
                      add_sources=[('p', spec(**{MARK: True})), ('p', spec(SITE + 'county.json'))])

    def fingerprints(self, errors):
        return sorted(e.split('fingerprint ')[1].split(' ')[0].rstrip(',') for e in errors)

    def test_a_clean_tree_has_no_leak_and_the_check_counts_the_bodies_that_it_searched(self):
        self.work.add('inventar-note.json', json.dumps({'note': {'p': {'rezultat': 'One response. Key names only.'}}}))
        report = self.work.check()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['persons'], {'marked': 1, 'checked': 1, 'unavailable': 0})

    def test_a_value_in_a_note_a_report_or_a_specification_is_found_by_its_fingerprint_and_the_value_is_never_printed(self):
        self.work.add('inventar-note.json', json.dumps({'note': {'p': {'rezultat': 'The contact is Ana Exemplu, born 1980.'}}}))
        self.work.add('observatii/inventare/adaugari/x.json', json.dumps([{'proiect': 'p', 'nota': 'Born 1980-01-01T00:00:00.000000Z in the file.'}]))
        self.work.add('integrare/revizuire.csv', 'id,motiv\nD1,"mail ana.exemplu@example.org"\n')
        errors = self.work.leaks()
        self.assertEqual(len(errors), 3)
        self.assertEqual(self.fingerprints(errors), sorted(hashlib.sha256(v.encode()).hexdigest()[:8] for v in ('Ana Exemplu', '1980-01-01T00:00:00.000000Z', 'ana.exemplu@example.org')))
        text = ' '.join(errors)
        for value in body_values(BODY, 'json')[0]:
            if len(value) >= 4:
                self.assertNotIn(value, text, 'no value of the body, identifying or not, is in the answer')
        for name in ('inventar-note.json', 'x.json', 'revizuire.csv'):
            self.assertIn(name, text)

    def test_the_docs_folder_is_searched_too(self):
        docs = self.work.taxonomy.parent.parent / 'docs'
        (docs / 'reports').mkdir(parents=True)
        (docs / 'ACTIVITY.md').write_text('The source shows Ion Fictiv in row 2.\n')
        (docs / 'reports' / 'r.md').write_text('and Ana Exemplu here\n')
        errors = self.work.leaks()
        self.assertEqual(len(errors), 2)
        self.assertTrue(any('ACTIVITY.md' in e for e in errors) and any('r.md' in e for e in errors))

    def test_only_the_files_that_the_inventory_and_its_editors_write_are_searched(self):
        for name in ('observatii/mentiuni.csv', 'source/mentiuni.csv', 'runs/r/web.json', 'observatii/documentare/index.json', 'observatii/profil.csv'):
            self.work.add(name, 'a search result names Ana Exemplu\n')
        self.assertEqual(self.work.leaks(), [], 'search results, frozen packages and collected pages are written by no reader of the inventory')
        self.assertEqual({p.name for p in scope_files(self.work.taxonomy)}, {p.name for p in self.work.out.glob('*.json')} | {p.name for p in self.work.out.glob('*.csv')})
        self.work.add('inventar-concepte.json', 'Ana Exemplu')
        self.assertIn('inventar-concepte.json', {p.name for p in scope_files(self.work.taxonomy)})

    def test_a_single_word_a_short_number_and_a_key_name_are_not_looked_for(self):
        for word in ('Administrator', 'Romania', 'x1', 'people', 'name', 'ana.exemplu'):
            self.work.add('inventar-note.json', json.dumps({'text': f'a label {word} in a note'}))
            self.assertEqual(self.work.leaks(), [], word)

    def test_a_phone_number_of_ten_digits_is_looked_for_and_the_match_is_a_whole_word(self):
        self.work.add('inventar-note.json', json.dumps({'text': 'call 0721000111 now'}))
        self.assertEqual(len(self.work.leaks()), 1)
        self.work.add('inventar-note.json', json.dumps({'text': 'a hash 0721000111abc and ana.exemplu@example.orgx and XAna Exemplu'}))
        self.assertEqual(self.work.leaks(), [], 'a value inside a longer word is not the value')

    def test_a_value_that_an_unmarked_body_holds_too_is_data_and_not_a_leak(self):
        self.work.add('inventar-note.json', json.dumps({'text': 'The shelter is on Strada Fictiva 12 and in Alba Iulia.'}))
        self.assertEqual(self.work.leaks(), [], 'the county file is retained and holds this value')
        county = self.work.sources()[SITE + 'county.json']
        (self.work.out / county['snapshot']).unlink()
        self.assertEqual(len(self.work.leaks()), 1, 'without the other body the value is the one of the marked body')

    def test_a_value_that_the_address_of_the_source_holds_is_not_a_value(self):
        url = SITE + 'info?tel=0721000111'
        work = Tree(self)
        work.run(work.entries(), work.docs(), Net({url: json.dumps({'q': '0721000111', 'who': 'Ana Exemplu'})}), add_sources=[('p', spec(url, **{MARK: True}))])
        work.add('inventar-note.json', json.dumps({'text': 'asked for 0721000111'}))
        self.assertEqual(work.leaks(), [], 'the request already holds this number')
        work.add('inventar-note.json', json.dumps({'text': 'answered Ana Exemplu'}))
        self.assertEqual(len(work.leaks()), 1)

    def test_a_missing_body_is_unavailable_and_is_not_searched_and_not_an_error(self):
        for path in (self.work.out / 'surse').glob('*.json'):
            path.unlink()
        self.work.add('inventar-note.json', json.dumps({'text': 'Ana Exemplu'}))
        report = self.work.check()
        self.assertEqual(report['persons'], {'marked': 1, 'checked': 0, 'unavailable': 1})
        self.assertFalse([e for e in report['errors'] if 'source with persons' in e])

    def test_the_cells_of_a_csv_body_are_values_and_its_header_is_not(self):
        work = Tree(self)
        hint = {'tip': 'csv', 'delimitator': 'tab', 'rand_antet': 2}
        body = 'machine names\nNume si prenume\tScor\nIon Fictiv\t5\n'
        work.run(work.entries(), work.docs(), Net({TABLE: body}), add_sources=[('p', spec(TABLE, citire=hint, **{MARK: True}))])
        work.add('inventar-note.json', json.dumps({'text': 'The columns are Nume si prenume and Scor.'}))
        self.assertEqual(work.leaks(), [], 'a header cell is a key name')
        work.add('inventar-note.json', json.dumps({'text': 'The first row is Ion Fictiv.'}))
        self.assertEqual(len(work.leaks()), 1)

    def test_a_search_with_the_real_files_of_the_tree_needs_the_retained_bodies_and_finds_nothing(self):
        out, observations = TAXONOMY / 'observatii/inventare', TAXONOMY / 'observatii'
        previous = load_previous(out)
        report = {'errors': [], 'unavailable': [], 'persons': {'marked': 0, 'checked': 0, 'unavailable': 0}}
        check_persons(report, previous, out, observations)
        self.assertGreater(report['persons']['marked'], 0, 'the tracked registry marks the sources of persons')
        if report['persons']['checked'] == 0:
            self.skipTest('the retained bodies are not in git: a fresh checkout cannot search them')
        self.assertEqual(report['errors'], [], 'a value of a source with persons reached a tracked file (the answer shows file and fingerprint)')


class Values(unittest.TestCase):
    def test_which_values_identify(self):
        for value in ('Ana Exemplu', 'Strada Fictiva 12', 'Curtea de Apel', '1980-01-01T00:00:00.000000Z', '1980-01-01 10:30', 'ana@example.org', '0721000111', '+40721000111',
                      '1800101123456'):
            self.assertTrue(identifies(value), value)
        for value in ('Administrator', 'Romania', '23785448', '26.080743', '2019', 'w23785448', '1980-01-01', 'residential', 'urn:ogc:def:crs:OGC:1.3:CRS84', '072100011'):
            self.assertFalse(identifies(value), value)

    def test_the_candidates_leave_out_key_names_short_texts_and_the_address(self):
        values = {'Ana Exemplu', 'Ana', 'An A', 'name', ' Ion Fictiv ', 'Key Name', 'in the url'}
        self.assertEqual(candidates(values, {'Key Name'}, 'https://x.example/?q=in the url'), ['An A', 'Ana Exemplu', 'Ion Fictiv'])

    def test_the_values_of_json_cut_json_and_csv_bodies(self):
        values, names = body_values(BODY, 'json')
        self.assertLessEqual(set(VALUES), values)
        self.assertLessEqual({'name', 'people', 'street', 'meta'}, names)
        self.assertNotIn('name', values)
        cut = '{"people": [{"name": "Ana Exemplu"}, {"name": "Ion Fi'
        values, _ = body_values(cut, 'json-esantion')
        self.assertEqual(values, {'Ana Exemplu'}, 'a value that the cut ended is not a value')
        values, names = body_values('machine\nNume\tScor\nIon Fictiv\t5\n', 'csv', {'tip': 'csv', 'delimitator': 'tab', 'rand_antet': 2})
        self.assertEqual((values, names), ({'Ion Fictiv', '5'}, {'machine', 'Nume', 'Scor'}))
        values, names = body_values('Nume,Scor\nIon Fictiv,5\n', 'csv')
        self.assertEqual((values, names), ({'Ion Fictiv', '5'}, {'Nume', 'Scor'}))

    def test_whole_word_matching_and_the_fingerprint_of_a_leak(self):
        self.assertTrue(occurs('Ana Exemplu', 'by Ana Exemplu, then'))
        self.assertTrue(occurs('Ana Exemplu', 'Ana Exemplu'))
        self.assertTrue(occurs('Ana Exemplu', 'x Ana Exempluz Ana Exemplu'))
        self.assertFalse(occurs('Ana Exemplu', 'x Ana Exempluz'))
        self.assertFalse(occurs('Ana Exemplu', 'xAna Exemplu'))
        self.assertFalse(occurs('Ana Exemplu', 'Ana_Exemplu'))
        with tempfile.TemporaryDirectory() as folder:
            clean, dirty = Path(folder) / 'clean.md', Path(folder) / 'dirty.md'
            clean.write_text('Key names only.\n')
            dirty.write_text('The contact is Ion Fictiv.\n')
            self.assertEqual(leaks(['Ion Fictiv'], [clean, dirty]), [(dirty, hashlib.sha256(b'Ion Fictiv').hexdigest()[:8])])
            self.assertEqual(leaks(['Ion Fictiv'], [clean, dirty], lambda value: True), [])


class Specifications(unittest.TestCase):
    """The tracked specification files and the tracked registry. They need no retained body, so a fresh checkout runs these too."""

    @classmethod
    def setUpClass(cls):
        folder = TAXONOMY / 'observatii/inventare'
        cls.specs = {path.name: json.loads(path.read_text()) for path in sorted((folder / 'adaugari').glob('*.json'))}
        cls.registry = {(d['proiect'], d['url']): d for d in json.loads((folder / 'descoperiri.json').read_text())['descoperiri']}
        cls.sources = {s['url']: s for s in json.loads((folder / 'seturi-date.json').read_text())['surse']}

    def test_the_mark_of_every_tracked_specification_is_true_or_absent(self):
        for name, items in self.specs.items():
            for item in items:
                self.assertEqual(mark_errors(item, f'{name} {item.get("url")}'), [])

    def test_a_marked_specification_is_marked_in_the_registry_and_in_the_source_record(self):
        marked = [(name, item) for name, items in self.specs.items() for item in items if is_marked(item)]
        self.assertTrue(marked)
        for name, item in marked:
            record = self.registry[(item['proiect'], item['url'])]
            self.assertTrue(is_marked(record), f'{name}: replay the file with --add-sources-file')
            self.assertTrue(is_marked(self.sources[item['url']]), item['url'])
            self.assertEqual(record['nota'], item['nota'], 'the note of a marked specification is the note of the registry')

    def test_the_sources_of_the_entries_that_lot_d_named_are_marked(self):
        for (slug, url), record in self.registry.items():
            if slug in ('onorata-instanta', 'politicieni-corupti', 'dupa-cutremur') and record['stare'] == 'activ':
                self.assertTrue(is_marked(record) and is_marked(self.sources[url]), f'{slug} {url}')
        api = 'https://lista-firme.info/api/v1/info?cui=51859625'
        self.assertTrue(is_marked(self.registry[('lista-firme', api)]) and is_marked(self.sources[api]))
        self.assertFalse([u for (s, u), r in self.registry.items() if s == 'lista-firme' and u != api and is_marked(r)], 'the migrations of the repository hold columns, not persons')

    def test_every_marked_source_record_of_the_tree_has_the_form_of_a_source_of_persons(self):
        for url, source in self.sources.items():
            if is_marked(source):
                self.assertEqual(problems(source), [], url)
        marked = {u for (_, u), r in self.registry.items() if is_marked(r)}
        for url in marked:
            self.assertTrue(is_marked(self.sources[url]), url)

    def test_the_tracked_render_specifications_are_valid(self):
        files = sorted((TAXONOMY / 'observatii/inventare/adaugari').glob('*-randare.json'))
        self.assertTrue(files)
        self.assertIsInstance(render_pages.marked_pages(files), set)


class RenderText(Isolated):
    """The browser helper keeps no text for a page that lists persons. A fake browser stands in for Chromium; no page is opened."""
    URL = 'https://ok.example/'
    TEXT = 'Lista: Ana Exemplu, Ion Fictiv (născut 1980)'

    def args(self, **changes):
        base = dict(data_dir=PUBLIC_ROOT, out_dir=self.tmp / 'randare', lot='', slug='s', wait_ms=0, timeout_ms=1, allow_host=[])
        return types.SimpleNamespace(**{**base, **changes})

    def render(self, url=None, **changes):
        control = [{'tag': 'select', 'name': 'county', 'id': None, 'type': 'select-one', 'label': None, 'options': ['Alba', 'Arad']}]
        with mock.patch.dict(sys.modules, fake_sync_playwright(Browser())), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(SyncPage, 'inner_text', lambda page, selector: self.TEXT), mock.patch.object(SyncPage, 'evaluate', lambda page, script: control):
            written = render_pages.render([url or self.URL], self.args(**changes))
        return json.loads(written[0].read_text()), written[0].read_text()

    def spec_file(self, **item):
        path = self.tmp / 'x-randare.json'
        path.write_text(json.dumps([{'proiect': 's', 'url': 'https://ok.example/data.json', 'locate': {'pagina': self.URL, 'randare': 'https://ok.example/data.json'}, **item}]))
        return path

    def test_without_the_mark_and_without_the_option_the_record_keeps_the_text_as_before(self):
        record, raw = self.render()
        self.assertEqual(record['text_randat'], self.TEXT)
        self.assertNotIn('text_lungime', record)
        self.assertNotIn('text_sha256', record)

    def test_the_option_keeps_a_null_a_length_and_a_hash_and_leaves_the_controls_and_the_requests(self):
        record, raw = self.render(fara_text=True)
        self.assertIsNone(record['text_randat'])
        self.assertEqual((record['text_lungime'], record['text_sha256']), (len(self.TEXT), hashlib.sha256(self.TEXT.encode()).hexdigest()))
        self.assertNotIn('Ana Exemplu', raw)
        self.assertNotIn('Ion Fictiv', raw)
        self.assertEqual(record['controale_vizibile'][0]['options'], ['Alba', 'Arad'])
        self.assertEqual((record['stare'], record['url_cerut'], record['cereri_date'], record['nota'][:8]), ('ok', self.URL, [], 'No click'))

    def test_the_mark_of_a_render_specification_has_the_same_effect_as_the_option(self):
        record, raw = self.render(spec=[self.spec_file(**{MARK: True})])
        self.assertIsNone(record['text_randat'])
        self.assertNotIn('Ana Exemplu', raw)
        self.assertEqual(record['text_lungime'], len(self.TEXT))

    def test_the_mark_belongs_to_the_page_of_the_specification_and_a_specification_without_it_changes_nothing(self):
        other, _ = self.render(url='https://ok.example/other', spec=[self.spec_file(**{MARK: True})])
        self.assertEqual(other['text_randat'], self.TEXT)
        unmarked, _ = self.render(spec=[self.spec_file()])
        self.assertEqual(unmarked['text_randat'], self.TEXT)

    def test_a_wrong_mark_or_a_file_that_is_not_a_list_stops_the_render_before_the_browser(self):
        for item in ({MARK: False}, {MARK: 'true'}):
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.render(spec=[self.spec_file(**item)])
        notes = self.tmp / 'notes-randare.json'
        notes.write_text('{"a": 1}')
        with self.assertRaises(ValueError):
            self.render(spec=[notes])

    def test_marked_pages_reads_the_page_of_each_marked_specification(self):
        path = self.spec_file(**{MARK: True})
        self.assertEqual(render_pages.marked_pages([path]), {self.URL})
        self.assertEqual(render_pages.marked_pages([self.spec_file()]), set())
        self.assertEqual(render_pages.marked_pages([]), set())
        self.assertEqual(render_pages.text_fields('abc', False), {'text_randat': 'abc'})
        self.assertEqual(render_pages.text_fields('abc', True), {'text_randat': None, 'text_lungime': 3, 'text_sha256': hashlib.sha256(b'abc').hexdigest()})


if __name__ == '__main__':
    unittest.main()
