"""Offline checks for incremental inventory collection: preservation, discovery registry, safe writes, request budget.

Every network call is a fake. The fixtures reproduce failure modes of the first inventory pass: a targeted run that
rebuilt unrelated projects from missing caches, a file limit that dropped earlier source memberships, and a failed
refresh that replaced good evidence.
"""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_docs
from inventory import (check_report, discover_candidates, render_outputs, update_inventory)
from inventory_state import (RequestLog, StateError, load_previous, new_discovery, retire, source_id, validate_state,
                             write_atomic)

RAW = 'https://raw.githubusercontent.com/org/repo/main/'


def entry(slug, url):
    return {'slug': slug, 'nume': slug, 'url': url, 'descriere_scurta': 'Purpose ' + slug, 'descriere': '',
            'capabilities': [], 'formats': []}


def docs_for(slug, url, links, text=''):
    page = {'state': 'colectat', 'scope': 'proiect', 'final_url': url, 'kind': 'pagina', 'sha256': 'page-' + slug,
            'snapshot': f'pagini/{slug}.json', 'fetched_at': '2026-01-01T00:00:00+00:00',
            'links': [[link, ''] for link in links], 'text': text, 'input_candidates': [{'name': 'q', 'type': 'search'}]}
    return {'slug': slug, 'url': url, 'state': 'documentatie-gasita', 'pages': [page]}


class Net:
    """A fake network: URL -> body. `fail` makes every request answer with an HTTP error."""

    def __init__(self, bodies):
        self.bodies, self.calls, self.fail = dict(bodies), [], None

    def __call__(self, url):
        self.calls.append(url)
        base = {'url': url, 'final_url': url, 'fetched_at': '2026-02-01T00:00:00+00:00'}
        if self.fail or url not in self.bodies:
            return {**base, 'http_status': self.fail or 404, 'state': 'eroare-http', 'error': 'HTTP Error'}
        return {**base, 'http_status': 200, 'content_type': 'text/csv' if url.endswith('.csv') else 'application/json',
                'state': 'ok', 'body': self.bodies[url]}


class Workspace:
    """A temporary inventory folder with the same run-and-write steps as the command line."""

    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'inventare'

    def run(self, entries, docs, net=None, **options):
        state = update_inventory(entries, docs, {}, load_previous(self.out), cache=self.out / 'surse', fetch=net,
                                 now='2026-03-01T00:00:00+00:00', **options)
        write_atomic(self.out, render_outputs(state))
        return state

    def files(self):
        return {p.name: p.read_bytes() for p in sorted(self.out.iterdir()) if p.is_file()}

    def profile(self, slug):
        return next(p for p in json.loads((self.out / 'proiecte.json').read_text())['proiecte'] if p['slug'] == slug)

    def sources(self):
        return {s['url']: s for s in json.loads((self.out / 'seturi-date.json').read_text())['surse']}

    def registry(self):
        return json.loads((self.out / 'descoperiri.json').read_text())['descoperiri']


