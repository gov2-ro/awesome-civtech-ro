"""Offline checks of the local review interface (scripts/review_ui.py). Every test runs on a temporary copy of the data root,
which is a git repository of its own (the baseline of a reset). The real data root is never written; tearDownModule proves it.
"""
import atexit
import copy
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import common
import inventory_report
import review_ui
from inventory_concepts import (CANDIDATES, candidate_blockers, candidate_key, candidate_signature, check_concepts, repeated_exclusions, selector_matches,
                                validate_candidates, validate_concept, validate_group_state, validate_selector)
from inventory_site import publish_finder, variable_matches
from review_ui import ReviewError, Store

REAL = common.PUBLIC_ROOT.parent
REAL_FILES = [common.PUBLIC_ROOT / 'revizuire.csv', common.PUBLIC_ROOT / 'relatii.csv', REAL / 'inventar-concepte.json', REAL / 'inventar-note.json']
# The review files of the fixture come from a commit where no item and no group was decided (31 provider items, 30 groups).
# The real files change with every editorial decision; the tests must not depend on that progress.
PINNED = 'v0.23.0'
TODAY = '2026-10-25'
GIT_ENV = {**os.environ, 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_SYSTEM': '/dev/null'}
TEMPLATE = None
REAL_BEFORE = None


def git(cwd, *args):
    done = subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test@example.org', '-c', 'commit.gpgsign=false',
                           '-c', 'core.hooksPath=/dev/null', *args], cwd=cwd, capture_output=True, text=True, env=GIT_ENV)
    assert done.returncode == 0, done.stderr
    return done.stdout


def setUpModule():
    """One template: a copy of the taxonomy v2 package (without runs and the heavy retained bodies) committed in a repository of its own."""
    global TEMPLATE, REAL_BEFORE
    REAL_BEFORE = [p.read_bytes() for p in REAL_FILES]
    TEMPLATE = Path(tempfile.mkdtemp(prefix='review-ui-template-'))
    atexit.register(shutil.rmtree, TEMPLATE, True)
    shutil.copytree(REAL, TEMPLATE / 'taxonomy-v2', ignore=shutil.ignore_patterns('runs', '__pycache__', 'catalogue.json', 'surse', 'pagini'))
    repo = Path(common.ROOT)
    for real in REAL_FILES[:3]:
        rel = real.relative_to(repo).as_posix()
        pinned = subprocess.run(['git', 'show', f'{PINNED}:{rel}'], cwd=repo, capture_output=True, env=GIT_ENV)
        if pinned.returncode:
            raise unittest.SkipTest(f'{PINNED}:{rel} is not available (a shallow clone?): {pinned.stderr.decode().strip()}')
        (TEMPLATE / 'taxonomy-v2' / real.relative_to(REAL)).write_bytes(pinned.stdout)
    git(TEMPLATE, 'init', '-q')
    git(TEMPLATE, 'add', '-A')
    git(TEMPLATE, 'commit', '-qm', 'baseline')


def tearDownModule():
    shutil.rmtree(TEMPLATE, True)
    assert [p.read_bytes() for p in REAL_FILES] == REAL_BEFORE, 'a test changed a real review file'


