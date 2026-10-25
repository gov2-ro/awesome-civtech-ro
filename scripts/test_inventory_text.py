"""Offline checks for the text-format readers: HTML and markdown tables, SQL, C#, Laravel PHP, annotated JSON in documents, page
scripts and API reference pages. Fixtures in scripts/fixtures/text are copies of public files at recorded revisions or pages read on
2026-10-25. `demoanaf-api-docs.html` is a trimmed copy of https://demoanaf.ro/api-docs (the copy buttons and 52 of the 60 endpoint cards
removed; the markup of the kept parts is unchanged). `harta-firmelor-date.html` is a trimmed copy of https://harta-firmelor.ro/date as the owner
saved it from their browser on 2026-10-25 (the scripts, the header and the footer, five of the eight file cards and ten of the fourteen columns of
the first card removed; the markup of the kept parts is unchanged)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inventory import analyse_source, check_report, contract_index, link_contract, parse_source, strip_links
from inventory_apidocs import operations as api_operations, parameter_items, read as read_api_docs
from inventory_csvcards import csv_datasets, read as read_csv_cards
from inventory_state import protect
from inventory_text import (csharp, html_tabele, js_acces, json_comentat, markdown, parse_tables, php, sample_type, sql, table_fields)
from test_inventory_state import Net, Workspace, docs_for, entry

FIXTURES = Path(__file__).parent / 'fixtures/text'


def text(name):
    return (FIXTURES / name).read_text()


def interval(field):
    start, end = field['pointer'].split(':')[1].split('-')
    return int(start), int(end)


class HtmlTables(unittest.TestCase):
    def test_data_table_header_cells_are_fields_with_declared_units_and_sample_types(self):
        _, fields, _ = html_tabele(text('afacut-tabel.html'))
        self.assertEqual([f['nume'] for f in fields], ['Data raportării', 'Tranșa (mld lei)', 'Cumulat (mld lei)'])
        self.assertEqual([f['unitate'] for f in fields], [None, 'mld lei', 'mld lei'])
        self.assertEqual([f['tipuri_observate'] for f in fields], [['forma-de-data'], ['forma-numerica'], ['forma-numerica']])
        self.assertTrue(all(f['stare_tip'] == 'antet-tabel-html' and f['tip_declarat'] is None for f in fields))
        self.assertEqual(fields[1]['pointer'], '/tabele/1/antet/1')

    def test_dictionary_table_gives_one_field_per_row_with_its_own_unit_and_period(self):
        _, fields, _ = html_tabele(text('biografia-tabele.html'), {'tabele': [2]})
        self.assertEqual([f['nume'] for f in fields], ['LOC101B', 'LOC103B', 'LOC104B', 'LOC108B'])
        first = fields[0]
        self.assertEqual((first['descriere'], first['unitate'], first['perioada_declarata']), ('Locuințe existente la sfârșitul anului', 'Numar', '1990–2025'))
        self.assertEqual(fields[1]['unitate'], 'Metri patrati arie desfasurata')
        self.assertTrue(all(f['stare_tip'] == 'declarat-in-tabel-documentatie' for f in fields))
        every = html_tabele(text('biografia-tabele.html'))[1]
        self.assertGreater(len(every), len(fields), 'without a selection the first table contributes its header cells')

    def test_group_list_table_keeps_the_group_and_does_not_invent_types(self):
        _, fields, _ = html_tabele(text('registru-api.html'))
        names = {f['nume']: f['grup'] for f in fields}
        self.assertEqual(names['CUI'], 'Identificare')
        self.assertEqual(names['IBAN'], 'Fiscal')
        self.assertTrue(all(f['tip_declarat'] is None and f['stare_tip'] == 'declarat-in-text-documentatie' for f in fields))

    def test_consent_tables_and_misaligned_rows_do_not_become_variables(self):
        body = ('<table><tr><th>Cookie</th><th>Duration</th></tr><tr><td>a</td><td>1 year</td></tr></table>'
                '<table><tr><th>Candidat</th><th>Voturi</th><th>%</th></tr><tr><td></td><td></td><td>X</td><td>1.200</td><td>3 %</td></tr></table>')
        _, fields, _ = html_tabele(body)
        self.assertEqual([f['nume'] for f in fields], ['Candidat', 'Voturi', '%'])
        self.assertEqual([f['tipuri_observate'] for f in fields], [[], [], []], 'a row of another width is not matched to columns')

    def test_sample_types_keep_identifiers_as_text_and_romanian_numbers_as_numbers(self):
        self.assertEqual([sample_type(v) for v in ('0,53', '211.562', '36,16 %', '27 mai 2025', '2026-10-22', '', 'Alba', '007')],
                         ['forma-numerica', 'forma-numerica', 'forma-numerica', 'forma-de-data', 'forma-de-data', 'null', 'text', 'forma-numerica'])

    def test_header_row_of_th_cells_and_thead_are_both_headers(self):
        tables = parse_tables('<table><thead><tr><td>a</td></tr></thead><tbody><tr><td>1</td></tr></tbody></table>'
                              '<table><tr><th>b</th></tr><tr><td>2</td></tr></table><table><tr><td>c</td></tr></table>')
        self.assertEqual([t['header'] for t in tables], [['a'], ['b'], None])

    def test_markdown_dictionary_tables_only(self):
        body = '| Field | Type | Description |\n| --- | --- | --- |\n| `id` | string | The key |\n\n| Step | Model | Why |\n| - | - | - |\n| 1 | a | b |\n'
        _, fields, _ = markdown(body)
        self.assertEqual([(f['nume'], f['tip_declarat'], f['descriere']) for f in fields], [('`id`', 'string', 'The key')])


class CodeReaders(unittest.TestCase):
    def test_csharp_properties_keep_declared_types_and_exact_locators(self):
        body = text('PollingStationModel.cs')
        _, fields, _ = csharp(body)
        got = {f['cale']: f['tip_declarat'] for f in fields}
        self.assertEqual(got['PollingStationModel.Latitude'], 'double')
        self.assertEqual(got['PollingStationModel.AssignedAddresses'], 'IEnumerable<AssignedAddresses>')
        self.assertEqual(got['AssignedAddresses.StreetCode'], 'string')
        for field in fields:
            start, end = interval(field)
            self.assertIn(field['nume'], body[start:end])
            self.assertEqual(field['linie'], body.count('\n', 0, start) + 1)

    def test_csharp_query_binding_is_an_api_parameter_with_its_public_name(self):
        _, fields, _ = csharp(text('PollingStationsQuery.cs'))
        by_name = {f['nume']: f for f in fields}
        self.assertEqual(by_name['pollingStationId']['tip_declarat'], 'int?')
        self.assertEqual((by_name['pollingStationId']['rol'], by_name['pollingStationId']['loc'], by_name['pollingStationId']['nume_in_cod']),
                         ('parametru-api', 'query', 'PollingStationId'))

    def test_sql_columns_keep_their_declared_type_and_nullability(self):
        body = text('patch-00001.sql')
        _, fields, _ = sql(body)
        got = {f['cale']: (f['tip_declarat'], f['obligatoriu']) for f in fields}
        self.assertEqual(got['variable.name'], ('varchar(100)', True))
        self.assertEqual(got['user.createDate'], ('int', True))
        self.assertNotIn('variable.primary', ' '.join(got), 'key clauses are not columns')
        self.assertEqual(len(fields), 10)
        start, end = interval(next(f for f in fields if f['cale'] == 'user.email'))
        self.assertEqual(body[start:end], 'email varchar(255) not null')

    def test_sql_alter_add_column(self):
        _, fields, _ = sql('alter table statement add column verdict tinyint(4) not null default 0;')
        self.assertEqual((fields[0]['cale'], fields[0]['tip_declarat'], fields[0]['modificare']), ('statement.verdict', 'tinyint(4)', 'alter-add'))

    def test_laravel_resource_keeps_docblock_descriptions_and_types_and_nothing_else(self):
        _, fields, _ = php(text('TurnoutResource.php'))
        by_name = {f['nume']: f for f in fields}
        self.assertEqual((by_name['total']['tip_declarat'], by_name['total']['descriere']), ('integer', 'Total number of people who voted in the election.'))
        self.assertIsNone(by_name['areas']['tip_declarat'], 'a key without a docblock declares no type')
        self.assertEqual(by_name['demographics']['expresie'], 'DemographicsResource::make($this->demographics)')
        self.assertEqual({f['rol'] for f in fields}, {'camp-raspuns'})

    def test_laravel_migration_columns_modifiers_and_stored_formulas(self):
        _, fields, _ = php(text('create_turnouts_table.php'))
        by_name = {f['cale']: f for f in fields}
        total = by_name['turnouts.total']
        self.assertEqual(total['tip_declarat'], 'integer')
        self.assertEqual(total['formula_declarata'], 'permanent + complement + supplement + mobile')
        self.assertIn('unsigned', total['modificatori'])
        self.assertFalse(by_name['turnouts.area']['obligatoriu'])
        self.assertEqual(by_name['turnouts.election_id']['baza_numelui'], 'conventie-laravel')
        self.assertIn('turnouts.men_18-24', by_name)
        self.assertEqual(by_name['_temp_turnouts.section']['grup'], '_temp_turnouts')

    def test_laravel_migration_nullable_chain_over_several_lines(self):
        _, fields, _ = php(text('create_votes_table.php'))
        county = next(f for f in fields if f['cale'] == 'votes.county_id')
        self.assertEqual((county['tip_declarat'], county['obligatoriu']), ('smallInteger', False))

    def test_page_script_names_are_usage_not_a_schema(self):
        body = ("<script>const CONFIG = {token: 'x'};</script><script>r.fields['Județ']; r.fields[\"Județ\"]; r.fields.Vârsta; other.fields['no'];"
                " rec.records['Y']</script>")
        _, fields, _ = js_acces(body)
        self.assertEqual([(f['nume'], f['accesari'], f['stare_tip']) for f in fields],
                         [('Județ', 2, 'utilizat-in-cod-pagina'), ('Vârsta', 1, 'utilizat-in-cod-pagina'), ('no', 1, 'utilizat-in-cod-pagina')])
        self.assertTrue(all(f['tip_declarat'] is None for f in fields))
        start, end = interval(fields[0])
        self.assertEqual(body[start:end], "fields['Județ']")

    def test_annotated_json_shapes_keep_alternatives_comments_and_type_names(self):
        body = text('extraction-shape.md')
        _, fields, truncated = json_comentat(body)
        by_path = {f['cale'].split('::')[-1]: f for f in fields}
        self.assertEqual(by_path['document_type']['valori_enum'][:2], ['plenary_stenogram', 'plenary_joint_session'])
        self.assertEqual(by_path['metadata.chamber']['valori_enum'], ['Camera Deputaților', 'Senatul', 'joint'])
        self.assertIn('per-component dict', by_path['extraction.extractor_versions']['descriere'])
        self.assertEqual(by_path['body']['tipuri_observate'], ['object'])
        self.assertEqual(by_path['committees[].chair']['tip_referinta'], 'Speaker')
        self.assertTrue(all(f['stare_tip'] == 'exemplu-in-documentatie' and f['tip_declarat'] is None for f in fields))
        for field in fields:
            start, end = interval(field)
            self.assertEqual(body[start:end], '"' + field['nume'] + '"')


def api_card(method, path, params=None, description='Descriere', badges=('Pro',), cache=None):
    """A minimal endpoint card in the markup that the reader needs: a method badge, a path template, badges, paragraphs."""
    head = f'<div><span class="m">{method}</span><code class="p">{path}</code>' + ''.join(f'<span>{b}</span>' for b in badges) + '</div>'
    head += f'<span class="c">Cache:<!-- --> <!-- -->{cache}</span>' if cache else ''
    body = f'<p class="d">{description}</p>' + (f'<p class="x">Parametri:<!-- --> <!-- -->{params}</p>' if params is not None else '')
    return f'<h2>Grup</h2>{head}{body}'


def span_text(body, field):
    start, end = interval(field)
    return body[start:end]


class ApiDocs(unittest.TestCase):
    body = text('demoanaf-api-docs.html')

    def setUp(self):
        self.operations, self.fields = read_api_docs(self.body)
        self.by_op = {}
        for field in self.fields:
            self.by_op.setdefault(field.get('operatie'), {})[field['nume']] = field

    def test_operations_keep_method_template_access_cache_and_description_as_the_page_writes_them(self):
        names = [o['operatie'] for o in self.operations]
        self.assertEqual(names[:3], ['GET /api/company/{cui}', 'GET /api/company/{cui}/balance/{year}', 'POST /api/company/batch'])
        first = self.operations[0]
        self.assertEqual((first['metoda'], first['cale'], first['acces'], first['cache'], first['categorie']),
                         ('GET', '/api/company/{cui}', ['Pro', 'x402'], '24h', 'Companie'))
        self.assertTrue(first['descriere'].startswith('Informații complete despre o firmă'))
        only_pro = next(o for o in self.operations if o['cale'] == '/api/sicap/procedure/{notice}/search')
        self.assertEqual(only_pro['acces'], ['Pro'], 'an endpoint without the x402 badge does not accept per-request payment')
        self.assertIsNone(next(o for o in self.operations if o['cale'] == '/api/rates').get('in_contract', None))
        self.assertTrue(span_text(self.body, first).startswith('<span') and span_text(self.body, first).endswith('</code>'))
        self.assertIn('/api/company/:cui', span_text(self.body, first))

    def test_a_description_that_is_an_untranslated_key_is_not_a_description(self):
        top = next(o for o in self.operations if o['cale'] == '/api/seap/cpv/{cpv}/top-suppliers')
        self.assertIsNone(top['descriere'])
        self.assertEqual(top['descriere_cheie_nerezolvata'], 'ep.seap-cpv-top.description')
        self.assertNotIn('descriere_cheie_nerezolvata', self.operations[0])

    def test_parameter_text_gives_descriptions_hints_alternatives_and_the_declared_body_type(self):
        cui = self.by_op['GET /api/company/{cui}']['cui']
        self.assertEqual((cui['descriere'], cui['rol'], cui['loc'], cui['baza_loc']), ('1-10 cifre', 'parametru-api', 'path', 'sablon-cale'))
        self.assertEqual(self.by_op['GET /api/company/{cui}/balance/{year}']['year']['indicatie_pagina'], 'YYYY')
        search = self.by_op['GET /api/search']
        self.assertEqual((search['q']['indicatie_pagina'], search['limit']['indicatie_pagina']), ('text', '1-50, default 20'))
        contracts = self.by_op['GET /api/seap/company/{cui}/contracts']
        self.assertEqual(contracts['role']['valori_enum'], ['authority', 'supplier', 'both'])
        self.assertNotIn('valori_enum', contracts['limit'], 'a range in parentheses is a hint, not a list of alternatives')
        batch = self.by_op['POST /api/company/batch']['cuis']
        self.assertEqual((batch['rol'], batch['loc'], batch['tip_declarat']), ('corp-cerere', 'body', 'string[]'))
        self.assertTrue(all(f['tip_declarat'] is None for f in self.fields if f['rol'] == 'parametru-api'), 'no type is inferred')

    def test_location_is_set_only_when_the_page_shows_it(self):
        contracts = self.by_op['GET /api/seap/company/{cui}/contracts']
        self.assertEqual((contracts['cui']['loc'], contracts['limit']['loc'], contracts['limit']['baza_loc']), ('path', 'query', 'exemplu-cerere'))
        self.assertIsNone(contracts['dateFrom']['loc'], 'a GET parameter that is neither in the template nor in the example has no stated place')
        self.assertNotIn('baza_loc', contracts['dateFrom'])

    def test_a_path_parameter_missing_from_the_parameter_text_is_still_declared_by_the_template(self):
        notice = self.by_op['GET /api/sicap/procedure/{notice}/search']['notice']
        self.assertEqual((notice['loc'], span_text(self.body, notice)), ('path', ':notice'))
        self.assertNotIn('descriere', notice)

    def test_an_endpoint_without_parameters_has_no_input_records(self):
        self.assertNotIn('GET /api/rates', self.by_op)

    def test_every_locator_cuts_the_text_that_the_record_names(self):
        for field in self.fields:
            cut = span_text(self.body, field)
            self.assertIn(field['nume'], cut.replace('&quot;', ''), field['pointer'])
        self.assertEqual(span_text(self.body, self.by_op['POST /api/company/batch']['cuis']), 'cuis: string[]')
        self.assertEqual(span_text(self.body, self.by_op['GET /api/search']['limit']), 'limit (1-50, default 20)')

    def test_response_members_are_the_named_envelope_and_the_error_example_and_nothing_else(self):
        responses = [f for f in self.fields if f['rol'] == 'camp-raspuns']
        self.assertEqual([(f['cale'], f['stare_tip']) for f in responses],
                         [('$.success', 'declarat-in-documentatie-api'), ('$.data', 'declarat-in-documentatie-api'),
                          ('$.meta', 'declarat-in-documentatie-api'), ('$.error', 'exemplu-in-documentatie'),
                          ('$.error.code', 'exemplu-in-documentatie'), ('$.error.message', 'exemplu-in-documentatie')])
        self.assertTrue(all(f['tip_declarat'] is None and 'operatie' not in f and f['grup'] == 'plic-raspuns' for f in responses))
        self.assertEqual([f['status_raspuns'] for f in responses if 'status_raspuns' in f], ['429'] * 3)
        self.assertEqual(span_text(self.body, responses[0]), 'success')
        self.assertEqual(span_text(self.body, responses[4]), '&quot;code&quot;')

    def test_same_name_in_another_role_is_a_different_record(self):
        body = api_card('GET', '/api/caen/:code', 'code (4 cifre)') + text('demoanaf-api-docs.html')
        _, fields = read_api_docs(body)
        self.assertEqual({(f['nume'], f['rol']) for f in fields if f['nume'] == 'code'}, {('code', 'parametru-api'), ('code', 'camp-raspuns')})

    def test_unknown_shapes_are_errors_and_never_guesses(self):
        for params in ('cui - 1 to 10', 'a b c', 'q (text', 'body: cuis'):
            with self.assertRaises(ValueError, msg=params):
                read_api_docs(api_card('GET', '/api/x', params))
        with self.assertRaises(ValueError):
            read_api_docs('<html><body><h1>Not an API page</h1></body></html>')
        with self.assertRaises(ValueError):
            read_api_docs(api_card('GET', '/api/x', 'q <b>text</b>'))
        with self.assertRaises(ValueError):
            read_api_docs(api_card('GET', '/api/x') + api_card('GET', '/api/x'))

    def test_semicolons_commas_and_dashes_split_only_outside_brackets(self):
        items = parameter_items('q — text, număr anunț, cod CPV sau CUI; cpv, from (AAAA-LL-ZZ), limit (1–50); number — contract (1/32435 → 1%2F32435)')
        self.assertEqual([(i[0], i[1], i[2]) for i in items],
                         [('q', 'text, număr anunț, cod CPV sau CUI', None), ('cpv', None, None), ('from', None, 'AAAA-LL-ZZ'),
                          ('limit', None, '1–50'), ('number', 'contract (1/32435 → 1%2F32435)', None)])

    def test_entities_in_the_parameter_text_keep_the_whole_text_as_the_locator(self):
        body = api_card('GET', '/api/x', 'q (a &amp; b), limit')
        _, fields = read_api_docs(body)
        self.assertEqual([f['indicatie_pagina'] for f in fields if 'indicatie_pagina' in f], ['a & b'])
        self.assertEqual({span_text(body, f) for f in fields}, {'q (a &amp; b), limit'})

    def test_hint_selects_the_reader_and_the_source_keeps_operations_and_fields_apart(self):
        response = {'url': 'https://a.example/api-docs', 'final_url': 'https://a.example/api-docs', 'state': 'ok', 'content_type': 'text/html',
                    'body': self.body}
        record = analyse_source(response, {'tip': 'html-api-docs', 'contract': 'https://a.example/openapi.json'})
        self.assertEqual((record['format'], record['baza_tipului'], record['stare']), ('html-api-docs', 'cod-sau-documentatie', 'analizat'))
        self.assertEqual((len(record['operatii']), len(record['campuri'])), (8, 26))
        self.assertEqual(record['operatii'], api_operations(self.body))
        with self.assertRaises(ValueError):
            parse_source(self.body, 'https://a.example/api-docs', 'text/html')


CONTRACT = {'openapi': '3.0.0', 'paths': {
    '/api/company/{cui}': {'get': {'parameters': [{'name': 'cui', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}]}},
    '/api/search': {'get': {'parameters': [{'name': 'q', 'in': 'query', 'schema': {'type': 'string'}}]}},
    '/api/rates': {'get': {}},
    '/api/contract-only': {'get': {'parameters': [{'name': 'x', 'in': 'query', 'schema': {'type': 'string'}}]}}}}


class ApiDocsContract(unittest.TestCase):
    A = 'https://a.example/'

    def sources(self):
        page = {'url': self.A + 'api-docs', 'final_url': self.A + 'api-docs', 'state': 'ok', 'content_type': 'text/html', 'body': text('demoanaf-api-docs.html')}
        contract = {'url': self.A + 'openapi.json', 'final_url': self.A + 'openapi.json', 'state': 'ok', 'content_type': 'application/json',
                    'body': json.dumps(CONTRACT)}
        return (analyse_source(page, {'tip': 'html-api-docs', 'contract': self.A + 'openapi.json'}), analyse_source(contract))

    def test_each_operation_and_input_says_whether_the_contract_declares_it(self):
        page, contract = self.sources()
        linked = link_contract(page, contract, CONTRACT)
        by_name = {o['operatie']: o['in_contract'] for o in linked['operatii']}
        self.assertEqual(by_name['GET /api/rates'], {'sursa_id': contract['id'], 'pointer': '/paths/~1api~1rates/get'})
        self.assertIsNone(by_name['GET /api/seap/cpv/{cpv}/top-suppliers'])
        fields = {(f['operatie'], f['nume']): f['in_contract'] for f in linked['campuri'] if 'in_contract' in f}
        self.assertEqual(fields[('GET /api/search', 'q')]['pointer'], '/paths/~1api~1search/get/parameters/0')
        self.assertIsNone(fields[('GET /api/search', 'limit')], 'a parameter that only the page documents is marked null')
        self.assertEqual(fields[('GET /api/company/{cui}', 'cui')]['pointer'], '/paths/~1api~1company~1{cui}/get/parameters/0')
        self.assertFalse([f for f in linked['campuri'] if f['rol'] == 'camp-raspuns' and 'in_contract' in f], 'response members are not compared')
        summary = linked['comparatie_contract']
        self.assertEqual((summary['operatii_comune'], summary['operatii_doar_in_pagina'], summary['operatii_doar_in_contract']),
                         (3, 5, ['GET /api/contract-only']))
        self.assertEqual((summary['intrari_comune'], summary['intrari_doar_in_pagina'], summary['intrari_doar_in_contract']),
                         (2, 18, ['GET /api/contract-only :: x']))
        self.assertEqual(summary['sha256'], contract['sha256'])
        self.assertEqual(strip_links(linked)['campuri'], page['campuri'], 'the comparison adds keys and changes no reader output')

    def test_same_name_in_another_operation_is_not_a_match(self):
        page, contract = self.sources()
        document = json.loads(json.dumps(CONTRACT))
        document['paths']['/api/search']['get']['parameters'][0]['name'] = 'cui'
        linked = link_contract(page, contract, document)
        search_q = next(f for f in linked['campuri'] if f.get('operatie') == 'GET /api/search' and f['nume'] == 'q')
        self.assertIsNone(search_q['in_contract'])
        self.assertIn('GET /api/search :: cui', linked['comparatie_contract']['intrari_doar_in_contract'])
        self.assertEqual(sorted(contract_index(document)[1])[:1], [('parametru-api', 'GET /api/company/{cui}', 'cui')])

    def run_workspace(self):
        work = Workspace(self)
        entries = [entry('a', self.A)]
        docs = {'a': docs_for('a', self.A, [self.A + 'openapi.json'])}
        net = Net({self.A + 'openapi.json': json.dumps(CONTRACT), self.A + 'api-docs': text('demoanaf-api-docs.html')})
        spec = {'url': self.A + 'api-docs', 'citire': {'tip': 'html-api-docs', 'contract': self.A + 'openapi.json'}}
        work.run(entries, docs, net, add_sources=[('a', spec)])
        return work, entries, docs, net

    def test_a_run_compares_the_page_with_the_contract_and_a_replay_gives_the_same_bytes(self):
        work, entries, docs, _ = self.run_workspace()
        source = work.sources()[self.A + 'api-docs']
        self.assertEqual((source['comparatie_contract']['operatii_comune'], source['comparatie_contract']['intrari_comune']), (3, 2))
        self.assertEqual(work.profile('a')['campuri_din_surse'], 3 + 26 - 2, 'three contract parameters and 26 page records; the two that restate the contract count once')
        before = work.files()
        work.run(entries, docs, None, offline=True)
        self.assertEqual(work.files(), before)

    def test_evidence_check_recomputes_fields_operations_and_the_comparison(self):
        work, _, _, _ = self.run_workspace()
        obs = work.out.parent
        report = check_report(work.out, obs)
        self.assertEqual((report['errors'], report['verified']), ([], 2))
        path = work.out / 'seturi-date.json'
        state = json.loads(path.read_text())
        page = next(s for s in state['surse'] if s['url'] == self.A + 'api-docs')
        original = json.dumps(state)
        page['operatii'][0]['in_contract'] = None
        path.write_text(json.dumps(state))
        self.assertTrue(any('differ from the retained body' in e for e in check_report(work.out, obs)['errors']))
        page['operatii'][0]['in_contract'] = {'sursa_id': page['comparatie_contract']['sursa_id'], 'pointer': '/paths/~1api~1company~1{cui}/get'}
        page['comparatie_contract']['intrari_comune'] += 1
        path.write_text(json.dumps(state))
        self.assertTrue(any('comparison with the contract differs' in e for e in check_report(work.out, obs)['errors']))
        path.write_text(original)
        page['campuri'][0]['pointer'] = 'char:1-2'
        path.write_text(json.dumps(state))
        self.assertTrue(any('differ from the retained body' in e for e in check_report(work.out, obs)['errors']))

    def test_an_absent_contract_body_makes_the_comparison_unverified_not_corrupt(self):
        work, _, _, _ = self.run_workspace()
        contract = work.sources()[self.A + 'openapi.json']
        (work.out / contract['snapshot']).unlink()
        report = check_report(work.out, work.out.parent)
        self.assertEqual(report['errors'], [])
        self.assertIn('contract comparison: ' + self.A + 'api-docs', report['unavailable'])
        self.assertEqual(report['verified'], 1, 'only the page body was hash-verified')


class CsvCards(unittest.TestCase):
    """A page whose cards offer CSV files, each with a list of columns (harta-firmelor.ro/date). The reader never downloads a file."""
    URL = 'https://harta-firmelor.ro/date'

    def setUp(self):
        self.body = text('harta-firmelor-date.html')
        self.datasets, self.fields = read_csv_cards(self.body, self.URL)
        self.by_file = {d['fisier']['valoare']: d for d in self.datasets}

    def cut(self, pointer):
        start, end = pointer.split(':')[1].split('-')
        return self.body[int(start):int(end)]

    def test_each_card_with_a_download_link_is_a_dataset_and_other_cards_are_not(self):
        self.assertEqual(list(self.by_file), ['firme-pe-an-infiintare.csv', 'bilanturi-pe-an.csv', 'registru-cifre.csv'])
        self.assertEqual([d['coloane'] for d in self.datasets][1], ['year', 'balance_sheets', 'employees_reported', 'median_turnover_lei', 'partial_year'])
        self.assertNotIn('Când se actualizează', ' '.join(d['titlu']['valoare'] for d in self.datasets))

    def test_dataset_facts_keep_the_page_text_with_an_exact_locator_and_say_what_was_changed(self):
        sheets = self.by_file['bilanturi-pe-an.csv']
        self.assertEqual((sheets['titlu']['valoare'], sheets['randuri']['valoare'], sheets['perioada']['valoare']), ('Bilanțuri depuse pe an', 18, '2008 → 2025'))
        self.assertEqual(sheets['masurat_la'], {'valoare': '2026-09-11', 'pointer': sheets['masurat_la']['pointer'], 'baza': 'declarat-in-pagina',
                                                'text': '11.09.2026', 'transformare': 'data-zz.ll.aaaa-in-iso'})
        self.assertEqual(self.cut(sheets['masurat_la']['pointer']), '11.09.2026')
        self.assertEqual(self.cut(sheets['perioada']['pointer']), '2008 → 2025')
        self.assertEqual(self.cut(sheets['fisier']['pointer']), '/date/bilanturi-pe-an.csv')
        self.assertEqual((sheets['adresa']['valoare'], sheets['adresa']['legatura']), ('https://harta-firmelor.ro/date/bilanturi-pe-an.csv', '/date/bilanturi-pe-an.csv'))
        registry = self.by_file['registru-cifre.csv']
        self.assertEqual(registry['perioada']['valoare'], 'situația la 11.09.2026', 'a snapshot period stays text; it is not turned into a range')

    def test_the_sources_of_a_file_are_listed_apart_in_page_order_with_their_own_locators(self):
        names = [s['valoare'] for s in self.by_file['registru-cifre.csv']['surse']]
        self.assertEqual(len(names), 9)
        self.assertEqual((names[0], names[1], names[-1]), ('ONRC — Registrul Comerțului', 'Geocodare — adresele pe hartă', 'ANRM — licențe și permise miniere'))
        for source in self.by_file['registru-cifre.csv']['surse']:
            self.assertEqual(self.cut(source['pointer']), source['valoare'])
        self.assertEqual([s['valoare'] for s in self.by_file['bilanturi-pe-an.csv']['surse']], ['MFP — bilanțurile'])

    def test_the_licence_is_the_pages_and_covers_its_files(self):
        licence = self.datasets[0]['licenta']
        self.assertEqual((licence['valoare'], licence['acopera']), ('CC BY 4.0', 'fisierele-paginii'))
        self.assertEqual(licence['url']['valoare'], 'https://creativecommons.org/licenses/by/4.0/')
        self.assertEqual(licence['atribuire']['valoare'], 'Sursa: harta-firmelor.ro')
        self.assertEqual(self.cut(licence['atribuire']['pointer']), 'Sursa: harta-firmelor.ro')
        self.assertTrue(all(d['licenta'] == licence for d in self.datasets))

    def test_every_column_is_a_field_with_its_declared_description_and_no_type(self):
        self.assertEqual(len(self.fields), 12)
        self.assertEqual(len({f['cale'] for f in self.fields}), 12, 'the same column name in two files is two fields')
        self.assertEqual([f['nume'] for f in self.fields if f['nume'] == 'year'], ['year', 'year'])
        self.assertTrue(all(f['descriere'] and f['tip_declarat'] is None and 'tipuri_observate' not in f for f in self.fields))
        self.assertEqual({f['stare_tip'] for f in self.fields}, {'declarat-in-lista-documentatie'})
        self.assertEqual({f['grup'] for f in self.fields}, set(self.by_file))
        by_cale = {f['cale']: f for f in self.fields}
        self.assertEqual(by_cale['bilanturi-pe-an.csv::year']['descriere'], 'Anul fiscal al bilanțului.')
        self.assertEqual(by_cale['bilanturi-pe-an.csv::year']['perioada_declarata'], '2008 → 2025')

    def test_a_field_locator_holds_the_name_and_the_description_as_the_page_writes_them(self):
        for field in self.fields:
            piece = self.cut(field['pointer'])
            self.assertTrue(piece.startswith('<dt') and piece.endswith('</dd>'), piece[:40])
            self.assertIn('>' + field['nume'] + '</dt>', piece)
        active = next(f for f in self.fields if f['nume'] == 'status_active')
        self.assertEqual(active['descriere'], 'Câte dintre ele au azi starea „In functiune".')
        self.assertIn('„In functiune&quot;.', self.cut(active['pointer']), 'the entity stays in the retained text; the field holds the decoded text')

    def test_a_unit_is_taken_only_from_a_phrase_that_states_it(self):
        units = {f['cale']: (f['unitate'], f['baza_unitatii']) for f in self.fields if 'unitate' in f}
        self.assertEqual(units, {'bilanturi-pe-an.csv::median_turnover_lei': ('lei nominali', 'declarat-in-descriere')})
        employees = next(f for f in self.fields if f['nume'] == 'employees_reported')
        self.assertNotIn('unitate', employees, 'a count of employees states no unit')

    def test_the_reader_makes_no_request_and_the_dataset_list_matches_the_field_reader(self):
        with patch('socket.socket', side_effect=AssertionError('the reader must not open a connection')):
            fmt, fields, truncated = parse_source(self.body, self.URL, 'text/html', {'tip': 'html-carduri-csv'})
            datasets = csv_datasets(self.body, self.URL)
        self.assertEqual((fmt, fields, truncated, datasets), ('html-carduri-csv', self.fields, False, self.datasets))
        with self.assertRaises(ValueError):
            parse_source(self.body, self.URL, 'text/html')

    def test_a_page_without_a_file_card_a_repeated_file_or_a_repeated_column_is_an_error(self):
        with self.assertRaises(ValueError):
            read_csv_cards('<html><body><h3 data-slot="card-title">Nothing</h3></body></html>')
        card = ('<div data-slot="card"><h3 data-slot="card-title">T</h3><a href="/date/a.csv" download="">a.csv</a>'
                '<dl><dt>Rânduri</dt><dd>1</dd></dl><h3>Coloanele</h3><dl>%s</dl></div>')
        entry = '<div><dt>x</dt><dd>d</dd></div>'
        self.assertEqual(len(read_csv_cards(card % entry)[1]), 1)
        with self.assertRaises(ValueError):
            read_csv_cards(card % (entry * 2))
        with self.assertRaises(ValueError):
            read_csv_cards((card % entry) * 2)
        with self.assertRaises(ValueError):
            read_csv_cards(card % '<div><dt>x</dt><dd></dd></div>')

    def test_a_missing_fact_stays_empty_and_an_unreadable_date_stays_text(self):
        page = ('<div data-slot="card"><h3 data-slot="card-title">T</h3><a href="/f/a.csv" download="">a.csv</a>'
                '<dl><dt>Măsurat la</dt><dd>31.02.2026</dd></dl></div>')
        dataset = read_csv_cards(page)[0][0]
        self.assertEqual((dataset['masurat_la']['valoare'], dataset['randuri'], dataset['perioada'], dataset['surse'], dataset['licenta']),
                         ('31.02.2026', None, None, [], None))
        self.assertNotIn('transformare', dataset['masurat_la'])


class Integration(unittest.TestCase):
    def test_extension_and_hint_choose_the_reader_and_html_stays_an_error_without_a_hint(self):
        self.assertEqual(parse_source(text('PollingStationModel.cs'), 'https://raw.example/a/Model.cs')[0], 'csharp')
        self.assertEqual(parse_source(text('patch-00001.sql'), 'https://raw.example/a/00001.sql')[0], 'sql')
        with self.assertRaises(ValueError):
            parse_source(text('afacut-tabel.html'), 'https://example.org/drumuri/')
        fmt, fields, _ = parse_source(text('afacut-tabel.html'), 'https://example.org/drumuri/', 'text/html', 'html-tabele')
        self.assertEqual((fmt, len(fields)), ('html-tabele', 3))
        self.assertEqual(parse_source(text('biografia-tabele.html'), 'https://example.org/m/', 'text/html', {'tip': 'html-tabele', 'tabele': [2]})[1][0]['nume'], 'LOC101B')

    def test_a_credential_in_a_page_script_is_masked_before_the_body_is_kept_or_hashed(self):
        token = 'pat' + 'ABCDEFGHIJKLMN' + '.' + '0' * 64
        page = {'url': 'https://example.org/data', 'final_url': 'https://example.org/data', 'state': 'ok', 'content_type': 'text/html',
                'body': f"<script>const CONFIG = {{ baseId: 'app1', token: '{token}' }}; const k = {{apiKey: \"abcdefghijklmnopqrstuvwxyz\"}}; r.fields['A']</script>"}
        safe = protect(page)
        self.assertNotIn(token, safe['body'])
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz', safe['body'])
        self.assertEqual(safe['redactari'], 2)
        record = analyse_source(safe, {'tip': 'js-acces'})
        self.assertEqual([f['nume'] for f in record['campuri']], ['A'])
        self.assertNotIn(token, json.dumps(record))
        data = {'url': 'https://example.org/o.json', 'state': 'ok', 'content_type': 'application/json', 'body': '{"token": "string"}'}
        self.assertIs(protect(data), data)

    def test_evidence_check_recomputes_text_readers_from_the_retained_body(self):
        url = 'https://example.org/Model.cs'
        response = {'url': url, 'final_url': url, 'state': 'ok', 'content_type': 'text/plain', 'body': text('PollingStationModel.cs')}
        record = analyse_source(response)
        self.assertEqual((record['format'], record['baza_tipului']), ('csharp', 'cod-sau-documentatie'))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            (out / 'seturi-date.json').write_text(json.dumps({'surse': [record]}))
            self.assertEqual(check_report(out, out)['errors'], [])
            record['campuri'][0]['pointer'] = 'char:1-2'
            (out / 'seturi-date.json').write_text(json.dumps({'surse': [record]}))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']))


if __name__ == '__main__':
    unittest.main()