class Preservation(unittest.TestCase):
    A, B = 'https://a.example/', 'https://b.example/'

    def setUp(self):
        self.entries = [entry('a', self.A), entry('b', self.B)]
        self.url_a, self.url_b = self.A + 'data.csv', self.B + 'data.csv'
        self.docs = {'a': docs_for('a', self.A, [self.url_a]), 'b': docs_for('b', self.B, [self.url_b])}
        self.bodies = {self.url_a: 'cui,value\n001,1\n', self.url_b: 'county,total,year\nAB,1,2020\n'}

    def test_targeted_run_keeps_unrelated_projects_without_caches_or_documentation(self):
        work = Workspace(self)
        work.run(self.entries, self.docs, Net(self.bodies))
        before_b, source_b = work.profile('b'), work.sources()[self.url_b]
        registry_b = [d for d in work.registry() if d['proiect'] == 'b']
        self.assertEqual(before_b['campuri_din_surse'], 3)
        # A fresh checkout: no cached bodies, no documentation snapshots for b.
        shutil.rmtree(work.out / 'surse')
        net = Net(self.bodies)
        work.run(self.entries, {'a': self.docs['a']}, net, selected={'a'})
        self.assertEqual(net.calls, [self.url_a])
        self.assertEqual(work.profile('b'), before_b)
        self.assertEqual(work.sources()[self.url_b], source_b)
        self.assertEqual([d for d in work.registry() if d['proiect'] == 'b'], registry_b)
        self.assertEqual(work.profile('a')['campuri_din_surse'], 2)

    def test_offline_run_with_missing_bodies_keeps_tracked_records_and_says_so(self):
        work = Workspace(self)
        work.run(self.entries, self.docs, Net(self.bodies))
        before = work.files()
        shutil.rmtree(work.out / 'surse')
        state = work.run(self.entries, self.docs, None, offline=True)
        self.assertEqual(sorted(state['report']['pastrate']), sorted(self.bodies))
        for name in ('proiecte.json', 'seturi-date.json', 'rezumat.csv', 'campuri.csv', 'descoperiri.json'):
            self.assertEqual(work.files()[name], before[name], name)

    def test_offline_run_without_tracked_state_invents_no_fields(self):
        work = Workspace(self)
        state = work.run(self.entries, self.docs, None, offline=True)
        self.assertEqual(work.profile('a')['campuri_din_surse'], 0)
        self.assertEqual(work.sources()[self.url_a]['state'], 'necolectat')
        self.assertEqual(state['report']['reimprospatate'], [])

    def test_smaller_budget_keeps_earlier_membership_and_discoveries(self):
        links = [f'{self.A}file{n}.csv' for n in range(5)]
        docs = {'a': docs_for('a', self.A, links)}
        bodies = {link: 'id\n1\n' for link in links}
        work = Workspace(self)
        work.run(self.entries[:1], docs, Net(bodies), max_files=5)
        self.assertEqual(len(work.profile('a')['surse_structurate']), 5)
        work.run(self.entries[:1], docs, Net(bodies), max_files=3)
        self.assertEqual(len(work.profile('a')['surse_structurate']), 5)
        work.run(self.entries[:1], {}, Net({}), max_files=1)
        self.assertEqual(len(work.profile('a')['surse_structurate']), 5)
        self.assertEqual({d['stare'] for d in work.registry()}, {'activ'})

    def test_default_limit_admits_three_and_records_the_rest_as_discovered(self):
        links = [f'{self.A}file{n}.csv' for n in range(5)]
        docs = {'a': docs_for('a', self.A, links)}
        bodies = {link: 'id\n1\n' for link in links}
        work = Workspace(self)
        work.run(self.entries[:1], docs, Net(bodies))
        self.assertEqual(len(work.profile('a')['surse_structurate']), 3)
        self.assertEqual(sorted(d['stare'] for d in work.registry()), ['activ'] * 3 + ['descoperit'] * 2)
        net = Net(bodies)
        work.run(self.entries[:1], docs, net, max_files=5)
        self.assertEqual(len(work.profile('a')['surse_structurate']), 5)
        self.assertEqual(len(net.calls), 2, 'only the newly admitted sources are fetched')

    def test_unselected_project_is_not_rediscovered_or_admitted(self):
        work = Workspace(self)
        work.run(self.entries, {'a': self.docs['a']}, Net(self.bodies))
        self.assertEqual(work.profile('b')['surse_structurate'], [])
        # b now has documentation, but a targeted run on a must leave b alone.
        work.run(self.entries, self.docs, Net(self.bodies), selected={'a'})
        self.assertEqual(work.profile('b')['surse_structurate'], [])
        work.run(self.entries, self.docs, Net(self.bodies), selected={'b'})
        self.assertEqual(len(work.profile('b')['surse_structurate']), 1)