class Fixture(unittest.TestCase):
    """A fresh copy of the template for each test, and a store on its integration copy."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='review-ui-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copytree(TEMPLATE, self.tmp / 'repo', symlinks=True)
        self.repo = self.tmp / 'repo'
        self.root = self.repo / 'taxonomy-v2/integrare'
        self.store = Store(self.root, today=lambda: TODAY)
        self.paths = self.store.paths

    def hashes(self):
        return self.store.hashes()

    def provider(self, item_id, action, **fields):
        request = {'action': action, 'hashes': self.hashes(), 'note': 'Verificat.', **fields}
        return self.store.decide_provider(item_id, request)

    def accept(self, item_id, name, url):
        return self.provider(item_id, 'accept', name=name, url=url)

    def group(self, gid, action, **fields):
        return self.store.decide_group(gid, {'action': action, 'hashes': {'concepte': self.hashes()['concepte']}, 'note': 'Verificat.', **fields})

    def member(self, gid, number, action, **fields):
        return self.store.decide_group(gid, {'action': action, 'hashes': {'concepte': self.hashes()['concepte']}, 'note': '', **fields}, member=number)

    def rows(self, name):
        return review_ui.parse_csv(self.paths[name].read_bytes())[1]

    def item(self, item_id):
        return next(r for r in self.rows('revizuire') if r['id'] == item_id)

    def relation(self, row_id):
        return next((r for r in self.rows('relatii') if r['id'] == row_id), None)

    def concepts(self):
        return json.loads(self.paths['concepte'].read_text())['concepte']

    def concept(self, gid):
        return next(c for c in self.concepts() if c['id'] == gid)

    def head(self, name):
        return git(self.repo, 'show', 'HEAD:' + self.store.git.rel(self.paths[name])).encode()


class ProviderDecisions(Fixture):
    def test_accept_with_a_linked_relation_row(self):
        before = self.rows('relatii')
        result = self.accept('D132', 'ANAF', 'https://demoanaf.ro/')
        item = self.item('D132')
        self.assertEqual((item['stare'], item['decizie_editor']), ('acceptat', f'Acceptat {TODAY}: Verificat.'))
        row = self.relation('L132')
        self.assertEqual((row['stare'], row['camp_sursa'], row['valoare_sursa'], row['obiect_literal']), ('acceptat', 'surse_date', 'https://demoanaf.ro/', 'ANAF'))
        self.assertEqual(len(self.rows('relatii')), len(before), 'a linked row is changed, not added')
        self.assertEqual([r for r in self.rows('relatii') if r['id'] != 'L132'], [r for r in before if r['id'] != 'L132'])
        self.assertEqual(result['state']['progress']['providers']['decided'], 1)

    def test_accept_can_edit_the_name_and_the_evidence_of_a_linked_row(self):
        self.accept('D134', 'Oficiul Național al Registrului Comerțului', 'https://example.org/despre#date')
        row = self.relation('L134')
        self.assertEqual((row['obiect_literal'], row['valoare_sursa']), ('Oficiul Național al Registrului Comerțului', 'https://example.org/despre#date'))

    def test_accept_without_a_relation_row_appends_the_next_free_id(self):
        self.accept('D147', 'Parlamentul European', 'https://www.europescope.eu/data')
        self.accept('D148', 'Consiliul Uniunii Europene', 'https://www.europescope.eu/data')
        rows = self.rows('relatii')
        self.assertEqual([r['id'] for r in rows[-2:]], ['L147', 'L148'])
        self.assertEqual(rows[-2], {'id': 'L147', 'subiect': 'europescope', 'predicat': 'date_din', 'obiect': '', 'obiect_literal': 'Parlamentul European',
                                    'camp_sursa': 'surse_date', 'valoare_sursa': 'https://www.europescope.eu/data', 'stare': 'acceptat'})
        self.assertEqual(self.item('D147')['decizie_editor'], f'Acceptat {TODAY} (rând L147): Verificat.')
        self.assertEqual(self.item('D147')['propunere'], review_ui.find_row(review_ui.parse_csv(self.head('revizuire'))[1], 'D147')['propunere'])

    def test_reject_flips_a_linked_propus_row_and_defer_keeps_it(self):
        self.provider('D133', 'reject')
        self.assertEqual((self.item('D133')['stare'], self.relation('L133')['stare']), ('respins', 'respins'))
        self.assertTrue(self.item('D133')['decizie_editor'].startswith(f'Respins {TODAY}'))
        self.provider('D134', 'defer')
        self.assertEqual((self.item('D134')['stare'], self.relation('L134')['stare']), ('amanat', 'propus'))
        self.assertTrue(self.item('D134')['decizie_editor'].startswith(f'Amânat {TODAY}'))

    def test_a_decision_changes_only_the_rows_it_names(self):
        self.provider('D133', 'reject')
        changed = [i for i, (a, b) in enumerate(zip(self.head('revizuire').splitlines(), self.paths['revizuire'].read_bytes().splitlines())) if a != b]
        self.assertEqual(len(changed), 1)
        changed = [i for i, (a, b) in enumerate(zip(self.head('relatii').splitlines(), self.paths['relatii'].read_bytes().splitlines())) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(self.head('relatii').splitlines()), len(self.paths['relatii'].read_bytes().splitlines()))

    def test_reject_or_defer_removes_a_row_that_only_this_item_appended(self):
        self.accept('D147', 'Parlamentul European', 'https://www.europescope.eu/data')
        self.provider('D147', 'reject')
        self.assertIsNone(self.relation('L147'))
        self.assertEqual(self.item('D147')['stare'], 'respins')
        self.assertNotIn('rând', self.item('D147')['decizie_editor'])
        self.assertEqual(self.paths['relatii'].read_bytes(), self.head('relatii'))

    def test_a_decision_can_change_after_a_commit_without_losing_history(self):
        self.accept('D147', 'Parlamentul European', 'https://www.europescope.eu/data')
        git(self.repo, 'commit', '-qam', 'accept D147')
        self.provider('D147', 'reject')
        row = self.relation('L147')
        self.assertEqual(row['stare'], 'respins', 'a committed row stays for history')
        self.assertIn('(rând L147)', self.item('D147')['decizie_editor'])
        self.accept('D147', 'Parlamentul European', 'https://www.europescope.eu/data')
        self.assertEqual([r['id'] for r in self.rows('relatii') if r['id'] >= 'L147'], ['L147'], 'the same row is reused')
        self.assertEqual(self.relation('L147')['stare'], 'acceptat')

    def test_duplicate_needs_an_existing_item_of_the_same_project(self):
        original = self.item('D153')['motiv']
        self.provider('D153', 'duplicate', duplicate_of='D140')
        item = self.item('D153')
        self.assertEqual((item['stare'], item['decizie_editor']), ('tehnic', ''))
        self.assertTrue(item['motiv'].startswith('Duplicat: D140. Verificat.'))
        self.assertEqual(review_ui.original_reason(item), original, 'the first reason is kept after the new one')
        self.assertEqual(review_ui.parse_csv(self.paths['revizuire'].read_bytes())[1][0]['id'], 'R001')
        for other, text in (('D999', 'existent'), ('R001', 'existent'), ('D133', 'aceluiași proiect'), ('D154', 'aceluiași proiect'), ('', 'obligatoriu'),
                            ('D153', 'un duplicat')):
            with self.subTest(other=other), self.assertRaises(ReviewError) as caught:
                self.provider('D154', 'duplicate', duplicate_of=other)
            self.assertIn(text, str(caught.exception))

    def test_a_duplicate_can_become_a_decision_again(self):
        original = self.item('D153')['motiv']
        self.provider('D153', 'duplicate', duplicate_of='D140')
        self.accept('D153', 'Oficiul Național al Registrului Comerțului', 'https://registru.horecaos.org/surse')
        self.assertEqual(self.item('D153')['motiv'], original)

    def test_the_same_accepted_source_cannot_be_added_twice(self):
        self.accept('D140', 'Oficiul Național al Registrului Comerțului (ONRC)', 'https://registru.horecaos.org/')
        before = self.paths['relatii'].read_bytes()
        with self.assertRaises(ReviewError) as caught:
            self.accept('D153', 'oficiul national al registrului comertului (onrc)', 'https://registru.horecaos.org/surse')
        self.assertIn('deja sursă acceptată', str(caught.exception))
        self.assertEqual(self.paths['relatii'].read_bytes(), before)
        self.assertEqual(self.store.provider('D153')['warnings'][-1][:20], 'Un element înrudit, ')

    def test_reset_restores_head_and_removes_an_appended_row(self):
        for item_id, name, url in (('D132', 'ANAF', 'https://demoanaf.ro/'), ('D147', 'Parlamentul European', 'https://www.europescope.eu/data')):
            self.accept(item_id, name, url)
            self.provider(item_id, 'reset')
        self.provider('D133', 'reject')
        self.provider('D133', 'reset')
        self.provider('D153', 'duplicate', duplicate_of='D140')
        self.provider('D153', 'reset')
        self.assertEqual(self.paths['revizuire'].read_bytes(), self.head('revizuire'))
        self.assertEqual(self.paths['relatii'].read_bytes(), self.head('relatii'))
        self.assertFalse(self.store.provider('D132')['head']['changed'])

    def test_reset_without_a_head_says_so_and_writes_nothing(self):
        shutil.rmtree(self.repo / '.git')
        store = Store(self.root, today=lambda: TODAY)
        before = self.paths['revizuire'].read_bytes()
        with self.assertRaises(ReviewError) as caught:
            store.decide_provider('D132', {'action': 'reset', 'hashes': store.state()['hashes']})
        self.assertIn('Nu există o versiune HEAD', str(caught.exception))
        self.assertEqual(self.paths['revizuire'].read_bytes(), before)

    def test_a_proposal_that_limits_the_provider_to_one_dataset_is_flagged_and_its_name_is_cut(self):
        view = self.store.provider('D160')
        self.assertTrue(any('un singur set' in w for w in view['warnings']))
        self.assertEqual(view['prefill']['name'], 'Inspecția Muncii (Ministerul Muncii)')

    def test_related_items_name_the_same_project_and_provider(self):
        related = {r['id']: r for r in self.store.provider('D140')['related']}
        self.assertEqual(related['D153']['same_provider'], True)
        self.assertEqual(related['D141']['same_provider'], False)
        self.assertEqual(related['D154']['same_provider'], False)
        self.assertEqual({r['id'] for r in self.store.provider('D141')['related'] if r['same_provider']}, {'D154'})

    def test_input_is_validated_before_any_write(self):
        before = self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()
        bad = [dict(action='accept', name='ANAF', url='javascript:alert(1)'), dict(action='accept', name='ANAF', url='https://bad host/'),
               dict(action='accept', name='', url='https://demoanaf.ro/'), dict(action='accept', name='=cmd', url='https://demoanaf.ro/'),
               dict(action='accept', name='ANAF', url='https://demoanaf.ro/', note='  '), dict(action='explode'),
               dict(action='accept', name='ANAF', url='https://demoanaf.ro/', note='x' * 2000)]
        for fields in bad:
            with self.subTest(fields=fields), self.assertRaises(ReviewError):
                self.provider('D132', **{'action': 'accept', **fields})
        with self.assertRaises(ReviewError):
            self.provider('R001', 'accept', name='x', url='https://x.example/')
        with self.assertRaises(ReviewError):
            self.provider('D999', 'defer')
        self.assertEqual((self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()), before)

    def test_the_note_is_one_line(self):
        self.provider('D133', 'defer', note='prima\n\nA doua   linie')
        self.assertEqual(self.item('D133')['decizie_editor'], f'Amânat {TODAY}: prima A doua linie')


class SafeWrites(Fixture):
    def test_loading_and_saving_without_a_change_gives_identical_bytes(self):
        for name in ('revizuire', 'relatii'):
            raw = self.paths[name].read_bytes()
            header, rows = review_ui.parse_csv(raw)
            self.assertEqual(review_ui.dump_csv(header, rows), raw)
        raw = self.paths['concepte'].read_bytes()
        self.assertEqual(review_ui.dump_json(review_ui.parse_json(raw), raw), raw)

    def test_a_file_that_would_not_round_trip_is_refused_rather_than_rewritten(self):
        raw = self.paths['relatii'].read_bytes().replace(b'\n', b'\r\n')
        self.paths['relatii'].write_bytes(raw)
        with self.assertRaises(ReviewError):
            self.store.state()
        self.assertEqual(self.paths['relatii'].read_bytes(), raw)
        self.paths['relatii'].write_bytes(b'\xef\xbb\xbf' + self.head('relatii'))
        with self.assertRaises(ReviewError):
            review_ui.parse_csv(self.paths['relatii'].read_bytes())

    def test_a_stale_hash_refuses_the_write(self):
        hashes = self.hashes()
        self.provider('D133', 'defer')
        stale = {'action': 'defer', 'note': 'x', 'hashes': hashes}  # the page loaded the old files
        before = self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()
        with self.assertRaises(ReviewError) as caught:
            self.store.decide_provider('D134', stale)
        self.assertEqual((caught.exception.status, caught.exception.reload), (409, True))
        self.assertEqual((self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()), before)
        with self.assertRaises(ReviewError) as caught:
            self.store.decide_group('cui', {'action': 'amanat', 'note': 'x', 'hashes': {'concepte': 'old'}})
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(ReviewError):
            self.store.decide_provider('D134', {'action': 'defer', 'note': 'x'})  # no hashes at all

    def test_an_edit_on_disk_after_the_page_loaded_refuses_the_write(self):
        hashes = self.hashes()
        raw = self.paths['concepte'].read_text()
        self.paths['concepte'].write_text(raw.replace('"Identificatorul fiscal', '"Un identificator fiscal', 1))
        with self.assertRaises(ReviewError) as caught:
            self.store.decide_group('cui', {'action': 'amanat', 'note': 'x', 'hashes': {'concepte': hashes['concepte']}})
        self.assertEqual(caught.exception.status, 409)
        self.assertNotIn('"decizie_editor"', self.paths['concepte'].read_text())

    def test_a_failed_validation_writes_nothing(self):
        before = self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()
        rev_rows, rel_rows = self.rows('revizuire'), self.rows('relatii')
        next(r for r in rev_rows if r['id'] == 'D133').update(stare='acceptat', decizie_editor='')  # a closed item without a decision
        with patch.object(review_ui, 'apply_provider', return_value=(rev_rows, rel_rows, 'x')), self.assertRaises(ReviewError) as caught:
            self.provider('D133', 'defer')
        self.assertEqual(caught.exception.status, 422)
        self.assertIn('editor decision', str(caught.exception))  # the message of the existing validator
        self.assertEqual((self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()), before)
        data = json.loads(self.paths['concepte'].read_text())
        data['concepte'][0]['stare'] = 'revizuit'  # no decision text and members still propus
        raw = self.paths['concepte'].read_bytes()
        with patch.object(review_ui, 'apply_group', return_value=(data, 'x')), self.assertRaises(ReviewError) as caught:
            self.group('cui', 'amanat')
        self.assertEqual(caught.exception.status, 422)
        self.assertEqual(self.paths['concepte'].read_bytes(), raw)
        self.assertEqual(list(self.root.glob('.review-*')) + list(self.root.parent.glob('.review-*')), [])

    def test_the_write_is_all_or_nothing_across_the_two_files(self):
        before = self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()
        real = os.replace
        calls = []

        def failing(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise OSError('disk full')
            return real(src, dst)

        with patch.object(review_ui.os, 'replace', failing), self.assertRaises(OSError):
            self.provider('D133', 'reject')
        self.assertEqual((self.paths['revizuire'].read_bytes(), self.paths['relatii'].read_bytes()), before)
        self.assertEqual(list(self.root.glob('.review-*')), [])

    def test_a_file_that_does_not_change_is_not_replaced(self):
        before = self.paths['relatii'].stat().st_mtime_ns
        self.provider('D153', 'duplicate', duplicate_of='D140')
        self.assertEqual(self.paths['relatii'].stat().st_mtime_ns, before, 'a file that does not change is not replaced')

    def test_the_real_data_root_is_untouched(self):
        self.provider('D133', 'reject')
        self.assertEqual([p.read_bytes() for p in REAL_FILES], REAL_BEFORE)


class Http(Fixture):
    def setUp(self):
        super().setUp()
        self.server = review_ui.make_server(self.store, 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, method, path, body=None, token=True, host='default', headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=60)
        sent = {'Host': f'127.0.0.1:{self.port}' if host == 'default' else host, **(headers or {})}
        if body is not None:
            sent['Content-Type'] = 'application/json'
        if token:
            sent['X-Review-Token'] = self.server.token if token is True else token
        connection.request(method, path, body=None if body is None else json.dumps(body), headers=sent)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        return response.status, (json.loads(raw) if response.getheader('Content-Type', '').startswith('application/json') else raw.decode()), response

    def test_it_listens_on_the_loopback_address_only(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')

    def test_the_page_carries_the_token_and_its_assets_without_external_requests(self):
        status, page, response = self.call('GET', '/', token=False)
        self.assertEqual(status, 200)
        self.assertIn(self.server.token, page)
        self.assertNotIn('{{TOKEN}}', page)
        self.assertNotRegex(page, r'(src|href)="https?://')
        self.assertIn("default-src 'none'", response.getheader('Content-Security-Policy'))
        for name in ('review_ui.css', 'review_ui.js'):
            self.assertEqual(self.call('GET', '/assets/' + name, token=False)[0], 200)
        self.assertEqual(self.call('GET', '/assets/../review_ui.py', token=False)[0], 404)
        self.assertEqual(self.call('GET', '/nothing', token=False)[0], 404)
        self.assertEqual(self.call('PUT', '/api/state')[0], 405)

    def test_a_foreign_host_origin_or_token_gets_403(self):
        body = {'action': 'defer', 'note': 'x', 'hashes': {k: v for k, v in self.hashes().items() if k != 'concepte'}}
        before = self.paths['revizuire'].read_bytes()
        cases = [('POST', '/api/provider/D133/decide', body, False, 'default', None), ('POST', '/api/provider/D133/decide', body, 'wrong', 'default', None),
                 ('POST', '/api/provider/D133/decide', body, True, 'evil.example', None), ('POST', '/api/provider/D133/decide', body, True, 'localhost:1', None),
                 ('POST', '/api/provider/D133/decide', body, True, 'default', {'Origin': 'https://evil.example'}),
                 ('GET', '/api/state', None, False, 'evil.example', None), ('GET', '/', None, False, 'evil.example', None),
                 ('POST', '/api/check', {}, False, 'default', None)]
        for method, path, payload, token, host, headers in cases:
            with self.subTest(path=path, token=token, host=host, headers=headers):
                self.assertEqual(self.call(method, path, payload, token=token, host=host, headers=headers)[0], 403)
        self.assertEqual(self.paths['revizuire'].read_bytes(), before)
        self.assertEqual(self.call('GET', '/api/state', host=f'localhost:{self.port}')[0], 200)

    def test_a_decision_over_http_writes_the_files_and_returns_the_new_state(self):
        status, state, _ = self.call('GET', '/api/state')
        self.assertEqual((status, state['progress']['providers']['total'], state['progress']['groups']['total']), (200, 31, 30))
        status, item, _ = self.call('GET', '/api/provider/D132')
        self.assertEqual((status, item['prefill']['name'], item['row']['id']), (200, 'ANAF', 'L132'))
        status, answer, _ = self.call('POST', '/api/provider/D132/decide', {'action': 'accept', 'note': 'Verificat.', 'name': 'ANAF', 'url': 'https://demoanaf.ro/',
                                                                            'hashes': item['hashes']})
        self.assertEqual(status, 200, answer)
        self.assertEqual(answer['state']['progress']['providers']['decided'], 1)
        self.assertEqual(self.relation('L132')['stare'], 'acceptat')
        status, answer, _ = self.call('POST', '/api/provider/D133/decide', {'action': 'defer', 'note': 'x', 'hashes': item['hashes']})
        self.assertEqual((status, answer['reload']), (409, True), 'the hashes of the page are now old')
        status, answer, _ = self.call('POST', '/api/provider/D133/decide', {'action': 'nonsense', 'note': 'x', 'hashes': answer and self.hashes()})
        self.assertEqual(status, 400)
        self.assertEqual(self.call('GET', '/api/provider/R001')[0], 404)
        self.assertEqual(self.call('POST', '/api/provider/D133/decide', None)[0], 415)
        self.assertEqual(self.call('GET', '/api/group/does-not-exist')[0], 404)

    def test_a_group_and_a_member_over_http(self):
        status, group, _ = self.call('GET', '/api/group/populatie')
        self.assertEqual((status, group['stare'], len(group['members'])), (200, 'propus', 4))
        status, answer, _ = self.call('POST', '/api/group/populatie/member/1', {'action': 'confirm', 'hashes': group['hashes']})
        self.assertEqual(status, 200, answer)
        self.assertEqual(answer['item']['members'][0]['stare'], 'confirmat')
        status, answer, _ = self.call('POST', '/api/group/populatie/member/2', {'action': 'exclude', 'hashes': answer['item']['hashes']})
        self.assertEqual((status, 'Notă' in answer['error']), (400, True), 'exclusion needs a note')

    def test_the_check_panel_runs_the_three_checks_and_the_git_panel_shows_the_change(self):
        self.provider('D132', 'accept', name='ANAF', url='https://demoanaf.ro/')
        status, answer, _ = self.call('POST', '/api/check', {})
        self.assertEqual(status, 200)
        names = [c['name'] for c in answer['checks']]
        self.assertEqual(names, ['validate.py --publication', 'inventory.py --check', 'inventory_report.py --check'])
        self.assertEqual(answer['checks'][0]['code'], 0, answer['checks'][0])
        self.assertTrue(all(isinstance(c['code'], int) and c['tail'] for c in answer['checks']))
        status, panel, _ = self.call('GET', '/api/git')
        self.assertEqual(status, 200)
        self.assertEqual({f['path'].rsplit('/', 1)[1] for f in panel['files']}, {'revizuire.csv', 'relatii.csv'})
        self.assertIn('relatii.csv', panel['stat'])
        self.assertEqual(panel['public']['lines'], [{'sign': '+', 'slug': 'demoanaf', 'name': 'ANAF', 'evidence': 'https://demoanaf.ro/'}])
        self.assertTrue(any(c.startswith('git add') and 'inventar-concepte.json' in c for c in panel['commands']))
        self.assertTrue(any(c == 'python3 scripts/inventory_report.py' for c in panel['commands']))
        self.assertFalse(any('git push' in c for c in panel['commands']))


class GroupDecisions(Fixture):
    def confirm_all(self, gid, exclude=()):
        for number in range(1, len(self.concept(gid)['selectors']) + 1):
            if number in exclude:
                self.member(gid, number, 'exclude', note='Nu poartă variabila.')
            else:
                self.member(gid, number, 'confirm')

    def test_state_keys_validate(self):
        base = {'id': 'g', 'label': 'G', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['a']}]}
        self.assertEqual(validate_concept(base), [])
        for key, value, text in (('stare', 'gata', 'unknown group state'), ('stare', 'revizuit', 'needs decizie_editor'), ('stare', 'respins', 'needs decizie_editor'),
                                 ('data_revizie', '25.10.2026', 'ISO date'), ('decizie_editor', 3, 'must be text')):
            with self.subTest(key=key, value=value):
                self.assertTrue(any(text in e for e in validate_concept({**base, key: value})), validate_concept({**base, key: value}))
        self.assertEqual(validate_concept({**base, 'stare': 'amanat'}), [], 'a deferred group needs no decision text')
        self.assertEqual(validate_concept({**base, 'stare': 'propus'}), [])
        reviewed = {**base, 'stare': 'revizuit', 'decizie_editor': 'ok', 'data_revizie': TODAY}
        self.assertEqual(validate_concept({**reviewed, 'selectors': [{**base['selectors'][0], 'stare': 'confirmat'}]}), [])
        self.assertTrue(any('propus member' in e for e in validate_concept(reviewed)), 'a revizuit group with a member left propus')
        self.assertTrue(any('propus member' in e for e in validate_concept({**reviewed, 'selectors': [{**base['selectors'][0], 'stare': 'propus'}]})))

    def test_selector_states_validate(self):
        sel = {'projects': ['p'], 'names': ['a']}
        self.assertEqual(validate_selector({**sel, 'stare': 'confirmat'}, 'w'), [])
        self.assertEqual(validate_selector({**sel, 'stare': 'exclus', 'nota_editor': 'Nu este CUI.'}, 'w'), [])
        self.assertTrue(any('needs nota_editor' in e for e in validate_selector({**sel, 'stare': 'exclus'}, 'w')))
        self.assertTrue(any('needs nota_editor' in e for e in validate_selector({**sel, 'stare': 'exclus', 'nota_editor': ' '}, 'w')))
        self.assertTrue(any('unknown selector state' in e for e in validate_selector({**sel, 'stare': 'ok'}, 'w')))
        self.assertEqual(validate_group_state({'selectors': []}, 'w'), [])

    def test_an_excluded_selector_never_matches_but_stays_for_history(self):
        field = {'name': 'cui', 'path': '$.cui', 'role': 'camp-date'}
        selector = {'projects': ['p'], 'names': ['cui']}
        self.assertTrue(selector_matches(selector, 'p', field, 'https://x.example/'))
        self.assertTrue(selector_matches({**selector, 'stare': 'confirmat'}, 'p', field, 'https://x.example/'))
        excluded = {**selector, 'stare': 'exclus', 'nota_editor': 'Nu.'}
        self.assertFalse(selector_matches(excluded, 'p', field, 'https://x.example/'))
        self.assertTrue(selector_matches(excluded, 'p', field, 'https://x.example/', include_excluded=True))
        sources = [{'id': 's', 'url': 'https://x.example/'}]
        fields = [dict(name='cui', path='$.cui', role='camp-date', basis='schema', declaredType=None, observedTypes=[], unit=None, description='', source='s', reference='/x')]
        self.assertEqual(variable_matches('p', fields, sources, [{'id': 'g', 'selectors': [excluded]}]), [])
        self.assertEqual(variable_matches('p', fields, sources, [{'id': 'g', 'selectors': [excluded, selector]}])[0]['count'], 1)

    def test_an_excluded_selector_that_reaches_no_field_is_not_a_check_error(self):
        concept = {'id': 'g', 'label': 'G', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['gone'], 'stare': 'exclus', 'nota_editor': 'x'}]}
        report = check_concepts([concept], {'p': []}, None, {'p'})
        self.assertEqual(report['errors'], [])
        concept['selectors'][0].pop('stare')
        self.assertTrue(any('matches no field' in e for e in check_concepts([concept], {'p': []}, None, {'p'})['errors']))

    def test_a_rejected_group_produces_no_finder_matches_and_no_index_entry(self):
        sources = [{'id': 's', 'url': 'https://x.example/'}]
        fields = [dict(name='cui', path='$.cui', role='camp-date', basis='schema', declaredType=None, observedTypes=[], unit=None, description='', source='s', reference='/x')]
        groups = [{'id': 'a', 'label': 'A', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['cui']}], 'stare': 'respins', 'decizie_editor': 'x'},
                  {'id': 'b', 'label': 'B', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['cui']}], 'stare': 'revizuit', 'decizie_editor': 'x'},
                  {'id': 'c', 'label': 'C', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['cui']}]}]
        self.assertEqual([m['id'] for m in variable_matches('p', fields, sources, groups)], ['b', 'c'])
        root = self.tmp / 'finder'
        (root / 'site/inventar').mkdir(parents=True)
        for name in ('style.css', 'inventory.css', 'inventory.js'):
            (root / 'site' / name).write_text('/* fixture */')
        (root / 'inventar-concepte.json').write_text(json.dumps({'concepte': groups}))
        (root / 'integrare').mkdir()
        publish_finder([dict(slug='p', name='P', kind='proiect', status='activ', dataRelation='date-publice')], root / 'integrare', root / 'site', {'p': (fields, sources)})
        index = json.loads((root / 'site/inventar/index.json').read_text())
        self.assertEqual([(v['id'], v['state']) for v in index['variables']], [('b', 'revizuit'), ('c', 'propus')])
        self.assertEqual([m['id'] for m in index['entries'][0]['variables']], ['b', 'c'])

    def test_a_group_review_needs_every_member_decided_a_confirmed_member_and_the_ticks(self):
        view = self.store.group('cui')
        self.assertEqual(len(view['blockers']), 2, 'members still propus, and no confirmed member')
        self.assertEqual(len(view['deductions']), 4, 'the ticks belong to the request, not to the file')
        with self.assertRaises(ReviewError) as caught:
            self.group('cui', 'revizuit')
        self.assertIn('propuși', str(caught.exception))
        self.confirm_all('cui')
        ticks = [d['id'] for d in self.store.group('cui')['deductions']]
        with self.assertRaises(ReviewError) as caught:
            self.group('cui', 'revizuit', ticked=ticks[:3])
        self.assertIn('deducții', str(caught.exception))
        before = self.paths['concepte'].read_bytes()
        result = self.group('cui', 'revizuit', ticked=ticks, note='Membrii și formularea sunt verificate.')
        self.assertNotEqual(self.paths['concepte'].read_bytes(), before)
        concept = self.concept('cui')
        self.assertEqual((concept['stare'], concept['decizie_editor'], concept['data_revizie']), ('revizuit', 'Membrii și formularea sunt verificate.', TODAY))
        self.assertEqual(list(concept)[-3:], ['stare', 'decizie_editor', 'data_revizie'], 'new keys go after the existing ones')
        self.assertEqual(result['state']['progress']['groups']['decided'], 1)
        self.assertEqual(result['item']['blockers'], [])

    def test_a_group_with_every_member_excluded_cannot_be_reviewed(self):
        gid = 'siruta'
        self.member(gid, 1, 'exclude', note='Nu poartă variabila.')
        with self.assertRaises(ReviewError) as caught:
            self.group(gid, 'revizuit')
        self.assertIn('Niciun membru nu este confirmat', str(caught.exception))
        self.group(gid, 'respins', note='Nu există variabila.')
        self.assertEqual(self.concept(gid)['stare'], 'respins')

    def test_member_decisions_keep_the_file_otherwise_unchanged(self):
        before = self.paths['concepte'].read_text()
        self.member('populatie', 1, 'confirm')
        self.member('populatie', 2, 'exclude', note='Alt sens.')
        concept = self.concept('populatie')
        self.assertEqual((concept['selectors'][0]['stare'], 'nota_editor' in concept['selectors'][0]), ('confirmat', False))
        self.assertEqual((concept['selectors'][1]['stare'], concept['selectors'][1]['nota_editor']), ('exclus', 'Alt sens.'))
        self.assertEqual(list(concept['selectors'][1])[-2:], ['stare', 'nota_editor'])
        after = self.paths['concepte'].read_text()
        added = [line for line in after.splitlines() if line not in before.splitlines()]
        self.assertTrue(all('stare' in line or 'nota_editor' in line or line.strip() in (',', '') or line.rstrip().endswith(',') for line in added), added)
        self.member('populatie', 1, 'reset')
        self.member('populatie', 2, 'reset')
        self.assertEqual(self.paths['concepte'].read_text(), before, 'resetting both members restores the exact bytes')

    def test_exclusion_needs_a_note_and_a_reviewed_group_is_locked_until_reset(self):
        with self.assertRaises(ReviewError):
            self.member('populatie', 1, 'exclude')
        with self.assertRaises(ReviewError):
            self.member('populatie', 9, 'confirm')
        self.group('populatie', 'amanat', note='Mai târziu.')
        self.member('populatie', 1, 'confirm')  # a deferred group is still open
        self.group('populatie', 'respins', note='Nu.')
        with self.assertRaises(ReviewError) as caught:
            self.member('populatie', 2, 'confirm')
        self.assertIn('Resetați grupul', str(caught.exception))

    def test_group_reset_restores_head_and_a_member_reset_goes_to_propus(self):
        self.confirm_all('siruta')
        self.group('siruta', 'revizuit', note='Verificat.')
        self.group('siruta', 'reset')
        self.assertEqual(self.paths['concepte'].read_bytes(), self.head('concepte'))
        self.assertFalse(self.store.group('siruta')['head']['changed'])

    def test_the_top_level_state_and_the_other_groups_are_untouched(self):
        before = json.loads(self.paths['concepte'].read_text())
        self.member('populatie', 1, 'confirm')
        after = json.loads(self.paths['concepte'].read_text())
        self.assertEqual((after['stare'], after['nota']), (before['stare'], before['nota']))
        self.assertEqual([c for c in after['concepte'] if c['id'] != 'populatie'], [c for c in before['concepte'] if c['id'] != 'populatie'])

    def test_group_view_shows_members_evidence_basis_and_deductions(self):
        group = self.store.group('cui')
        self.assertEqual(group['basis'], 'parafraza-editoriala')
        self.assertEqual(group['basis_label'], 'parafrază editorială')
        deduced = [f for m in group['members'] for f in m['facts'] if f['basis'] == 'deductie-din-dovezi']
        self.assertEqual(len(deduced), 4)
        self.assertEqual({f['basis_label'] for f in deduced}, {'deducție din dovezi'})
        member = group['members'][5]
        self.assertEqual((member['names'], member['stare']), (['afn'], 'propus'))
        self.assertEqual(member['reach']['count'], 1)
        self.assertEqual(member['reach']['examples'][0]['path'], '$.items[].afn')
        self.assertEqual(member['projects'], [{'slug': 'banii-nostri', 'name': 'Banii Noștri'}])


class CandidateFixture(Fixture):
    """The candidate queue. The template has no open candidate (the owner confirmed them all), so each test makes its own on the temporary copy: three reviewed
    groups (all members confirmed) and one candidate for each, a selector that another group holds. The copy is committed, so that HEAD holds the open candidates."""
    REVIEWED = ('cui', 'judet', 'localitate')

    def setUp(self):
        super().setUp()
        raw = self.paths['concepte'].read_bytes()
        data = review_ui.parse_json(raw)
        by_id = {c['id']: c for c in data['concepte']}
        with_facts = next(s for s in by_id['populatie']['selectors'] if s.get('fapte'))  # a selector with pinned facts, to show their evidence
        self.selectors = {'cui': copy.deepcopy(with_facts), 'judet': copy.deepcopy(by_id['localitate']['selectors'][0]),
                          'localitate': copy.deepcopy(by_id['cui']['selectors'][0])}
        for gid in self.REVIEWED:
            for selector in by_id[gid]['selectors']:
                selector['stare'] = 'confirmat'
            by_id[gid].update(stare='revizuit', decizie_editor='Verificat.', data_revizie='2026-10-24')
        self.paths['concepte'].write_bytes(review_ui.dump_json(data, raw))
        self.put_candidates([{'grup': gid, 'selector': selector} for gid, selector in self.selectors.items()])
        self.commit('reviewed groups and candidates')
        self.store = Store(self.root, today=lambda: TODAY)

    # -- helpers ---------------------------------------------------------------------------------------------------

    def put_candidates(self, items):
        """Write the candidate list into the notes, in the middle of the file (where a batch puts it), as the tool would write it."""
        raw = self.paths['note'].read_bytes()
        notes = review_ui.parse_json(raw)
        notes.pop(CANDIDATES, None)
        anchor = list(notes)[len(notes) // 2]
        out = {}
        for key, value in notes.items():
            out[key] = value
            if key == anchor and items:
                out[CANDIDATES] = items
        self.paths['note'].write_bytes(review_ui.dump_json(out, raw))

    def commit(self, message='decision'):
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-qm', message)

    def rows(self):
        return self.store.state()['candidates']

    def cid(self, group, state=None):
        return next(r['id'] for r in self.rows() if r['group'] == group and (state is None or r['stare'] == state))

    def decide(self, cid, action, note='', **fields):
        hashes = self.hashes()
        return self.store.decide_candidate(cid, {'action': action, 'note': note, 'hashes': {k: hashes[k] for k in ('concepte', 'note')}, **fields})

    def notes(self):
        return json.loads(self.paths['note'].read_text())

    def items(self):
        return self.notes().get(CANDIDATES, [])

    def both(self):
        return self.paths['concepte'].read_bytes(), self.paths['note'].read_bytes()

    def head_both(self):
        return self.head('concepte'), self.head('note')

    def errors(self):
        snap = self.store.read()
        return self.store.errors_of(snap['concepts'], notes=snap['notes'])



class CandidateDecisions(CandidateFixture):
    # -- the queue and the detail ----------------------------------------------------------------------------------

    def test_the_fixture_is_clean_and_the_queue_lists_the_open_candidates_with_the_group_label(self):
        self.assertEqual(self.errors(), [])
        state = self.store.state()
        self.assertEqual([(r['group'], r['label'], r['stare'], r['problems']) for r in state['candidates']],
                         [(g, self.concept(g)['label'], 'propus', 0) for g in self.REVIEWED])
        self.assertEqual(state['progress']['candidates'], {'total': 3, 'open': 3, 'decided': 0, 'by_state': {'propus': 3}})
        self.assertTrue(all(review_ui.CANDIDATE_ID.match(r['id']) for r in state['candidates']))
        self.assertTrue(state['validation']['ok'])

    def test_the_real_data_root_has_an_empty_queue(self):
        state = Store(common.PUBLIC_ROOT).state()
        self.assertEqual((state['candidates'], state['progress']['candidates']['open']), ([], 0))

    def test_the_detail_shows_the_group_the_reach_the_pinned_facts_and_the_confirmed_members(self):
        view = self.store.candidate(self.cid('cui'))
        self.assertEqual((view['stare'], view['origin'], view['blockers'], view['warnings'], view['head']), ('propus', 'lista', [], [], {'available': True, 'changed': False}))
        self.assertEqual((view['group']['id'], view['group']['label'], view['group']['definition'], view['group']['stare']),
                         ('cui', self.concept('cui')['label'], self.concept('cui')['definition'], 'revizuit'))
        selector = self.selectors['cui']
        self.assertEqual(view['member']['reach'], self.store.fields.examples(selector))
        self.assertEqual(view['member']['names'], review_ui.as_list(selector.get('names')))
        self.assertEqual([f['key'] for f in view['member']['facts']], [f['cheie'] for f in selector['fapte']])
        self.assertTrue(all(f['evidence'] is None or f['evidence']['state'] in review_ui.STATE_LABELS for f in view['member']['facts']))
        self.assertEqual(len(view['confirmed']), len(self.concept('cui')['selectors']))
        self.assertEqual([m['number'] for m in view['confirmed'] if m['same_project']], [n for n, m in enumerate(self.concept('cui')['selectors'], 1)
                         if set(m['projects']) & set(selector['projects'])])
        self.assertTrue(all(m['same_project'] for m in view['confirmed'][:sum(m['same_project'] for m in view['confirmed'])]), 'the members of the same project come first')
        self.assertEqual(view['hashes'], {k: self.hashes()[k] for k in ('concepte', 'note')})

    # -- confirm ---------------------------------------------------------------------------------------------------

    def test_confirm_moves_the_selector_into_the_group_and_out_of_the_list(self):
        before = self.concept('cui')
        answer = self.decide(self.cid('cui'), 'confirm', note='Poartă CUI-ul.')
        group = self.concept('cui')
        self.assertEqual(len(group['selectors']), len(before['selectors']) + 1)
        self.assertEqual(group['selectors'][:-1], before['selectors'])
        self.assertEqual(group['selectors'][-1], {**self.selectors['cui'], 'stare': 'confirmat', 'nota_editor': 'Poartă CUI-ul.'})
        self.assertEqual(list(group['selectors'][-1])[-2:], ['stare', 'nota_editor'], 'the review keys go after the existing ones')
        self.assertEqual({k: group[k] for k in ('stare', 'decizie_editor', 'data_revizie')}, {k: before[k] for k in ('stare', 'decizie_editor', 'data_revizie')},
                         'the group keeps its state and its review date')
        self.assertEqual([i['grup'] for i in self.items()], ['judet', 'localitate'])
        self.assertEqual([c for c in self.concepts() if c['id'] != 'cui'], [c for c in json.loads(self.head('concepte'))['concepte'] if c['id'] != 'cui'])
        self.assertEqual(self.errors(), [])
        self.assertEqual((answer['state']['progress']['candidates']['open'], answer['state']['progress']['candidates']['by_state']), (2, {'propus': 2, 'confirmat': 1}))
        self.assertEqual((answer['item']['origin'], answer['item']['stare'], answer['item']['member_number']), ('confirmat', 'confirmat', len(group['selectors'])))
        self.assertIn('membrul', answer['message'])

    def test_confirm_without_a_note_writes_no_note(self):
        self.decide(self.cid('judet'), 'confirm')
        self.assertEqual(self.concept('judet')['selectors'][-1], {**self.selectors['judet'], 'stare': 'confirmat'})
        self.assertNotIn('nota_editor', self.concept('judet')['selectors'][-1])

    def test_a_decision_writes_the_two_files_and_no_other_file(self):
        self.decide(self.cid('cui'), 'confirm')
        changed = {line[3:] for line in git(self.repo, 'status', '--porcelain').splitlines()}
        self.assertEqual({Path(c).name for c in changed}, {'inventar-concepte.json', 'inventar-note.json'})
        self.decide(self.cid('judet'), 'exclude', note='Nu.')
        self.assertEqual({Path(line[3:]).name for line in git(self.repo, 'status', '--porcelain').splitlines()}, {'inventar-concepte.json', 'inventar-note.json'})

    def test_confirming_the_last_candidate_removes_the_key_and_a_reset_puts_it_back_in_its_place(self):
        for group in self.REVIEWED:
            self.decide(self.cid(group, 'propus'), 'confirm')
        self.assertNotIn(CANDIDATES, self.notes())
        self.assertEqual(self.errors(), [])
        for group in ('localitate', 'cui', 'judet'):  # not in the order of the list: each goes back to its place
            self.decide(self.cid(group, 'confirmat'), 'reset')
        self.assertEqual(self.both(), self.head_both(), 'the key and the candidates are back where HEAD had them, byte for byte')

    # -- exclude ---------------------------------------------------------------------------------------------------

    def test_exclude_needs_a_note_and_keeps_the_candidate_for_history(self):
        cid = self.cid('judet')
        before = self.both()
        for note in ('', '   '):
            with self.assertRaises(ReviewError) as caught:
                self.decide(cid, 'exclude', note=note)
            self.assertIn('obligatoriu', str(caught.exception))
        self.assertEqual(self.both(), before)
        answer = self.decide(cid, 'exclude', note='Nu poartă județul.')
        items = self.items()
        self.assertEqual(len(items), 3, 'the candidate stays in the notes')
        self.assertEqual(items[1], {'grup': 'judet', 'selector': self.selectors['judet'], 'stare': 'exclus', 'nota_editor': 'Nu poartă județul.'})
        self.assertEqual(list(items[1]), ['grup', 'selector', 'stare', 'nota_editor'])
        self.assertEqual(self.paths['concepte'].read_bytes(), before[0], 'no member is added')
        self.assertEqual(self.errors(), [])
        progress = answer['state']['progress']['candidates']
        self.assertEqual((progress['open'], progress['decided'], progress['by_state']), (2, 1, {'propus': 2, 'exclus': 1}))
        self.assertEqual((answer['item']['stare'], answer['item']['nota_editor']), ('exclus', 'Nu poartă județul.'))
        self.assertEqual(answer['item']['id'], cid, 'an excluded candidate keeps its place and its id')

    def test_an_excluded_candidate_can_be_confirmed_later_and_excluded_again(self):
        cid = self.cid('cui')
        self.decide(cid, 'exclude', note='Nu.')
        self.decide(cid, 'exclude', note='Încă o dată.')
        self.assertEqual(self.items()[0]['nota_editor'], 'Încă o dată.')
        self.decide(cid, 'confirm', note='M-am răzgândit.')
        self.assertEqual(self.concept('cui')['selectors'][-1]['nota_editor'], 'M-am răzgândit.')
        self.assertEqual([i['grup'] for i in self.items()], ['judet', 'localitate'])

    # -- reset -----------------------------------------------------------------------------------------------------

    def test_reset_brings_an_excluded_candidate_back_to_head(self):
        cid = self.cid('cui')
        self.decide(cid, 'exclude', note='Nu.')
        self.assertTrue(self.store.candidate(cid)['head']['changed'])
        self.decide(cid, 'reset')
        self.assertEqual(self.both(), self.head_both())
        self.assertEqual(self.store.candidate(cid)['head'], {'available': True, 'changed': False})

    def test_reset_brings_a_confirmed_candidate_back_and_takes_the_member_out_of_the_group(self):
        self.decide(self.cid('judet'), 'confirm', note='Da.')
        ghost = next(r for r in self.rows() if r['stare'] == 'confirmat')
        self.assertEqual((ghost['group'], ghost['short']), ('judet', '#2'), 'a confirmed candidate keeps its place at HEAD in the queue')
        self.assertEqual([r['group'] for r in self.rows()], ['cui', 'judet', 'localitate'])
        answer = self.decide(ghost['id'], 'reset')
        self.assertEqual(self.both(), self.head_both())
        self.assertEqual((answer['item']['origin'], answer['item']['stare'], answer['item']['id']), ('lista', 'propus', ghost['id']))

    def test_a_confirmed_candidate_cannot_be_changed_before_it_is_reset(self):
        self.decide(self.cid('judet'), 'confirm')
        ghost = self.cid('judet', 'confirmat')
        before = self.both()
        for action in ('confirm', 'exclude'):
            with self.assertRaises(ReviewError) as caught:
                self.decide(ghost, action, note='Nu.')
            self.assertIn('Resetați-l', str(caught.exception))
        self.assertEqual(self.both(), before)

    def test_reset_works_only_while_no_commit_holds_the_decision(self):
        cid = self.cid('cui')
        self.decide(cid, 'exclude', note='Nu.')
        self.commit('exclude cui')
        self.assertEqual(self.store.candidate(cid)['head'], {'available': True, 'changed': False}, 'HEAD holds the exclusion now: nothing to reset')
        before = self.both()
        self.decide(cid, 'reset')
        self.assertEqual(self.both(), before)
        self.decide(self.cid('judet'), 'confirm')
        self.commit('confirm judet')
        self.assertEqual([r['group'] for r in self.rows()], ['cui', 'localitate'], 'a committed confirmation leaves the queue for good')
        with self.assertRaises(ReviewError) as caught:
            self.decide('2-' + candidate_key({'grup': 'judet', 'selector': self.selectors['judet']})[:12], 'reset')
        self.assertEqual(caught.exception.status, 409)

    def test_reset_without_a_head_version_says_so_and_writes_nothing(self):
        extra = {'grup': 'judet', 'selector': {**self.selectors['judet'], 'names': ['judet_nou']}}
        self.put_candidates(self.items() + [extra])
        cid = self.rows()[-1]['id']
        self.assertEqual(self.store.candidate(cid)['head'], {'available': False, 'changed': False})
        self.decide(cid, 'exclude', note='Nu.')
        before = self.both()
        with self.assertRaises(ReviewError) as caught:
            self.decide(cid, 'reset')
        self.assertIn('nu există în HEAD', str(caught.exception))
        self.assertEqual(self.both(), before)
        shutil.rmtree(self.repo / '.git')
        store = Store(self.root, today=lambda: TODAY)
        with self.assertRaises(ReviewError) as caught:
            store.decide_candidate(store.state()['candidates'][0]['id'], {'action': 'reset', 'hashes': {k: store.hashes()[k] for k in ('concepte', 'note')}})
        self.assertIn('Nu există o versiune HEAD', str(caught.exception))

    # -- a stale page ----------------------------------------------------------------------------------------------

    def test_a_stale_file_hash_refuses_the_write(self):
        cid, hashes = self.cid('cui'), self.hashes()
        edited = self.notes()
        edited['editat'] = 'de mână'  # an edit that still round-trips: only the hash changes
        self.paths['note'].write_bytes(review_ui.dump_json(edited, self.paths['note'].read_bytes()))
        before = self.both()
        for stale in ({'concepte': hashes['concepte'], 'note': hashes['note']}, {'concepte': 'old', 'note': self.hashes()['note']},
                      {'concepte': self.hashes()['concepte'], 'note': 'old'}):
            with self.subTest(stale=stale), self.assertRaises(ReviewError) as caught:
                self.store.decide_candidate(cid, {'action': 'confirm', 'hashes': stale})
            self.assertEqual((caught.exception.status, caught.exception.reload), (409, True))
        with self.assertRaises(ReviewError) as caught:
            self.store.decide_candidate(cid, {'action': 'confirm', 'hashes': {'concepte': self.hashes()['concepte']}})  # one hash is missing
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.both(), before)

    def test_an_edit_of_the_concepts_file_after_the_page_loaded_refuses_the_write(self):
        cid, hashes = self.cid('cui'), self.hashes()
        self.paths['concepte'].write_text(self.paths['concepte'].read_text().replace('"Identificatorul fiscal', '"Un identificator fiscal', 1))
        before = self.both()
        with self.assertRaises(ReviewError) as caught:
            self.store.decide_candidate(cid, {'action': 'exclude', 'note': 'x', 'hashes': {k: hashes[k] for k in ('concepte', 'note')}})
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.both(), before)

    def test_a_stale_place_or_hash_cannot_decide_another_candidate(self):
        first, second = self.cid('cui'), self.cid('judet')
        before = self.both()
        wrong = [('2-' + first.split('-')[1], 409), ('1-' + second.split('-')[1], 409), ('9-' + first.split('-')[1], 409), ('0-' + first.split('-')[1], 409)]
        for cid, status in wrong:
            with self.subTest(cid=cid), self.assertRaises(ReviewError) as caught:
                self.decide(cid, 'exclude', note='Nu.')
            self.assertEqual((caught.exception.status, caught.exception.reload), (status, True))
        for cid in ('cui', '1', '1-abc', '1-' + 'g' * 12, ''):
            with self.subTest(cid=cid), self.assertRaises(ReviewError) as caught:
                self.decide(cid, 'exclude', note='Nu.')
            self.assertEqual(caught.exception.status, 404)
        self.assertEqual(self.both(), before)
        self.decide(first, 'confirm')  # the list shifts: the second candidate is now the first
        with self.assertRaises(ReviewError) as caught:
            self.decide(second, 'exclude', note='Nu.')
        self.assertEqual(caught.exception.status, 409, 'a page that still holds the old place does not decide the candidate that took it')
        self.assertEqual([i['grup'] for i in self.items()], ['judet', 'localitate'])
        self.assertNotIn('stare', self.items()[0])

    def test_an_unknown_action_is_refused(self):
        before = self.both()
        with self.assertRaises(ReviewError) as caught:
            self.decide(self.cid('cui'), 'delete')
        self.assertIn('Acțiune necunoscută', str(caught.exception))
        self.assertEqual(self.both(), before)

    # -- the group of a candidate ----------------------------------------------------------------------------------

    def test_a_candidate_with_a_missing_group_or_a_group_that_is_not_reviewed_is_an_error_that_the_page_shows(self):
        stray = {'grup': 'nu-exista', 'selector': {**self.selectors['cui'], 'names': ['x1']}}
        proposed = {'grup': 'siruta', 'selector': {**self.selectors['cui'], 'names': ['x2']}}
        self.put_candidates(self.items() + [stray, proposed])
        errors = self.errors()
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(any('the group nu-exista does not exist' in e for e in errors))
        self.assertTrue(any('needs a revizuit group, and the group is propus' in e for e in errors))
        state = self.store.state()
        self.assertEqual((state['validation']['ok'], state['validation']['count']), (False, 2))
        self.assertEqual([r['problems'] for r in state['candidates']], [0, 0, 0, 1, 1])
        for number, text in ((4, 'nu există'), (5, 'este «propus»')):
            view = self.store.candidate(state['candidates'][number - 1]['id'])
            self.assertEqual(len(view['blockers']), 1)
            self.assertIn(text, view['blockers'][0])
            before = self.both()
            with self.assertRaises(ReviewError) as caught:
                self.decide(view['id'], 'confirm')
            self.assertEqual(caught.exception.status, 422)
            self.assertIn('nu poate fi confirmat', str(caught.exception))
            self.assertIn(text, str(caught.exception))
            self.assertEqual(self.both(), before)
        self.decide(state['candidates'][3]['id'], 'exclude', note='Grupul nu există.')  # an excluded candidate is history: it is no error any more
        self.assertEqual(len(self.errors()), 1)

    def test_a_candidate_that_a_group_already_holds_cannot_be_confirmed(self):
        group = self.concept('judet')
        held = {'grup': 'judet', 'selector': {k: v for k, v in group['selectors'][0].items() if k not in ('stare', 'nota_editor')}}
        self.put_candidates(self.items() + [held])
        self.assertTrue(any('already holds this selector as member 1' in e for e in self.errors()))
        before = self.both()
        with self.assertRaises(ReviewError) as caught:
            self.decide(self.rows()[-1]['id'], 'confirm')
        self.assertIn('are deja acest selector ca membru (membrul 1)', str(caught.exception))
        self.assertEqual(self.both(), before)

    def test_a_group_decision_that_would_strand_an_open_candidate_is_refused(self):
        before = self.paths['concepte'].read_bytes()
        with self.assertRaises(ReviewError) as caught:
            self.group('cui', 'amanat', note='Mai târziu.')
        self.assertEqual(caught.exception.status, 422)
        self.assertIn('needs a revizuit group', str(caught.exception))
        self.assertEqual(self.paths['concepte'].read_bytes(), before)
        self.decide(self.cid('cui'), 'exclude', note='Nu.')
        self.group('cui', 'amanat', note='Mai târziu.')  # nothing is open for the group any more
        self.assertEqual(self.concept('cui')['stare'], 'amanat')

    def test_a_reset_that_would_bring_back_an_error_of_head_is_refused(self):
        stray = {'grup': 'siruta', 'selector': {**self.selectors['cui'], 'names': ['x']}}
        self.put_candidates(self.items() + [stray])
        self.commit('a candidate of a proposed group')
        self.store = Store(self.root, today=lambda: TODAY)
        self.assertEqual(len(self.errors()), 1)
        cid = self.rows()[-1]['id']
        self.decide(cid, 'exclude', note='Nu.')
        self.assertEqual(self.errors(), [])
        before = self.both()
        with self.assertRaises(ReviewError) as caught:
            self.decide(cid, 'reset')
        self.assertEqual(caught.exception.status, 422)
        self.assertIn('nu s-a scris nimic', str(caught.exception))
        self.assertEqual(self.both(), before)

    def test_a_member_that_head_already_holds_is_never_taken_out_by_a_reset(self):
        member = {k: v for k, v in self.concept('judet')['selectors'][0].items() if k not in ('stare', 'nota_editor')}
        self.put_candidates(self.items() + [{'grup': 'judet', 'selector': member}])
        self.commit('a candidate that its group holds')  # an error at HEAD
        self.store = Store(self.root, today=lambda: TODAY)
        self.put_candidates(self.items()[:-1])  # a person drops it from the notes
        self.assertEqual([r['stare'] for r in self.rows()], ['propus'] * 3, 'HEAD holds the member: the candidate is not shown as confirmed since HEAD')

    def test_a_failed_validation_writes_nothing_to_either_file(self):
        data = json.loads(self.paths['concepte'].read_text())
        data['concepte'][0]['stare'] = 'gata'  # an unknown state: a new error
        before = self.both()
        with patch.object(review_ui, 'apply_candidate', return_value=(data, self.notes(), 'x', 'k')), self.assertRaises(ReviewError) as caught:
            self.decide(self.cid('cui'), 'confirm')
        self.assertEqual(caught.exception.status, 422)
        self.assertEqual(self.both(), before)
        self.assertEqual(list(self.root.parent.glob('.review-*')), [])

    def test_the_write_is_all_or_nothing_across_the_dictionary_and_the_notes(self):
        before = self.both()
        real, calls = os.replace, []

        def failing(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise OSError('disk full')
            return real(src, dst)

        with patch.object(review_ui.os, 'replace', failing), self.assertRaises(OSError):
            self.decide(self.cid('cui'), 'confirm')
        self.assertEqual(len(calls) >= 2, True)
        self.assertEqual(self.both(), before)
        self.assertEqual(list(self.root.parent.glob('.review-*')), [])

    # -- bytes -----------------------------------------------------------------------------------------------------

    def test_both_files_stay_byte_stable_and_only_the_decision_changes(self):
        for name in ('concepte', 'note'):
            raw = self.paths[name].read_bytes()
            self.assertEqual(review_ui.dump_json(review_ui.parse_json(raw), raw), raw)
        old_keys = list(self.notes())
        self.decide(self.cid('cui'), 'confirm', note='Da.')
        self.decide(self.cid('judet'), 'exclude', note='Nu.')
        for name in ('concepte', 'note'):
            raw = self.paths[name].read_bytes()
            self.assertEqual(review_ui.dump_json(review_ui.parse_json(raw), raw), raw, name)
        notes = self.notes()
        self.assertEqual(list(notes), old_keys, 'the keys of the notes keep their order')
        self.assertEqual({k: v for k, v in notes.items() if k != CANDIDATES}, {k: v for k, v in json.loads(self.head('note')).items() if k != CANDIDATES})
        self.assertFalse(self.paths['note'].read_bytes().endswith(b'\n') != self.head('note').endswith(b'\n'), 'the final newline (or its absence) is kept')
        diff = [l for l in git(self.repo, 'diff', 'HEAD', '--', self.store.git.rel(self.paths['note'])).splitlines() if l[:1] in '+-' and l[:3] not in ('+++', '---')]
        self.assertEqual({l[0] for l in diff}, {'-', '+'})
        self.assertTrue(all('stare' in l or 'nota_editor' in l or 'grup' in l or l[1:].strip() in ('{', '}', '},', '],', ']', '"selector": {') or 'selector' in l
                            or l[1:].startswith('      ') or l[1:].startswith('        ') for l in diff), diff)

    # -- a batch that proposes a refused candidate again -----------------------------------------------------------

    def test_a_candidate_that_equals_an_excluded_one_is_shown_with_the_refusal(self):
        self.decide(self.cid('cui'), 'exclude', note='Nu este CUI: este un cod intern.')
        again = {'grup': 'cui', 'selector': {**copy.deepcopy(self.selectors['cui']), 'context': 'Alt text de context, același câmp.'}}
        self.put_candidates(self.items() + [again])
        self.assertEqual(self.errors(), [], 'a repeated proposal is no error: the owner decides again')
        pairs = repeated_exclusions(self.items())
        self.assertEqual([(o['selector']['context'], e['nota_editor']) for o, e in pairs], [(again['selector']['context'], 'Nu este CUI: este un cod intern.')])
        view = self.store.candidate(self.rows()[-1]['id'])
        self.assertEqual(len(view['warnings']), 1)
        self.assertIn('Nu este CUI: este un cod intern.', view['warnings'][0])
        self.assertEqual(self.store.candidate(self.cid('cui', 'exclus'))['warnings'], [], 'the excluded one carries no warning')
        self.assertEqual(self.store.candidate(self.cid('judet'))['warnings'], [])

    # -- the check panel and the public build ---------------------------------------------------------------------

    def test_the_check_panel_counts_the_open_candidates_and_the_public_diff_stays_empty(self):
        self.assertEqual(self.store.git_panel()['candidates'], {'open': 3, 'excluded': 0, 'confirmed': 0})
        self.decide(self.cid('cui'), 'confirm')
        self.decide(self.cid('judet'), 'exclude', note='Nu.')
        panel = self.store.git_panel()
        self.assertEqual(panel['candidates'], {'open': 1, 'excluded': 1, 'confirmed': 1})
        self.assertEqual(panel['public'], {'available': True, 'lines': []}, 'a candidate does not change the public build')
        self.assertEqual({Path(f['path']).name for f in panel['files']}, {'inventar-concepte.json', 'inventar-note.json'})
        self.assertTrue(any(c.startswith('git add') and 'inventar-note.json' in c for c in panel['commands']))


class CandidateHttp(CandidateFixture):
    """The candidate routes over HTTP, on the same temporary copy."""
    call = Http.call

    def setUp(self):
        super().setUp()
        self.server = review_ui.make_server(self.store, 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_the_queue_the_detail_and_a_decision_over_http(self):
        status, state, _ = self.call('GET', '/api/state')
        self.assertEqual((status, [c['group'] for c in state['candidates']], state['progress']['candidates']['open']), (200, list(self.REVIEWED), 3))
        cid = state['candidates'][1]['id']
        status, view, _ = self.call('GET', f'/api/candidate/{cid}')
        self.assertEqual((status, view['group']['id'], view['stare']), (200, 'judet', 'propus'))
        status, answer, _ = self.call('POST', f'/api/candidate/{cid}/decide', {'action': 'exclude', 'note': 'Nu.', 'hashes': view['hashes']})
        self.assertEqual((status, answer['item']['stare'], answer['state']['progress']['candidates']['open']), (200, 'exclus', 2), answer)
        status, answer, _ = self.call('POST', f'/api/candidate/{cid}/decide', {'action': 'confirm', 'hashes': view['hashes']})
        self.assertEqual((status, answer['reload']), (409, True), 'the hashes of the page are old now')
        status, view, _ = self.call('GET', f'/api/candidate/{cid}')
        status, answer, _ = self.call('POST', f'/api/candidate/{cid}/decide', {'action': 'reset', 'hashes': view['hashes']})
        self.assertEqual((status, answer['item']['stare']), (200, 'propus'))
        self.assertEqual(self.both(), self.head_both())

    def test_the_candidate_routes_refuse_a_wrong_identifier_a_wrong_token_and_a_wrong_body(self):
        cid = self.rows()[0]['id']
        hashes = {k: self.hashes()[k] for k in ('concepte', 'note')}
        before = self.both()
        self.assertEqual(self.call('GET', '/api/candidate/1-ffffffffffff')[0], 404)
        self.assertEqual(self.call('GET', '/api/candidate/x')[0], 404)
        self.assertEqual(self.call('POST', f'/api/candidate/{cid}/decide', {'action': 'exclude', 'note': 'x', 'hashes': hashes}, token=False)[0], 403)
        self.assertEqual(self.call('POST', f'/api/candidate/{cid}/decide', {'action': 'exclude', 'note': 'x', 'hashes': hashes}, host='evil.example')[0], 403)
        self.assertEqual(self.call('POST', f'/api/candidate/{cid}/decide', {'action': 'nonsense', 'hashes': hashes})[0], 400)
        self.assertEqual(self.call('POST', f'/api/candidate/{cid}/decide', {'action': 'exclude', 'hashes': hashes})[0], 400, 'a note is needed')
        self.assertEqual(self.call('POST', '/api/candidate/1-ffffffffffff/decide', {'action': 'exclude', 'note': 'x', 'hashes': hashes})[0], 409)
        self.assertEqual(self.call('POST', '/api/candidate/x/decide', {'action': 'exclude', 'note': 'x', 'hashes': hashes})[0], 404)
        self.assertEqual(self.both(), before)

    def test_the_page_has_the_candidate_tab(self):
        status, page, _ = self.call('GET', '/', token=False)
        self.assertIn('id="tab-candidates"', page)
        status, script, _ = self.call('GET', '/assets/review_ui.js', token=False)
        self.assertIn('/api/candidate/', script)


class CandidateRules(unittest.TestCase):
    """The rules of the candidate list that need no data root."""
    GROUPS = [{'id': 'g', 'label': 'G', 'definition': 'D', 'stare': 'revizuit', 'decizie_editor': 'ok', 'selectors': [{'projects': ['p'], 'names': ['a'], 'stare': 'confirmat'}]},
              {'id': 'h', 'label': 'H', 'definition': 'D', 'selectors': [{'projects': ['p'], 'names': ['b']}]}]

    def candidate(self, **fields):
        return {'grup': 'g', 'selector': {'projects': ['p'], 'names': ['c']}, **fields}

    def errors(self, *items):
        return validate_candidates(list(items), self.GROUPS, {'p'})

    def test_a_valid_open_or_excluded_candidate_has_no_error(self):
        self.assertEqual(self.errors(self.candidate(), self.candidate(stare='propus'), self.candidate(stare='exclus', nota_editor='Nu.')), [])
        self.assertEqual(validate_candidates(None, self.GROUPS), [])
        self.assertEqual(validate_candidates([], self.GROUPS), [])

    def test_each_rule_has_its_error(self):
        cases = [(self.candidate(stare='gata'), 'unknown candidate state'), (self.candidate(stare='exclus'), 'needs nota_editor'),
                 (self.candidate(stare='exclus', nota_editor=' '), 'needs nota_editor'), (self.candidate(nota_editor=3), 'nota_editor must be text'),
                 (self.candidate(extra=1), 'unknown candidate key extra'), ({'selector': self.candidate()['selector']}, 'needs grup'),
                 ({'grup': 'g'}, 'needs a selector'), (self.candidate(selector={'projects': ['p']}), 'needs names or path'),
                 (self.candidate(selector={'projects': ['q'], 'names': ['c']}), 'unknown project q'),
                 (self.candidate(grup='x'), 'the group x does not exist'), (self.candidate(grup='h'), 'the group is propus'),
                 (self.candidate(selector={'projects': ['p'], 'names': ['a'], 'stare': 'confirmat'}), 'already holds this selector as member 1')]
        for item, text in cases:
            with self.subTest(text=text):
                self.assertTrue(any(text in e for e in self.errors(item)), self.errors(item))
        self.assertEqual(validate_candidates({'a': 1}, self.GROUPS), ['selectori_candidati: must be a list'])
        self.assertTrue(any('must be an object' in e for e in self.errors('text')))

    def test_an_excluded_candidate_is_history_and_needs_no_reviewed_group(self):
        self.assertEqual(self.errors(self.candidate(grup='x', stare='exclus', nota_editor='Nu.'), self.candidate(grup='h', stare='exclus', nota_editor='Nu.')), [])

    def test_the_blockers_of_a_candidate_name_their_reason(self):
        groups = {c['id']: c for c in self.GROUPS}
        self.assertEqual(candidate_blockers(self.candidate(), groups), [])
        self.assertEqual(candidate_blockers(self.candidate(grup='x'), groups), [('missing-group', 'x')])
        self.assertEqual(candidate_blockers(self.candidate(grup='h'), groups), [('group-state', 'propus')])
        self.assertEqual(candidate_blockers(self.candidate(selector={'projects': ['p'], 'names': ['a']}), groups), [('held', 1)])
        self.assertEqual(len({review_ui.blocker_text(*b) for b in [('missing-group', 'x'), ('group-state', 'propus'), ('held', 1)]}), 3)

    def test_the_identity_is_the_group_and_the_selector_whatever_their_key_order(self):
        a = {'grup': 'g', 'selector': {'projects': ['p'], 'names': ['c']}}
        b = {'selector': {'names': ['c'], 'projects': ['p']}, 'grup': 'g', 'stare': 'exclus', 'nota_editor': 'x'}
        self.assertEqual(candidate_key(a), candidate_key(b))
        self.assertNotEqual(candidate_key(a), candidate_key({**a, 'grup': 'h'}))
        self.assertNotEqual(candidate_key(a), candidate_key({**a, 'selector': {'projects': ['p'], 'names': ['d']}}))

    def test_equal_selection_ignores_text_and_the_order_of_lists(self):
        a = self.candidate(selector={'projects': ['p', 'q'], 'names': ['x', 'y'], 'path': ['$.x'], 'context': 'one'})
        b = self.candidate(selector={'projects': ['q', 'p'], 'names': ['y', 'x'], 'path': '$.x', 'context': 'two', 'nota': 'other'}, stare='exclus', nota_editor='Nu.')
        self.assertEqual(candidate_signature(a), candidate_signature(b))
        self.assertEqual(repeated_exclusions([a, b]), [(a, b)])
        for other in (self.candidate(grup='h', selector=a['selector']), self.candidate(selector={**a['selector'], 'names': ['x']}),
                      self.candidate(selector={**a['selector'], 'source': 'https://x.example/'}), self.candidate(selector={**a['selector'], 'role': 'camp-date'})):
            with self.subTest(other=other):
                self.assertEqual(repeated_exclusions([other, b]), [])
        self.assertEqual(repeated_exclusions([b, b]), [], 'an excluded candidate is not a new proposal')
        self.assertEqual(repeated_exclusions([a]), [])

    def test_the_candidate_key_returns_where_head_had_it(self):
        head = {'a': 1, 'b': 2, CANDIDATES: [1], 'c': 3}
        self.assertEqual(list(review_ui.with_candidates({'a': 1, 'b': 2, 'c': 3}, [1], head)), ['a', 'b', CANDIDATES, 'c'])
        self.assertEqual(list(review_ui.with_candidates({'a': 1, 'c': 3}, [1], head)), ['a', CANDIDATES, 'c'], 'the nearest key before it that is still there')
        self.assertEqual(list(review_ui.with_candidates({'c': 3}, [1], head)), [CANDIDATES, 'c'], 'no key before it is left: first')
        self.assertEqual(list(review_ui.with_candidates({'a': 1, 'c': 3}, [1], None)), ['a', 'c', CANDIDATES], 'without HEAD: at the end')
        self.assertEqual(list(review_ui.with_candidates({'a': 1, 'c': 3}, [1], {'a': 1})), ['a', 'c', CANDIDATES], 'HEAD without the key: at the end')
        self.assertEqual(review_ui.with_candidates({'a': 1, CANDIDATES: [1, 2]}, [2], head), {'a': 1, CANDIDATES: [2]}, 'the list is replaced in place')
        self.assertEqual(review_ui.with_candidates({'a': 1, CANDIDATES: [1]}, [], head), {'a': 1}, 'an empty list removes the key')

    def test_a_restored_candidate_goes_after_the_last_listed_candidate_that_head_lists_before_it(self):
        keys = [{'grup': 'g', 'selector': {'projects': ['p'], 'names': [n]}} for n in 'abcd']
        extra = {'grup': 'g', 'selector': {'projects': ['p'], 'names': ['new']}}
        self.assertEqual(review_ui.insert_position([], keys, 2), 0)
        self.assertEqual(review_ui.insert_position([keys[0], keys[3]], keys, 1), 1)
        self.assertEqual(review_ui.insert_position([keys[3]], keys, 1), 0)
        self.assertEqual(review_ui.insert_position([keys[0], keys[1]], keys, 3), 2)
        self.assertEqual(review_ui.insert_position([keys[0], extra, keys[3]], keys, 2), 1, 'a candidate that HEAD does not list does not count: it goes right after the first')

    def test_the_candidate_id_is_the_place_and_the_start_of_the_hash(self):
        item = self.candidate()
        self.assertEqual(review_ui.candidate_id(3, item), f'3-{candidate_key(item)[:12]}')
        self.assertTrue(review_ui.CANDIDATE_ID.match(review_ui.candidate_id(12, item)))


class EvidenceStates(unittest.TestCase):
    """The three states of the brief, on retained copies in a fixture folder; a recorded hash is required for `verificat`."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='review-ui-evidence-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.url = 'https://example.org/data'
        self.body = 'Datele vin din «Registrul Comerțului» și sunt publicate lunar.'
        (self.tmp / 'inventare/surse').mkdir(parents=True)
        (self.tmp / 'inventare/surse/a.json').write_text(json.dumps({'body': self.body}))
        sources = [{'url': self.url, 'snapshot': 'surse/a.json'}]
        self.evidence = review_ui.Evidence(review_ui.EvidenceLocator(self.tmp / 'inventare', self.tmp, sources))
        self.pin = review_ui.sha(self.body)

    def view(self, **kw):
        return self.evidence.view(self.url, **{'fragment': 'Registrul Comerțului', **kw})

    def test_matching_hash_and_fragment_is_verified(self):
        result = self.view(pin=self.pin[:16])
        self.assertEqual((result['state'], result['label'], result['kind']), ('verificat', 'verificat', 'sursa'))
        self.assertEqual(result['snippets'][0]['match'], 'Registrul Comerțului')
        self.assertTrue(result['snippets'][0]['before'].endswith('«'))

    def test_a_changed_body_is_schimbat(self):
        (self.tmp / 'inventare/surse/a.json').write_text(json.dumps({'body': self.body + ' Text nou.'}))
        fresh = review_ui.Evidence(self.evidence.locator)
        result = fresh.view(self.url, pin=self.pin[:16], fragment='Registrul Comerțului')
        self.assertEqual((result['state'], result['label']), ('schimbat', 'schimbat'))
        self.assertTrue(result['fragment_found'], 'the page still says whether the fragment is there')

    def test_an_absent_copy_is_indisponibil_local(self):
        result = self.evidence.view('https://example.org/other', pin=self.pin[:16], fragment='x')
        self.assertEqual((result['state'], result['label'], result['snippets']), ('indisponibil', 'indisponibil local', []))

    def test_never_verificat_without_a_hash_check(self):
        result = self.view()
        self.assertEqual((result['state'], result['label']), ('fara-amprenta', 'fără amprentă'))
        self.assertEqual(result['snippets'][0]['match'], 'Registrul Comerțului', 'the fragment is still shown')
        self.assertNotEqual(self.evidence.view(self.url, needles=['registrul comertului'])['state'], 'verificat')

    def test_a_matching_hash_with_a_missing_fragment_is_flagged(self):
        result = self.view(pin=self.pin[:16], fragment='Alt text')
        self.assertEqual((result['state'], result['fragment_found']), ('fragment-lipsa', False))

    def test_needles_are_highlighted_without_regard_to_case_or_diacritics(self):
        result = self.evidence.view(self.url, needles=['registrul comertului'])
        self.assertEqual(result['snippets'][0]['match'], 'Registrul Comerțului')

    def test_the_kind_of_copy_named_by_a_pin_is_the_only_one_compared(self):
        (self.tmp / 'documentare').mkdir()
        (self.tmp / 'documentare/index.json').write_text(json.dumps({'entries': [{'pages': [{'final_url': self.url, 'state': 'colectat', 'snapshot': 'pagini/a.json'}]}]}))
        (self.tmp / 'documentare/pagini').mkdir()
        (self.tmp / 'documentare/pagini/a.json').write_text(json.dumps({'text': 'Alt text colectat.'}))
        locator = review_ui.EvidenceLocator(self.tmp / 'inventare', self.tmp, [{'url': self.url, 'snapshot': 'surse/a.json'}])
        evidence = review_ui.Evidence(locator)
        self.assertEqual(evidence.view(self.url, pin=self.pin[:16], fragment='Registrul', kind='sursa')['state'], 'verificat')
        self.assertEqual(evidence.view(self.url, pin=self.pin[:16], fragment='Registrul', kind='documentatie')['state'], 'schimbat')
        self.assertEqual(evidence.view(self.url, pin=self.pin[:16], fragment='Registrul', kind='cache')['state'], 'indisponibil')

    def test_the_tracked_provider_proofs_of_the_real_root_read_their_local_copies_when_present(self):
        store = Store(common.PUBLIC_ROOT)
        views = [store.provider(f'D{n}')['evidence'] for n in range(147, 163)]
        states = {v['state'] for v in views if v}
        self.assertLessEqual(states, {'verificat', 'indisponibil'}, 'a changed or unpinned copy would need a person to read it')


