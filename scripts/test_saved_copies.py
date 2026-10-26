"""Offline checks for pages that the owner saved from their own browser (`inventory.py --import-saved`, `collect_docs.py --import-saved`).

A site can answer every automated request with a security checkpoint and forbid automated extraction. The owner then saves the page by hand.
The copy is evidence with its own origin: it is never labelled as fetched, no request is made for it, and it is verified like a fetched body.
Every network call here is a fake or is absent. The fixture is the trimmed copy of https://harta-firmelor.ro/date used by the reader tests.
"""
import hashlib
import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import collect_docs
import inventory
from collect_docs import (KeepSaved, add_saved_page, is_saved, merge_refresh, restore, save, saved_copy, saved_errors, saved_page, saved_time)
from inventory import check_report, import_saved, restore_cache
from inventory_state import StateError, source_id
from test_inventory_state import Net, Workspace, docs_for, entry

FIXTURES = Path(__file__).parent / 'fixtures/text'
URL = 'https://p.example/date'
SAVED_AT = '2026-10-25T20:39:00+02:00'
NOW = datetime(2026, 10, 25, 19, 0, tzinfo=timezone.utc)
LLMS = ('# p.example\n\n> A map of firms.\n\nAutomated extraction of the data is not allowed. The terms forbid systematic extraction of the content.\n\n'
        '## Links\n\n- [Open data](https://p.example/date): aggregate figures as CSV, licence CC BY 4.0\n- [API](https://api.p.example/docs): keys on request\n')


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


class SavedCopyRecord(unittest.TestCase):
    def test_the_record_has_the_shape_of_a_body_and_says_who_made_it(self):
        raw = LLMS.encode()
        record = saved_copy('https://p.example/llms.txt', raw, SAVED_AT, '/home/owner/Downloads/llms saved.txt', 'why', now=NOW)
        self.assertEqual((record['state'], record['body'], record['content_type']), ('ok', LLMS, 'text/plain'))
        self.assertIsNone(record['http_status'])
        self.assertEqual(record['fetched_at'], '2026-10-25T18:39:00+00:00', 'the saved-at time, in UTC, is the retrieval time')
        self.assertEqual((record['origine'], record['salvat_la']), ('copie-salvata-de-proprietar', SAVED_AT))
        self.assertEqual(record['sha256_fisier'], sha(raw))
        self.assertEqual(record['nume_fisier'], 'llms saved.txt', 'the directory of the owner is not kept')
        self.assertEqual(record['nota_copie'], 'why')
        self.assertTrue(is_saved(record))
        self.assertEqual(saved_errors(record), [])

    def test_a_fetched_response_is_not_a_saved_copy(self):
        self.assertFalse(is_saved({'state': 'ok', 'http_status': 200, 'body': 'x'}))
        self.assertFalse(is_saved(None))

    def test_the_time_needs_an_offset_and_cannot_be_in_the_future(self):
        for bad in ('2026-10-25T20:39:00', '2026-10-25', 'yesterday', '', '2026-10-26T20:39:00+02:00'):
            with self.assertRaises(ValueError, msg=bad):
                saved_copy(URL, b'<html>text</html>', bad, 'a.html', now=NOW)
        self.assertEqual(saved_time('2026-10-25T18:39:00Z', NOW).utcoffset().total_seconds(), 0)

    def test_files_that_cannot_be_kept_as_text_are_refused(self):
        for raw, reason in ((b'', 'empty'), (b'   \n', 'blank'), (b'PK\x03\x04binary', 'zip'), (b'%PDF-1.7 ...', 'pdf'), (b'caf\xe9', 'latin-1'),
                            (b'a' * (collect_docs.MAX_BYTES + 1), 'too large')):
            with self.assertRaises(ValueError, msg=reason):
                saved_copy(URL, raw, SAVED_AT, 'a.html', now=NOW)
        with self.assertRaises(ValueError):
            saved_copy('ftp://p.example/a', b'text', SAVED_AT, 'a.html', now=NOW)

    def test_a_record_with_a_status_a_wrong_time_or_no_hash_is_inconsistent(self):
        record = saved_copy(URL, b'<html>text</html>', SAVED_AT, 'a.html', now=NOW)
        self.assertTrue(any('HTTP status' in p for p in saved_errors({**record, 'http_status': 200})))
        self.assertTrue(any('fetched_at' in p for p in saved_errors({**record, 'fetched_at': '2026-10-25T20:39:00+00:00'})))
        self.assertTrue(any('SHA-256' in p for p in saved_errors({**record, 'sha256_fisier': 'abc'})))
        self.assertTrue(saved_errors({**record, 'salvat_la': '2026-10-25T20:39:00'}))


