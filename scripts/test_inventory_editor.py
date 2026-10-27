"""Offline checks for the fields that an editor adds to a source (module `inventory_editor`, file `campuri-editor.csv`).

Every body and every person in these fixtures is invented; every network call is a fake. A test that reads the tracked file checks its form and not its rows:
the owner fills the file, so no test pins a row or a count.
"""
import copy
import csv
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate
from inventory_concepts import sha
from inventory_editor import COLUMNS, FILE, ROLES, STATE, TYPES, check, field_record, membership_errors, merge, read_file, without_added
from inventory_persons import problems, scope_files
from inventory_site import BASIS, FIELD_BASIS_LABELS, ROLE_LABELS, group_hits, publish_finder, publish_preview, variable_matches
from inventory_state import StateError, source_id
from test_inventory_persons import BODY as PEOPLE_BODY, PEOPLE, Tree, spec
from test_inventory_state import Net

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://data.example/'
URL = SITE + 'doc.json'
BODY = json.dumps({'rows': [{'id': 1}], 'nota': 'campul total_pe_an este in lei'})
FRAGMENT = 'total_pe_an este in lei'


def cells(**given):
    base = {'slug': 'p', 'url_sursa': URL, 'nume': 'total_pe_an', 'cale': '$.total_pe_an', 'rol': 'camp-date', 'tip_declarat': 'number', 'unitate': 'lei',
            'descriere': 'Totalul pe an', 'fragment': FRAGMENT, 'nota': ''}
    return {**base, **given}


def text_of(*rows, columns=COLUMNS):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(c, '') for c in columns])
    return stream.getvalue()


def read_text(text, name=FILE):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_text(text, encoding='utf-8')
        return read_file(path)


class FakeLocator:
    """What `EvidenceLocator.text` answers: a text and its kind for each address, None for the others."""

    def __init__(self, texts):
        self.texts, self.asked = texts, []

    def text(self, url, only=None):
        self.asked.append((url, only))
        found = self.texts.get(url)
        return (found, 'sursa') if found is not None and only in (None, 'sursa') else (None, None)


def source(ident_url=URL, **more):
    return {'id': source_id(ident_url), 'url': ident_url, 'format': 'json', 'stare': 'analizat', 'sha256': 'x',
            'campuri': [{'nume': 'id', 'cale': '$.rows[].id', 'rol': 'camp-date', 'stare_tip': 'observat-in-esantion-json', 'pointer': '/rows/0/id'}], **more}


def members(*slugs, url=URL):
    return {(slug, source_id(url)) for slug in slugs}


