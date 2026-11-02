"""Checks for compact, explicitly partial explorer inventory previews."""
import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inventory import analyse_source
from inventory_concepts import validate_families
from inventory_state import counted_fields
from common import RESERVED_DATA_SLUGS, inventory_exclusion
from inventory_site import (BASIS, document_links, fold_restatements, group_api_parameters, left_out, publish_overview, publish_preview, scope_reason,
                            sheet_titles, variable_matches, publish_finder)


def built(slug, **fields):
    """A built item that is in the scope of the variable inventory (a project, active, with a relation to data); a test overrides what it needs."""
    return {'slug': slug, 'name': slug, 'kind': 'proiect', 'status': 'activ', 'dataRelation': 'date-publice', **fields}


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
            site = root / 'site'; site.mkdir(); items = [built('x')]
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
            site = root / 'site'; site.mkdir(); items = [built('x'), built('empty')]
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
            site = root / 'site'; site.mkdir(); items = [built('x')]
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
            items = [built('no-fields', name='No fields', institutions=['institutie:parlament'],
                          dataSources=[{'name': 'Camera Deputaților', 'evidence': 'https://example.org/method'},
                                       {'name': 'Senatul României', 'evidence': 'https://example.org/other'}]),
                     built('resource', name='A resource', kind='resursa'),
                     built('org', name='An organisation', kind='organizatie')]
            (root / 'furnizori.csv').write_text('nume_sursa,furnizor,nume,eticheta,tip,stare,nota\n'
                                                'Camera Deputaților,camera,Camera Deputaților,Parlament,institutie-publica,propus,\n'
                                                'Senatul României,senat,Senatul României,Parlament,institutie-publica,propus,\n')
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
        items = [built('p', name='Proj'), built('bare', name='Bare & co', kind='resursa'), built('org', name='Org', kind='organizatie')]
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


def source(ident, url, fmt, title=None, **extra):
    return {'id': ident, 'url': url, 'format': fmt, 'title': title or ident, **extra}


def field_of(ident, name='f'):
    return {'name': name, 'path': '$.' + name, 'role': 'camp-date', 'source': ident}


