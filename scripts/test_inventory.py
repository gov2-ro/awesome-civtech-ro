"""Offline checks for source inventory extraction and evidence provenance."""
import json
import tempfile
import unittest
from pathlib import Path

from inventory import (analyse_source, build_profiles, candidate_sources, check_inventory, declared_fields, file_url,
                       observed_fields, openapi_fields, parse_source, source_id)


class Inventory(unittest.TestCase):
    def test_declared_schema_refs_arrays_types_and_units(self):
        doc = {'components': {'schemas': {'Record': {'type': 'object', 'required': ['value'], 'properties': {
            'value': {'type': 'number', 'x-unit': 'RON'}, 'code': {'type': 'string'}}}}}}
        schema = {'type': 'array', 'items': {'$ref': '#/components/schemas/Record'}}
        fields = declared_fields(schema, doc)
        self.assertEqual([f['cale'] for f in fields], ['$[].value', '$[].code'])
        self.assertEqual(fields[0]['unitate'], 'RON')
        self.assertTrue(fields[0]['obligatoriu'])
        self.assertEqual(fields[1]['tip_declarat'], 'string')
        self.assertEqual(fields[0]['pointer'], '/components/schemas/Record/properties/value')

    def test_recursive_schema_stops_at_a_bound(self):
        doc = {'components': {'schemas': {'Node': {'type': 'object', 'properties': {
            'name': {'type': 'string'}, 'next': {'$ref': '#/components/schemas/Node'}}}}}}
        fields = declared_fields({'$ref': '#/components/schemas/Node'}, doc)
        self.assertGreater(len(fields), 1)
        self.assertLess(len(fields), 30)

    def test_openapi_inherited_parameters_keep_their_real_pointer(self):
        doc = {'openapi': '3.0.0', 'paths': {'/rows/{id}': {
            'parameters': [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}],
            'get': {'parameters': [{'name': 'year', 'in': 'query', 'schema': {'type': 'integer'}}],
                    'responses': {'200': {'content': {'application/json': {'schema': {'type': 'object', 'properties': {
                        'value': {'type': 'number'}}}}}}}}}}}
        fields = openapi_fields(doc)
        self.assertEqual([f['rol'] for f in fields], ['parametru-api', 'parametru-api', 'camp-raspuns'])
        self.assertEqual(fields[0]['pointer'], '/paths/~1rows~1{id}/parameters/0')
        self.assertEqual(fields[1]['pointer'], '/paths/~1rows~1{id}/get/parameters/0')
        self.assertEqual(fields[2]['tip_declarat'], 'number')

    def test_json_sample_does_not_promote_observed_types_to_contract(self):
        fields = observed_fields([{'id': '001', 'amount': 1, 'active': True}, {'id': '002', 'amount': None}])
        amount = next(f for f in fields if f['nume'] == 'amount')
        self.assertEqual(amount['tipuri_observate'], ['integer', 'null'])
        self.assertNotIn('tip_declarat', amount)
        self.assertEqual(next(f for f in fields if f['nume'] == 'id')['tipuri_observate'], ['string'])
        self.assertEqual(next(f for f in fields if f['nume'] == 'active')['tipuri_observate'], ['boolean'])

    def test_csv_keeps_identifier_columns_and_unknown_types(self):
        fmt, fields, _ = parse_source('\ufeffCUI;valoare\n001;10\n', 'https://example.org/data.csv')
        self.assertEqual(fmt, 'csv')
        self.assertEqual([f['nume'] for f in fields], ['CUI', 'valoare'])
        self.assertTrue(all(f['tip_declarat'] is None for f in fields))
        with self.assertRaises(ValueError):
            parse_source('id,id\n1,2\n', 'https://example.org/data.csv')

    def test_keyed_collection_is_sampled_and_identifiers_do_not_become_field_names(self):
        doc = {'meta': {'year': 2025}, 'companii': {f'{n:08d}': {'cui': f'{n:08d}', 'cifra_afaceri': n} for n in range(150)}}
        fmt, fields, limited = parse_source(json.dumps(doc), 'https://example.org/bilant.json')
        paths = [f['cale'] for f in fields]
        self.assertEqual(fmt, 'json')
        self.assertIn('$.companii{*}.cui', paths)
        self.assertFalse([p for p in paths if '00000001' in p], 'a key must not become part of a field path')
        collection = next(f for f in fields if f['cale'] == '$.companii{*}')
        self.assertEqual((collection['numar_chei'], collection['rol']), (150, 'colectie-cu-chei'))
        self.assertTrue(limited)
        self.assertEqual(next(f for f in fields if f['cale'] == '$.companii{*}.cui')['tipuri_observate'], ['string'])
        # A small keyed object (an enumeration of counties) stays a plain record.
        _, small, _ = parse_source(json.dumps({'counties': {f'C{n}': {'km': n} for n in range(40)}}), 'https://example.org/c.json')
        self.assertIn('$.counties.C7.km', [f['cale'] for f in small])

    def test_openapi_member_that_holds_a_url_is_a_data_index_not_a_contract(self):
        index = {'name': 'API', 'license': 'CC BY 4.0', 'openapi': 'https://example.org/openapi.json', 'endpoints': [{'path': 'a.json'}]}
        fmt, fields, _ = parse_source(json.dumps(index), 'https://example.org/index.json')
        self.assertEqual(fmt, 'json')
        self.assertIn('$.license', [f['cale'] for f in fields])
        self.assertEqual(parse_source(json.dumps({'openapi': '3.1.0', 'paths': {}}), 'https://example.org/o.json')[0], 'openapi')
        self.assertEqual(parse_source(json.dumps({'swagger': '2.0', 'paths': {}}), 'https://example.org/o.json')[0], 'openapi')

    def test_schema_annotation_does_not_turn_data_into_a_schema(self):
        fmt, fields, _ = parse_source(json.dumps({'$schema': 'catalog.schema.json', 'services': [{'name': 'API'}]}), 'https://example.org/catalog.json')
        self.assertEqual(fmt, 'json')
        self.assertTrue(any(f['cale'] == '$.services[].name' for f in fields))
        with self.assertRaises(ValueError):
            parse_source('<html>Fallback</html>', 'https://example.org/file.csv', 'text/html')

    def test_openapi_shared_model_is_recorded_once_with_operation_bindings(self):
        schema = {'$ref': '#/components/schemas/Row'}
        response = {'200': {'content': {'application/json': {'schema': schema}}}}
        doc = {'openapi': '3.0.0', 'paths': {p: {'get': {'responses': response}} for p in ('/a', '/b')},
               'components': {'schemas': {'Row': {'type': 'object', 'properties': {'id': {'type': 'string'}}}}}}
        fields = openapi_fields(doc)
        self.assertEqual(len(fields), 1)
        self.assertEqual({a['operatie'] for a in fields[0]['aparitii']}, {'GET /a', 'GET /b'})

    def test_ins_dimension_names_come_from_live_metadata(self):
        body = json.dumps({'matrix_code': 'ACC102B', 'dimensions': [{'dim_column_name': 'REF_AREA', 'dim_type': 'geo', 'dim_label': 'Area'}]})
        fmt, fields, _ = parse_source(body, 'https://ins.gov2.ro/api/datasets/ACC102B')
        self.assertEqual(fmt, 'metadate-ins')
        self.assertEqual(fields[0]['nume'], 'REF_AREA')
        self.assertEqual(fields[0]['tip_semantic'], 'geo')

    def test_candidate_files_use_project_scope_and_prioritize_schema(self):
        entry = {'slug': 'x', 'url': 'https://example.org/project/'}
        page = {'state': 'colectat', 'scope': 'proiect', 'final_url': entry['url'], 'links': [], 'text': '\n'.join([
            'https://example.org/project/data.csv', 'https://example.org/project/openapi.json',
            'https://example.org/other/data.json', 'https://unrelated.org/data.json',
            'https://example.org/project/package-lock.json'])}
        got = candidate_sources(entry, {'pages': [page]})
        self.assertEqual([g['url'] for g in got], ['https://example.org/project/openapi.json', 'https://example.org/project/data.csv'])
        self.assertEqual(file_url('https://github.com/org/repo/blob/main/data.csv'), 'https://raw.githubusercontent.com/org/repo/main/data.csv')

    def test_failed_or_invalid_sources_do_not_invent_fields(self):
        failed = analyse_source({'url': 'https://example.org/data.json', 'state': 'eroare-http', 'http_status': 404})
        self.assertEqual(failed['campuri'], [])
        self.assertEqual(failed['completitudine'], 'neconfirmat')
        invalid = analyse_source({'url': 'https://example.org/data.json', 'final_url': 'https://example.org/data.json',
                                  'state': 'ok', 'body': '<html>Not JSON</html>'})
        self.assertEqual(invalid['stare'], 'eroare-parsare')
        self.assertEqual(invalid['campuri'], [])

    def test_evidence_check_detects_a_changed_body_and_an_invalid_pointer(self):
        response = {'url': 'https://example.org/data.json', 'final_url': 'https://example.org/data.json',
                    'state': 'ok', 'body': '{"amount": 1}'}
        source = analyse_source(response)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out / source['snapshot']; path.parent.mkdir()
            path.write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            metadata = out / 'seturi-date.json'
            metadata.write_text(json.dumps({'surse': [source]}))
            self.assertEqual(check_inventory(out, out), [])
            source['campuri'][0]['pointer'] = '/missing'
            metadata.write_text(json.dumps({'surse': [source]}))
            self.assertTrue(any('Invalid field pointer' in e for e in check_inventory(out, out)))
            response['body'] = '{"amount": 2}'
            path.write_text(json.dumps(response))
            self.assertTrue(any('Source hash mismatch' in e for e in check_inventory(out, out)))

    def test_evidence_check_rejects_a_false_declared_type(self):
        response = {'url': 'https://example.org/schema.json', 'final_url': 'https://example.org/schema.json',
                    'state': 'ok', 'body': json.dumps({'type': 'object', 'properties': {'id': {'type': 'string'}}})}
        source = analyse_source(response)
        source['campuri'][0]['tip_declarat'] = 'number'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out / source['snapshot']; path.parent.mkdir()
            path.write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            (out / 'seturi-date.json').write_text(json.dumps({'surse': [source]}))
            self.assertTrue(any('Declared type differs' in e for e in check_inventory(out, out)))

    def test_shared_source_references_and_controls_remain_candidates(self):
        entries = [{'slug': s, 'nume': s, 'url': 'https://example.org/', 'descriere_scurta': 'Purpose',
                    'descriere': '', 'capabilities': [], 'formats': []} for s in ('a', 'b')]
        url = 'https://example.org/data.json'; ident = source_id(url)
        candidates = {s: [{'url': url}] for s in ('a', 'b')}
        sources = {ident: {'campuri': [{'nume': 'value'}]}}
        docs = {'a': {'state': 'documentatie-gasita', 'pages': [{'state': 'colectat', 'scope': 'proiect',
                 'final_url': 'https://example.org/', 'snapshot': 'pagini/a.json',
                 'input_candidates': [{'name': 'q', 'type': 'search'}]}]}}
        profiles = build_profiles(entries, docs, sources, candidates, {})
        self.assertEqual(profiles[0]['surse_structurate'], profiles[1]['surse_structurate'])
        self.assertEqual(profiles[0]['intrari_utilizator'][0]['stare_tip'], 'control-html-candidat')
        self.assertTrue(all(p['completitudine'] == 'partial' for p in profiles))


if __name__ == '__main__':
    unittest.main()