class PublicPayload(Fixture):
    """The public payload follows the accepted provider relations only."""

    def build(self, name):
        site = self.tmp / name
        done = subprocess.run([sys.executable, str(review_ui.SCRIPTS / 'build.py'), '--data-dir', str(self.root), '--site-dir', str(site), '--allow-draft'],
                              capture_output=True, text=True, cwd=common.ROOT)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads((site / 'data.json').read_text())
        payload.pop('generated', None)
        return payload

    def sources(self, payload):
        return {e['slug']: e['dataSources'] for e in payload['items'] if e.get('dataSources')}

    def test_payload_changes_only_when_a_provider_is_accepted(self):
        base = self.build('site-base')
        self.provider('D133', 'reject')
        self.provider('D134', 'defer')
        self.provider('D153', 'duplicate', duplicate_of='D140')
        self.group('populatie', 'amanat', note='Mai târziu.')
        self.assertEqual(self.build('site-closed'), base, 'reject, defer, duplicate and group states leave the public payload unchanged')
        self.accept('D132', 'ANAF', 'https://demoanaf.ro/')
        accepted = self.build('site-accepted')
        before, after = self.sources(base), self.sources(accepted)
        self.assertEqual({k for k in set(before) | set(after) if before.get(k) != after.get(k)}, {'demoanaf'})
        self.assertIn({'name': 'ANAF', 'evidence': 'https://demoanaf.ro/'}, after['demoanaf'])
        self.assertEqual(len(after['demoanaf']), len(before.get('demoanaf', [])) + 1)
        stripped = lambda payload: {**payload, 'items': [dict(e, dataSources=None) if e['slug'] == 'demoanaf' else e for e in payload['items']]}
        self.assertEqual(stripped(accepted), stripped(base), 'nothing but dataSources of demoanaf differs')