class Reading(unittest.TestCase):
    def test_a_header_row_alone_is_a_valid_file_with_no_field(self):
        self.assertEqual(read_text(text_of()), ([], []))
        self.assertEqual(read_file(Path('/nonexistent/' + FILE)), ([], []), 'no file, no field')

    def test_a_row_gives_its_cells_and_its_line(self):
        rows, errors = read_text(text_of(cells(), cells(nume='b', cale='$.b')))
        self.assertEqual(errors, [])
        self.assertEqual([r['linie'] for r in rows], [2, 3])
        self.assertEqual(rows[0], {**cells(), 'linie': 2})

    def test_the_columns_must_be_the_ten_columns(self):
        self.assertEqual(read_text(text_of(columns=COLUMNS[:-1]))[1], [f'{FILE}:1: missing columns: nota'])
        rows, errors = read_text(text_of(columns=[*COLUMNS, 'extra']))
        self.assertEqual((rows, errors), ([], [f'{FILE}:1: unknown columns: extra']))
        self.assertEqual(read_text(text_of(cells(), columns=list(reversed(COLUMNS))))[1], [], 'the order of the columns is free')

    def test_each_required_cell_must_be_filled(self):
        for column in ('slug', 'url_sursa', 'nume', 'cale', 'rol', 'fragment'):
            with self.subTest(column=column):
                rows, errors = read_text(text_of(cells(**{column: ' '})))
                self.assertEqual(rows, [])
                self.assertTrue(any(f'{column} is empty' in e for e in errors), errors)
        self.assertEqual(read_text(text_of(cells(tip_declarat='', unitate='', descriere='', nota='')))[1], [], 'the other cells may be empty')

    def test_the_code_lists_are_checked(self):
        self.assertEqual(read_text(text_of(cells(rol='nu-exista')))[1], [f'{FILE}:2: rol is unknown: nu-exista (values: {", ".join(ROLES)})'])
        for role in ROLES:
            self.assertEqual(read_text(text_of(cells(rol=role)))[1], [], role)
        self.assertTrue(any('tip_declarat is unknown: varchar(255)' in e for e in read_text(text_of(cells(tip_declarat='varchar(255)')))[1]))
        self.assertTrue(any('tip_declarat is unknown: floatt' in e for e in read_text(text_of(cells(tip_declarat='string|floatt')))[1]))
        self.assertEqual(read_text(text_of(cells(tip_declarat='string|null')))[1], [], 'several types are separated by |')
        for kind in TYPES:
            self.assertEqual(read_text(text_of(cells(tip_declarat=kind)))[1], [], kind)

    def test_the_slug_and_the_address_have_a_valid_form(self):
        self.assertTrue(any('slug is not valid: Not_Slug' in e for e in read_text(text_of(cells(slug='Not_Slug')))[1]))
        for url in ('ftp://x.example/a', 'doc.json', 'javascript:alert(1)'):
            self.assertTrue(any('url_sursa is not an http or https address' in e for e in read_text(text_of(cells(url_sursa=url)))[1]), url)
        self.assertEqual(read_text(text_of(cells(url_sursa=URL + '#anchor')))[1], [], 'an address with a fragment is the address of the source')

    def test_the_same_field_twice_is_an_error_on_the_second_line(self):
        rows, errors = read_text(text_of(cells(), cells(descriere='again'), cells(rol='camp-raspuns'), cells(slug='q')))
        self.assertEqual([r['linie'] for r in rows], [2, 4])
        self.assertEqual(errors, [f'{FILE}:3: the same field as line 2', f'{FILE}:5: the same field as line 2'], 'the entry does not make a field another one: the source holds it')

    def test_a_row_with_too_many_cells_is_an_error_and_an_empty_line_is_skipped(self):
        text = ','.join(COLUMNS) + '\n' + ','.join(['a'] * 11) + '\n,,,,,,,,,\n'
        rows, errors = read_text(text)
        self.assertEqual(rows, [])
        self.assertEqual(errors, [f'{FILE}:2: the row has more cells than the header'])

    def test_the_file_is_read_as_utf_8_with_or_without_a_byte_order_mark_and_a_fragment_keeps_its_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / FILE
            path.write_bytes(b'\xef\xbb\xbf' + text_of(cells(fragment='  lei\nîn  ', descriere='Număr de școli ')).replace('\n', '\r\n').encode('utf-8'))
            rows, errors = read_file(path)
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]['descriere'], 'Număr de școli', 'a cell is stripped')
        self.assertEqual(rows[0]['fragment'], '  lei\nîn  ', 'a fragment keeps its spaces, and a Windows line end becomes a new line')

    def test_the_tracked_file_has_the_columns_and_valid_rows_whatever_the_owner_wrote(self):
        path = ROOT / 'data/taxonomy-v2/observatii/inventare' / FILE
        self.assertTrue(path.exists())
        with path.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(next(csv.reader(stream)), COLUMNS)
        self.assertEqual(read_file(path)[1], [])


class Records(unittest.TestCase):
    def row(self, **given):
        return {**cells(**given), 'linie': 7}

    def test_a_record_has_the_keys_of_the_readers_and_the_marks_of_an_editor(self):
        record = field_record(self.row(), {'sha256': 'abc', 'text': 'sursa'})
        self.assertEqual(record, {'nume': 'total_pe_an', 'cale': '$.total_pe_an', 'tip_declarat': 'number', 'stare_tip': 'adaugat-de-editor', 'rol': 'camp-date',
                                  'pointer': f'{FILE}:7', 'unitate': 'lei', 'descriere': 'Totalul pe an', 'dovada_editor': {'sha256': 'abc', 'text': 'sursa'}})

    def test_the_fragment_is_never_copied_into_the_record(self):
        self.assertNotIn(FRAGMENT, json.dumps(field_record(self.row(nota='o notă'), {'sha256': 'abc', 'text': 'sursa'})))
        self.assertEqual(field_record(self.row(nota='o notă'))['nota_editor'], 'o notă')

    def test_a_type_is_one_text_or_a_list_or_none(self):
        self.assertEqual(field_record(self.row(tip_declarat='string'))['tip_declarat'], 'string')
        self.assertEqual(field_record(self.row(tip_declarat='string|null'))['tip_declarat'], ['string', 'null'])
        self.assertIsNone(field_record(self.row(tip_declarat=''))['tip_declarat'])

    def test_a_cell_that_is_empty_leaves_its_key_out_and_the_default_evidence_says_that_nothing_is_verified(self):
        record = field_record(self.row(unitate='', descriere='', nota=''))
        self.assertTrue({'unitate', 'descriere', 'nota_editor'}.isdisjoint(record))
        self.assertEqual(record['dovada_editor'], {'sha256': None, 'text': None})

    def test_the_state_is_in_the_list_of_the_preview_and_the_label_in_both_scripts(self):
        self.assertEqual(STATE, 'adaugat-de-editor')
        self.assertEqual(BASIS[STATE], 'editor')
        self.assertEqual(FIELD_BASIS_LABELS['editor'], 'adăugat de editor')
        for name in ('app.js', 'inventory.js'):
            self.assertIn("editor: 'adăugat de editor'" if name == 'app.js' else "editor:'adăugat de editor'", (ROOT / 'site' / name).read_text(), name)

    def test_the_roles_are_the_roles_of_the_field_browser(self):
        self.assertEqual(set(ROLES), set(ROLE_LABELS))
        app = (ROOT / 'site/app.js').read_text()
        body = re.search(r'const INV_ROLES\s*=\s*\{(.*?)\};', app, re.S).group(1)
        self.assertEqual(set(ROLES), {a or b for a, b in re.findall(r"""(?:'([^']+)'|([A-Za-z_]\w*))\s*:""", body)})