class SavedSource(unittest.TestCase):
    """The page `date` saved by the owner becomes a source of project `p`, read by the reader that the registry names."""

    def setUp(self):
        self.work = Workspace(self)
        self.entries = [entry('p', 'https://p.example/')]
        self.docs = {'p': docs_for('p', 'https://p.example/', [])}
        self.raw = (FIXTURES / 'harta-firmelor-date.html').read_bytes()
        self.spec = {'url': URL, 'metoda': 'adaugat-explicit', 'citire': {'tip': 'html-carduri-csv'}}
        self.response, _ = import_saved(self.work.out / 'surse', URL, self.raw, SAVED_AT, 'saved.html', 'note', now=NOW)
        self.state = self.run_offline()
        self.obs = self.work.out.parent

    def run_offline(self, **options):
        return self.work.run(self.entries, self.docs, None, offline=True, add_sources=[('p', self.spec)], **options)

    def source(self):
        return self.work.sources()[URL]

    def test_the_import_writes_the_same_cache_file_as_a_fetched_body(self):
        stored = json.loads((self.work.out / 'surse' / (source_id(URL) + '.json')).read_text())
        self.assertEqual((stored['body'], stored['sha256_fisier'], stored['origine']), (self.raw.decode(), sha(self.raw), 'copie-salvata-de-proprietar'))
        self.assertIsNone(stored['http_status'])

    def test_the_source_is_read_but_says_that_it_was_saved_and_never_fetched(self):
        source = self.source()
        self.assertEqual((source['origine'], source['state'], source['stare'], source['format']), ('copie-salvata-de-proprietar', 'ok', 'analizat', 'html-carduri-csv'))
        self.assertIsNone(source['http_status'])
        self.assertEqual(source['fetched_at'], '2026-10-25T18:39:00+00:00')
        self.assertEqual((source['sha256'], source['sha256_fisier']), (sha(self.raw), sha(self.raw)))
        self.assertEqual((len(source['campuri']), len(source['seturi'])), (12, 3))
        self.assertNotIn('ultima_incercare', source)
        self.assertEqual(self.work.profile('p')['campuri_din_surse'], 12)
        self.assertEqual(self.work.registry()[0]['metoda'], 'adaugat-explicit')

    def test_no_request_is_made_for_a_saved_address_even_when_a_refresh_is_forced(self):
        before = self.work.files()
        net = Net({URL: '<html>another page</html>'})
        self.work.run(self.entries, self.docs, net, force=True, add_sources=[('p', self.spec)])
        self.work.run(self.entries, self.docs, net, force_urls=[URL], add_sources=[('p', self.spec)])
        self.assertEqual(net.calls, [])
        self.assertEqual(self.work.files(), before)
        # The cache file is gone but the source is tracked: the run still makes no request and keeps the record.
        (self.work.out / 'surse' / (source_id(URL) + '.json')).unlink()
        state = self.work.run(self.entries, self.docs, net, add_sources=[('p', self.spec)])
        self.assertEqual(net.calls, [])
        self.assertEqual(state['report']['pastrate'], [URL])
        self.assertEqual(self.work.files(), before)

    def test_a_replay_from_the_cache_gives_the_same_bytes(self):
        first = self.work.files()
        self.run_offline()
        self.assertEqual(self.work.files(), first)
        again = Workspace(self)
        import_saved(again.out / 'surse', URL, self.raw, SAVED_AT, 'saved.html', 'note', now=NOW)
        again.run(self.entries, self.docs, None, offline=True, add_sources=[('p', self.spec)])
        for name in ('proiecte.json', 'seturi-date.json', 'campuri.csv', 'rezumat.csv', 'descoperiri.json'):
            self.assertEqual(again.files()[name], first[name], name)

    def test_the_evidence_check_verifies_the_retained_body_and_counts_it_as_saved(self):
        report = check_report(self.work.out, self.obs)
        self.assertEqual((report['errors'], report['verified'], [u for u in report['unavailable'] if u.startswith('http')]), ([], 1, []))
        self.assertEqual(report['saved'], {'total': 1, 'verified': 1, 'unavailable': 0})

    def test_an_altered_retained_body_is_an_error_and_is_not_counted_as_verified(self):
        path = self.work.out / self.source()['snapshot']
        stored = json.loads(path.read_text())
        stored['body'] = stored['body'].replace('Bilanțuri depuse pe an', 'Bilanțuri depuse pe luna')
        path.write_text(json.dumps(stored))
        report = check_report(self.work.out, self.obs)
        self.assertTrue(any('hash mismatch' in e for e in report['errors']))
        self.assertEqual((report['verified'], report['saved']['verified']), (0, 0))

    def test_a_body_that_is_not_the_recorded_file_a_status_or_a_wrong_time_is_an_error(self):
        path = self.work.out / 'seturi-date.json'
        original = json.loads(path.read_text())

        def errors_after(**changes):
            state = json.loads(json.dumps(original))
            state['surse'][0].update(changes)
            path.write_text(json.dumps(state))
            return check_report(self.work.out, self.obs)['errors']

        self.assertTrue(any('not the file that the owner saved' in e for e in errors_after(sha256_fisier=sha('another file'))))
        self.assertTrue(any('HTTP status' in e for e in errors_after(http_status=200)))
        self.assertTrue(any('fetched_at' in e for e in errors_after(fetched_at='2026-10-25T20:39:00+00:00')))
        self.assertTrue(any('SHA-256' in e for e in errors_after(sha256_fisier='')))
        path.write_text(json.dumps(original))
        self.assertEqual(check_report(self.work.out, self.obs)['errors'], [])

    def test_a_changed_field_or_dataset_record_is_an_error(self):
        path = self.work.out / 'seturi-date.json'
        state = json.loads(path.read_text())
        state['surse'][0]['seturi'][0]['randuri']['valoare'] = 38
        path.write_text(json.dumps(state))
        self.assertTrue(any('differ from the retained body' in e for e in check_report(self.work.out, self.obs)['errors']))

    def test_an_absent_body_is_reported_unavailable_and_never_verified(self):
        (self.work.out / self.source()['snapshot']).unlink()
        report = check_report(self.work.out, self.obs)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['verified'], 0)
        self.assertEqual([u for u in report['unavailable'] if u.startswith('http')], [URL])
        self.assertEqual(report['saved'], {'total': 1, 'verified': 0, 'unavailable': 1})

    def test_a_credential_in_the_saved_page_is_masked_and_the_two_hashes_differ_on_purpose(self):
        raw = self.raw + b'<script>const k = {apiKey: "abcdefghijklmnopqrstuvwxyz"}</script>'
        work = Workspace(self)
        response, _ = import_saved(work.out / 'surse', URL, raw, SAVED_AT, 'saved.html', now=NOW)
        self.assertEqual(response['redactari'], 1)
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz', response['body'])
        self.assertEqual(response['sha256_fisier'], sha(raw))
        work.run(self.entries, self.docs, None, offline=True, add_sources=[('p', self.spec)])
        source = work.sources()[URL]
        self.assertNotEqual(source['sha256'], source['sha256_fisier'])
        self.assertEqual(check_report(work.out, work.out.parent)['errors'], [])

    def test_a_fetched_body_is_never_replaced_but_a_failed_fetch_is(self):
        work = Workspace(self)
        work.run(self.entries, self.docs, Net({URL: '<html>fetched page</html>'}), add_sources=[('p', {'url': URL, 'metoda': 'adaugat-explicit'})])
        path = work.out / 'surse' / (source_id(URL) + '.json')
        before = path.read_bytes()
        with self.assertRaises(StateError):
            import_saved(work.out / 'surse', URL, self.raw, SAVED_AT, 'saved.html', now=NOW)
        self.assertEqual(path.read_bytes(), before)
        failed = Workspace(self)
        failed.run(self.entries, self.docs, Net({}), add_sources=[('p', {'url': URL, 'metoda': 'adaugat-explicit'})])
        response, previous = import_saved(failed.out / 'surse', URL, self.raw, SAVED_AT, 'saved.html', now=NOW)
        self.assertIsNotNone(previous)
        self.assertEqual(json.loads((failed.out / 'surse' / path.name).read_text())['origine'], 'copie-salvata-de-proprietar')
        self.assertEqual(response['origine'], 'copie-salvata-de-proprietar')

    def test_a_failed_run_puts_the_previous_cache_back(self):
        cache = self.work.out / 'surse'
        path = cache / (source_id(URL) + '.json')
        fresh = Workspace(self)
        response, previous = import_saved(fresh.out / 'surse', URL, self.raw, SAVED_AT, 'saved.html', now=NOW)
        self.assertIsNone(previous)
        restore_cache(fresh.out / 'surse', URL, previous)
        self.assertFalse((fresh.out / 'surse' / path.name).exists())
        before = path.read_bytes()
        second, previous = import_saved(cache, URL, self.raw + b'<!-- newer -->', SAVED_AT, 'saved.html', now=NOW)
        self.assertNotEqual(path.read_bytes(), before)
        restore_cache(cache, URL, previous)
        self.assertEqual(path.read_bytes(), before)

    def test_a_newer_copy_replaces_the_source_and_keeps_the_earlier_version(self):
        old = self.source()
        import_saved(self.work.out / 'surse', URL, self.raw + b'<!-- newer -->', '2026-10-25T20:50:00+02:00', 'saved.html', now=NOW)
        self.run_offline()
        new = self.source()
        self.assertNotEqual(new['sha256'], old['sha256'])
        self.assertEqual(new['fetched_at'], '2026-10-25T18:50:00+00:00')
        self.assertEqual(new['versiuni_anterioare'], [{'sha256': old['sha256'], 'fetched_at': old['fetched_at'], 'snapshot': old['snapshot'],
                                                       'origine': 'copie-salvata-de-proprietar', 'salvat_la': SAVED_AT}])
        self.assertEqual(check_report(self.work.out, self.obs)['errors'], [])