class ReportAndRoot(Fixture):
    def test_the_report_counts_decided_providers_and_groups_by_state(self):
        data = inventory_report.load(self.root)
        state = inventory_report.review_state(data)
        self.assertEqual((state['provider_items'], state['provider_states']['deschis'], state['group_states']['propus']), (31, 31, 30))
        self.accept('D132', 'ANAF', 'https://demoanaf.ro/')
        self.member('populatie', 1, 'exclude', note='Alt sens.')
        self.group('populatie', 'respins', note='Nu.')
        state = inventory_report.review_state(inventory_report.load(self.root))
        self.assertEqual((state['provider_states']['acceptat'], state['provider_states']['deschis'], state['group_states']['respins'],
                          state['member_states']['exclus']), (1, 30, 1, 1))
        members = inventory_report.membership(inventory_report.load(self.root))
        self.assertFalse(any('populatie' in m['concepts'] for m in members.values()), 'a rejected group has no members in the report')

    def test_default_data_root_and_the_command(self):
        self.assertEqual(common.PUBLIC_ROOT, REAL / 'integrare', 'the tool defaults to the public root')
        done = subprocess.run([sys.executable, str(review_ui.SCRIPTS / 'review_ui.py'), '--data-dir', str(self.tmp / 'none'), '--port', '0'],
                              capture_output=True, text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('not a taxonomy v2 data root', done.stderr)

    def test_the_build_never_copies_the_review_tool_into_a_site_directory(self):
        site = self.tmp / 'site-out'
        done = subprocess.run([sys.executable, str(review_ui.SCRIPTS / 'build.py'), '--data-dir', str(self.root), '--site-dir', str(site), '--allow-draft'],
                              capture_output=True, text=True, cwd=common.ROOT)
        self.assertEqual(done.returncode, 0, done.stderr)
        found = [p.name for p in site.rglob('*') if 'review_ui' in p.name or p.suffix == '.py']
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()