class Merging(unittest.TestCase):
    def merged(self, rows, texts=None, sources=None, who=('p',), **more):
        sources = sources if sources is not None else {source_id(URL): source(**more)}
        locator = FakeLocator({URL: BODY} if texts is None else texts)
        errors, notes = merge(sources, rows, members(*who), locator)
        return sources, errors, notes

    def rows(self, *given):
        return [{**cells(**g), 'linie': n} for n, g in enumerate(given, 2)]

    def test_a_row_becomes_a_field_of_its_source_after_the_fields_of_the_readers_with_the_hash_of_the_text(self):
        sources, errors, notes = self.merged(self.rows({}, {'nume': 'b', 'cale': '$.b'}))
        self.assertEqual((errors, notes), ([], []))
        fields = sources[source_id(URL)]['campuri']
        self.assertEqual([f['nume'] for f in fields], ['id', 'total_pe_an', 'b'])
        self.assertEqual(fields[1]['dovada_editor'], {'sha256': sha(BODY), 'text': 'sursa'})
        self.assertEqual(fields[1]['stare_tip'], STATE)

    def test_a_fragment_that_does_not_occur_is_an_error_and_adds_no_field(self):
        sources, errors, _ = self.merged(self.rows({'fragment': 'text that the body never holds'}))
        self.assertEqual(errors, [f'{FILE}:2: the fragment is not in the retained text of {URL}'])
        self.assertEqual(len(sources[source_id(URL)]['campuri']), 1)

    def test_a_text_that_this_checkout_does_not_hold_is_a_note_and_the_hash_stays_empty(self):
        sources, errors, notes = self.merged(self.rows({}), texts={})
        self.assertEqual(errors, [])
        self.assertEqual(len(notes), 1)
        self.assertIn('not verified', notes[0])
        self.assertEqual(sources[source_id(URL)]['campuri'][1]['dovada_editor'], {'sha256': None, 'text': None})

    def test_a_row_for_a_source_that_the_entry_does_not_own_is_an_error(self):
        _, errors, _ = self.merged(self.rows({}), who=('q',))
        self.assertEqual(errors, [f'{FILE}:2: {URL} is not a source of p'])
        _, errors, _ = self.merged(self.rows({'url_sursa': SITE + 'other.json'}))
        self.assertEqual(errors, [f'{FILE}:2: {SITE}other.json is not a source of p'])
        self.assertEqual(membership_errors(self.rows({'slug': 'unknown'}), members('p')), [f'{FILE}:2: {URL} is not a source of unknown'])

    def test_a_row_for_a_source_with_no_record_in_the_inventory_is_an_error(self):
        _, errors, _ = self.merged(self.rows({}), sources={})
        self.assertEqual(errors, [f'{FILE}:2: the inventory holds no record of {URL}'])

    def test_a_field_that_a_reader_already_gives_is_an_error(self):
        _, errors, _ = self.merged(self.rows({'nume': 'id', 'cale': '$.rows[].id'}))
        self.assertEqual(len(errors), 1)
        self.assertIn('the readers already give the field id', errors[0])
        sources, errors, _ = self.merged(self.rows({'nume': 'id', 'cale': '$.rows[].id', 'rol': 'camp-raspuns'}))
        self.assertEqual(errors, [], 'the same name and path in another role is another field')

    def test_a_replay_gives_the_same_records_and_never_changes_the_state_that_it_started_from(self):
        sources, _, _ = self.merged(self.rows({}))
        before = copy.deepcopy(sources)
        again = dict(sources)
        errors, _ = merge(again, self.rows({}), members('p'), FakeLocator({URL: BODY}))
        self.assertEqual((errors, again), ([], before))
        self.assertEqual(sources, before)
        record = source()
        snapshot = copy.deepcopy(record)
        merge({source_id(URL): record}, self.rows({}), members('p'), FakeLocator({URL: BODY}))
        self.assertEqual(record, snapshot, 'the record that came from the tracked state is replaced by a new one, never edited in place')

    def test_the_records_of_an_earlier_run_go_when_the_file_no_longer_has_the_row(self):
        sources, _, _ = self.merged(self.rows({}))
        errors, _ = merge(sources, [], members('p'), FakeLocator({URL: BODY}))
        self.assertEqual(errors, [])
        self.assertEqual([f['nume'] for f in sources[source_id(URL)]['campuri']], ['id'])
        self.assertEqual(without_added(sources[source_id(URL)]), sources[source_id(URL)])

    def test_a_row_for_a_source_with_persons_that_holds_a_value_of_a_person_is_an_error_without_the_value(self):
        body = json.dumps({'people': [{'name': 'Ana Exemplu', 'role': 'Administrator'}], 'nota': 'campul total_pe_an este in lei'})
        sources = {source_id(URL): source(persoane=True)}
        locator = FakeLocator({URL: body})
        errors, _ = merge(sources, self.rows({'descriere': 'Contact: Ana Exemplu'}), members('p'), locator)
        self.assertEqual(len(errors), 1)
        self.assertIn('identifies a person', errors[0])
        self.assertNotIn('Ana Exemplu', errors[0])
        self.assertRegex(errors[0], r'fingerprint [0-9a-f]{8}')
        sources = {source_id(URL): source(persoane=True)}
        errors, _ = merge(sources, self.rows({'fragment': '"name": "Ana Exemplu"'}), members('p'), locator)
        self.assertEqual(len(errors), 1, 'the fragment is searched too')
        self.assertTrue(merge({source_id(URL): source(persoane=True)}, self.rows({}), members('p'), locator) == ([], []), 'a row without such a value passes')
        self.assertEqual(merge({source_id(URL): source()}, self.rows({'descriere': 'Contact: Ana Exemplu'}), members('p'), locator), ([], []), 'a source without the mark is not searched')

    def test_a_body_that_is_not_in_the_format_of_a_source_with_persons_cannot_be_searched(self):
        errors, _ = merge({source_id(URL): source(persoane=True)}, self.rows({'fragment': 'este in lei'}), members('p'), FakeLocator({URL: 'not json at all, este in lei'}))
        self.assertEqual(len(errors), 1)
        self.assertIn('not a body of the format', errors[0])

    def test_the_editor_record_of_a_source_with_persons_may_hold_its_own_keys_and_no_other(self):
        record = field_record({**cells(), 'linie': 2}, {'sha256': 'a', 'text': 'sursa'})
        marked = {'url': 'u', 'stare': 'analizat', 'format': 'json', 'persoane': True, 'campuri': [record]}
        self.assertEqual(problems(marked), [])
        marked['campuri'] = [{**record, 'exemplu': 'Ana Exemplu'}, {'nume': 'x', 'cale': 'x', 'stare_tip': 'observat-in-esantion-json', 'descriere': 'a reader copied text'}]
        self.assertEqual(sorted(p.rsplit(' ', 1)[-1] for p in problems(marked)), ['descriere', 'exemplu'])