class SavedDocumentation(unittest.TestCase):
    """A saved llms.txt joins the documentation index of its entry."""
    ENTRY = {'slug': 'p', 'url': 'https://p.example/'}
    LLMS_URL = 'https://p.example/llms.txt'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.obs = Path(self.tmp.name)
        self.docs = self.obs / 'documentare'
        self.response = saved_copy(self.LLMS_URL, LLMS.encode(), SAVED_AT, 'llms.txt', 'by hand', now=NOW)
        self.page = saved_page(self.ENTRY, self.response)
        self.failed = {'url': self.LLMS_URL, 'final_url': self.LLMS_URL, 'http_status': 429, 'state': 'eroare-http', 'kind': 'llms', 'scope': 'proiect'}
        self.record = {'slug': 'p', 'url': 'https://p.example/', 'state': 'documentatie-neconfirmata', 'inventory_completeness': 'neanalizat',
                       'pages': [{**self.failed, 'url': 'https://p.example/', 'final_url': 'https://p.example/', 'kind': 'pagina'}, self.failed]}

    def test_the_page_is_documentation_of_the_right_kind_and_scope_with_its_own_origin(self):
        page = self.page
        self.assertEqual((page['state'], page['kind'], page['scope'], page['origine']), ('colectat', 'llms', 'proiect', 'copie-salvata-de-proprietar'))
        self.assertIsNone(page['http_status'])
        self.assertEqual(page['sha256'], sha(page['text']))
        self.assertEqual(page['sha256_fisier'], sha(LLMS.encode()))
        self.assertIn(('https://p.example/date', 'Open data'), [tuple(link) for link in page['links']])

    def test_it_replaces_a_failed_page_and_makes_the_entry_documented(self):
        record = add_saved_page(self.record, self.page)
        self.assertEqual([p['state'] for p in record['pages']], ['eroare-http', 'colectat'])
        self.assertEqual(record['state'], 'documentatie-gasita')
        again = add_saved_page(record, saved_page(self.ENTRY, saved_copy(self.LLMS_URL, (LLMS + '\nMore.\n').encode(), SAVED_AT, 'llms.txt', now=NOW)))
        self.assertEqual(len(again['pages']), 2, 'a newer saved copy replaces the older one')

    def test_it_never_replaces_a_page_that_was_fetched_and_collected(self):
        fetched = {**self.failed, 'http_status': 200, 'state': 'colectat', 'text': LLMS, 'sha256': sha(LLMS)}
        with self.assertRaises(ValueError):
            add_saved_page({**self.record, 'pages': [fetched]}, self.page)

    def test_a_saved_address_is_not_requested_and_the_saved_page_stays_without_a_failed_attempt(self):
        record = add_saved_page(self.record, self.page)

        class Fetch:
            requests = 0

            def __init__(self):
                self.calls = []

            def __call__(self, url, sample=None):
                self.calls.append(url)
                return {'url': url, 'final_url': url, 'http_status': 429, 'fetched_at': '2026-10-26T00:00:00+00:00', 'state': 'eroare-http', 'error': 'HTTP Error 429'}

        fetch = Fetch()
        fresh = collect_docs.collect(self.ENTRY, KeepSaved(fetch, {self.LLMS_URL}))
        self.assertNotIn(self.LLMS_URL, fetch.calls)
        self.assertIn('https://p.example/', fetch.calls, 'the other addresses still follow the ordinary rules')
        merged = merge_refresh(record, fresh)
        saved = next(p for p in merged['pages'] if p['url'] == self.LLMS_URL)
        self.assertEqual(saved, next(p for p in record['pages'] if p['url'] == self.LLMS_URL))
        self.assertNotIn('ultima_incercare', saved)
        self.assertEqual(merged['state'], 'documentatie-gasita')

    def test_the_index_round_trips_and_the_evidence_check_verifies_the_retained_text(self):
        save({'p': add_saved_page(self.record, self.page)}, self.docs)
        page = next(p for p in restore(self.docs)['p']['pages'] if p['url'] == self.LLMS_URL)
        self.assertEqual((page['text'], page['origine']), (self.page['text'], 'copie-salvata-de-proprietar'))
        work = Workspace(self)
        work.run([entry('p', 'https://p.example/')], {}, None, offline=True)
        report = check_report(work.out, self.obs)
        self.assertEqual((report['errors'], report['saved']), ([], {'total': 1, 'verified': 1, 'unavailable': 0}))
        self.assertEqual(report['verified'], 0, 'a documentation page is not a source body')
        snapshot = self.docs / next(p for p in json.loads((self.docs / 'index.json').read_text())['entries'][0]['pages'] if p.get('origine'))['snapshot']
        stored = json.loads(snapshot.read_text())
        snapshot.write_text(json.dumps({**stored, 'text': stored['text'] + ' edited'}))
        altered = check_report(work.out, self.obs)
        self.assertTrue(any('Saved page text hash differs' in e for e in altered['errors']))
        self.assertEqual(altered['saved']['verified'], 0)
        snapshot.unlink()
        absent = check_report(work.out, self.obs)
        self.assertEqual(absent['errors'], [])
        self.assertEqual(absent['saved'], {'total': 1, 'verified': 0, 'unavailable': 1})
        self.assertIn('documentation: p ' + self.LLMS_URL, absent['unavailable'])


