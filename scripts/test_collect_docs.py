"""Offline checks for documentation collection, scope and evidence preservation."""
import json
import tempfile
import unittest
from pathlib import Path

from collect_docs import canonical, collect, kind_of, merge_refresh, parse_page, restore, save, scope_of


def response(url, body, content_type='text/html', state='ok'):
    return dict(url=url, final_url=url, state=state, body=body, content_type=content_type, http_status=200)


def html(body):
    return '<html><body>' + body + '</body></html>'


class DocumentationCollection(unittest.TestCase):
    def test_text_excludes_scripts_and_keeps_tables_inputs_and_headings(self):
        body = html('<a href>Missing link</a><script>Invented provider</script><h2>Metodologie</h2><p>' + 'Evidence ' * 20 +
                    '</p><table><tr><th>amount</th><th>RON</th></tr></table><input name="year" type="number">')
        parsed = parse_page(body, 'text/html', 'https://example.org/', 'pagina')
        self.assertNotIn('Invented provider', parsed['text'])
        self.assertEqual(parsed['table_candidates'], [['amount', 'RON']])
        self.assertEqual(parsed['input_candidates'][0]['name'], 'year')
        self.assertEqual(parsed['sections'][0]['kind'], 'metodologie')

    def test_html_fallback_is_not_an_llms_file(self):
        result = parse_page(html('Homepage ' * 30), 'text/html', 'https://example.org/llms.txt', 'llms')
        self.assertEqual(result['state'], 'html-in-loc-de-llms')
        self.assertEqual(result['text'], '')

    def test_markdown_llms_resolves_relative_links(self):
        result = parse_page('# Project\n' + 'Evidence ' * 20 + '\n[Method](./methodology/)', 'text/plain',
                            'https://example.org/project/llms.txt', 'llms')
        self.assertIn(('https://example.org/project/methodology/', 'Method'), result['links'])

    def test_scoped_paths_do_not_absorb_other_projects(self):
        self.assertEqual(scope_of('https://example.org/a/', 'https://example.org/a/method/'), 'proiect')
        self.assertEqual(scope_of('https://example.org/a/', 'https://example.org/b/'), 'gazda-comuna')
        self.assertEqual(scope_of('https://example.org/a/', 'https://example.org/llms.txt'), 'gazda-comuna')
        self.assertEqual(scope_of('https://example.org/a/', 'https://elsewhere.org/a/'), 'alta-gazda')

    def test_duplicate_homepage_is_not_a_methodology_document(self):
        start = 'https://example.org/'
        body = html('Ordinary homepage ' * 20)
        result = collect(dict(slug='a', url=start), lambda url: response(url, body))
        copies = [p for p in result['pages'] if p['state'] == 'copie-pagina-initiala']
        self.assertTrue(copies)
        self.assertEqual(result['state'], 'documentatie-neconfirmata')

    def test_inline_methodology_is_useful_without_another_page(self):
        body = html('<h2>Metodologie</h2><p>' + 'Evidence ' * 20 + '</p>')
        result = collect(dict(slug='a', url='https://example.org/'), lambda url: response(url, body))
        self.assertEqual(result['state'], 'documentatie-gasita')
        self.assertEqual(result['inventory_completeness'], 'neanalizat')

    def test_anchor_methodology_is_preserved_and_does_not_need_fallback(self):
        seen = []
        def fetch(url):
            seen.append(url)
            return response(url, html('<a href="#method">Metoda</a><p>' + 'Evidence ' * 20 + '</p>'))
        result = collect(dict(slug='a', url='https://example.org/'), fetch)
        self.assertEqual(result['state'], 'documentatie-gasita')
        self.assertEqual(result['pages'][0]['sections'][0]['url'], 'https://example.org/#method')
        self.assertNotIn('https://example.org/metodologie/', seen)

    def test_shared_llms_does_not_trigger_cross_project_crawl(self):
        seen = []
        def fetch(url):
            seen.append(url)
            if url == 'https://example.org/llms.txt':
                return response(url, '# Library\n' + 'Text ' * 30 + '\n[Method](https://example.org/b/methodology/)', 'text/plain')
            return response(url, '', state='eroare-http')
        result = collect(dict(slug='a', url='https://example.org/a/'), fetch)
        self.assertNotIn('https://example.org/b/methodology/', seen)
        self.assertEqual(result['state'], 'documentatie-neconfirmata')
        self.assertTrue(any(p['scope'] == 'gazda-comuna' and p['state'] == 'colectat' for p in result['pages']))

    def test_save_restore_preserves_evidence_and_partial_runs(self):
        record = collect(dict(slug='a', url='https://example.org/'),
                         lambda url: response(url, html('Evidence ' * 30)))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            save({'a': record}, out)
            restored = restore(out)
            self.assertEqual(restored['a']['pages'][0]['text'], record['pages'][0]['text'])
            self.assertEqual(restored['a']['pages'][0]['sha256'], record['pages'][0]['sha256'])
            self.assertNotIn('text', json.loads((out / 'index.json').read_text())['entries'][0]['pages'][0])
            save({**restored, 'b': dict(slug='b', url='', state='fara-url-http', pages=[], inventory_completeness='neanalizat')}, out)
            self.assertEqual(set(restore(out)), {'a', 'b'})

    def test_shared_snapshot_keeps_each_project_scope(self):
        page = collect(dict(slug='a', url='https://example.org/'), lambda url: response(url, html('Evidence ' * 30)))['pages'][0]
        first = dict(slug='a', url=page['url'], state='documentatie-gasita', inventory_completeness='neanalizat', pages=[page])
        second = dict(slug='b', url='https://example.org/project/', state='documentatie-neconfirmata',
                      inventory_completeness='neanalizat', pages=[{**page, 'scope': 'gazda-comuna', 'kind': 'despre'}])
        with tempfile.TemporaryDirectory() as tmp:
            save({'a': first, 'b': second}, Path(tmp))
            restored = restore(Path(tmp))
            self.assertEqual(restored['a']['pages'][0]['scope'], 'proiect')
            self.assertEqual(restored['a']['pages'][0]['kind'], 'pagina')
            self.assertEqual(restored['b']['pages'][0]['scope'], 'gazda-comuna')

    def test_data_page_discovery_is_explicit_and_keeps_the_page_limit(self):
        seen = []
        def fetch(url):
            seen.append(url)
            if url == 'https://example.org/':
                return response(url, html('<a href="/edition-one/">Ediția 01</a><p>' + 'Evidence ' * 30 + '</p>'))
            return response(url, html('Edition data ' * 30))
        entry = dict(slug='a', url='https://example.org/')
        collect(entry, fetch, 4)
        self.assertNotIn('https://example.org/edition-one/', seen)
        seen.clear()
        record = collect(entry, fetch, 4, follow_data_links=True)
        self.assertIn('https://example.org/edition-one/', seen)
        self.assertLessEqual(len(record['pages']), 4)

    def test_failed_refresh_keeps_the_pages_an_earlier_run_collected(self):
        entry = dict(slug='a', url='https://example.org/')
        good = collect(entry, lambda url: response(url, html('<h2>Metodologie</h2><p>' + 'Evidence ' * 20 + '</p>')))
        self.assertEqual(good['state'], 'documentatie-gasita')
        down = collect(entry, lambda url: response(url, '', state='eroare-retea'))
        self.assertEqual(down['state'], 'documentatie-neconfirmata')
        merged = merge_refresh(good, down)
        self.assertEqual(merged['state'], 'documentatie-gasita')
        home = next(p for p in merged['pages'] if p['url'] == entry['url'])
        self.assertEqual(home['state'], 'colectat')
        self.assertEqual(home['ultima_incercare']['state'], 'eroare-retea')
        self.assertEqual(home['sha256'], good['pages'][0]['sha256'])
        # A page that is collected again replaces its earlier copy and carries no failure note.
        fresh = collect(entry, lambda url: response(url, html('<h2>Metodologie</h2><p>' + 'Newer ' * 30 + '</p>')))
        replaced = merge_refresh(good, fresh)
        self.assertNotIn('ultima_incercare', replaced['pages'][0])
        self.assertNotEqual(replaced['pages'][0]['sha256'], good['pages'][0]['sha256'])
        # A different project URL is a different site: nothing carries over.
        moved = collect(dict(slug='a', url='https://elsewhere.org/'), lambda url: response(url, '', state='eroare-http'))
        self.assertEqual(merge_refresh(good, moved), moved)

    def test_refresh_after_a_crash_in_collection_keeps_pages_and_the_error_state(self):
        entry = dict(slug='a', url='https://example.org/')
        good = collect(entry, lambda url: response(url, html('<h2>Metodologie</h2><p>' + 'Evidence ' * 20 + '</p>')))
        crashed = dict(slug='a', url=good['url'], state='eroare-colectare', error='boom', inventory_completeness='neanalizat', pages=[])
        merged = merge_refresh(good, crashed)
        self.assertEqual(merged['state'], 'eroare-colectare')
        self.assertEqual([p['url'] for p in merged['pages']], [p['url'] for p in good['pages'] if p['state'] == 'colectat'])

    def test_restored_pages_are_saved_without_changing_their_snapshot_content(self):
        record = collect(dict(slug='a', url='https://example.org/'), lambda url: response(url, html('Evidence ' * 30)))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            save({'a': record}, out)
            read = lambda: {p.name: json.loads(p.read_text()) for p in (out / 'pagini').iterdir()}
            snapshots = read()
            save(restore(out), out)
            self.assertEqual(read(), snapshots)

    def test_non_http_urls_and_english_names(self):
        self.assertEqual(canonical('mailto:a@example.org'), '')
        self.assertEqual(kind_of('https://example.org/how-it-works/'), 'despre')
        self.assertEqual(kind_of('https://example.org/llms-full.txt'), 'llms')
        self.assertEqual(canonical('https://example.org/a/#method'), 'https://example.org/a/')


if __name__ == '__main__':
    unittest.main()