class KindLocator:
    """A locator with several copies of one address: the source body, a cached page body. `only` picks the kind, as `EvidenceLocator.text` does."""

    def __init__(self, **kinds):
        self.kinds = kinds

    def text(self, url, only=None):
        for kind in ('sursa', 'documentatie', 'cache'):
            if kind in self.kinds and only in (None, kind):
                return self.kinds[kind], kind
        return None, None


class Checking(unittest.TestCase):
    """`check` on a generated state that the test builds by hand."""

    def state(self, evidence, rows=None, owner=True, record=True):
        rows = [{**cells(), 'linie': 2}] if rows is None else rows
        base = source()
        added = field_record(rows[0], evidence) if rows else None
        previous = {'profiles': {'p': {'surse_structurate': [source_id(URL)] if owner else []}},
                    'sources': {source_id(URL): {**base, 'campuri': [*base['campuri'], *([added] if added else [])]}} if record else {}}
        return rows, previous

    def test_a_hash_that_the_retained_text_gives_is_verified(self):
        rows, previous = self.state({'sha256': sha(BODY), 'text': 'sursa'})
        self.assertEqual(check(rows, previous, FakeLocator({URL: BODY})), {'errors': [], 'unavailable': [], 'verified': 1, 'rows': 1})

    def test_the_hash_is_compared_with_the_kind_of_copy_that_it_was_made_on(self):
        cached = BODY + ' (the cached page)'
        rows, previous = self.state({'sha256': sha(cached), 'text': 'cache'})
        self.assertEqual(check(rows, previous, KindLocator(sursa=BODY, cache=cached))['errors'], [], 'a pin made on the cached page is not compared with the source body')
        rows, previous = self.state({'sha256': sha(BODY), 'text': 'sursa'})
        self.assertEqual(check(rows, previous, KindLocator(sursa=BODY, cache=cached))['errors'], [])
        self.assertEqual(len(check(rows, previous, KindLocator(sursa=BODY + ' changed', cache=cached))['errors']), 1)

    def test_a_row_for_a_source_that_has_no_record_in_the_inventory_is_an_error(self):
        rows, previous = self.state({'sha256': None, 'text': None}, record=False)
        errors = check(rows, previous, FakeLocator({}))['errors']
        self.assertEqual(errors, [f'{FILE}:2: {URL} has no record in the inventory; run inventory.py --offline'])

    def test_a_row_for_a_source_that_the_entry_does_not_own_is_an_error(self):
        rows, previous = self.state({'sha256': sha(BODY), 'text': 'sursa'}, owner=False)
        self.assertEqual(check(rows, previous, FakeLocator({URL: BODY}))['errors'], [f'{FILE}:2: {URL} is not a source of p'])

    def test_a_record_without_its_row_is_an_error_and_no_row_with_no_record_is_not(self):
        rows, previous = self.state({'sha256': sha(BODY), 'text': 'sursa'})
        self.assertEqual(len(check([], previous, FakeLocator({URL: BODY}))['errors']), 1)
        rows, previous = self.state(None, rows=[])
        self.assertEqual(check([], previous, FakeLocator({URL: BODY}))['errors'], [])