class CommandLine(unittest.TestCase):
    def run_main(self, *argv):
        with patch('sys.argv', ['inventory.py', *argv]), self.assertRaises(SystemExit) as raised:
            inventory.main()
        return raised.exception.code

    def test_the_import_needs_its_time_and_refuses_options_that_could_make_a_request(self):
        with patch('sys.stderr'):
            self.assertEqual(self.run_main('--import-saved', 'p', URL, 'x.html'), 2)
            self.assertEqual(self.run_main('--import-saved', 'p', URL, 'x.html', '--saved-at', SAVED_AT, '--force'), 2)
            self.assertEqual(self.run_main('--import-saved', 'p', URL, 'x.html', '--saved-at', SAVED_AT, '--dry-run'), 2)
            self.assertEqual(self.run_main('--import-saved', 'p', URL, 'x.html', '--saved-at', SAVED_AT, '--only', 'q'), 2)
            self.assertEqual(self.run_main('--saved-at', SAVED_AT), 2)

    def test_a_specification_of_the_same_run_finds_its_fragment_in_the_copy_and_no_request_is_made(self):
        # The copy is in the cache before the specifications are resolved, so a specification can locate a fragment in it (`cache: true`).
        url = 'https://p.example/data.csv'
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            copy, spec, out = tmp / 'data.csv', tmp / 'spec.json', tmp / 'inventare'
            copy.write_text('year,county\n2020,AB\n')
            spec.write_text(json.dumps([{'proiect': 'p', 'url': url, 'metoda': 'adaugat-explicit', 'locate': {'cache': True, 'pagina': url, 'text': 'year,county'},
                                         'dovezi': [{'cache': True, 'pagina': url, 'text': '2020,AB', 'rol': 'rand-de-proba'}]}]))
            argv = ['inventory.py', '--import-saved', 'p', url, str(copy), '--saved-at', SAVED_AT, '--add-sources-file', str(spec), '--out', str(out)]
            with patch('sys.argv', argv), patch.object(inventory, 'load_catalogue', return_value=[entry('p', 'https://p.example/')]), \
                    patch.object(inventory, 'restore', return_value={'p': docs_for('p', 'https://p.example/', [])}), \
                    patch.object(inventory, 'load_vocabulary', return_value={'concepts': {}}), \
                    patch.object(socket, 'socket', side_effect=AssertionError('a request was made')), \
                    redirect_stdout(io.StringIO()) as output:
                code = inventory.main()
            self.assertEqual(code, 0, output.getvalue())
            records = [r for r in json.loads((out / 'descoperiri.json').read_text())['descoperiri'] if r['url'] == url]
            self.assertEqual(len(records), 1, 'the specification and the import make one registry record')
            self.assertEqual((records[0]['locator_stare'], records[0]['dovada']['fragment'], records[0]['dovada']['pointer']), ('cunoscut', 'year,county', '/body'))
            self.assertEqual([e['rol'] for e in records[0]['dovezi_suplimentare']], ['rand-de-proba'])
            self.assertEqual(check_report(out, tmp)['errors'], [])

    def test_a_specification_that_finds_nothing_leaves_no_copy_in_the_cache(self):
        url = 'https://p.example/data.csv'
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            copy, spec, out = tmp / 'data.csv', tmp / 'spec.json', tmp / 'inventare'
            copy.write_text('year,county\n2020,AB\n')
            spec.write_text(json.dumps([{'proiect': 'p', 'url': url, 'locate': {'cache': True, 'pagina': url, 'text': 'not in the copy'}}]))
            argv = ['inventory.py', '--import-saved', 'p', url, str(copy), '--saved-at', SAVED_AT, '--add-sources-file', str(spec), '--out', str(out)]
            with patch('sys.argv', argv), patch.object(inventory, 'load_catalogue', return_value=[entry('p', 'https://p.example/')]), \
                    patch.object(inventory, 'restore', return_value={'p': docs_for('p', 'https://p.example/', [])}), \
                    patch.object(inventory, 'load_vocabulary', return_value={'concepts': {}}), redirect_stdout(io.StringIO()) as output:
                code = inventory.main()
            self.assertEqual(code, 2, output.getvalue())
            self.assertIn('Evidence not found', output.getvalue())
            self.assertFalse((out / 'surse' / (source_id(url) + '.json')).exists(), 'the failed run puts the cache back')
            self.assertFalse((out / 'seturi-date.json').exists())


if __name__ == '__main__':
    unittest.main()
