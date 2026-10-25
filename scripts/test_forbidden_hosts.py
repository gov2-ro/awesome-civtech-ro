"""Offline checks for the list of hosts that no script requests (data/taxonomy-v2/colectare-interzisa.csv).

    python3 scripts/test_forbidden_hosts.py            # or: python3 -m unittest scripts/test_forbidden_hosts.py -v

A site can forbid automated access. The list names its host; every script that opens a connection to a project's site asks the list first,
and again for each redirect it follows. A listed host gets no request. The skipped result has the state `colectare-interzisa` with the
reason of the list. It is never an error, never a failed attempt, and never `offline`.

Stdlib only. Every test runs with its own temporary list and with name resolution and outbound connections switched off, so a request that
the guard misses fails the test instead of reaching a site. The libraries of profile.py, review.py and the browser are replaced by fakes;
the two tests that need the real `httpx` (its request hook on a redirect) are skipped when it is absent:

    uv run --offline --with httpx python3 -m unittest scripts/test_forbidden_hosts.py -v

The browser fake (`Browser`) copies what the real Chromium did when it was run by hand against a local server (2026-10-26, no outside host):
a Playwright route handler sees the first request of a navigation, but not the redirect hop of a request that it let through, so that hop
reached the server. With `--host-resolver-rules` the listed name could not be resolved, the hop never left the browser, and Playwright
reported it in the event `requestfailed`. The tests check that every browser path starts the browser with `common.browser_args()` and listens to that event.
"""
import asyncio
import contextlib
import email.message
import functools
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
import urllib.request
import urllib.response
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collect_docs  # noqa: E402
import common  # noqa: E402
import inventory  # noqa: E402
import render_pages  # noqa: E402
import validate  # noqa: E402
from common import ForbiddenHost  # noqa: E402
from inventory_state import RequestLog  # noqa: E402
from test_enrichment import Copy, rows_of  # noqa: E402
from test_inventory_state import Net, Workspace, docs_for, entry  # noqa: E402
from test_saved_copies import NOW, SAVED_AT  # noqa: E402

REAL_LIST = HERE.parent / 'data' / 'taxonomy-v2' / 'colectare-interzisa.csv'
MOTIV = 'Cererile automate sunt respinse (HTTP 429).'
LIST = f'gazda,motiv,dovada,data,nota\nharta-firmelor.ro,"{MOTIV}",https://harta-firmelor.ro/llms.txt,2026-10-24,\n'
STATE = 'colectare-interzisa'
LISTED = 'https://harta-firmelor.ro/'
HAS_HTTPX = importlib.util.find_spec('httpx') is not None