class Run(unittest.TestCase):
    """The merge inside a run of `update_inventory`, the replay and the check, on a workspace of the real tree."""

    def setUp(self):
        self.work = Tree(self)
        self.entries, self.docs = self.work.entries(), self.work.docs()
        self.work.run(self.entries, self.docs, Net({URL: BODY}), add_sources=[('p', spec(URL))])

    def rows(self, *given):
        path = self.work.out / FILE
        path.write_text(text_of(*[cells(**g) for g in given]), encoding='utf-8')
        rows, errors = read_file(path)
        self.assertEqual(errors, [])
        return rows

    def run_with(self, rows, **options):
        return self.work.run(self.entries, self.docs, None, offline=True, editor_rows=rows, **options)

    def generated(self):
        """The files that a run writes: the folder without the hand-edited file."""
        return {name: data for name, data in self.work.files().items() if name != FILE}

    def test_a_row_is_a_field_of_its_source_counted_by_the_profile_and_written_to_the_generated_files(self):
        plain = self.generated()
        state = self.run_with(self.rows({}))
        source = self.work.sources()[URL]
        added = [f for f in source['campuri'] if f['stare_tip'] == STATE]
        self.assertEqual([f['nume'] for f in added], ['total_pe_an'])
        self.assertEqual(added[0]['dovada_editor'], {'sha256': source['sha256'], 'text': 'sursa'}, 'the hash of the retained body, which the source record holds too')
        self.assertEqual(self.work.profile('p')['campuri_din_surse'], len(source['campuri']))
        self.assertIn(f'{FILE}:2,adaugat-de-editor', (self.work.out / 'campuri.csv').read_text())
        self.assertNotEqual(self.generated()['campuri.csv'], plain['campuri.csv'])
        self.assertEqual(state['report']['avertismente'], [])
        self.assertNotIn(FRAGMENT, (self.work.out / 'seturi-date.json').read_text(), 'only the editor file holds the fragment')

    def test_an_empty_file_gives_the_bytes_that_a_run_without_the_file_gives_and_a_replay_is_stable(self):
        plain = self.generated()
        self.run_with(self.rows())
        self.assertEqual(self.generated(), plain)
        self.run_with(self.rows({}))
        once = self.generated()
        self.run_with(self.rows({}))
        self.assertEqual(self.generated(), once, 'a second replay changes no byte')
        self.run_with(self.rows())
        self.assertEqual(self.generated(), plain, 'removing the row removes the field')

    def test_an_error_in_a_row_stops_the_run_and_no_file_changes(self):
        before = self.generated()
        with self.assertRaises(StateError) as caught:
            self.run_with(self.rows({'fragment': 'a text that the body does not hold'}))
        self.assertIn('the fragment is not in the retained text', str(caught.exception))
        self.assertEqual(self.generated(), before, 'the state is computed before anything is written: a StateError leaves the folder as it was')
        with self.assertRaises(StateError):
            self.run_with(self.rows({'url_sursa': SITE + 'other.json'}))

    def test_a_missing_body_is_a_warning_and_the_field_is_kept_without_a_hash(self):
        for path in (self.work.out / 'surse').iterdir():
            path.unlink()
        state = self.run_with(self.rows({}))
        field = next(f for f in self.work.sources()[URL]['campuri'] if f['stare_tip'] == STATE)
        self.assertEqual(field['dovada_editor'], {'sha256': None, 'text': None})
        self.assertTrue(any('not verified' in w for w in state['report']['avertismente']))

    def test_a_group_selector_matches_an_added_field_and_the_field_browser_names_its_basis(self):
        self.run_with(self.rows({}))
        concepts = [{'id': 'total', 'label': 'Total', 'definition': 'd', 'selectors': [{'projects': ['p'], 'names': ['total_pe_an'], 'source': URL}]}]
        base = Path(self.work.tmp.name)
        (self.work.taxonomy / 'inventar-concepte.json').write_text(json.dumps({'concepte': concepts, 'familii': []}))
        site = base / 'site'
        (site / 'inventar').mkdir(parents=True)
        for name in ('style.css', 'inventory.css', 'inventory.js'):
            (site / name).write_text('/* fixture */')
        item = {'slug': 'p', 'name': 'P', 'kind': 'proiect', 'status': 'activ', 'dataRelation': 'date-publice'}
        with patch('inventory_site.observation_paths', return_value={'profile': self.work.obs / 'profil.csv'}):
            projections = publish_preview([item], self.work.taxonomy / 'integrare', site)
        publish_finder([item], self.work.taxonomy / 'integrare', site, projections)
        fields, sources = projections['p']
        added = next(f for f in fields if f['name'] == 'total_pe_an')
        self.assertEqual((added['basis'], added['unit'], added['description'], added['declaredType']), ('editor', 'lei', 'Totalul pe an', 'number'))
        self.assertEqual([m['id'] for m in variable_matches('p', fields, sources, concepts)], ['total'], 'a selector reaches a field that an editor added')
        self.assertEqual(group_hits('p', fields, sources, concepts)[0][1][0][1]['names'], ['total_pe_an'])
        payload = (site / 'inventar/p.json').read_text()
        self.assertNotIn(FRAGMENT, payload)
        self.assertNotIn('dovada', payload, 'the evidence of an editor never reaches the explorer')
        page = (site / 'date/p/index.html').read_text()
        self.assertIn('adăugat de editor', page)
        self.assertNotIn(FRAGMENT, page)

    def test_the_check_verifies_each_fragment_and_names_what_it_cannot_read(self):
        self.run_with(self.rows({}))
        report = self.work.check()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['editor'], {'rows': 1, 'verified': 1, 'unavailable': 0})
        for path in (self.work.out / 'surse').iterdir():
            path.unlink()
        report = self.work.check()
        self.assertEqual(report['errors'], [], 'a body that is absent is not an error')
        self.assertEqual(report['editor'], {'rows': 1, 'verified': 0, 'unavailable': 1})
        self.assertTrue(any(FILE in u and 'editor field' in u for u in report['unavailable']))

    def test_the_check_finds_a_row_that_the_generated_records_do_not_follow(self):
        self.run_with(self.rows({}))
        (self.work.out / FILE).write_text(text_of(cells(descriere='Another description')), encoding='utf-8')
        errors = self.work.check()['errors']
        self.assertTrue(any('differ from campuri-editor.csv; run inventory.py --offline' in e for e in errors), errors)
        (self.work.out / FILE).write_text(text_of(), encoding='utf-8')
        self.assertTrue(any('differ from campuri-editor.csv' in e for e in self.work.check()['errors']), 'a record whose row was removed')
        (self.work.out / FILE).write_text(text_of(cells(), cells(nume='b', cale='$.b', fragment='este in lei')), encoding='utf-8')
        self.assertTrue(any('differ from campuri-editor.csv' in e for e in self.work.check()['errors']), 'a row that the records lack')

    def test_the_check_finds_a_fragment_that_the_body_no_longer_holds_and_a_hash_that_changed(self):
        self.run_with(self.rows({}))
        (self.work.out / FILE).write_text(text_of(cells(fragment='gone from the body')), encoding='utf-8')
        errors = self.work.check()['errors']
        self.assertTrue(any('the fragment is not in the retained text' in e for e in errors), errors)
        (self.work.out / FILE).write_text(text_of(cells()), encoding='utf-8')
        state = json.loads((self.work.out / 'seturi-date.json').read_text())
        added = next(f for s in state['surse'] for f in s['campuri'] if f['stare_tip'] == STATE)
        added['dovada_editor']['sha256'] = '0' * 64
        (self.work.out / 'seturi-date.json').write_text(json.dumps(state))
        errors = self.work.check()['errors']
        self.assertTrue(any('changed since the hash was recorded' in e for e in errors), errors)
        added['dovada_editor']['sha256'] = None
        (self.work.out / 'seturi-date.json').write_text(json.dumps(state))
        self.assertTrue(any('no hash of the retained text is recorded' in e for e in self.work.check()['errors']), 'a hash that was never recorded, with the text at hand')

    def test_the_check_of_the_readers_is_not_disturbed_by_an_added_field(self):
        self.run_with(self.rows({}))
        self.assertEqual(self.work.check()['errors'], [], 'the fields of the readers are compared with the body without the field of the editor')
        self.assertEqual(self.work.check()['verified'], 1)

    def test_the_check_reads_a_file_with_a_wrong_row(self):
        (self.work.out / FILE).write_text(text_of(cells(rol='nu-exista')), encoding='utf-8')
        self.assertTrue(any('rol is unknown' in e for e in self.work.check()['errors']))
        (self.work.out / FILE).write_text(text_of(cells(slug='other')), encoding='utf-8')
        self.assertTrue(any('is not a source of other' in e for e in self.work.check()['errors']))

    def test_a_retired_source_cannot_keep_a_row(self):
        self.run_with(self.rows({}))
        with self.assertRaises(StateError) as caught:
            self.work.run(self.entries, self.docs, None, offline=True, editor_rows=read_file(self.work.out / FILE)[0], retire_sources=[('p', URL, 'not needed')])
        self.assertIn('is not a source of p', str(caught.exception))


