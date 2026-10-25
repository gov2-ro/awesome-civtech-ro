"""Offline checks for the text-format readers: HTML and markdown tables, SQL, C#, Laravel PHP, annotated JSON in documents and page
scripts. Fixtures in scripts/fixtures/text are copies of public files at recorded revisions or pages read on 2026-10-25."""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, parse_source
from inventory_state import protect
from inventory_text import (csharp, html_tabele, js_acces, json_comentat, markdown, parse_tables, php, sample_type, sql, table_fields)

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