def load_script(name):
    """scripts/<name>.py under another module name (profile.py would clash with the stdlib `profile`)."""
    spec = importlib.util.spec_from_file_location(f'civtech_forbidden_{name}', HERE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hosts(urls):
    return sorted({common.host_of(u) for u in urls})


class Isolated(unittest.TestCase):
    """A temporary list in place of the real one, and no outbound connection: a request that gets past a guard fails the test."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.list_path = self.tmp / 'colectare-interzisa.csv'
        patcher = mock.patch.object(common, 'FORBIDDEN_PATH', self.list_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(common._forbidden_rows.cache_clear)
        self.write_list(LIST)
        for target in ('socket.getaddrinfo', 'socket.create_connection'):
            blocker = mock.patch(target, side_effect=AssertionError('a test opened a connection'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def write_list(self, text):
        self.list_path.write_text(text, encoding='utf-8')
        common._forbidden_rows.cache_clear()


# --- The check -------------------------------------------------------------------------------------------------------------


class Matching(Isolated):
    def test_the_exact_host_its_subdomains_and_www_match(self):
        for url in ('https://harta-firmelor.ro', 'http://harta-firmelor.ro/x?y=1#z', 'https://api.harta-firmelor.ro/v1', 'https://www.harta-firmelor.ro/',
                    'https://a.b.harta-firmelor.ro', 'https://HARTA-Firmelor.RO./', 'https://harta-firmelor.ro:8443/', 'https://user:pw@harta-firmelor.ro/',
                    '//harta-firmelor.ro/protocol-relative'):
            with self.subTest(url=url):
                row = common.forbidden(url)
                self.assertIsNotNone(row)
                self.assertEqual((row['gazda'], row['motiv']), ('harta-firmelor.ro', MOTIV))

    def test_a_look_alike_host_does_not_match(self):
        for url in ('https://notharta-firmelor.ro/', 'https://harta-firmelor.ro.example.org/', 'https://harta-firmelor.org/', 'https://xharta-firmelor.ro',
                    'https://firmelor.ro/', 'https://example.org/harta-firmelor.ro', 'https://example.org/?u=https://harta-firmelor.ro',
                    'https://harta-firmelor.ro@example.org/', 'https://harta-firmelor-ro.example/'):
            with self.subTest(url=url):
                self.assertIsNone(common.forbidden(url))

    def test_a_row_written_with_www_covers_the_bare_host(self):
        self.write_list('gazda,motiv\nwww.site.example,Motiv.\n')
        self.assertIsNotNone(common.forbidden('https://site.example/'))
        self.assertIsNotNone(common.forbidden('https://sub.site.example/'))

    def test_a_url_without_a_host_matches_nothing(self):
        for url in ('', 'harta-firmelor.ro', '/relative/path', 'mailto:a@harta-firmelor.ro', 'data:text/plain,harta-firmelor.ro', 'https://[::1', 'file:///x'):
            with self.subTest(url=url):
                self.assertIsNone(common.forbidden(url))

    def test_an_empty_or_absent_list_names_no_host(self):
        for text in ('', 'gazda,motiv,dovada,data,nota\n', 'gazda,motiv\n,Un rând fără gazdă.\n'):
            with self.subTest(text=text):
                self.write_list(text)
                self.assertIsNone(common.forbidden(LISTED))
        self.list_path.unlink()
        common._forbidden_rows.cache_clear()
        self.assertIsNone(common.forbidden(LISTED))
        self.assertEqual(common.forbidden_rows(), [])

    def test_a_list_without_its_columns_stops_the_run_instead_of_allowing_every_request(self):
        self.write_list('host,reason\nharta-firmelor.ro,x\n')
        with self.assertRaises(ValueError):
            common.forbidden(LISTED)

    def test_a_given_list_replaces_the_file(self):
        self.assertIsNone(common.forbidden(LISTED, rows=[]))
        self.assertIsNotNone(common.forbidden('https://other.example/', rows=[{'gazda': 'other.example', 'motiv': 'm'}]))

    def test_refuse_forbidden_raises_with_the_row_and_lets_other_hosts_through(self):
        common.refuse_forbidden('https://ok.example/')
        with self.assertRaises(ForbiddenHost) as raised:
            common.refuse_forbidden('https://api.harta-firmelor.ro/x')
        self.assertEqual((raised.exception.url, raised.exception.row['gazda']), ('https://api.harta-firmelor.ro/x', 'harta-firmelor.ro'))
        self.assertIn(STATE, str(raised.exception))

    def test_the_real_list_names_harta_firmelor_with_its_evidence_and_passes_validate(self):
        rows = list(common._forbidden_rows(str(REAL_LIST)))
        self.assertEqual(rows[0]['gazda'], 'harta-firmelor.ro')
        self.assertEqual((rows[0]['dovada'], rows[0]['data']), ('https://harta-firmelor.ro/llms.txt', '2026-10-24'))
        self.assertIn('429', rows[0]['motiv'])
        for url in ('https://harta-firmelor.ro/date', 'https://api.harta-firmelor.ro/', 'https://www.harta-firmelor.ro/'):
            self.assertIsNotNone(common.forbidden(url, rows=rows), url)
        found = []
        with mock.patch.object(validate, 'report', lambda *a: found.append(a)):
            validate.check_forbidden(REAL_LIST, common.load_catalogue())
        self.assertEqual(found, [])

    def test_the_browser_cannot_resolve_a_listed_host_or_its_subdomains(self):
        self.assertEqual(common.browser_args(), ['--host-resolver-rules=MAP harta-firmelor.ro ~NOTFOUND, MAP *.harta-firmelor.ro ~NOTFOUND'])
        self.write_list('gazda,motiv\nwww.a.example,m\nb.example,m\n')
        self.assertEqual(common.browser_args(), ['--host-resolver-rules=MAP a.example ~NOTFOUND, MAP *.a.example ~NOTFOUND, '
                                                 'MAP b.example ~NOTFOUND, MAP *.b.example ~NOTFOUND'])
        self.write_list('gazda,motiv\n')
        self.assertEqual(common.browser_args(), [])

    def test_a_failed_request_to_a_listed_host_is_noted_only_for_a_navigation(self):
        refused = []
        request = lambda url, navigation: types.SimpleNamespace(url=url, is_navigation_request=lambda: navigation)
        for url, navigation in (('https://ok.example/', True), (LISTED, False), ('https://www.harta-firmelor.ro/hop', True)):
            common.note_failed_request(request(url, navigation), refused)
        self.assertEqual(refused, ['https://www.harta-firmelor.ro/hop'])

    def test_the_route_handler_aborts_a_listed_request_and_notes_a_navigation(self):
        refused = []
        for url, navigation, outcome in (('https://ok.example/', True, 'continue'), (LISTED + 'x', True, 'abort'), ('https://api.harta-firmelor.ro/', False, 'abort')):
            route = FakeRoute(url, navigation)
            common.refuse_route(route, refused)
            self.assertEqual(route.outcome, outcome, url)
        self.assertEqual(refused, [LISTED + 'x'])  # a subresource is aborted too, but only a navigation is noted

    def test_the_skip_line_names_the_entry_the_reason_and_the_host(self):
        line = common.skip_line('harta-firmelor', common.forbidden(LISTED))
        self.assertTrue(all(part in line for part in (STATE, 'harta-firmelor', MOTIV, '[harta-firmelor.ro]')))


class FakeRoute:
    def __init__(self, url, navigation=True):
        self.request = types.SimpleNamespace(url=url, is_navigation_request=lambda: navigation)
        self.outcome = None

    def continue_(self):
        self.outcome = 'continue'

    def abort(self):
        self.outcome = 'abort'


# --- collect_docs.py and inventory.py ----------------------------------------------------------------------------------------


class Web(urllib.request.HTTPSHandler):
    """Answers in place of the network. `pages` maps a URL to a body, or to ('redirect', URL). `seen` lists every URL asked for."""

    def __init__(self, pages=None):
        super().__init__()
        self.pages, self.seen = dict(pages or {}), []

    def https_open(self, req):
        url = req.full_url
        self.seen.append(url)
        target = self.pages.get(url, 'A page. ' * 20)
        headers = email.message.Message()
        if isinstance(target, tuple):
            headers['Location'] = target[1]
            response = urllib.response.addinfourl(io.BytesIO(b''), headers, url, 302)
            response.msg = 'Found'
            return response
        headers['Content-Type'] = 'text/plain'
        response = urllib.response.addinfourl(io.BytesIO(target.encode()), headers, url, 200)
        response.msg = 'OK'
        return response


class FakeNetwork(Isolated):
    """collect_docs opens its connections through `build_opener`; the fake handler takes the place of the HTTPS handler."""

    def setUp(self):
        super().setUp()
        self.web = Web()
        real = urllib.request.build_opener
        patcher = mock.patch.object(collect_docs, 'build_opener', lambda *handlers: real(*handlers, self.web))
        patcher.start()
        self.addCleanup(patcher.stop)


class Fetcher(FakeNetwork):
    def test_a_listed_address_gets_no_request_no_log_row_no_cache_entry_and_no_budget(self):
        log = RequestLog(self.tmp / 'cereri.csv', 'lot')
        fetcher = collect_docs.Fetcher(timeout=1, max_requests=1, log=log)
        for url in (LISTED + 'llms.txt', 'https://api.harta-firmelor.ro/docs', LISTED + 'llms.txt'):
            result = fetcher(url)
            self.assertEqual((result['state'], result['motiv'], result['gazda']), (STATE, MOTIV, 'harta-firmelor.ro'), url)
            self.assertIsNone(result['http_status'])
            self.assertNotIn('error', result)
        self.assertEqual(fetcher(LISTED, sample=100)['state'], STATE)
        self.assertEqual((self.web.seen, fetcher.requests, log.rows(), fetcher.cache), ([], 0, [], {}))
        # The budget of one request is still there for a host that is not listed.
        self.assertEqual(fetcher('https://ok.example/a')['state'], 'ok')
        self.assertEqual((fetcher.requests, self.web.seen), (1, ['https://ok.example/a']))
        self.assertEqual(fetcher('https://ok.example/b')['state'], 'limita-cereri')

    def test_a_redirect_to_a_listed_host_is_not_followed(self):
        self.web.pages['https://ok.example/'] = ('redirect', 'https://www.harta-firmelor.ro/x')
        log = RequestLog(self.tmp / 'cereri.csv', 'lot')
        result = collect_docs.Fetcher(timeout=1, log=log)('https://ok.example/')
        self.assertEqual((result['state'], result['motiv']), (STATE, MOTIV))
        self.assertNotIn('error', result)
        self.assertEqual(self.web.seen, ['https://ok.example/'])  # the listed host received nothing
        self.assertEqual([(r['url'], r['stare']) for r in log.rows()], [('https://ok.example/', STATE)])  # the allowed host was asked, so the row stays

    def test_a_redirect_between_allowed_hosts_is_still_followed(self):
        self.web.pages['https://ok.example/'] = ('redirect', 'https://other.example/b')
        result = collect_docs.Fetcher(timeout=1)('https://ok.example/')
        self.assertEqual((result['state'], result['final_url']), ('ok', 'https://other.example/b'))
        self.assertEqual(self.web.seen, ['https://ok.example/', 'https://other.example/b'])


class DocumentationCollection(FakeNetwork):
    def entry_record(self, **changes):
        page = {'url': LISTED, 'final_url': LISTED, 'kind': 'pagina', 'scope': 'proiect', 'state': 'colectat', 'text': 'Evidence ' * 20,
                'sha256': 'a' * 64, 'fetched_at': '2026-10-01T00:00:00+00:00', 'links': [], 'headings': [], 'input_candidates': [], 'table_candidates': []}
        record = {'slug': 'harta-firmelor', 'url': 'https://harta-firmelor.ro/', 'state': 'documentatie-gasita', 'inventory_completeness': 'neanalizat', 'pages': [page]}
        return {**record, **changes}

    def test_a_listed_entry_is_not_collected_and_says_why(self):
        calls = []
        result = collect_docs.collect({'slug': 'h', 'url': 'https://harta-firmelor.ro'}, lambda url, *a: calls.append(url))
        self.assertEqual(calls, [])
        self.assertEqual((result['state'], result['motiv'], result['pages']), (STATE, MOTIV, []))
        self.assertNotIn('error', result)

    def test_an_allowed_entry_is_collected_as_before(self):
        calls = []
        result = collect_docs.collect({'slug': 'o', 'url': 'https://ok.example'}, lambda url, *a: calls.append(url) or {'url': url, 'final_url': url, 'state': 'eroare-http'})
        self.assertTrue(calls)
        self.assertNotEqual(result['state'], STATE)

    def test_the_earlier_record_stays_as_it_is_with_no_failed_attempt(self):
        old = self.entry_record()
        new = collect_docs.collect({'slug': 'harta-firmelor', 'url': 'https://harta-firmelor.ro'}, lambda *a: self.fail('a request was made'))
        self.assertEqual(collect_docs.merge_refresh(old, new), old)
        self.assertNotIn('ultima_incercare', json.dumps(collect_docs.merge_refresh(old, new)))
        # A page that a redirect turned into a refusal keeps its earlier copy, with no failed-attempt mark either.
        refused = {**old, 'pages': [{'url': LISTED, 'final_url': LISTED, 'kind': 'pagina', 'scope': 'proiect', 'state': STATE, 'motiv': MOTIV}]}
        merged = collect_docs.merge_refresh(old, refused)
        self.assertEqual(merged['pages'], old['pages'])
        self.assertEqual(merged['state'], 'documentatie-neconfirmata')

    def test_a_listed_entry_with_no_record_gets_one_with_the_state_and_the_reason(self):
        old = None
        new = collect_docs.collect({'slug': 'harta-firmelor', 'url': 'https://harta-firmelor.ro'}, lambda *a: self.fail('a request was made'))
        self.assertEqual(collect_docs.merge_refresh(old, new), new)

    def run_main(self, *argv):
        out = io.StringIO()
        with mock.patch.object(sys, 'argv', ['collect_docs.py', '--out', str(self.tmp / 'documentare'), *argv]), contextlib.redirect_stdout(out):
            code = collect_docs.main()
        return code, out.getvalue()

    def test_main_with_force_makes_no_request_for_a_listed_entry_and_keeps_the_index(self):
        out = self.tmp / 'documentare'
        collect_docs.save({'harta-firmelor': self.entry_record()}, out)
        collect_docs.save(collect_docs.restore(out), out)  # a restored record rewrites the same bytes from now on
        before = {p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}
        code, text = self.run_main('--only', 'harta-firmelor', '--force')
        self.assertEqual(code, 0)
        self.assertIn(STATE, text)
        self.assertIn('0 requests', text)
        self.assertEqual(self.web.seen, [])
        self.assertEqual({p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}, before)

    def test_main_records_a_listed_entry_that_has_no_record_without_a_request(self):
        code, text = self.run_main('--only', 'harta-firmelor')
        self.assertEqual((code, self.web.seen), (0, []))
        records = collect_docs.restore(self.tmp / 'documentare')
        self.assertEqual((records['harta-firmelor']['state'], records['harta-firmelor']['motiv'], records['harta-firmelor']['pages']), (STATE, MOTIV, []))


class InventorySources(FakeNetwork):
    P, Q = 'https://harta-firmelor.ro/', 'https://ok.example/'

    def setUp(self):
        super().setUp()
        self.csv_p, self.csv_q = self.P + 'data.csv', self.Q + 'data.csv'
        self.entries = [entry('p', self.P), entry('q', self.Q)]
        self.docs = {'p': docs_for('p', self.P, [self.csv_p]), 'q': docs_for('q', self.Q, [self.csv_q])}
        self.bodies = {self.csv_p: 'cui,value\n001,1\n', self.csv_q: 'county,total\nAB,1\n'}

    def test_a_listed_source_is_not_requested_and_the_run_says_so(self):
        work = Workspace(self)
        net = Net(self.bodies)
        for options in ({}, {'force': True}, {'force_urls': [self.csv_p]}):
            state = work.run(self.entries, self.docs, net, **options)
            self.assertEqual(state['report']['interzise'], [self.csv_p])
        self.assertEqual(set(net.calls), {self.csv_q})  # the allowed source is fetched; the listed one never
        source = work.sources()[self.csv_p]
        self.assertEqual((source['state'], work.profile('p')['campuri_din_surse']), ('necolectat', 0))
        for key in ('ultima_incercare', 'error', 'http_status'):
            self.assertNotIn(key, source)
        cached = {p.name.split('.')[0].split('-')[0] for p in (work.out / 'surse').glob('*.json')}  # the cache file and its snapshot
        self.assertEqual(cached, {work.sources()[self.csv_q]['id']})  # only the allowed source left a cache file
        self.assertEqual(state['report']['esuate'], [])  # not a failed refresh

    def test_a_body_retained_before_the_listing_stays_the_evidence_and_is_not_requested_again(self):
        work = Workspace(self)
        self.write_list('gazda,motiv\n')
        work.run(self.entries, self.docs, Net(self.bodies))
        before = work.files()
        self.write_list(LIST)
        net = Net(self.bodies)
        state = work.run(self.entries, self.docs, net, force=True)
        self.assertEqual(net.calls, [self.csv_q])
        self.assertEqual(state['report']['interzise'], [])
        for name in ('proiecte.json', 'campuri.csv', 'rezumat.csv'):
            self.assertEqual(work.files()[name], before[name], name)

    def test_an_owner_saved_copy_of_a_listed_host_is_kept_and_not_requested(self):
        spec = {'url': self.csv_p, 'metoda': 'adaugat-explicit'}
        work = Workspace(self)
        inventory.import_saved(work.out / 'surse', self.csv_p, b'cui,value\n001,1\n', SAVED_AT, 'saved.csv', now=NOW)
        work.run(self.entries, self.docs, None, offline=True, add_sources=[('p', spec)])
        net = Net(self.bodies)
        state = work.run(self.entries, self.docs, net, force=True, add_sources=[('p', spec)])
        self.assertEqual(net.calls, [self.csv_q])
        self.assertEqual(state['report']['interzise'], [])
        self.assertEqual(work.sources()[self.csv_p]['origine'], 'copie-salvata-de-proprietar')
        self.assertEqual(inventory.check_report(work.out, work.out.parent)['saved'], {'total': 1, 'verified': 1, 'unavailable': 0})

    def run_main(self, *argv):
        out = io.StringIO()
        with mock.patch.object(sys, 'argv', ['inventory.py', '--out', str(self.tmp / 'inventare'), *argv]), contextlib.redirect_stdout(out):
            code = inventory.main()
        return code, out.getvalue()

    def test_probe_makes_no_request_for_a_listed_address_and_leaves_no_log_row_or_cache_file(self):
        code, text = self.run_main('--probe', self.P + 'date', 'https://api.harta-firmelor.ro/x', self.Q + 'a.csv', '--lot', 'lot-z')
        self.assertEqual(code, 0)
        self.assertEqual(self.web.seen, [self.Q + 'a.csv'])
        self.assertIn('1 requests in this run', text)
        lines = [l for l in text.splitlines() if STATE in l]
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(MOTIV in l for l in lines))
        log = RequestLog(self.tmp / 'inventare' / 'jurnal-cereri.csv', 'lot-z')
        self.assertEqual([r['url'] for r in log.rows()], [self.Q + 'a.csv'])
        self.assertEqual(len(list((self.tmp / 'inventare' / 'surse').glob('*.json'))), 1)


# --- render_pages.py --------------------------------------------------------------------------------------------------------


class Browser:
    """Stands for Chromium behind Playwright, modelled on what the real one did when it was run on loopback (a local server, a listed name
    and a redirect between them): a route handler sees the first request of a navigation, but NOT the redirect hop of a request that it let
    through, so that hop reached the server. A browser launched with --host-resolver-rules cannot resolve a listed host: the hop fails,
    and Playwright reports it as a failed navigation request (event `requestfailed`). `reached` lists the requests that got to a server;
    without the resolver rule a listed host appears in it."""

    def __init__(self, redirects=None):
        self.redirects, self.launched, self.launch_args = dict(redirects or {}), 0, []
        self.opened, self.reached, self.listeners, self.handler, self.current = [], [], [], None, ''

    def on(self, event, handler):
        if event == 'requestfailed':
            self.listeners.append(handler)

    def unresolvable(self, url):
        host = urlsplit(url).hostname or ''
        for argument in self.launch_args:
            for rule in argument.partition('=')[2].split(','):
                words = rule.split()
                if len(words) == 3 and words[:1] == ['MAP'] and words[2] == '~NOTFOUND':
                    if host == words[1] or (words[1].startswith('*.') and host.endswith(words[1][1:])):
                        return True
        return False

    def settle(self, url, start, outcome):
        """What happens to one request after the route handler (if there was one) decided `outcome`."""
        self.opened.append((url, outcome))
        if outcome == 'abort' or self.unresolvable(url):
            for listener in self.listeners:
                listener(types.SimpleNamespace(url=url, is_navigation_request=lambda: True))
            raise RuntimeError('net::ERR_ABORTED' if outcome == 'abort' else 'net::ERR_NAME_NOT_RESOLVED at ' + start)
        self.reached.append(url)
        self.current = url

    def navigate(self, start):
        url, hop = start, False
        while url:
            if hop:
                outcome = 'hop'
            else:
                route = FakeRoute(url)
                self.handler(route)
                outcome = route.outcome
            self.settle(url, start, outcome)
            url, hop = self.redirects.get(url), True


class SyncPage:
    def __init__(self, browser):
        self.browser = browser

    def route(self, pattern, handler):
        self.browser.handler = handler

    def on(self, event, handler):
        self.browser.on(event, handler)

    def goto(self, url, **kw):
        self.browser.navigate(url)
        return types.SimpleNamespace(status=200)

    url = property(lambda self: self.browser.current)
    wait_for_timeout = lambda self, ms: None  # noqa: E731
    title = lambda self: 'Titlu'  # noqa: E731
    inner_text = lambda self, selector: 'Text'  # noqa: E731
    evaluate = lambda self, script: []  # noqa: E731
    content = lambda self: '<html></html>'  # noqa: E731
    close = lambda self: None  # noqa: E731


class SyncChromium:
    def __init__(self, browser):
        self.browser = browser

    def launch(self, **kw):
        self.browser.launched += 1
        self.browser.launch_args = kw.get('args', [])
        return self

    def new_context(self, **kw):
        return self

    def new_page(self, **kw):
        return SyncPage(self.browser)

    def route(self, pattern, handler):
        self.browser.handler = handler

    def on(self, event, handler):
        self.browser.on(event, handler)

    def close(self):
        pass


def fake_sync_playwright(browser):
    module = types.ModuleType('playwright.sync_api')
    chromium = SyncChromium(browser)

    class Manager:
        chromium = None

        def __enter__(self):
            return types.SimpleNamespace(chromium=chromium)

        def __exit__(self, *a):
            return False

        def start(self):
            return types.SimpleNamespace(chromium=chromium)

    module.sync_playwright, module.TimeoutError = Manager, type('TimeoutError', (Exception,), {})
    package = types.ModuleType('playwright')
    package.sync_api = module
    return {'playwright': package, 'playwright.sync_api': module}


class RenderPages(Isolated):
    def args(self, **changes):
        base = dict(data_dir=common.PUBLIC_ROOT, out_dir=self.tmp / 'randare', lot='', slug='s', wait_ms=0, timeout_ms=1, allow_host=[])
        return types.SimpleNamespace(**{**base, **changes})

    def test_listed_urls_are_dropped_before_the_browser_starts(self):
        browser = Browser()
        out = io.StringIO()
        with mock.patch.dict(sys.modules, fake_sync_playwright(browser)), contextlib.redirect_stdout(out):
            self.assertEqual(render_pages.render([LISTED + 'a', 'https://api.harta-firmelor.ro/b'], self.args()), [])
        self.assertEqual((browser.launched, browser.opened), (0, []))
        self.assertEqual(out.getvalue().count(STATE), 2)
        self.assertFalse((self.tmp / 'randare').exists())

    def test_only_the_allowed_urls_are_rendered(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(render_pages.without_forbidden([LISTED, 'https://ok.example/'], 's'), ['https://ok.example/'])

    def test_a_redirect_to_a_listed_host_never_reaches_it_and_is_recorded_without_an_error_state(self):
        browser = Browser({'https://ok.example/': 'https://www.harta-firmelor.ro/x'})
        log = self.tmp / 'log'
        with mock.patch.dict(sys.modules, fake_sync_playwright(browser)), contextlib.redirect_stdout(io.StringIO()):
            written = render_pages.render(['https://ok.example/'], self.args())
        self.assertEqual(browser.launch_args, common.browser_args())
        self.assertEqual(browser.opened, [('https://ok.example/', 'continue'), ('https://www.harta-firmelor.ro/x', 'hop')])
        self.assertEqual(browser.reached, ['https://ok.example/'])  # the hop is not a route decision; the resolver rule stopped it
        record = json.loads(written[0].read_text())
        self.assertEqual((record['stare'], record['motiv'], record['gazda_interzisa']), (STATE, MOTIV, 'harta-firmelor.ro'))
        self.assertIsNone(record['http_status'])
        self.assertFalse(log.exists())

    def test_an_allowed_page_is_rendered_as_before(self):
        browser = Browser()
        with mock.patch.dict(sys.modules, fake_sync_playwright(browser)), contextlib.redirect_stdout(io.StringIO()):
            written = render_pages.render(['https://ok.example/'], self.args())
        self.assertEqual(json.loads(written[0].read_text())['stare'], 'ok')
        self.assertEqual(browser.launched, 1)


# --- profile.py -------------------------------------------------------------------------------------------------------------


class Tree:
    """Enough of selectolax for the paths that these tests reach."""

    def __init__(self, html=''):
        pass

    def css(self, selector):
        return []

    def css_first(self, selector):
        return None


class Stream:
    def __init__(self, status, body, url):
        self.response = types.SimpleNamespace(status_code=status, headers={'content-type': 'text/plain'}, url=url, encoding='utf-8')
        self.response.aiter_bytes = self.chunks
        self.body = body

    async def chunks(self):
        yield self.body

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *a):
        return False


class Client:
    """A fake httpx.AsyncClient. `requests` lists every address it was asked for. `refuse` raises ForbiddenHost for an address, as the
    request hook of the real client does for a redirect hop."""

    def __init__(self, refuse=()):
        self.requests, self.refuse = [], set(refuse)

    def ask(self, url):
        self.requests.append(url)
        if url in self.refuse:
            raise ForbiddenHost(url, common.forbidden(LISTED) or {'gazda': 'x', 'motiv': 'm'})

    def stream(self, method, url, **kw):
        self.ask(url)
        return Stream(404, b'', url)

    async def get(self, url, **kw):
        self.ask(url)
        return types.SimpleNamespace(status_code=404, headers={}, text='', json=lambda: [] if 'cdx' in url else {}, raise_for_status=lambda: None)

    async def head(self, url, **kw):
        self.ask(url)
        return types.SimpleNamespace(status_code=404, headers={})


def stub_httpx(clients=None):
    """The part of httpx that profile.main and fetch_page use. Every AsyncClient created is kept in `clients`."""
    class AsyncClient(Client):
        def __init__(self, **kw):
            super().__init__()
            self.options = kw
            (clients if clients is not None else []).append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    return types.SimpleNamespace(ConnectError=type('ConnectError', (Exception,), {}), Timeout=lambda *a, **k: None, AsyncClient=AsyncClient)


class Profile(Isolated):
    @classmethod
    def setUpClass(cls):
        cls.profile = load_script('profile')

    def setUp(self):
        super().setUp()
        for name, value in (('httpx', stub_httpx()), ('HTMLParser', Tree), ('Image', object()), ('ImageOps', object())):
            patcher = mock.patch.object(self.profile, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def stderr(self):
        return contextlib.redirect_stderr(io.StringIO())

    def test_listed_entries_are_left_out_with_one_line_each(self):
        entries = [{'slug': 'h', 'url': 'https://harta-firmelor.ro'}, {'slug': 'o', 'url': 'https://ok.example'}, {'slug': 'a', 'url': 'https://api.harta-firmelor.ro/x'}]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            kept = self.profile.without_forbidden(entries)
        self.assertEqual([e['slug'] for e in kept], ['o'])
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(STATE in l and MOTIV in l for l in lines))

    def test_the_request_hook_raises_for_a_listed_request_and_lets_the_others_pass(self):
        request = lambda url: types.SimpleNamespace(url=url)  # httpx.Request has a URL whose str() is the address
        asyncio.run(self.profile.refuse_listed(request('https://ok.example/')))
        for url in ('https://www.harta-firmelor.ro/x', 'https://api.harta-firmelor.ro/'):
            with self.assertRaises(ForbiddenHost):
                asyncio.run(self.profile.refuse_listed(request(url)))

    def test_get_refuses_a_listed_address_before_the_client_is_asked(self):
        client = Client()
        with self.assertRaises(ForbiddenHost):
            asyncio.run(self.profile.get(client, LISTED + 'x', 100))
        self.assertEqual(client.requests, [])

    def test_a_listed_page_is_no_profile_result_and_no_error(self):
        client = Client()
        page = asyncio.run(self.profile.fetch_page(client, client, LISTED))
        self.assertEqual(client.requests, [])
        self.assertEqual(page['colectare_interzisa']['gazda'], 'harta-firmelor.ro')
        for key in ('error', 'http_status', 'ssl_error'):
            self.assertNotIn(key, page)

    def test_a_listed_entry_gets_no_request_and_no_profile(self):
        client = Client()
        with self.stderr():
            result = asyncio.run(self.profile.profile_one(asyncio.Semaphore(1), client, client, {'slug': 'h', 'url': 'https://harta-firmelor.ro'}))
        self.assertEqual((result, client.requests), (None, []))

    def test_a_redirect_to_a_listed_host_gives_no_profile_and_no_offline_status(self):
        client = Client(refuse=['https://ok.example/'])  # the hook of the real client raises on the hop
        with self.stderr():
            result = asyncio.run(self.profile.profile_one(asyncio.Semaphore(1), client, client, {'slug': 'o', 'url': 'https://ok.example/'}))
        self.assertIsNone(result)
        self.assertEqual(client.requests, ['https://ok.example/'])  # no icon, no wayback, no second attempt

    def test_an_allowed_entry_that_answers_404_is_still_offline(self):
        client = Client()
        with self.stderr():
            result = asyncio.run(self.profile.profile_one(asyncio.Semaphore(1), client, client, {'slug': 'o', 'url': 'https://ok.example/'}))
        self.assertEqual(result['status'], 'offline')

    def test_the_other_requests_to_a_site_are_guarded_too(self):
        client = Client()
        self.assertEqual(asyncio.run(self.profile.wp_latest(client, LISTED)), '')
        self.assertEqual(asyncio.run(self.profile.header_lastmod(client, LISTED)), '')
        self.assertEqual(asyncio.run(self.profile.sitemap_info(client, LISTED)), ('', 0))
        self.assertEqual(asyncio.run(self.profile.feed_latest(client, LISTED, [LISTED + 'feed'])), ('', ''))
        self.assertEqual(asyncio.run(self.profile.fetch_icon(client, 'h', [LISTED + 'favicon.ico', 'https://api.harta-firmelor.ro/i.png'])), '')
        self.assertEqual(asyncio.run(self.profile.fetch_image(client, 'h', [LISTED + 'og.png'])), None)
        self.assertEqual(client.requests, [])

    def test_link_favicons_skip_a_listed_host_and_keep_the_others(self):
        client = Client()
        entries = [{'slug': 'a', 'linkuri': f'{LISTED}date https://ok.example/y https://api.harta-firmelor.ro/docs'}]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            asyncio.run(self.profile.link_icons(client, entries, {}, True))
        self.assertTrue(client.requests)
        self.assertEqual([h for h in hosts(client.requests) if h.endswith('harta-firmelor.ro')], [])
        self.assertIn('https://ok.example/', client.requests)
        self.assertIn(STATE, err.getvalue())

    def test_the_clients_carry_the_request_hook_that_stops_redirects(self):
        clients = []
        c = Copy()
        self.addCleanup(c.close)
        path = c.root / 'observatii' / 'profil.csv'
        row = next(r for r in rows_of(path) if r['slug'] == 'harta-firmelor')
        with mock.patch.object(self.profile, 'httpx', stub_httpx(clients)), self.stderr():
            for mode in ((), ('--extra',)):
                with mock.patch.object(sys, 'argv', ['profile.py', '--data-dir', str(c.overlay), '--only', 'harta-firmelor', '--force', '--no-shots', *mode]):
                    asyncio.run(self.profile.main())
                self.assertEqual(next(r for r in rows_of(path) if r['slug'] == 'harta-firmelor'), row)
        self.assertTrue(clients)
        for client in clients:
            self.assertEqual(client.requests, [])
            self.assertEqual(client.options['event_hooks'], {'request': [self.profile.refuse_listed]})

    def test_main_leaves_the_stored_row_of_a_listed_entry_as_it_is(self):
        c = Copy()
        self.addCleanup(c.close)
        path = c.root / 'observatii' / 'profil.csv'
        before = next(r for r in rows_of(path) if r['slug'] == 'harta-firmelor')
        self.assertTrue(before['status'] and before['http_status'])
        clients = []
        err = io.StringIO()
        with mock.patch.object(self.profile, 'httpx', stub_httpx(clients)), contextlib.redirect_stderr(err), \
                mock.patch.object(sys, 'argv', ['profile.py', '--data-dir', str(c.overlay), '--only', 'harta-firmelor', '--force']):
            asyncio.run(self.profile.main())
        after = next(r for r in rows_of(path) if r['slug'] == 'harta-firmelor')
        self.assertEqual(after, before)
        self.assertNotIn(after['status'], ('offline', 'necunoscut'))
        self.assertEqual([c.requests for c in clients], [[]] * len(clients))
        self.assertEqual(err.getvalue().count(f'{STATE} harta-firmelor'), 1)


    def test_the_browser_pass_opens_no_listed_page_and_aborts_a_redirect_to_one(self):
        browser = AsyncBrowser({'https://ok.example/': 'https://www.harta-firmelor.ro/x'})
        rows = {'h': {'url': 'https://harta-firmelor.ro', 'status': 'blocat'}, 'o': {'url': 'https://ok.example/', 'status': 'blocat'},
                'f': {'url': 'https://fine.example/', 'status': 'blocat', 'image': {'src': 'img/og/f.webp'}}}
        err = io.StringIO()
        with mock.patch.dict(sys.modules, fake_async_playwright(browser)), contextlib.redirect_stderr(err):
            asyncio.run(self.profile.screenshots(rows, ['h', 'o', 'f']))
        self.assertEqual(browser.launch_args, common.browser_args())
        self.assertEqual(browser.opened, [('https://ok.example/', 'continue'), ('https://www.harta-firmelor.ro/x', 'hop'), ('https://fine.example/', 'continue')])
        self.assertEqual(browser.reached, ['https://ok.example/', 'https://fine.example/'])  # the listed host was never reached
        self.assertEqual((rows['h']['status'], rows['o']['status']), ('blocat', 'blocat'))  # not offline, not changed
        self.assertNotIn('image', rows['o'])
        self.assertEqual(rows['f']['status'], 'activ')  # a page that is not listed is confirmed as before
        self.assertEqual(err.getvalue().count(STATE), 2)

    @unittest.skipUnless(HAS_HTTPX, 'needs httpx (uv run --offline --with httpx python3 -m unittest ...)')
    def test_the_real_request_hook_stops_a_redirect_hop_and_a_direct_call(self):
        import httpx
        seen = []

        def handler(request):
            seen.append(str(request.url))
            if request.url.host == 'ok.example':
                return httpx.Response(302, headers={'location': 'https://www.harta-firmelor.ro/x'})
            if request.url.host == 'moved.example':
                return httpx.Response(302, headers={'location': 'https://other.example/b'})
            return httpx.Response(200, text='a page', headers={'content-type': 'text/plain'})

        async def run(action):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True,
                                         event_hooks={'request': [self.profile.refuse_listed]}) as client:
                return await action(client)

        with self.assertRaises(ForbiddenHost):
            asyncio.run(run(lambda client: self.profile.get(client, 'https://ok.example/', 1000)))
        self.assertEqual(seen, ['https://ok.example/'])  # the listed host received nothing
        page = asyncio.run(run(lambda client: self.profile.fetch_page(client, client, 'https://ok.example/')))
        self.assertIn('colectare_interzisa', page)
        self.assertNotIn('error', page)
        with self.assertRaises(ForbiddenHost):  # a call that does not go through get(): the hook alone stops it
            asyncio.run(run(lambda client: client.get('https://api.harta-firmelor.ro/x')))
        self.assertNotIn('api.harta-firmelor.ro', ' '.join(seen))
        seen.clear()
        r, body = asyncio.run(run(lambda client: self.profile.get(client, 'https://moved.example/', 1000)))  # between allowed hosts: followed
        self.assertEqual((body, seen), (b'a page', ['https://moved.example/', 'https://other.example/b']))


class AsyncRoute(FakeRoute):
    async def continue_(self):
        self.outcome = 'continue'

    async def abort(self):
        self.outcome = 'abort'


class AsyncBrowser(Browser):
    async def navigate_async(self, start):
        url, hop = start, False
        while url:
            if hop:
                outcome = 'hop'
            else:
                route = AsyncRoute(url)
                await self.handler(route)
                outcome = route.outcome
            self.settle(url, start, outcome)
            url, hop = self.redirects.get(url), True


def fake_async_playwright(browser):
    """Stands for playwright.async_api, with the behaviour of Browser."""
    class Page:
        async def goto(self, url, **kw):
            await browser.navigate_async(url)
            return types.SimpleNamespace(status=200)

        async def add_style_tag(self, **kw):
            pass

        async def wait_for_timeout(self, ms):
            pass

        async def title(self):
            return 'Titlu'

        async def close(self):
            pass

    class Context:
        async def route(self, pattern, handler):
            browser.handler = handler

        def on(self, event, handler):
            browser.on(event, handler)

        async def new_page(self):
            return Page()

    class Chrome:
        async def new_context(self, **kw):
            return Context()

        async def close(self):
            pass

    class Chromium:
        async def launch(self, **kw):
            browser.launched += 1
            browser.launch_args = kw.get('args', [])
            return Chrome()

    class Manager:
        async def __aenter__(self):
            return types.SimpleNamespace(chromium=Chromium())

        async def __aexit__(self, *a):
            return False

    module = types.ModuleType('playwright.async_api')
    module.async_playwright = Manager
    package = types.ModuleType('playwright')
    package.async_api = module
    return {'playwright': package, 'playwright.async_api': module}


# --- review.py ------------------------------------------------------------------------------------------------------------


class Review(Isolated):
    @classmethod
    def setUpClass(cls):
        cls.review = load_script('review')

    def raising(self, url='https://www.harta-firmelor.ro/x'):
        return ForbiddenHost(url, common.forbidden(url))

    def test_fetch_stops_a_listed_address_before_a_client_exists(self):
        with mock.patch.object(self.review, 'httpx', object()):  # object() has no Client: reaching httpx would be an AttributeError
            with self.assertRaises(ForbiddenHost):
                self.review.fetch(LISTED + 'x')

    def test_the_request_hook_raises_for_a_listed_request_and_lets_the_others_pass(self):
        request = lambda url: types.SimpleNamespace(url=url)
        self.review.refuse_listed(request('https://ok.example/'))
        for url in ('https://www.harta-firmelor.ro/x', 'https://api.harta-firmelor.ro/'):
            with self.assertRaises(ForbiddenHost):
                self.review.refuse_listed(request(url))

    def test_the_homepage_of_a_listed_host_is_no_page_and_no_error(self):
        with mock.patch.object(self.review, 'httpx', object()):
            page = self.review.homepage('https://harta-firmelor.ro')
        self.assertEqual(list(page), ['colectare_interzisa'])
        self.assertEqual(page['colectare_interzisa']['gazda'], 'harta-firmelor.ro')

    def test_a_redirect_found_by_the_download_or_by_the_browser_gives_the_same_result(self):
        with mock.patch.object(self.review, 'fetch', side_effect=self.raising()):
            self.assertEqual(list(self.review.homepage('https://ok.example/')), ['colectare_interzisa'])
        thin = self.review.Page('https://ok.example/', '<html></html>', 200)
        with mock.patch.object(self.review, 'fetch', return_value=thin), mock.patch.object(self.review, 'parse', return_value=('short', {}, {})), \
                mock.patch.object(self.review, 'render', side_effect=self.raising()):
            self.assertEqual(list(self.review.homepage('https://ok.example/')), ['colectare_interzisa'])

    def test_an_ordinary_failure_is_still_an_error(self):
        with mock.patch.object(self.review, 'fetch', side_effect=RuntimeError('boom')):
            self.assertIn('eroare', self.review.homepage('https://ok.example/'))

    def test_the_browser_render_refuses_a_listed_address_and_aborts_a_redirect_to_one(self):
        browser = Browser({'https://ok.example/': 'https://harta-firmelor.ro/x'})
        with mock.patch.dict(sys.modules, fake_sync_playwright(browser)), mock.patch.object(self.review, '_browser', None):
            with self.assertRaises(ForbiddenHost):
                self.review.render(LISTED)
            self.assertEqual(browser.launched, 0)
            with self.assertRaises(ForbiddenHost):
                self.review.render('https://ok.example/')
        self.assertEqual(browser.launch_args, common.browser_args())
        self.assertEqual(browser.opened, [('https://ok.example/', 'continue'), ('https://harta-firmelor.ro/x', 'hop')])
        self.assertEqual(browser.reached, ['https://ok.example/'])

    def run_main(self, c, page, *args):
        asked = []

        class Messages:
            def create(self, **kw):
                asked.append(kw)
                raise AssertionError('the API was called')

        fake = types.SimpleNamespace(Anthropic=lambda: types.SimpleNamespace(messages=Messages()))
        err = io.StringIO()
        with mock.patch.multiple(self.review, anthropic=fake, httpx=object(), HTMLParser=object(), homepage=page), \
                mock.patch.object(sys, 'argv', ['review.py', '--data-dir', str(c.overlay), '--workers', '1', *args]), contextlib.redirect_stderr(err):
            self.review.main()
        return asked, err.getvalue()

    def test_main_skips_a_listed_entry_before_any_download_or_question_and_keeps_its_answer(self):
        c = Copy()
        self.addCleanup(c.close)
        downloads = []
        asked, err = self.run_main(c, lambda url: downloads.append(url) or self.fail('a page was downloaded'), '--only', 'harta-firmelor')
        self.assertEqual((asked, downloads), ([], []))
        self.assertIn(f'{STATE} harta-firmelor', err)
        stored = c.root / 'observatii' / 'review' / 'raw.jsonl'
        self.assertNotIn('harta-firmelor', stored.read_text() if stored.exists() else '')
        self.assertFalse((c.root / 'observatii' / 'mentiuni_etichete.csv').exists() and 'harta-firmelor' in (c.root / 'observatii' / 'mentiuni_etichete.csv').read_text())

    def test_main_skips_an_entry_whose_download_ended_on_a_listed_host(self):
        c = Copy()
        self.addCleanup(c.close)
        row = common.forbidden(LISTED)
        asked, err = self.run_main(c, lambda url: {'colectare_interzisa': row}, '--only', '465')
        self.assertEqual(asked, [])
        self.assertIn(f'{STATE} 465', err)

    @unittest.skipUnless(HAS_HTTPX, 'needs httpx (uv run --offline --with httpx python3 -m unittest ...)')
    def test_the_real_client_does_not_follow_a_redirect_to_a_listed_host(self):
        import httpx
        seen = []

        def handler(request):
            seen.append(str(request.url))
            if request.url.host == 'ok.example':
                return httpx.Response(302, headers={'location': 'https://api.harta-firmelor.ro/x'})
            return httpx.Response(200, text='the listed host was reached')

        stub = types.SimpleNamespace(Client=functools.partial(httpx.Client, transport=httpx.MockTransport(handler)))
        with mock.patch.object(self.review, 'httpx', stub):
            with self.assertRaises(ForbiddenHost):
                self.review.fetch('https://ok.example/')
            self.assertEqual(seen, ['https://ok.example/'])
            self.assertEqual(list(self.review.homepage('https://ok.example/')), ['colectare_interzisa'])


# --- validate.py ----------------------------------------------------------------------------------------------------------


class ValidateList(Isolated):
    def findings(self, text, entries=None):
        self.write_list(text)
        found = []
        with mock.patch.object(validate, 'report', lambda *a: found.append(a)):
            validate.check_forbidden(self.list_path, entries)
        return [(level, line, message) for level, _, line, message in found]

    GOOD = 'gazda,motiv,dovada,data,nota\nharta-firmelor.ro,Motiv.,https://harta-firmelor.ro/llms.txt,2026-10-24,\n'

    def test_a_sound_file_has_no_finding(self):
        self.assertEqual(self.findings(self.GOOD), [])
        self.assertEqual(self.findings(LIST + 'site.example,"Cu virgulă, între ghilimele.","un citat",2026-01-02,o notă\n'), [])

    def test_a_missing_or_unknown_column_is_an_error(self):
        self.assertEqual([f[0] for f in self.findings('gazda,motiv,dovada,data\nharta-firmelor.ro,m,d,2026-10-24\n')], ['error'])
        self.assertIn('nota', self.findings('gazda,motiv,dovada,data\nharta-firmelor.ro,m,d,2026-10-24\n')[0][2])
        self.assertIn('altceva', self.findings('gazda,motiv,dovada,data,nota,altceva\n')[0][2])

    def test_a_value_that_is_not_a_host_name_is_an_error(self):
        for bad in ('https://harta-firmelor.ro', 'Harta-Firmelor.ro', 'harta-firmelor.ro/x', 'harta-firmelor', 'harta firmelor.ro', 'harta-firmelor.ro:80',
                    '-harta.ro', 'harta-.ro', '.harta.ro', 'harta..ro', ''):
            with self.subTest(host=bad):
                found = self.findings(f'gazda,motiv,dovada,data,nota\n{bad},m,d,2026-10-24,\n')
                self.assertEqual([f[0] for f in found], ['error'])

    def test_www_in_the_host_is_an_error_because_the_list_ignores_it(self):
        found = self.findings('gazda,motiv,dovada,data,nota\nwww.harta-firmelor.ro,m,d,2026-10-24,\n')
        self.assertEqual([f[0] for f in found], ['error'])
        self.assertIn('www', found[0][2])

    def test_a_duplicate_host_is_an_error_that_names_the_first_line(self):
        found = self.findings(self.GOOD + 'harta-firmelor.ro,alt motiv,d,2026-10-25,\n')
        self.assertEqual([(f[0], f[1]) for f in found], [('error', 3)])
        self.assertIn('2', found[0][2])

    def test_an_empty_reason_and_a_bad_date_are_errors(self):
        self.assertEqual([f[0] for f in self.findings('gazda,motiv,dovada,data,nota\nharta-firmelor.ro,,d,2026-10-24,\n')], ['error'])
        for bad in ('', '2026-13-01', '24.10.2026', '2026-02-30', '2026-1-1', 'ieri'):
            with self.subTest(date=bad):
                self.assertEqual([f[0] for f in self.findings(f'gazda,motiv,dovada,data,nota\nharta-firmelor.ro,m,d,{bad},\n')], ['error'])

    def test_a_missing_proof_is_only_a_warning(self):
        self.assertEqual([f[0] for f in self.findings('gazda,motiv,dovada,data,nota\nharta-firmelor.ro,m,,2026-10-24,\n')], ['warning'])

    def test_a_host_that_no_entry_uses_is_a_warning_not_an_error(self):
        entries = [{'slug': 'a', 'url': 'https://ok.example/'}, {'slug': 'b', 'url': ''}]
        found = self.findings(self.GOOD, entries)
        self.assertEqual([(f[0], f[1]) for f in found], [('warning', 2)])
        self.assertIn('harta-firmelor.ro', found[0][2])
        for url in ('https://harta-firmelor.ro', 'https://www.harta-firmelor.ro/x', 'https://api.harta-firmelor.ro/'):
            self.assertEqual(self.findings(self.GOOD, [{'slug': 'a', 'url': url}]), [], url)
        self.assertEqual(self.findings(self.GOOD, None), [])  # no catalogue to compare with: no warning

    def test_an_absent_file_is_an_error_because_it_would_leave_every_site_open(self):
        self.list_path.unlink()
        found = []
        with mock.patch.object(validate, 'report', lambda *a: found.append(a)):
            validate.check_forbidden(self.list_path, None)
        self.assertEqual([f[0] for f in found], ['error'])

    def test_the_command_exits_with_an_error_on_a_bad_list_and_cleanly_on_a_good_one(self):
        def run():
            validate.errors = validate.warnings = 0
            with mock.patch.object(sys, 'argv', ['validate.py']), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as raised:
                validate.main()
            return raised.exception.code

        self.write_list(LIST)
        self.addCleanup(lambda: setattr(validate, 'errors', 0))
        self.addCleanup(lambda: setattr(validate, 'warnings', 0))
        self.assertEqual(run(), 0)
        self.write_list('gazda,motiv,dovada,data,nota\nhttps://harta-firmelor.ro,m,d,2026-10-24,\n')
        self.assertEqual(run(), 1)


if __name__ == '__main__':
    unittest.main()