class Persons(unittest.TestCase):
    def setUp(self):
        self.work = Tree(self)
        self.entries, self.docs = self.work.entries(), self.work.docs()
        self.work.run(self.entries, self.docs, Net({PEOPLE: PEOPLE_BODY}), add_sources=[('p', spec(persoane=True))])

    def row(self, **given):
        return cells(**{'url_sursa': PEOPLE, 'nume': 'badge_nr', 'cale': '$.people[].badge', 'rol': 'camp-date', 'fragment': '"role": "Administrator"', **given})

    def write(self, *rows):
        path = self.work.out / FILE
        path.write_text(text_of(*rows), encoding='utf-8')
        return read_file(path)[0]

    def test_a_row_of_a_source_with_persons_joins_the_record_with_its_own_keys(self):
        self.work.run(self.entries, self.docs, None, offline=True, editor_rows=self.write(self.row()))
        source = self.work.sources()[PEOPLE]
        self.assertTrue(source['persoane'])
        self.assertEqual([f['nume'] for f in source['campuri'] if f['stare_tip'] == STATE], ['badge_nr'])
        self.assertEqual(problems(source), [])
        self.assertEqual(self.work.check()['errors'], [])
        self.assertNotIn('Ana Exemplu', '\n'.join(data.decode() for data in self.work.files().values()))

    def test_the_merge_refuses_a_value_of_a_person_in_any_text_cell(self):
        for column, value in (('descriere', 'Owner: Ana Exemplu'), ('nota', 'see ana.exemplu@example.org'), ('unitate', 'Strada Fictiva 12'), ('cale', '$.people["Ion Fictiv"]')):
            with self.subTest(column=column):
                with self.assertRaises(StateError) as caught:
                    self.work.run(self.entries, self.docs, None, offline=True, editor_rows=self.write(self.row(**{column: value})))
                self.assertIn('identifies a person', str(caught.exception))
                self.assertNotIn(value.split(': ')[-1], str(caught.exception))

    def test_the_file_is_in_the_scope_of_the_leak_check_and_the_check_finds_a_value_that_was_written_after_the_run(self):
        rows = self.write(self.row())
        self.assertIn(self.work.out / FILE, scope_files(self.work.taxonomy), 'the leak check looks into campuri-editor.csv')
        self.work.run(self.entries, self.docs, None, offline=True, editor_rows=rows)
        self.assertEqual(self.work.leaks(), [])
        self.write(self.row(nota='Ana Exemplu'))
        leaks = self.work.leaks()
        self.assertEqual(len(leaks), 1)
        self.assertIn(FILE, leaks[0])
        self.assertNotIn('Ana Exemplu', leaks[0])
        self.assertRegex(leaks[0], r'fingerprint [0-9a-f]{8}')


