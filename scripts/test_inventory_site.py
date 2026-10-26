"""Checks for compact, explicitly partial explorer inventory previews."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inventory import analyse_source
from inventory_concepts import validate_families
from inventory_state import counted_fields
from inventory_site import (BASIS, document_links, fold_restatements, group_api_parameters, publish_overview, publish_preview, sheet_titles, variable_matches,
                            publish_finder)


class InventorySite(unittest.TestCase):
    def test_inventory_flag_needs_a_v2_root(self):
        root = Path(__file__).resolve().parents[1]
        before = (root / 'site/data.json').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(root / 'scripts/build.py'), '--data-dir', 'data', '--site-dir', tmp, '--with-inventory'],
                                    capture_output=True, text=True, cwd=root)
        self.assertEqual(result.returncode, 2)
        self.assertIn('needs a v2 root', result.stderr)
        self.assertEqual((root / 'site/data.json').read_bytes(), before)

    def test_a_source_names_a_licence_only_when_all_its_sets_declare_the_same_one(self):
        from inventory_site import source_licence
        def fact(name, attribution='Sursa: exemplu.ro'):
            return {'valoare': name, 'url': {'valoare': 'https://creativecommons.org/licenses/by/4.0/'}, 'atribuire': {'valoare': attribution}}
        same = {'seturi': [{'licenta': fact('CC BY 4.0')}, {'licenta': fact('CC BY 4.0')}]}
        self.assertEqual(source_licence(same), {'name': 'CC BY 4.0', 'url': 'https://creativecommons.org/licenses/by/4.0/', 'attribution': 'Sursa: exemplu.ro'})
        self.assertIsNone(source_licence({'seturi': [{'licenta': fact('CC BY 4.0')}, {'licenta': fact('CC0')}]}))
        self.assertIsNone(source_licence({'seturi': [{'licenta': fact('CC BY 4.0')}, {}]}), 'a set without a licence leaves the page without one')
        self.assertIsNone(source_licence({}))

    def test_a_datasette_listing_is_credited_with_its_declared_licence_and_source(self):
        from inventory_site import source_licence
        licence = {'valoare': 'CC Attribution 4.0 License', 'url': {'valoare': 'http://creativecommons.org/licenses/by/4.0/'}, 'atribuire': {'valoare': 'Expert Forum'}}
        self.assertEqual(source_licence({'baza': {'licenta': licence}}),
                         {'name': 'CC Attribution 4.0 License', 'url': 'http://creativecommons.org/licenses/by/4.0/', 'attribution': 'Sursa: Expert Forum'})
        self.assertEqual(source_licence({'baza': {'licenta': {'valoare': 'CC0'}}}), {'name': 'CC0', 'url': '', 'attribution': ''})
        self.assertIsNone(source_licence({'baza': {'licenta': None}}), 'a listing with no licence member is not credited')
        self.assertIsNone(source_licence({'baza': {}}))
        self.assertEqual(source_licence({'baza': {'licenta': {'valoare': 'CC0', 'url': {'valoare': 'javascript:alert(1)'}}}})['url'], '', 'an address that is not http(s) is dropped')

    def test_the_field_browser_shows_the_tables_of_a_datasette_listing_with_their_row_counts_and_credits_the_licence(self):
        body = (Path(__file__).parent / 'fixtures/datasette/banipartide-lista.json').read_text()
        source = {**analyse_source({'url': 'https://db.example/base.json', 'final_url': 'https://db.example/base.json', 'state': 'ok', 'http_status': None,
                                    'content_type': 'application/json', 'body': body, 'fetched_at': '2026-10-26T18:30:00+00:00'}),
                  'id': 's', 'origine': 'copie-salvata-de-proprietar'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); obs = root / 'observatii'; inv = obs / 'inventare'; inv.mkdir(parents=True)
            (inv / 'proiecte.json').write_text(json.dumps({'proiecte': [{'slug': 'x', 'surse_structurate': ['s']}]}))
            (inv / 'seturi-date.json').write_text(json.dumps({'surse': [source]}))
            site = root / 'site'; site.mkdir(); items = [{'slug': 'x'}]
            with patch('inventory_site.observation_paths', return_value={'profile': obs / 'profil.csv'}):
                publish_preview(items, root, site)
            data = json.loads((site / 'inventar/x.json').read_text())
        listed = data['sources'][0]
        self.assertEqual((listed['title'], listed['format'], listed['savedByOwner']), ('Bază de date Datasette · base.json', 'baza-datasette', True))
        self.assertEqual(listed['licence'], {'name': 'CC Attribution 4.0 License', 'url': 'http://creativecommons.org/licenses/by/4.0/', 'attribution': 'Sursa: Expert Forum'})
        self.assertEqual(len(data['fields']), 35)
        amount = next(f for f in data['fields'] if f['path'] == 'Subvenții.Suma')
        self.assertEqual((amount['group'], amount['rows'], amount['basis'], amount['role']), ('Subvenții', 1200, 'dblist', 'coloana-sql'))
        self.assertEqual({f['group'] for f in data['fields']}, {'Contributii campanie', 'Legenda partide', 'Subvenții', 'news'}, 'a hidden table is not shown')
        self.assertTrue(all(f['declaredType'] is None and not f['description'] for f in data['fields']))
        self.assertEqual(BASIS['declarat-in-lista-baza'], 'dblist')
        for script in ('app.js', 'inventory.js'):
            self.assertIn('dblist', (Path(__file__).resolve().parents[1] / 'site' / script).read_text(), 'the label of the new basis is in ' + script)

    def test_a_google_sheet_tab_takes_the_title_of_its_data_set_from_the_page_that_lists_it(self):
        def link(ident, gid, label, after=None):
            return {'tip': 'foaie-google', 'id_document': ident, 'gid': gid, 'eticheta': {'valoare': label},
                    'text_dupa': {'valoare': after} if after else None}
        export = 'https://docs.google.com/spreadsheets/d/{}/export?format=csv&gid={}'
        sources = {'page': {'format': 'html-lista-seturi', 'seturi': [
            {'titlu': {'valoare': 'Genul candidaților'}, 'legaturi': [link('AAA', '1', 'Deschide')]},
            {'titlu': {'valoare': 'Alocări'}, 'legaturi': [link('BBB', '0', 'Deschide', 'HG 1/2021 (X)'), link('CCC', '2', 'Deschide', 'HG 2/2021 (Y)')]},
            {'titlu': {'valoare': 'Plăți'}, 'legaturi': [link('DDD', '3', 'Deconturi'), link('EEE', '4', 'Plăți')]},
            {'titlu': {'valoare': 'Dosar'}, 'legaturi': [{'tip': 'dosar-drive', 'id_document': 'FFF', 'gid': None, 'eticheta': {'valoare': 'Deschide'}, 'text_dupa': None}]}]},
            'a': {'format': 'csv', 'url': export.format('AAA', '1')}, 'b': {'format': 'csv', 'url': export.format('BBB', '0')},
            'c': {'format': 'csv', 'url': export.format('CCC', '2')}, 'd': {'format': 'csv', 'url': export.format('DDD', '3')},
            'e': {'format': 'csv', 'url': export.format('EEE', '4')}, 'other': {'format': 'csv', 'url': export.format('ZZZ', '9')},
            'plain': {'format': 'csv', 'url': 'https://example.org/data.csv'}}
        profile = {'surse_structurate': list(sources)}
        titles = sheet_titles(profile, sources)
        self.assertEqual(titles, {'a': 'Foaie Google · Genul candidaților', 'b': 'Foaie Google · Alocări · HG 1/2021 (X)', 'c': 'Foaie Google · Alocări · HG 2/2021 (Y)',
                                  'd': 'Foaie Google · Plăți · Deconturi', 'e': 'Foaie Google · Plăți · Plăți'})
        self.assertEqual(sheet_titles({'surse_structurate': ['a']}, sources), {}, 'the page must belong to the same project')
        self.assertEqual(sheet_titles({'surse_structurate': ['a', 'page']}, {**sources, 'a': {'format': 'csv', 'url': export.format('AAA', '0')}}), {},
                         'the same document with another tab is another data set')

    def test_the_sheet_tabs_of_a_tracked_inventory_have_distinct_titles(self):
        root = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2/observatii/inventare'
        profiles = {p['slug']: p for p in json.loads((root / 'proiecte.json').read_text())['proiecte']}
        sources = {s['id']: s for s in json.loads((root / 'seturi-date.json').read_text())['surse']}
        profile = profiles['data-expertforum']
        titles = sheet_titles(profile, sources)
        tabs = [i for i in profile['surse_structurate'] if 'docs.google.com' in sources[i]['url']]
        self.assertEqual(set(titles), set(tabs), 'every tab that the page links has a title')
        self.assertEqual(len(set(titles.values())), len(tabs), 'the titles tell the tabs apart')

    def test_document_links_exclude_shared_host_and_failed_pages(self):
        records = {'pages': [
            {'state': 'colectat', 'scope': 'gazda-comuna', 'kind': 'llms', 'final_url': 'https://example.org/llms.txt'},
            {'state': 'eroare-http', 'scope': 'proiect', 'kind': 'despre', 'final_url': 'https://example.org/about'},
            {'state': 'colectat', 'scope': 'proiect', 'kind': 'pagina', 'final_url': 'https://example.org/',
             'sections': [{'kind': 'metodologie', 'url': 'https://example.org/#method', 'heading': 'Metoda'}]},
        ]}
        self.assertEqual([d['url'] for d in document_links(records)], ['https://example.org/#method'])

    def test_preview_splits_fields_and_never_exports_control_candidates_or_private_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); obs = root / 'observatii'; inv = obs / 'inventare'; inv.mkdir(parents=True)
            (obs / 'documentare').mkdir()
            (obs / 'documentare/index.json').write_text(json.dumps({'entries': []}))
            (inv / 'proiecte.json').write_text(json.dumps({'proiecte': [
                {'slug': 'x', 'surse_structurate': ['s'], 'intrari_utilizator': [{'nume': 'newsletter'}]},
                {'slug': 'empty', 'surse_structurate': []},
            ]}))
            (inv / 'seturi-date.json').write_text(json.dumps({'surse': [
                {'id': 's', 'url': 'https://example.org/schema.json', 'format': 'openapi', 'snapshot': 'private/raw.json',
                 'sha256': 'private-hash', 'campuri': [{'nume': 'cui', 'cale': '$.cui', 'rol': 'camp-raspuns',
                      'tip_declarat': 'string', 'stare_tip': 'declarat-in-schema', 'pointer': '/properties/cui'}]},
            ]}))
            site = root / 'site'; site.mkdir(); items = [{'slug': 'x'}, {'slug': 'empty'}]
            with patch('inventory_site.observation_paths', return_value={'profile': obs / 'profil.csv'}):
                publish_preview(items, root, site)
            self.assertEqual(items[0]['inventory']['count'], 1)
            self.assertTrue(items[0]['inventory']['partial'])
            self.assertIn('cui', items[0]['inventory']['keywords'])
            self.assertNotIn('fields', items[0]['inventory'])
            self.assertNotIn('inventory', items[1])
            data = json.loads((site / 'inventar/x.json').read_text())
            self.assertEqual(data['fields'][0]['basis'], 'schema')
            self.assertEqual(data['fields'][0]['declaredType'], 'string')
            raw = (site / 'inventar/x.json').read_text()
            self.assertNotIn('private', raw)
            self.assertNotIn('newsletter', raw)
            self.assertNotIn('snapshot', raw)
            (site / 'inventar/stale.json').write_text('{}')
            with patch('inventory_site.observation_paths', return_value={'profile': obs / 'profil.csv'}):
                publish_preview(items, root, site)
            self.assertFalse((site / 'inventar/stale.json').exists())

    def test_failed_refresh_is_visible_and_the_evidence_is_not_called_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); obs = root / 'observatii'; inv = obs / 'inventare'; inv.mkdir(parents=True)
            (inv / 'proiecte.json').write_text(json.dumps({'proiecte': [{'slug': 'x', 'surse_structurate': ['s', 't']}]}))
            field = {'nume': 'cui', 'cale': '$.cui', 'rol': 'camp-raspuns', 'tip_declarat': 'string', 'stare_tip': 'declarat-in-schema', 'pointer': '/p'}
            (inv / 'seturi-date.json').write_text(json.dumps({'surse': [
                {'id': 's', 'url': 'https://example.org/a.json', 'format': 'openapi', 'fetched_at': '2026-10-24T10:00:00+00:00', 'campuri': [field],
                 'ultima_incercare': {'la': '2026-10-25T09:00:00+00:00', 'stare': 'eroare-http', 'http_status': 503}},
                {'id': 't', 'url': 'https://example.org/b.json', 'format': 'openapi', 'fetched_at': '2026-10-24T10:00:00+00:00', 'campuri': [field]}]}))
            site = root / 'site'; site.mkdir(); items = [{'slug': 'x'}]
            with patch('inventory_site.observation_paths', return_value={'profile': obs / 'profil.csv'}):
                publish_preview(items, root, site)
            sources = json.loads((site / 'inventar/x.json').read_text())['sources']
            self.assertEqual(sources[0]['refreshFailed'], {'date': '2026-10-25', 'status': 503, 'state': 'eroare-http'})
            self.assertEqual(sources[0]['checked'], '2026-10-24')
            self.assertNotIn('refreshFailed', sources[1])
            self.assertEqual(items[0]['inventory']['stale'], 1)

    def test_repeated_api_parameters_keep_their_contexts(self):
        def field(pointer, operation, typ='string'):
            return {'source': 's', 'name': 'cpv', 'role': 'parametru-api', 'declaredType': typ,
                    'description': '', 'unit': None, 'format': None, 'path': 'cpv', 'reference': pointer,
                    'operations': [operation], 'location': 'query'}
        fields = group_api_parameters([field('/a', 'GET /a'), field('/b', 'GET /b'), field('/c', 'GET /c', 'integer')])
        self.assertEqual(len(fields), 2)
        self.assertEqual(fields[0]['operations'], ['GET /a', 'GET /b'])
        self.assertEqual([c['reference'] for c in fields[0]['contexts']], ['/a', '/b'])
        self.assertEqual(fields[1]['declaredType'], 'integer')

    def test_unsafe_source_url_does_not_become_a_public_link(self):
        pages = {'pages': [{'state': 'colectat', 'scope': 'proiect', 'kind': 'llms', 'final_url': 'javascript:alert(1)'}]}
        self.assertEqual(document_links(pages), [])

    def test_variable_groups_require_explicit_project_and_name_and_retain_type_evidence(self):
        concepts = [{'id': 'cui', 'selectors': [{'projects': ['known'], 'names': ['cui']}]}]
        def field(name, typ, basis):
            return dict(name=name, path='$.company.' + name, role='camp-date', basis=basis,
                        declaredType=typ, observedTypes=[], unit=None, description='', source='s', reference='/x')
        fields = [field('cui', 'string', 'schema'), field('cui', None, 'header'), field('id', 'integer', 'schema')]
        sources = [{'id': 's', 'url': 'https://example.org/data'}]
        self.assertEqual(variable_matches('unknown', fields, sources, concepts), [])
        matches = variable_matches('known', fields, sources, concepts)
        self.assertEqual(matches[0]['count'], 2)
        self.assertEqual([e['declaredType'] for e in matches[0]['evidence']], ['string', None])
        self.assertEqual([e['basis'] for e in matches[0]['evidence']], ['schema', 'header'])
        self.assertEqual(matches[0]['evidence'][0]['url'], sources[0]['url'])

    def test_finder_keeps_uninventoried_projects_and_separates_institutions_from_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); site = root / 'site'; (site / 'inventar').mkdir(parents=True)
            for name in ('style.css', 'inventory.css', 'inventory.js'):
                (site / name).write_text('/* fixture */')
            items = [dict(slug='no-fields', name='No fields', kind='proiect', institutions=['institutie:parlament'],
                          dataSources=[{'name': 'Camera Deputaților', 'evidence': 'https://example.org/method'},
                                       {'name': 'Senatul României', 'evidence': 'https://example.org/other'}]),
                     dict(slug='resource', name='A resource', kind='resursa'),
                     dict(slug='org', name='An organisation', kind='organizatie')]
            publish_finder(items, root / 'integrare', site, {})
            index = json.loads((site / 'inventar/index.json').read_text())
            self.assertEqual([e['slug'] for e in index['entries']], ['no-fields', 'resource'])
            entry = index['entries'][0]
            self.assertEqual(entry['variables'], [])
            self.assertEqual(entry['institutions'], ['institutie:parlament'])
            self.assertEqual(list(entry['providers']), ['Parlament'])
            self.assertEqual(len(entry['providers']['Parlament']), 2)
            page = (site / 'date/index.html').read_text()
            self.assertNotIn('v=BUILD', page)
            self.assertIn('<base href="../">', page)

    def test_a_restated_field_is_counted_once_and_kept_as_evidence(self):
        source = {'campuri': [{'nume': 'cui', 'in_contract': {'sursa_id': 'c', 'pointer': '/p/0'}}, {'nume': 'new', 'in_contract': None}, {'nume': 'x'}]}
        self.assertEqual([f['nume'] for f in counted_fields(source)], ['new', 'x'])
        def field(name, source, reference, restates=None, description=''):
            return dict(name=name, path=name, role='parametru-api', source=source, reference=reference, restates=restates,
                        description=description, declaredType=None, unit=None, format=None, operations=['GET /a'])
        listed = [{'id': 'c', 'url': 'https://example.org/openapi.json', 'title': 'Schemă API'},
                  {'id': 'p', 'url': 'https://example.org/api-docs', 'title': 'Documentația API (pagină)'}]
        fields = [field('cui', 'c', '/p/0'), field('cui', 'p', 'char:1-3', {'sursa_id': 'c', 'pointer': '/p/0'}, '1-10 cifre'),
                  field('orphan', 'p', 'char:5-9', {'sursa_id': 'c', 'pointer': '/missing'}), field('only', 'p', 'char:9-12')]
        kept = fold_restatements(fields, [], listed)
        self.assertEqual([(f['name'], f['source']) for f in kept], [('cui', 'c'), ('orphan', 'p'), ('only', 'p')])
        self.assertEqual(kept[0]['also'], [{'url': 'https://example.org/api-docs', 'title': 'Documentația API (pagină)', 'reference': 'char:1-3', 'description': '1-10 cifre'}])
        self.assertTrue(all('restates' not in f for f in kept))
        self.assertEqual(len(group_api_parameters(kept)[0]['also']), 1, 'collapsing parameters keeps one copy of the evidence')

    def test_families_need_known_ids(self):
        document = {'familii': [{'id': 'geo', 'label': 'Geografie'}, {'id': 'geo', 'label': 'Again'}, {'id': 'x'}],
                    'concepte': [{'id': 'judet', 'familie': 'geo'}, {'id': 'cui', 'familie': 'nope'}, {'id': 'free'}]}
        errors = validate_families(document)
        self.assertEqual(len(errors), 3, errors)
        self.assertTrue(any('duplicate' in e for e in errors) and any('needs id and label' in e for e in errors) and any("'nope'" in e for e in errors))

    def test_every_group_of_the_dictionary_has_a_known_family(self):
        document = json.loads((Path(__file__).resolve().parents[1] / 'data/taxonomy-v2/inventar-concepte.json').read_text())
        self.assertEqual(validate_families(document), [])
        self.assertTrue(all(c.get('familie') for c in document['concepte']))

    def test_overview_is_a_table_of_normalised_names_by_family(self):
        concepts = [{'id': 'cui', 'label': 'CUI', 'familie': 'ids', 'selectors': [{'projects': ['p'], 'names': ['cui', 'cui_firma']}]},
                    {'id': 'gone', 'label': 'Gone', 'familie': 'ids', 'stare': 'respins', 'selectors': [{'projects': ['p'], 'names': ['q']}]},
                    {'id': 'an', 'label': '<An>', 'familie': 'timp', 'selectors': [{'projects': ['p'], 'names': ['year']}]}]
        families = [{'id': 'ids', 'label': 'Identificatori'}, {'id': 'timp', 'label': 'Timp'}, {'id': 'geo', 'label': 'Geografie'}]
        def field(name, role='camp-raspuns', source='s'):
            return dict(name=name, path='$.' + name, role=role, source=source)
        fields = [field('cui'), field('cui_firma'), field('q', 'parametru-api'), field('q'), field('total', source='t'), field('year')]
        sources = [{'id': 's', 'url': 'https://example.org/api/openapi.json'}, {'id': 't', 'url': 'https://example.org/'}]
        items = [dict(slug='p', name='Proj', kind='proiect'), dict(slug='bare', name='Bare & co', kind='resursa'),
                 dict(slug='org', name='Org', kind='organizatie')]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            for name in ('style.css', 'inventory.css'):
                (site / name).write_text('/* fixture */')
            publish_overview(items, site, {'p': (fields, sources)}, concepts, families)
            page = (site / 'date/lista/index.html').read_text()
        head = page[page.index('<thead>'):page.index('</thead>')]
        self.assertEqual([h.split('<small>')[0] for h in head.split('<th scope="col">')[1:]], ['Proiect', 'Identificatori', 'Timp', 'Geografie', 'Altele'])
        row = page[page.index('<tr id="p">'):page.index('</tr>', page.index('<tr id="p">'))]
        cells = row.split('<td')[1:]
        self.assertEqual(cells[0], '><ul><li>CUI</li></ul></td>', 'two fields of one group give one normalised name')
        self.assertIn('<li>&lt;An&gt;</li>', cells[1])
        self.assertEqual(cells[2], '></td>')
        self.assertIn('>2</td>', cells[3], 'a rejected group leaves its fields with the others, counted by distinct name: q and total')
        self.assertNotIn('openapi.json', page, 'source field names belong to the project page, not to this table')
        self.assertIn('Bare &amp; co', page)
        self.assertNotIn('>Org<', page)
        self.assertNotIn('v=BUILD', page)
        self.assertIn('<base href="../../">', page)
        self.assertIn('(grupuri; 2 încă propuse)', page, 'the note counts the open groups; a rejected group is not one')
        for concept in concepts:
            concept['stare'] = 'revizuit' if concept['id'] != 'gone' else 'respins'
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            for name in ('style.css', 'inventory.css'):
                (site / name).write_text('/* fixture */')
            publish_overview(items, site, {'p': (fields, sources)}, concepts, families)
            self.assertIn('(grupurile revizuite)', (site / 'date/lista/index.html').read_text())

    def test_every_selector_of_the_dictionary_matches_a_current_field(self):
        from inventory_concepts import as_list, selector_matches
        root = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2'
        concepts = json.loads((root / 'inventar-concepte.json').read_text())['concepte']
        profiles = {p['slug']: p for p in json.loads((root / 'observatii/inventare/proiecte.json').read_text())['proiecte']}
        sources = {s['id']: s for s in json.loads((root / 'observatii/inventare/seturi-date.json').read_text())['surse']}
        for concept in concepts:
            for number, selector in enumerate(concept['selectors'], 1):
                with self.subTest(concept=concept['id'], selector=number):
                    found = [(slug, f) for slug in as_list(selector['projects']) for r in profiles[slug]['surse_structurate']
                             for f in sources[r]['campuri'] if selector_matches(selector, slug, {'name': f['nume'], 'path': f['cale'], 'role': f.get('rol', 'camp-date')}, sources[r]['url'])]
                    self.assertTrue(found)
                    self.assertEqual({slug for slug, _ in found} - set(as_list(selector['projects'])), set())

    def test_every_evidence_type_of_the_tracked_inventories_reaches_the_preview(self):
        root = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2/observatii/inventare'
        types = {f['stare_tip'] for s in json.loads((root / 'seturi-date.json').read_text())['surse'] for f in s['campuri']}
        self.assertEqual(types - set(BASIS), set(), 'a field with an unmapped evidence type would silently vanish from the preview')

    def test_ordinary_rebuild_removes_stale_inventory_pages(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / 'index.html').write_text('old preview')
            for name in ('inventar', 'date'):
                (site / name).mkdir()
                (site / name / 'index.json').write_text('draft')
            result = subprocess.run([sys.executable, str(root / 'scripts/build.py'), '--site-dir', str(site)],
                                    capture_output=True, text=True, cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((site / 'date').exists())
            self.assertFalse((site / 'inventar').exists())
            self.assertNotIn('inventoryPreview', json.loads((site / 'data.json').read_text()))


if __name__ == '__main__':
    unittest.main()