class ExplicitChanges(unittest.TestCase):
    def test_a_project_named_by_an_addition_is_updated_in_a_targeted_run(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/'), entry('b', 'https://b.example/')]
        url = RAW + 'abc/schema.json'
        net = Net({url: '{"id": 1}'})
        work.run(entries, {}, net, selected={'a'}, add_sources=[('b', {'url': url, 'metoda': 'repo-la-revizie'})])
        self.assertEqual(net.calls, [url])
        self.assertEqual(work.profile('b')['surse_structurate'], [source_id(url)])
        self.assertEqual(work.profile('a')['surse_structurate'], [])

    def test_force_url_refreshes_one_source_and_leaves_the_others_cached(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/one.csv', 'https://a.example/two.csv'])}
        bodies = {'https://a.example/one.csv': 'x\n1\n', 'https://a.example/two.csv': 'y\n1\n'}
        work.run(entries, docs, Net(bodies))
        net = Net(bodies)
        work.run(entries, docs, net, selected={'a'}, force_urls=['https://a.example/two.csv'])
        self.assertEqual(net.calls, ['https://a.example/two.csv'])

    def test_explicit_locator_must_exist_in_the_collected_page(self):
        from inventory import resolve_spec
        docs = {'a': docs_for('a', 'https://a.example/', [], 'GET /api/datasets?q={text}')}
        spec = resolve_spec(docs, 'a', {'url': 'https://a.example/api', 'locate': {'pagina': 'https://a.example/', 'text': 'GET /api/datasets'},
                                        'dovezi': [{'pagina': 'https://a.example/', 'text': 'q={text}', 'rol': 'parametru'}]})
        start, end = spec['dovada']['interval']
        self.assertEqual('GET /api/datasets?q={text}'[start:end], 'GET /api/datasets')
        self.assertEqual(spec['dovezi_suplimentare'][0]['rol'], 'parametru')
        with self.assertRaises(StateError):
            resolve_spec(docs, 'a', {'url': 'https://a.example/api', 'locate': {'pagina': 'https://a.example/', 'text': 'absent'}})


class ScopeOfTheSelection(unittest.TestCase):
    """A default run leaves out the entries that are out of the variable inventory (`skip`); a named project always runs. The records of a skipped entry stay as they are."""
    A, B = 'https://a.example/', 'https://b.example/'

    def setUp(self):
        self.entries = [entry('a', self.A), entry('b', self.B)]
        self.url_a, self.url_b = self.A + 'data.csv', self.B + 'data.csv'
        self.docs = {'a': docs_for('a', self.A, [self.url_a]), 'b': docs_for('b', self.B, [self.url_b])}
        self.bodies = {self.url_a: 'cui,value\n001,1\n', self.url_b: 'county,total,year\nAB,1,2020\n'}

    def first_run(self):
        work = Workspace(self)
        work.run(self.entries, {'a': self.docs['a']}, Net(self.bodies))  # b has no documentation yet: no source, no field
        self.assertEqual(work.profile('b')['campuri_din_surse'], 0)
        return work

    def test_a_default_run_does_not_refresh_or_rediscover_a_skipped_project(self):
        work = self.first_run()
        before = work.profile('b'), [d for d in work.registry() if d['proiect'] == 'b']
        net = Net(self.bodies)
        work.run(self.entries, self.docs, net, skip={'b'})
        self.assertEqual(net.calls, [], 'a is cached and unchanged, and b is skipped: no request')
        self.assertEqual((work.profile('b'), [d for d in work.registry() if d['proiect'] == 'b']), before)
        work.run(self.entries, self.docs, net, skip={'b'}, force=True)
        self.assertEqual(net.calls, [self.url_a], 'a default run with force refreshes the in-scope project only')
        self.assertEqual(work.profile('b'), before[0])

    def test_without_skip_the_same_run_changes_the_project(self):
        work = self.first_run()
        work.run(self.entries, self.docs, Net(self.bodies))
        self.assertEqual(len(work.profile('b')['surse_structurate']), 1, 'the control: the old default selection reached every project')

    def test_a_named_project_runs_although_it_is_in_skip(self):
        work = self.first_run()
        work.run(self.entries, self.docs, Net(self.bodies), selected={'b'}, skip={'b'})
        self.assertEqual(len(work.profile('b')['surse_structurate']), 1)

    def test_an_explicit_addition_changes_a_skipped_project_in_a_default_run(self):
        work = self.first_run()
        net = Net(self.bodies)
        work.run(self.entries, self.docs, net, skip={'b'}, add_sources=[('b', {'url': self.url_b, 'metoda': 'adaugat-explicit'})])
        self.assertEqual(work.profile('b')['surse_structurate'], [source_id(self.url_b)])
        self.assertEqual(net.calls, [self.url_b])

    def test_a_new_entry_gets_its_record_although_it_is_in_skip(self):
        work = Workspace(self)
        work.run(self.entries[:1], {'a': self.docs['a']}, Net(self.bodies))
        work.run(self.entries, self.docs, Net(self.bodies), skip={'b'})
        self.assertEqual(work.profile('b')['slug'], 'b', 'every catalogue entry has a record, the skipped ones included')

    def test_an_empty_selection_of_skipped_entries_does_not_widen_to_every_project(self):
        work = self.first_run()
        before = work.profile('b')
        work.run(self.entries, self.docs, Net(self.bodies), skip={'a', 'b'})
        self.assertEqual(work.profile('b'), before, 'when every entry is skipped, the run changes nothing; it does not fall back to all')


class ScopeInTheCommand(unittest.TestCase):
    """`inventory.py` without `--only` passes the entries that are out of scope as `skip`; with `--only` it passes none and prints a note."""

    ENTRIES = [{'slug': slug, 'nume': slug, 'url': f'https://{slug}.example/', 'kind': 'proiect'} for slug in ('in-scope', 'no-data', 'archived')]
    SCOPE = {'in-scope': '', 'no-data': 'fara-date', 'archived': 'inactiv'}

    def run_main(self, *argv):
        import io
        import sys
        import contextlib
        import inventory
        calls = []

        def fake_update(entries, docs, verified, previous, **options):
            calls.append(options)
            return {'profiles': [], 'sources': [], 'registry': {}, 'report': {k: [] for k in ('reimprospatate', 'esuate', 'pastrate', 'neinspectate', 'interzise', 'avertismente')}}

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as output, \
                patch.object(sys, 'argv', ['inventory.py', '--offline', '--dry-run', '--out', str(Path(tmp) / 'inventare'), *argv]), \
                patch.object(inventory, 'data_schema', return_value='v2'), patch.object(inventory, 'observation_paths', return_value={'profile': Path(tmp) / 'profil.csv'}), \
                patch.object(inventory, 'load_catalogue', return_value=self.ENTRIES), patch.object(inventory, 'inventory_scope', return_value=self.SCOPE), \
                patch.object(inventory, 'restore', return_value={}), patch.object(inventory, 'load_vocabulary', return_value={'concepts': {}}), \
                patch.object(inventory, 'update_inventory', fake_update):
            code = inventory.main()
        return code, calls, output.getvalue()

    def test_a_default_run_skips_the_entries_out_of_scope_and_says_how_many(self):
        code, calls, output = self.run_main()
        self.assertEqual((code, len(calls)), (0, 1))
        self.assertEqual((calls[0]['selected'], calls[0]['skip']), (set(), {'no-data', 'archived'}))
        self.assertIn('2 entries out of the variable inventory were not refreshed (inactiv 1, fara-date 1)', output)

    def test_only_runs_an_out_of_scope_entry_and_prints_a_note(self):
        code, calls, output = self.run_main('--only', 'archived,in-scope')
        self.assertEqual((calls[0]['selected'], calls[0]['skip']), ({'archived', 'in-scope'}, set()))
        self.assertIn('NOTE: archived is out of the variable inventory (inactiv); --only runs it anyway.', output)
        self.assertNotIn('NOTE: in-scope', output)
        self.assertNotIn('were not refreshed', output)


class SharedSources(unittest.TestCase):
    def setUp(self):
        self.url = RAW + 'shared.csv'
        self.entries = [entry('a', 'https://a.example/'), entry('b', 'https://b.example/')]
        self.docs = {'a': docs_for('a', 'https://a.example/', [self.url]), 'b': docs_for('b', 'https://b.example/', [self.url])}
        self.work = Workspace(self)
        self.work.run(self.entries, self.docs, Net({self.url: 'x,y\n1,2\n'}))

    def test_failed_refresh_of_one_project_leaves_the_other_with_usable_evidence(self):
        net = Net({})
        net.fail = 503
        state = self.work.run(self.entries, self.docs, net, selected={'a'}, force=True)
        source = self.work.sources()[self.url]
        self.assertEqual(len(source['campuri']), 2)
        self.assertEqual(source['stare'], 'analizat')
        self.assertEqual(source['ultima_incercare']['http_status'], 503)
        self.assertEqual(state['report']['esuate'], [self.url])
        self.assertEqual(self.work.profile('b')['campuri_din_surse'], 2)
        self.assertEqual(self.work.profile('b')['surse_structurate'], [source['id']])
        cached = json.loads((self.work.out / 'surse' / (source['id'] + '.json')).read_text())
        self.assertEqual(cached['state'], 'ok', 'a failed response never replaces a good cached body')

    def test_failure_is_remembered_until_a_fresh_success(self):
        net = Net({})
        net.fail = 500
        self.work.run(self.entries, self.docs, net, selected={'a'}, force=True)
        self.work.run(self.entries, self.docs, None, offline=True)
        self.assertIn('ultima_incercare', self.work.sources()[self.url])
        self.work.run(self.entries, self.docs, Net({self.url: 'x,y\n1,2\n'}), selected={'a'}, force=True)
        self.assertNotIn('ultima_incercare', self.work.sources()[self.url])

    def test_changed_body_keeps_the_previous_version_for_both_projects(self):
        old = self.work.sources()[self.url]
        self.work.run(self.entries, self.docs, Net({self.url: 'x,y,z\n1,2,3\n'}), selected={'b'}, force=True)
        source = self.work.sources()[self.url]
        self.assertEqual(len(source['campuri']), 3)
        self.assertEqual(source['versiuni_anterioare'][0]['sha256'], old['sha256'])
        self.assertTrue((self.work.out / old['snapshot']).exists())
        self.assertEqual(self.work.profile('a')['campuri_din_surse'], 3)
        self.assertEqual(self.work.profile('b')['campuri_din_surse'], 3)

    def test_unparsable_refresh_keeps_the_last_parsed_evidence(self):
        self.work.run(self.entries, self.docs, Net({self.url: '<html><body>Moved</body></html>'}), selected={'a'}, force=True)
        source = self.work.sources()[self.url]
        self.assertEqual(len(source['campuri']), 2)
        self.assertEqual(source['ultima_incercare']['stare'], 'ok')

    def test_a_source_used_by_two_projects_is_one_record_with_two_memberships(self):
        self.assertEqual(len(self.work.sources()), 1)
        self.assertEqual({d['proiect'] for d in self.work.registry() if d['stare'] == 'activ'}, {'a', 'b'})
        owners = [r for r in (self.work.out / 'campuri.csv').read_text().splitlines()[1:]]
        self.assertTrue(all(row.startswith('a|b,') for row in owners))


class SafeWrites(unittest.TestCase):
    def test_corrupt_proposed_output_leaves_every_tracked_file_unchanged(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv'])}
        work.run(entries, docs, Net({'https://a.example/d.csv': 'q\n1\n'}))
        before = work.files()
        texts = render_outputs(update_inventory(entries, docs, {}, load_previous(work.out), cache=work.out / 'surse', offline=True))
        texts['seturi-date.json'] = texts['seturi-date.json'][:-40]
        with self.assertRaises(StateError):
            write_atomic(work.out, texts)
        self.assertEqual(work.files(), before)
        texts = render_outputs(update_inventory(entries, docs, {}, load_previous(work.out), cache=work.out / 'surse', offline=True))
        texts['campuri.csv'] += 'ragged,row\n'
        with self.assertRaises(StateError):
            write_atomic(work.out, texts)
        self.assertEqual(work.files(), before)
        self.assertEqual([p.name for p in work.out.iterdir() if '.tmp' in p.name], [])

    def test_failed_replacement_leaves_no_temporary_files(self):
        work = Workspace(self)
        work.out.mkdir()
        with patch('inventory_state.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                write_atomic(work.out, {'a.json': '{}', 'b.json': '{}'})
        self.assertEqual(list(work.out.iterdir()), [])

    def test_unreadable_tracked_state_stops_before_any_write(self):
        work = Workspace(self)
        work.out.mkdir()
        (work.out / 'proiecte.json').write_text('{broken')
        with self.assertRaises(StateError):
            load_previous(work.out)

    def test_invalid_proposed_state_is_rejected(self):
        source = {'id': source_id('https://a.example/d.csv'), 'url': 'https://a.example/d.csv', 'stare': 'analizat', 'sha256': 'x', 'campuri': [1]}
        profile = {'slug': 'a', 'surse_structurate': [source['id'], 'missing-id']}
        registry = {('a', source['url']): new_discovery('a', source['url'], 'adaugat-explicit', state='activ')}
        errors = validate_state([profile], [source], registry)
        self.assertTrue(any('Unknown source reference' in e for e in errors))
        self.assertTrue(any('differ from the registry' in e for e in errors))
        previous = {'sources': {source['id']: source}}
        lost = validate_state([{'slug': 'a', 'surse_structurate': [source['id']]}], [{**source, 'stare': 'eroare-parsare'}], registry, previous)
        self.assertTrue(any('evidence would be lost' in e for e in lost))

    def test_replay_from_identical_caches_is_deterministic(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/'), entry('b', 'https://b.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv']),
                'b': docs_for('b', 'https://b.example/', [RAW + 'x.json'])}
        net = Net({'https://a.example/d.csv': 'q\n1\n', RAW + 'x.json': '[{"id": "007"}]'})
        work.run(entries, docs, net)
        first = work.files()
        work.run(entries, docs, None, offline=True)
        self.assertEqual(work.files(), first)
        work.run(entries, docs, None, offline=True, selected={'a'})
        self.assertEqual(work.files(), first)
        # A rebuild from nothing but the caches reproduces the same sources and profiles.
        again = Workspace(self)
        shutil.copytree(work.out / 'surse', again.out / 'surse')
        again.run(entries, docs, None, offline=True)
        for name in ('proiecte.json', 'seturi-date.json', 'campuri.csv', 'rezumat.csv'):
            self.assertEqual(again.files()[name], first[name], name)


class Registry(unittest.TestCase):
    def test_seeded_membership_without_documentation_has_an_unknown_locator(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv'])}
        work.run(entries, docs, Net({'https://a.example/d.csv': 'q\n1\n'}))
        (work.out / 'descoperiri.json').unlink()
        work.run(entries, {}, None, offline=True)
        record = work.registry()[0]
        self.assertEqual((record['metoda'], record['locator_stare'], record['dovada'], record['parinte'], record['descoperit_la']),
                         ('membru-anterior', 'necunoscut', None, None, None))
        self.assertEqual(record['stare'], 'activ')
        self.assertEqual(work.profile('a')['campuri_din_surse'], 1)
        # Later documentation completes the locator without inventing one in the meantime.
        work.run(entries, docs, None, offline=True)
        record = work.registry()[0]
        self.assertEqual(record['locator_stare'], 'cunoscut')
        self.assertEqual(record['dovada']['pointer'], '/links/0')
        self.assertEqual(record['istoric'][-1]['eveniment'], 'locator-completat')

    def test_seeding_recovers_the_original_locator_when_documentation_exists(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv'])}
        work.run(entries, docs, Net({'https://a.example/d.csv': 'q\n1\n'}))
        strip = lambda records: [{k: v for k, v in r.items() if k != 'istoric'} for r in records]
        before = strip(work.registry())
        (work.out / 'descoperiri.json').unlink()
        work.run(entries, docs, None, offline=True)
        self.assertEqual(strip(work.registry()), before)

    def test_text_discovery_records_an_exact_interval_and_the_page_hash(self):
        link = 'https://a.example/data/rows.json'
        text = 'Download the rows at ' + link + '. More text.'
        found = discover_candidates(entry('a', 'https://a.example/'), docs_for('a', 'https://a.example/', [], text))
        evidence = found[0]['dovada']
        start, end = evidence['interval']
        self.assertEqual(found[0]['metoda'], 'url-in-text')
        self.assertEqual(text[start:end], link)
        self.assertEqual((evidence['sha256'], evidence['pointer']), ('page-a', '/text'))
        self.assertEqual(found[0]['parinte'], 'https://a.example/')

    def test_discovery_respects_project_scope_and_shared_hosts(self):
        shared = entry('x', 'https://example.org/x/')
        links = ['https://example.org/x/data.json', 'https://example.org/y/data.json', 'https://example.org/data.json',
                 'https://other.example/data.json', RAW + 'file.json', 'https://example.org/x/{id}.json']
        found = discover_candidates(shared, docs_for('x', 'https://example.org/x/', links))
        self.assertEqual(sorted(c['url'] for c in found), ['https://example.org/x/data.json', RAW + 'file.json'])

    def test_retirement_needs_a_reason_and_keeps_the_record(self):
        record = new_discovery('a', 'https://a.example/d.csv', 'adaugat-explicit', state='activ')
        registry = {('a', record['url']): record}
        with self.assertRaises(StateError):
            retire(registry, 'a', record['url'], '  ', 'now')
        retire(registry, 'a', record['url'], 'The file was replaced by d2.csv.', '2026-03-01')
        self.assertEqual(record['stare'], 'retras')
        self.assertEqual(record['istoric'][-1]['motiv'], 'The file was replaced by d2.csv.')

    def test_retired_source_keeps_its_evidence_and_leaves_the_profile(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv'])}
        net = Net({'https://a.example/d.csv': 'q\n1\n'})
        work.run(entries, docs, net)
        work.run(entries, docs, None, offline=True, retire_sources=[('a', 'https://a.example/d.csv', 'Superseded.')])
        self.assertEqual(work.profile('a')['surse_structurate'], [])
        self.assertEqual(len(work.sources()['https://a.example/d.csv']['campuri']), 1)
        self.assertEqual(work.registry()[0]['retras']['motiv'], 'Superseded.')
        work.run(entries, docs, None, offline=True)
        self.assertEqual(work.registry()[0]['stare'], 'retras', 'discovery never reactivates a retired source')

    def test_temporary_http_errors_never_retire_a_source(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv'])}
        work.run(entries, docs, Net({'https://a.example/d.csv': 'q\n1\n'}))
        for status in (401, 404, 503):
            net = Net({})
            net.fail = status
            work.run(entries, docs, net, force=True)
        self.assertEqual(work.registry()[0]['stare'], 'activ')
        self.assertEqual(work.profile('a')['campuri_din_surse'], 1)

    def test_explicit_addition_records_method_parent_and_note(self):
        work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        spec = {'url': RAW + 'abc123/schema.json', 'metoda': 'repo-la-revizie', 'parinte': 'https://github.com/org/repo', 'nota': 'revision abc123'}
        work.run(entries, {}, Net({RAW + 'abc123/schema.json': '{"a": 1}'}), add_sources=[('a', spec)])
        record = work.registry()[0]
        self.assertEqual((record['metoda'], record['parinte'], record['nota'], record['stare']),
                         ('repo-la-revizie', 'https://github.com/org/repo', 'revision abc123', 'activ'))
        self.assertEqual(record['locator_stare'], 'necunoscut')


class EvidenceCheck(unittest.TestCase):
    def setUp(self):
        self.work = Workspace(self)
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv'])}
        self.work.run(entries, docs, Net({'https://a.example/d.csv': 'q\n1\n'}))
        self.obs = self.work.out.parent

    def test_absent_bodies_are_reported_apart_from_corruption(self):
        report = check_report(self.work.out, self.obs)
        self.assertEqual((report['errors'], report['verified']), ([], 1))
        source = next(iter(self.work.sources().values()))
        (self.work.out / source['snapshot']).unlink()
        report = check_report(self.work.out, self.obs)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['verified'], 0)
        self.assertEqual([u for u in report['unavailable'] if u.startswith('http')], [source['url']])

    def test_changed_body_is_corruption_not_absence(self):
        source = next(iter(self.work.sources().values()))
        path = self.work.out / source['snapshot']
        stored = json.loads(path.read_text())
        stored['body'] = 'q\n2\nextra\n'
        path.write_text(json.dumps(stored))
        report = check_report(self.work.out, self.obs)
        self.assertTrue(any('hash mismatch' in e for e in report['errors']))
        self.assertEqual([u for u in report['unavailable'] if u.startswith('http')], [])

    def test_registry_and_profile_must_agree(self):
        profiles = json.loads((self.work.out / 'proiecte.json').read_text())
        profiles['proiecte'][0]['surse_structurate'] = []
        (self.work.out / 'proiecte.json').write_text(json.dumps(profiles))
        self.assertTrue(any('differ from the registry' in e for e in check_report(self.work.out, self.obs)['errors']))

    def test_failed_refresh_is_listed_as_stale(self):
        net = Net({})
        net.fail = 503
        entries = [entry('a', 'https://a.example/')]
        docs = {'a': docs_for('a', 'https://a.example/', ['https://a.example/d.csv'])}
        self.work.run(entries, docs, net, force=True)
        self.assertEqual(check_report(self.work.out, self.obs)['stale'], ['https://a.example/d.csv'])


class LocatorCheck(unittest.TestCase):
    URL = 'https://a.example/data/rows.json'

    def setUp(self):
        import hashlib
        self.work = Workspace(self)
        self.obs = self.work.out.parent
        self.text = 'Download the rows at ' + self.URL + '. More.'
        page = docs_for('a', 'https://a.example/', [self.URL], self.text)['pages'][0]
        page['sha256'] = hashlib.sha256(self.text.encode()).hexdigest()
        self.snapshot = self.obs / 'documentare' / 'pagini' / 'a.json'
        self.snapshot.parent.mkdir(parents=True)
        self.snapshot.write_text(json.dumps({'text': self.text, 'links': page['links'], 'input_candidates': page['input_candidates']}))
        self.docs = {'a': {'slug': 'a', 'state': 'documentatie-gasita', 'pages': [page]}}
        self.entries = [entry('a', 'https://a.example/')]
        self.work.run(self.entries, self.docs, Net({self.URL: '{"id": "007"}'}))

    def errors(self):
        return check_report(self.work.out, self.obs)['errors']

    def test_untouched_locators_verify(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(check_report(self.work.out, self.obs)['unavailable'], [])

    def test_changed_page_text_is_a_hash_error(self):
        self.snapshot.write_text(json.dumps({'text': self.text + ' edited', 'links': [], 'input_candidates': [{'name': 'q', 'type': 'search'}]}))
        self.assertTrue(any('page hash differs' in e for e in self.errors()))

    def test_wrong_interval_and_wrong_link_pointer_are_errors(self):
        registry = json.loads((self.work.out / 'descoperiri.json').read_text())
        record = registry['descoperiri'][0]
        self.assertEqual(record['dovada']['pointer'], '/links/0')
        record['dovada']['pointer'] = '/links/5'
        (self.work.out / 'descoperiri.json').write_text(json.dumps(registry))
        self.assertTrue(any('invalid link pointer' in e for e in self.errors()))
        record['dovada'].update(pointer='/text', interval=[0, 8])
        (self.work.out / 'descoperiri.json').write_text(json.dumps(registry))
        self.assertTrue(any('interval does not hold' in e for e in self.errors()))

    def test_absent_documentation_snapshot_is_unavailable_not_an_error(self):
        self.snapshot.unlink()
        report = check_report(self.work.out, self.obs)
        self.assertEqual(report['errors'], [])
        self.assertTrue(any(u.startswith('discovery:') for u in report['unavailable']))


class BrowserHelper(unittest.TestCase):
    def test_only_same_site_data_requests_survive_and_credentials_are_redacted(self):
        from render_pages import keep_request, redact, summarise
        events = [
            {'url': 'https://app.example.org/api/data.json?year=2024&api_key=abc123', 'method': 'GET', 'resource_type': 'fetch', 'status': 200,
             'content_type': 'application/json', 'size': 120},
            {'url': 'https://app.example.org/api/data.json?year=2024&api_key=zzz', 'method': 'GET', 'resource_type': 'fetch', 'status': 200},
            {'url': 'https://www.google-analytics.com/collect', 'method': 'POST', 'resource_type': 'xhr', 'status': 204},
            {'url': 'https://example.org/static/app.js', 'method': 'GET', 'resource_type': 'script', 'status': 200},
            {'url': 'https://api.example.org/v1/stations', 'method': 'GET', 'resource_type': 'xhr', 'status': 200, 'content_type': 'application/json'},
        ]
        kept = summarise(events, 'app.example.org')
        self.assertEqual([k['url'] for k in kept], ['https://app.example.org/api/data.json?year=2024&api_key=REDACTED'])
        self.assertEqual(len(summarise(events, 'example.org')), 2)
        self.assertEqual(len(summarise(events, 'app.example.org', ['api.example.org'])), 2)
        self.assertFalse(keep_request(events[2], 'app.example.org'))
        self.assertEqual(redact('https://a.example/x?token=1&page=2#frag'), 'https://a.example/x?token=REDACTED&page=2')

    def test_browser_rows_never_count_against_the_direct_request_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = RequestLog(Path(tmp) / 'c.csv', 'C')
            log.add('GET', 'https://a.example/x.json', 'ok', 200, 10)
            log.add('BROWSER', 'https://a.example/', 'ok', 200, None, 'browser', 'randare a')
            log.add('BROWSER-GET', 'https://a.example/api', '200', 200, 5, 'browser', 'randare a')
            self.assertEqual(log.direct_requests(), 1)
            self.assertEqual(log.browser_counts(), (1, 1))


class FakeResponse:
    def __init__(self, raw, content_type='text/csv'):
        self.raw, self.status, self.url = raw, 200, 'https://a.example/x'
        self.headers = self
        self.type = content_type

    def get_content_type(self):
        return self.type

    def get_content_charset(self):
        return None

    def read(self, limit):
        return self.raw[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RequestBudget(unittest.TestCase):
    def test_budget_stops_requests_and_the_log_records_each_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = RequestLog(Path(tmp) / 'cereri.csv', 'lot-x')
            fetcher = collect_docs.Fetcher(max_requests=2, log=log, purpose='test')
            with patch('collect_docs.urlopen', side_effect=lambda *a, **k: FakeResponse(b'a,b\n1,2\n')):
                results = [fetcher(f'https://a.example/{n}.csv') for n in range(3)]
                fetcher('https://a.example/0.csv')
            self.assertEqual([r['state'] for r in results], ['ok', 'ok', 'limita-cereri'])
            self.assertEqual(fetcher.requests, 2)
            rows = log.rows()
            self.assertEqual([(r['metoda'], r['stare'], r['octeti'], r['cache']) for r in rows],
                             [('GET', 'ok', '8', 'nu'), ('GET', 'ok', '8', 'nu'), ('GET', 'ok', '', 'da')])
            self.assertEqual(log.direct_requests(), 2)
            self.assertEqual(RequestLog(Path(tmp) / 'cereri.csv', 'other').direct_requests(), 0)
            self.assertNotIn('User-Agent', (Path(tmp) / 'cereri.csv').read_text())

    def test_binary_bodies_are_not_decoded_as_text(self):
        with patch('collect_docs.urlopen', side_effect=lambda *a, **k: FakeResponse(b'PK\x03\x04binary', 'application/zip')):
            result = collect_docs.Fetcher()('https://a.example/book.xlsx')
        self.assertEqual((result['state'], result['body']), ('format-binar', ''))
        self.assertTrue(collect_docs.is_binary(b'%PDF-1.7 ...'))
        self.assertTrue(collect_docs.is_binary(b'name\x00value'))
        self.assertFalse(collect_docs.is_binary('CUI;județ\n001;AB\n'.encode()))


if __name__ == '__main__':
    unittest.main()