class SourceViews(unittest.TestCase):
    """The four views by source (`inventory_views`): offline, on small fixtures. No test pins a count of the data that the owner edits."""

    def fixture(self):
        items = [built('a', name='Alpha', dataSources=[{'name': 'SEAP', 'evidence': 'https://e.org/1'}, {'name': 'SICAP / SEAP', 'evidence': 'https://e.org/2'}]),
                 built('b', name='Beta', kind='resursa', dataSources=[{'name': 'INS', 'evidence': 'https://e.org/3'}, {'name': 'SEAP', 'evidence': 'https://e.org/4'}]),
                 built('c', name='Gamma'),
                 built('off', name='Offline', status='offline', dataSources=[{'name': 'SEAP', 'evidence': 'https://e.org/5'}]),
                 built('org', name='Org', kind='organizatie')]
        licence = {'name': 'CC BY 4.0', 'url': 'https://creativecommons.org/licenses/by/4.0/', 'attribution': ''}
        projections = {
            'a': ([field_of('a1'), field_of('a1', 'g'), field_of('a2')],
                  [source('a1', 'https://www.data.g4d.ro/x.csv', 'csv', 'Fișier A', licence=licence), source('a2', 'https://executii-bugetare.g4d.ro/api.json', 'json', 'Api A')]),
            'b': ([field_of('b1')], [source('b1', 'https://data.g4d.ro/y.csv', 'csv', 'Fișier B'), source('b2', 'https://ana.github.io/z.html', 'html-tabele', 'Tabel B')]),
            'c': ([field_of('c1')], [source('c1', 'https://ana.github.io/w.json', 'json', 'Json C')]),
            'off': ([field_of('o1')], [source('o1', 'https://data.g4d.ro/o.csv', 'csv', 'Fișier O')]),
            'org': ([field_of('r1')], [source('r1', 'https://r.org/r.csv', 'csv')])}
        return items, projections

    def publish(self, table=None, items=None, projections=None):
        from inventory_views import publish_source_views
        default_items, default_projections = self.fixture()
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        site = Path(tmp.name)
        for name in ('style.css', 'inventory.css'):
            (site / name).write_text('/* fixture */')
        summary = publish_source_views(items or default_items, site, projections or default_projections, table or {})
        return site, summary

    def page(self, site, name):
        return (site / 'date' / name / 'index.html').read_text()

    def test_the_views_are_the_reserved_slugs_in_one_order(self):
        from inventory_site import VIEWS
        self.assertEqual(tuple(v for v, _ in VIEWS), RESERVED_DATA_SLUGS)
        self.assertEqual(RESERVED_DATA_SLUGS[0], 'lista')

    def test_a_reserved_slug_is_an_error_of_validate(self):
        import validate
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'intrari.csv').write_text('slug,nume\nok,Ok\nformate,Formate\ngazde,Gazde\n')
            before = validate.errors
            with patch('taxonomy_v2.Files') as files, patch.object(validate, 'report') as report:
                files.return_value.path.return_value = root / 'intrari.csv'
                validate.check_reserved_slugs(root)
        self.assertEqual([c.args[0] for c in report.call_args_list], ['error', 'error'])
        self.assertEqual([c.args[2] for c in report.call_args_list], [3, 4])
        self.assertEqual(validate.errors, before)

    def test_every_format_has_one_kind_and_every_kind_has_a_format(self):
        from inventory_site import FORMAT_KIND_OF, FORMAT_KINDS, FORMATS
        self.assertEqual(sorted(set(FORMATS) - set(FORMAT_KIND_OF)), [], 'a format without a kind')
        self.assertEqual(sorted(set(FORMAT_KIND_OF) - set(FORMATS)), [], 'a kind for a format that does not exist')
        self.assertEqual(set(FORMAT_KIND_OF.values()), {k for k, _ in FORMAT_KINDS})
        self.assertEqual([label for _, label in FORMAT_KINDS],
                         ['API și JSON', 'Fișiere și seturi descrise', 'Tabele în pagină', 'Scriptul paginii', 'Cod sursă'])

    def test_the_formats_of_the_tracked_inventory_all_have_a_kind(self):
        from inventory_site import FORMAT_KIND_OF
        path = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2/observatii/inventare/campuri.csv'
        with open(path, encoding='utf-8', newline='') as handle:
            formats = {row['format'] for row in csv.DictReader(handle)}
        self.assertEqual(sorted(formats - set(FORMAT_KIND_OF)), [])

    def test_the_tracked_provider_file_is_valid_and_names_every_provider_of_the_relations(self):
        import common
        root = Path(__file__).resolve().parents[1] / 'data/taxonomy-v2/integrare'
        rows = common.read_providers(common.providers_path(root))
        names = common.provider_names(common.read_csv(root / 'relatii.csv'))
        errors, warnings = common.provider_problems(rows, names)
        self.assertEqual((errors, warnings), ([], []))

    def test_the_provider_checks(self):
        from common import provider_problems
        def row(name, fid='x', nume='X', tip='ong', stare='propus'):
            return {'nume_sursa': name, 'furnizor': fid, 'nume': nume, 'eticheta': '', 'tip': tip, 'stare': stare, 'nota': ''}
        self.assertEqual(provider_problems([row('A'), row('B')], ['A', 'B']), ([], []))
        errors, _ = provider_problems([row('A'), row('A')])
        self.assertEqual([m for _, m in errors if 'duplicat' in m], ['A: nume_sursa duplicat (și în linia 2)'])
        self.assertTrue(provider_problems([row('A', fid='Not Kebab')])[0])
        self.assertTrue(provider_problems([row('A', tip='guvern')])[0])
        self.assertTrue(provider_problems([row('A', stare='gata')])[0])
        self.assertTrue(provider_problems([row('A', tip='', stare='acceptat')])[0], 'an accepted row needs a type')
        self.assertEqual(provider_problems([row('A', tip='')])[0], [], 'a proposed row may leave the type open')
        self.assertTrue(provider_problems([row('A', nume='X'), row('B', nume='Y')])[0], 'one provider, two display names')
        self.assertTrue(provider_problems([row('A', tip='ong'), row('B', tip='companie')])[0], 'one provider, two types')
        errors, warnings = provider_problems([row('A'), row('Old')], ['A', 'New'])
        self.assertEqual(errors, [])
        self.assertEqual(sorted(w for _, w in warnings), ['New: numele din relatii.csv nu are rând în furnizori.csv', 'Old: numele nu apare în relatii.csv (rând depășit?)'])

    def test_a_row_of_the_provider_file_applies_only_when_accepted(self):
        from common import provider_table
        rows = [{'nume_sursa': 'SEAP', 'furnizor': 'seap-sicap', 'nume': 'SEAP / SICAP', 'eticheta': '', 'tip': 'institutie-publica', 'stare': 'acceptat', 'nota': ''},
                {'nume_sursa': 'SICAP / SEAP', 'furnizor': 'seap-sicap', 'nume': 'SEAP / SICAP', 'eticheta': '', 'tip': 'institutie-publica', 'stare': 'propus', 'nota': ''}]
        self.assertEqual(list(provider_table(rows)), ['SEAP'])
        site, summary = self.publish({})
        proposed = self.page(site, 'furnizori')
        self.assertNotIn('id="f-seap-sicap"', proposed, 'a name stays a provider of its own before the review')
        self.assertIn('id="f-nume-seap"', proposed)
        self.assertIn('id="f-nume-sicap-seap"', proposed)
        self.assertIn('data-type=""', proposed)
        self.assertNotIn('data-type="institutie-publica"', proposed)
        site, accepted = self.publish(provider_table(rows))
        page = self.page(site, 'furnizori')
        self.assertIn('id="f-seap-sicap"', page)
        self.assertIn('id="f-nume-sicap-seap"', page, 'the proposed row is not applied')
        self.assertIn('data-type="institutie-publica"', page)
        self.assertEqual((accepted['furnizori']['providers'], summary['furnizori']['providers']), (3, 3), 'one accepted row renames one provider and merges none')

    def test_two_accepted_names_of_one_provider_count_an_entry_once(self):
        from common import provider_table
        rows = [{'nume_sursa': n, 'furnizor': 'seap', 'nume': 'SEAP', 'eticheta': '', 'tip': 'institutie-publica', 'stare': 'acceptat', 'nota': ''} for n in ('SEAP', 'SICAP / SEAP')]
        site, _ = self.publish(provider_table(rows))
        page = self.page(site, 'furnizori')
        block = page[page.index('id="f-seap"'):]
        block = block[:block.index('</li></ul>')]
        self.assertIn('2 intrări', block)
        self.assertEqual(block.count('href="proiect/a/"'), 1)
        self.assertIn('Numele din relații: SEAP, SICAP / SEAP.', block)

    def test_the_provider_page_groups_by_type_counts_and_lists_the_entries_without_a_provider(self):
        from common import provider_table
        rows = [{'nume_sursa': 'SEAP', 'furnizor': 'seap', 'nume': 'SEAP', 'eticheta': '', 'tip': 'institutie-publica', 'stare': 'acceptat', 'nota': ''},
                {'nume_sursa': 'INS', 'furnizor': 'ins', 'nume': 'INS', 'eticheta': '', 'tip': 'ue-international', 'stare': 'acceptat', 'nota': ''}]
        site, summary = self.publish(provider_table(rows))
        page = self.page(site, 'furnizori')
        self.assertEqual(re.findall(r'<section class="ov-group" id="tip-([\w-]+)"', page), ['institutie-publica', 'ue-international', 'neclasificat'],
                         'the order of the code list, then the providers without a type; SICAP / SEAP has no accepted row')
        self.assertIn('Fără furnizor declarat (1)', page)
        self.assertIn('Gamma', page[page.index('id="fara-furnizor"'):])
        self.assertNotIn('>Offline<', page, 'an entry out of scope is not listed')
        self.assertEqual((summary['furnizori']['entries'], summary['furnizori']['bare']), (2, 1))
        self.assertEqual(re.findall(r'<tr id="m-(\w+)"', page), ['a', 'b'])
        self.assertEqual(page.count('class="ov-mark"'), 4, 'a mark for every pair of entry and provider: a-seap, a-sicap, b-seap, b-ins')
        self.assertIn('Același furnizor nu înseamnă același set de date.', page)

    def test_the_matrix_holds_the_most_used_providers_only(self):
        from inventory_views import MATRIX_SIZE
        items = [built(f'e{n}', name=f'E{n:02}', dataSources=[{'name': f'P{k:02}', 'evidence': 'https://e.org/'} for k in range(n + 1)]) for n in range(MATRIX_SIZE + 3)]
        site, summary = self.publish(items=items, projections={})
        page = self.page(site, 'furnizori')
        head = page[page.index('<thead>'):page.index('</thead>')]
        self.assertEqual(head.count('<th scope="col">') - 1, MATRIX_SIZE)
        self.assertIn('P00', head, 'the provider of every entry is the first column')
        self.assertNotIn('P14', head, 'a provider of one entry is not in the matrix')
        self.assertEqual(summary['furnizori']['matrix'], MATRIX_SIZE)

    def test_the_format_page_has_one_column_for_each_kind_and_counts_entries_and_fields(self):
        site, summary = self.publish()
        page = self.page(site, 'formate')
        head = page[page.index('<thead>'):page.index('</thead>')]
        labels = [h.split('<small>')[0] for h in head.split('<th scope="col">')[1:]]
        self.assertEqual(labels, ['Intrare', 'API și JSON', 'Fișiere și seturi descrise', 'Tabele în pagină', 'Scriptul paginii', 'Cod sursă'])
        self.assertEqual(summary['formate']['kinds'], {'api': 2, 'fisiere': 2, 'tabele': 1, 'script': 0, 'cod': 0}, 'entries with a source of the kind; offline and organisation excluded')
        row = page[page.index('<tr id="a">'):page.index('</tr>', page.index('<tr id="a">'))]
        self.assertIn('Fișier CSV</a> <small>2</small>', row, 'two fields of the csv source')
        self.assertIn('Fișier JSON</a> <small>1</small>', row)
        self.assertIn('<a href="date/a/">Toate variabilele</a>', row)
        self.assertIn('id="fmt-csv"', page)
        self.assertIn('id="fel-api"', page)
        self.assertNotIn('Fișier O', page)

    def test_a_format_that_has_no_kind_still_shows_in_its_own_column(self):
        items, projections = self.fixture()
        projections['a'] = ([field_of('a1')], [source('a1', 'https://x.org/a', 'nou-format')])
        site, _ = self.publish(items=items, projections=projections)
        page = self.page(site, 'formate')
        self.assertIn('Alt format', page)
        self.assertIn('id="fmt-nou-format"', page)

    def test_the_licence_page_groups_by_the_name_a_source_declares_and_puts_the_undeclared_last(self):
        site, summary = self.publish()
        page = self.page(site, 'licente')
        ids = re.findall(r'<section class="ov-licence" id="lic-([\w-]+)"', page)
        self.assertEqual(ids, ['cc-by-4-0', 'nedeclarata'])
        self.assertIn('<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>', page)
        self.assertEqual((summary['licente']['declared_sources'], summary['licente']['sources']), (1, 5))
        declared_block = page[page.index('id="lic-cc-by-4-0"'):page.index('id="lic-nedeclarata"')]
        self.assertIn('Fișier A', declared_block)
        self.assertNotIn('Api A', declared_block)
        self.assertIn('Api A', page[page.index('id="lic-nedeclarata"'):])
        self.assertIn('nu o părere juridică', page)

    def test_the_licence_of_a_schema_org_data_set_is_read_with_the_rule_of_the_variables_pages(self):
        from inventory_views import declared_licences
        facts = {'basis': 'declarat', 'schema': [{'name': 'x', 'licence': {'name': 'https://creativecommons.org/licenses/by/4.0/', 'url': 'https://creativecommons.org/licenses/by/4.0/'}}]}
        self.assertEqual(declared_licences({'facts': facts}), [{'name': 'https://creativecommons.org/licenses/by/4.0/', 'url': 'https://creativecommons.org/licenses/by/4.0/'}])
        self.assertEqual(declared_licences({}), [])
        both = declared_licences({'licence': {'name': 'CC0', 'url': ''}, 'facts': {'schema': [{'licence': {'name': 'CC0', 'url': ''}}, {'licence': {'name': 'ODbL', 'url': ''}}]}})
        self.assertEqual([x['name'] for x in both], ['CC0', 'ODbL'], 'a name is listed once for a source')

    def test_hosts_group_by_registered_domain_and_platforms_stay_whole(self):
        from inventory_views import host_group, source_host
        self.assertEqual(host_group('executii-bugetare.g4d.ro'), 'g4d.ro')
        self.assertEqual(host_group('data.g4d.ro'), 'g4d.ro')
        self.assertEqual(host_group('g4d.ro'), 'g4d.ro')
        self.assertEqual(host_group('x.y.gov.ro'), 'y.gov.ro', 'gov.ro is a suffix')
        self.assertEqual(host_group('api.firma.com.ro'), 'firma.com.ro')
        self.assertEqual(host_group('a.b.org.ro'), 'b.org.ro')
        self.assertEqual(host_group('www.site.co.uk'), 'site.co.uk')
        self.assertEqual(host_group('ana.github.io'), 'ana.github.io', 'a platform: the full host')
        self.assertEqual(host_group('raw.githubusercontent.com'), 'raw.githubusercontent.com')
        self.assertEqual(host_group('app.vercel.app'), 'app.vercel.app')
        self.assertEqual(host_group('127.0.0.1'), '127.0.0.1')
        self.assertEqual(host_group('localhost'), 'localhost')
        self.assertEqual(source_host('https://WWW.Data.G4D.ro/x?y=1'), 'data.g4d.ro')
        self.assertEqual(source_host('not a url'), '')

    def test_the_host_page_shows_the_hosts_of_two_entries_under_their_domain_and_counts_the_entries_on_their_own_domain(self):
        site, summary = self.publish()
        page = self.page(site, 'gazde')
        self.assertEqual(re.findall(r'data-host="([^"]+)"', page), ['ana.github.io', 'g4d.ro'], 'b and c share the full host of a platform; a and b share a registered domain')
        self.assertEqual(summary['gazde']['grouped'], {'g4d.ro': ['data.g4d.ro', 'executii-bugetare.g4d.ro']})
        block = page[page.index('data-host="g4d.ro"'):]
        self.assertIn('<code>executii-bugetare.g4d.ro</code>', block)
        self.assertIn('<code>data.g4d.ro</code>', block)
        self.assertNotIn('Offline', page)

    def test_the_number_of_entries_on_their_own_domain_counts_the_entries_that_no_other_entry_shares(self):
        items = [built('a', name='A'), built('b', name='B'), built('c', name='C'), built('d', name='D')]
        projections = {'a': ([], [source('s', 'https://one.example.org/a', 'csv')]), 'b': ([], [source('s', 'https://two.example.org/b', 'csv')]),
                       'c': ([], [source('s', 'https://solo.net/c', 'csv'), source('t', 'https://example.org/c', 'csv')]), 'd': ([], [source('s', 'https://alone.io/d', 'csv')])}
        site, summary = self.publish(items=items, projections=projections)
        self.assertEqual((summary['gazde']['own'], summary['gazde']['with_sources']), (1, 4), 'a, b and c share example.org; c has a host of its own, but also a shared one; only d is alone')
        self.assertIn('<strong>1</strong> din 4 intrări', self.page(site, 'gazde'))

    def test_all_five_pages_carry_one_switcher_that_marks_the_current_page(self):
        from inventory_site import VIEWS, publish_overview
        site, _ = self.publish()
        items, projections = self.fixture()
        publish_overview(items, site, projections, [], [])
        for name, label in VIEWS:
            with self.subTest(page=name):
                page = self.page(site, name)
                nav = page[page.index('<nav class="ov-views"'):page.index('</nav>')]
                self.assertEqual(nav.count('<a '), 5)
                self.assertEqual(re.findall(r'<a href="date/(\w+)/" aria-current="page">', nav), [name])
                self.assertEqual(nav.count('aria-current'), 1)
                self.assertEqual(re.findall(r'<a href="date/(\w+)/"', nav), list(RESERVED_DATA_SLUGS))
                self.assertIn('<base href="../../">', page)
                self.assertNotIn('v=BUILD', page)
                self.assertNotIn('<!--', page)
                self.assertIn('Lăsate pe dinafară (', page, 'every page ends with the entries that the inventory leaves out')
                self.assertIn('Lipsa', page)

    def test_the_links_of_the_views_resolve_from_the_folder_of_the_page_and_no_anchor_is_bare(self):
        from urllib.parse import urljoin, urlsplit
        site, _ = self.publish()
        for name in ('furnizori', 'formate', 'licente', 'gazde'):
            page = self.page(site, name)
            base = urljoin('https://civtech.example/date/' + name + '/', '../../')
            for href in re.findall(r'href="([^"]+)"', page):
                if href.startswith('https://'):
                    continue
                self.assertFalse(href.startswith(('#', '/')), f'{name}: {href}')
                target = urlsplit(urljoin(base, href))
                self.assertEqual(target.netloc, 'civtech.example')
                if target.fragment and target.path.startswith('/date/') and target.path.split('/')[2] in RESERVED_DATA_SLUGS and target.path != f'/date/{name}/':
                    other = self.page(site, target.path.split('/')[2])
                    self.assertIn(f'id="{target.fragment}"', other, f'{name}: the anchor {href} does not exist')

    def test_the_entry_page_links_each_provider_and_format_to_an_anchor_that_exists(self):
        from common import provider_table
        from inventory_site import source_links
        rows = [{'nume_sursa': 'SEAP', 'furnizor': 'seap', 'nume': 'SEAP', 'eticheta': '', 'tip': 'institutie-publica', 'stare': 'acceptat', 'nota': ''}]
        table = provider_table(rows)
        items, projections = self.fixture()
        site, _ = self.publish(table)
        furnizori, formate = self.page(site, 'furnizori'), self.page(site, 'formate')
        for item in items[:2]:
            line = source_links(item, projections[item['slug']][1], table)
            for fragment in re.findall(r'date/furnizori/#([\w-]+)', line):
                self.assertIn(f'id="{fragment}"', furnizori)
            for fragment in re.findall(r'date/formate/#([\w-]+)', line):
                self.assertIn(f'id="{fragment}"', formate)
            self.assertIn('date/formate/#fmt-csv', line)
        self.assertIn('date/furnizori/#f-seap', source_links(items[0], projections['a'][1], table))
        self.assertIn('date/furnizori/#f-nume-sicap-seap', source_links(items[0], projections['a'][1], table), 'a name without an accepted row links to its own anchor')
        self.assertEqual(source_links(items[2], [], table), '')

    def test_the_finder_header_links_the_four_pages(self):
        header = (Path(__file__).parent / 'templates/inventory.html').read_text()
        for name in ('furnizori', 'formate', 'licente', 'gazde'):
            self.assertIn(f'href="date/{name}/"', header)

    def test_the_label_file_replaces_the_labels_of_the_providers_of_the_finder(self):
        import inventory_site
        self.assertFalse(hasattr(inventory_site, 'SOURCE_LABELS'), 'the labels moved to furnizori.csv')