class CommandLine(unittest.TestCase):
    """The command reads the file before any work: a wrong row stops a run (exit 2, nothing written) and fails the check (exit 1). The tests copy the tracked
    state into a temporary folder (`--out`); they read no retained body and make no request."""

    def folder(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        tracked = ROOT / 'data/taxonomy-v2/observatii/inventare'
        for name in ('proiecte.json', 'seturi-date.json', 'descoperiri.json'):
            (out / name).write_bytes((tracked / name).read_bytes())
        (out / FILE).write_text(text, encoding='utf-8')
        return out

    def command(self, out, *options):
        import subprocess
        import sys
        return subprocess.run([sys.executable, str(ROOT / 'scripts/inventory.py'), '--out', str(out), *options], capture_output=True, text=True, cwd=ROOT)

    def test_a_wrong_row_stops_a_run_and_nothing_is_written(self):
        out = self.folder(text_of(cells(rol='nu-exista')))
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        result = self.command(out, '--offline')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('rol is unknown: nu-exista', result.stdout)
        self.assertIn('No inventory file was changed.', result.stdout)
        self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)

    def test_a_wrong_row_fails_the_check(self):
        result = self.command(self.folder(text_of(cells(rol='nu-exista'))), '--check')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f'ERROR: {FILE}:2: rol is unknown', result.stdout)

    def test_the_check_names_a_row_for_a_source_that_the_entry_does_not_own(self):
        result = self.command(self.folder(text_of(cells(slug='no-such-entry'))), '--check')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('is not a source of no-such-entry', result.stdout)

    def test_a_good_row_joins_its_source_in_a_run_and_the_check_says_what_it_could_not_read(self):
        # A real source of a real entry. This folder holds no retained body, so the run keeps the field without a hash (a warning) and the check says "not verified".
        url = 'https://aerlive.ro/wp-json/api/v1/cities/'
        out = self.folder(text_of(cells(slug='aerlive', url_sursa=url, nume='aqi_extra', cale='$.data[].aqi_extra', fragment='"gps"')))
        result = self.command(out, '--offline')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'WARNING: {FILE}:2: no retained text of {url}', result.stdout)
        source = next(x for x in json.loads((out / 'seturi-date.json').read_text())['surse'] if x['url'] == url)
        added = [f for f in source['campuri'] if f['stare_tip'] == STATE]
        self.assertEqual([(f['nume'], f['dovada_editor']) for f in added], [('aqi_extra', {'sha256': None, 'text': None})])
        self.assertIn(f'{FILE}:2,{STATE}', (out / 'campuri.csv').read_text())
        checked = self.command(out, '--check')
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn(f'1 fields added by an editor ({FILE}): 0 fragments found with the recorded hash, 1 in local bodies that are unavailable and not verified', checked.stdout)

    def test_the_file_with_its_header_only_adds_no_line_to_the_check(self):
        result = self.command(self.folder(text_of()), '--check')
        self.assertNotIn(FILE, result.stdout)
        self.assertNotIn('fields added by an editor', result.stdout)


