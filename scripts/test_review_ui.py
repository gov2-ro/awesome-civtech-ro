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
from inventory_concepts import (check_concepts, selector_matches, validate_concept, validate_group_state, validate_selector)
from inventory_site import publish_finder, variable_matches
from review_ui import ReviewError, Store

REAL = common.PUBLIC_ROOT.parent
REAL_FILES = [common.PUBLIC_ROOT / 'revizuire.csv', common.PUBLIC_ROOT / 'relatii.csv', REAL / 'inventar-concepte.json']
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
    for real in REAL_FILES:
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
        publish_finder([dict(slug='p', name='P', kind='proiect')], root / 'integrare', root / 'site', {'p': (fields, sources)})
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