class Scope(unittest.TestCase):
    """The scope of the variable inventory: a project or a resource, not inactive, with a relation to data other than `fara-date` (docs/briefs/data-relation.md, section 3).
    The fixtures build their own items: no test here pins the value of `relatie_date` that an editor sets for a real entry."""

    ROOT = Path(__file__).resolve().parents[1]

    def fixture(self, tmp):
        """A data root with fields for every slug (also for the out-of-scope ones), so that only the scope can keep an entry out."""
        root = Path(tmp) / 'integrare'
        obs = root.parent / 'observatii'
        inv = obs / 'inventare'
        inv.mkdir(parents=True)
        (obs / 'documentare').mkdir()
        slugs = ['in-date', 'in-calcul', 'in-resource', 'no-data', 'unassessed', 'gone-offline', 'gone-archived', 'gone-nodata', 'an-org']
        (obs / 'documentare/index.json').write_text(json.dumps({'entries': [
            {'slug': 'an-org', 'pages': [{'state': 'colectat', 'scope': 'proiect', 'kind': 'metodologie', 'final_url': 'https://org.example/method'}]}]}))
        (inv / 'proiecte.json').write_text(json.dumps({'proiecte': [{'slug': slug, 'surse_structurate': ['s-' + slug]} for slug in slugs]}))
        (inv / 'seturi-date.json').write_text(json.dumps({'surse': [
            {'id': 's-' + slug, 'url': f'https://example.org/{slug}.csv', 'format': 'csv',
             'campuri': [{'nume': 'col_' + slug, 'cale': 'col_' + slug, 'rol': 'camp-date', 'stare_tip': 'neprecizat-in-antet-csv', 'pointer': '/0'}]} for slug in slugs]}))
        site = Path(tmp) / 'site'
        (site / 'inventar').mkdir(parents=True)
        for name in ('style.css', 'inventory.css', 'inventory.js'):
            (site / name).write_text('/* fixture */')
        items = [built('in-date'), built('in-calcul', dataRelation='calcul', name='Calculator'), built('in-resource', kind='resursa', dataRelation='date-proprii'),
                 built('no-data', dataRelation='fara-date'), built('no-data-resource', kind='resursa', dataRelation='fara-date'),
                 built('unassessed', dataRelation=''), built('gone-offline', status='offline'), built('gone-archived', status='arhivat', dataRelation=''),
                 built('gone-nodata', kind='resursa', status='arhivat', dataRelation='fara-date'), built('an-org', kind='organizatie', dataRelation='')]
        return root, site, items

    def publish(self, tmp):
        root, site, items = self.fixture(tmp)
        with patch('inventory_site.observation_paths', return_value={'profile': root.parent / 'observatii/profil.csv'}):
            projections = publish_preview(items, root, site)
        publish_finder(items, root, site, projections)
        return site, items

    def test_one_rule_decides_from_kind_status_and_relation_to_data(self):
        cases = [(('proiect', 'activ', 'date-publice'), ''), (('resursa', 'activ', 'date-proprii'), ''), (('proiect', 'necunoscut', 'calcul'), ''),
                 (('proiect', 'neverificat', 'calcul'), ''), (('proiect', 'offline', 'date-publice'), 'inactiv'), (('resursa', 'arhivat', 'calcul'), 'inactiv'),
                 (('proiect', 'arhivat', 'fara-date'), 'inactiv'), (('proiect', 'offline', ''), 'inactiv'),
                 (('proiect', 'activ', 'fara-date'), 'fara-date'), (('resursa', 'necunoscut', 'fara-date'), 'fara-date'),
                 (('proiect', 'activ', ''), 'neevaluat'), (('resursa', 'activ', 'cod-necunoscut'), 'neevaluat'),
                 (('organizatie', 'activ', 'date-publice'), 'in-afara-ariei'), (('organizatie', 'offline', ''), 'in-afara-ariei')]
        for (kind, status, relation), reason in cases:
            with self.subTest(kind=kind, status=status, relation=relation):
                self.assertEqual(inventory_exclusion(kind, status, relation), reason)
                self.assertEqual(scope_reason({'kind': kind, 'status': status, 'dataRelation': relation}), reason)
        self.assertEqual(scope_reason({'kind': 'proiect', 'status': 'activ'}), 'neevaluat', 'an item without the key is not assessed')

    def test_the_rule_follows_the_code_list_and_the_inactive_group_of_the_explorer(self):
        from common import IN_SCOPE_RELATIONS, INACTIVE_STATUSES
        listed = []
        with (self.ROOT / 'data/taxonomy-v2/valori.csv').open(newline='') as handle:
            listed = [row['cod'] for row in csv.DictReader(handle) if row['lista'] == 'relatie_date']
        self.assertEqual(sorted(listed), sorted([*IN_SCOPE_RELATIONS, 'fara-date']), 'a new code needs a decision about its scope')
        app = (self.ROOT / 'site/app.js').read_text()
        for code in (*listed, 'neevaluat'):
            self.assertNotIn(f"'{code}'", app, f'site/app.js keeps no list of the codes: it reads vocabulary.dataGroups ({code})')
        inactive = re.findall(r"^\s+(\w+): \{ label: '[^']*', cls: '\w+', group: 'inactiv' \}", app, re.M)
        self.assertEqual(sorted(inactive), sorted(INACTIVE_STATUSES), 'isInactive in site/app.js and the Python rule name the same statuses')

    def test_the_two_public_groups_cover_every_code_and_agree_with_the_scope_rule(self):
        from common import DATA_GROUPS, data_group, public_reason
        with (self.ROOT / 'data/taxonomy-v2/valori.csv').open(newline='') as handle:
            listed = [row['cod'] for row in csv.DictReader(handle) if row['lista'] == 'relatie_date']
        self.assertEqual([g['key'] for g in DATA_GROUPS], ['cu-date', 'fara-date'])
        for code in (*listed, ''):
            with self.subTest(code=code or '(empty)'):
                homes = [g['key'] for g in DATA_GROUPS if code in g['codes']]
                self.assertEqual(homes, [data_group(code)], 'one group for each code, and an empty value too')
                in_scope = inventory_exclusion('proiect', 'activ', code) == ''
                self.assertEqual(data_group(code) == 'cu-date', in_scope, 'the group cu-date is the scope of /date/')
                self.assertEqual(public_reason(inventory_exclusion('proiect', 'activ', code)) == 'fara-date', data_group(code) == 'fara-date')
        self.assertEqual(data_group('cod-necunoscut'), 'fara-date', 'a code that valori.csv does not list is without data')
        self.assertEqual([public_reason(r) for r in ('fara-date', 'neevaluat', 'inactiv', 'in-afara-ariei')], ['fara-date', 'fara-date', 'inactiv', 'in-afara-ariei'])

    def test_the_preview_the_finder_and_the_list_leave_out_the_same_entries_and_count_them_by_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, items = self.publish(tmp)
            by = {i['slug']: i for i in items}
            in_scope = ['in-calcul', 'in-date', 'in-resource']
            index = json.loads((site / 'inventar/index.json').read_text())
            self.assertEqual(sorted(e['slug'] for e in index['entries']), in_scope)
            # The explorer panel is not limited by the scope: every entry with fields keeps its file and its `inventory` key.
            with_fields = [slug for slug in by if slug != 'no-data-resource']
            self.assertEqual(sorted(p.stem for p in (site / 'inventar').glob('*.json') if p.stem != 'index'), sorted(with_fields))
            self.assertEqual([slug for slug, item in by.items() if 'inventory' in item], with_fields)
            page = (site / 'date/lista/index.html').read_text()
            body = page[page.index('<tbody>'):page.index('</tbody>')]
            self.assertEqual(sorted(re.findall(r'<tr id="([^"]+)">', body)), in_scope)
            for slug in set(by) - set(in_scope):
                self.assertNotIn(f'/{slug}/"', page.split('<section class="ov-left">')[0], slug + ' is named in the table or in the list of entries without fields')
            self.assertEqual(index['leftOut'], {'fara-date': {'proiect': 2, 'resursa': 1}, 'inactiv': {'proiect': 2, 'resursa': 1}},
                             'without data: the code fara-date and an empty value together; inactive: whatever the code')
            self.assertEqual(left_out(items), index['leftOut'])

    def test_the_list_says_how_many_entries_it_leaves_out_by_reason_and_links_the_explorer(self):
        with tempfile.TemporaryDirectory() as tmp:
            site, _ = self.publish(tmp)
            page = (site / 'date/lista/index.html').read_text()
        section = page[page.index('<section class="ov-left">'):page.index('</section>', page.index('<section class="ov-left">'))]
        self.assertIn('<h2>Lăsate pe dinafară (6)</h2>', section, '3 without data (2 with the code, 1 with an empty value), 3 inactive')
        reasons = dict(re.findall(r'<li data-reason="([a-z-]+)">(.*?)</li>', section))
        self.assertEqual(list(reasons), ['fara-date', 'inactiv'], 'two reasons; an empty value is without data')
        self.assertIn('(3)', reasons['fara-date'])
        self.assertIn('(3)', reasons['inactiv'])
        self.assertIn('<a href="./?dat=fara-date">2 proiecte</a>', reasons['fara-date'])
        self.assertIn('<a href="./?k=resursa&amp;dat=fara-date">1 resursă</a>', reasons['fara-date'])
        self.assertNotIn('neevaluat', section.lower())
        self.assertNotIn('Neevaluat', section)
        self.assertIn('<a href="./?st=inactiv">2 proiecte</a>', reasons['inactiv'])
        self.assertIn('<a href="./?k=resursa&amp;st=inactiv">1 resursă</a>', reasons['inactiv'])
        bare = page[page.index('<section class="ov-bare">'):page.index('</section>', page.index('<section class="ov-bare">'))]
        self.assertIn('<h2>De analizat (', bare, 'the heading says that the inventory of these entries is still to do')
        self.assertIn('Lipsa câmpurilor nu înseamnă lipsa datelor', bare, 'the note stays with the entries that are in scope and have no fields')
        self.assertNotIn('Lipsa câmpurilor', section)

    def test_the_note_is_absent_when_the_inventory_leaves_nothing_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, site, _ = self.fixture(tmp)
            items = [built('in-date')]
            with patch('inventory_site.observation_paths', return_value={'profile': root.parent / 'observatii/profil.csv'}):
                projections = publish_preview(items, root, site)
            publish_finder(items, root, site, projections)
            self.assertNotIn('ov-left', (site / 'date/lista/index.html').read_text())
            self.assertEqual(json.loads((site / 'inventar/index.json').read_text())['leftOut'],
                             {'fara-date': {'proiect': 0, 'resursa': 0}, 'inactiv': {'proiect': 0, 'resursa': 0}})

    def test_an_entry_that_leaves_the_scope_keeps_its_explorer_panel_and_leaves_the_finder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, site, items = self.fixture(tmp)
            with patch('inventory_site.observation_paths', return_value={'profile': root.parent / 'observatii/profil.csv'}):
                publish_preview(items, root, site)
                self.assertTrue((site / 'inventar/in-date.json').exists() and 'inventory' in items[0])
                fresh = [built('in-date', dataRelation='fara-date')]
                projections = publish_preview(fresh, root, site)
            publish_finder(fresh, root, site, projections)
            self.assertTrue((site / 'inventar/in-date.json').exists())
            self.assertEqual(fresh[0]['inventory']['count'], 1)
            self.assertEqual(json.loads((site / 'inventar/index.json').read_text())['entries'], [])

    def test_an_organisation_keeps_its_documentation_links_in_the_explorer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, site, items = self.fixture(tmp)
            with patch('inventory_site.observation_paths', return_value={'profile': root.parent / 'observatii/profil.csv'}):
                publish_preview(items, root, site)
            org = next(i for i in items if i['slug'] == 'an-org')
            self.assertEqual([d['url'] for d in org['inventory']['docs']], ['https://org.example/method'], 'the fixture gives the organisation a methodology page')

    def test_the_site_and_the_scripts_give_every_public_entry_the_same_reason(self):
        import build
        from common import PUBLIC_ROOT, inventory_scope, public_catalogue
        with tempfile.TemporaryDirectory() as tmp:
            items, _ = build.items_v2(PUBLIC_ROOT, Path(tmp))
        reasons = inventory_scope(public_catalogue(PUBLIC_ROOT), PUBLIC_ROOT)
        self.assertEqual({i['slug'] for i in items}, set(reasons))
        self.assertEqual({i['slug']: scope_reason(i) for i in items}, reasons,
                         'collect_docs.py, inventory.py and the coverage export read the catalogue; the site reads the built items: both must agree')


if __name__ == '__main__':
    unittest.main()