class ValidateStep(unittest.TestCase):
    """`validate.py` reads the file with the generated profiles. CI has no retained bodies, so it checks the form and the owner of the source."""

    def run_check(self, text, profiles):
        found = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'taxonomy-v2' / 'integrare'
            inv = root.parent / 'observatii' / 'inventare'
            inv.mkdir(parents=True)
            (inv / FILE).write_text(text, encoding='utf-8')
            if profiles is not None:
                (inv / 'proiecte.json').write_text(json.dumps({'proiecte': profiles}))
            with patch('validate.observation_paths', return_value={'profile': root.parent / 'observatii' / 'profil.csv'}), \
                 patch('validate.report', side_effect=lambda level, path, line, msg: found.append((level, Path(path).name, line, msg))):
                validate.check_editor_fields(root)
        return found

    def test_a_good_row_of_an_owned_source_passes(self):
        self.assertEqual(self.run_check(text_of(cells()), [{'slug': 'p', 'surse_structurate': [source_id(URL)]}]), [])
        self.assertEqual(self.run_check(text_of(), []), [], 'the file with its header only')

    def test_each_wrong_row_is_an_error_on_its_own_line(self):
        found = self.run_check(text_of(cells(), cells(nume='b', cale='$.b', rol='nu-exista'), cells(nume='c', cale='$.c', tip_declarat='varchar(1)')),
                               [{'slug': 'p', 'surse_structurate': [source_id(URL)]}])
        self.assertEqual([(level, name, line) for level, name, line, _ in found], [('error', FILE, 3), ('error', FILE, 4)])
        self.assertIn('rol is unknown', found[0][3])
        self.assertIn('tip_declarat is unknown', found[1][3])

    def test_a_source_that_the_entry_does_not_own_is_an_error(self):
        found = self.run_check(text_of(cells()), [{'slug': 'p', 'surse_structurate': []}])
        self.assertEqual([(level, line) for level, _, line, _ in found], [('error', 2)])
        self.assertIn('is not a source of p', found[0][3])
        self.assertEqual(len(self.run_check(text_of(cells(slug='q')), [{'slug': 'p', 'surse_structurate': [source_id(URL)]}])), 1)

    def test_the_v2_checks_of_validate_include_the_file(self):
        with patch('taxonomy_v2.check', return_value=([], None)), patch('taxonomy_v2.Files'), patch.object(validate, 'check_mentiuni'), \
                patch('validate.observation_paths', return_value={'mentions': Path('/nonexistent/mentiuni.csv')}), \
                patch.object(validate, 'check_relation_fields'), patch.object(validate, 'check_editor_fields') as step:
            validate.check_v2(Path('/nonexistent/integrare'), publication=False)
        step.assert_called_once_with(Path('/nonexistent/integrare'))

    def test_the_columns_are_an_error_on_the_first_line(self):
        found = self.run_check(text_of(columns=COLUMNS[:-1]), [])
        self.assertEqual([(level, line) for level, _, line, _ in found], [('error', 1)])

    def test_a_root_without_profiles_checks_the_form_only(self):
        self.assertEqual(self.run_check(text_of(cells()), None), [])
        self.assertEqual(len(self.run_check(text_of(cells(rol='x')), None)), 1)


if __name__ == '__main__':
    unittest.main()
