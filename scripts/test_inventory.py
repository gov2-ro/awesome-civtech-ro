"""Offline checks for source inventory extraction and evidence provenance."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import inventory_literals
from inventory import (analyse_source, build_profiles, candidate_sources, check_inventory, declared_fields, file_url,
                       observed_fields, openapi_fields, parse_source, source_id)
from inventory_literals import read as read_literals


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
        # From 12 members of one kind, an object is a collection too (the rule of the page-script reader); a record of fewer members stays a record.
        _, counties, _ = parse_source(json.dumps({'counties': {f'C{n}': {'km': n} for n in range(40)}}), 'https://example.org/c.json')
        self.assertEqual([f['cale'] for f in counties], ['$.counties{*}', '$.counties{*}.km'])
        _, small, _ = parse_source(json.dumps({'counties': {f'C{n}': {'km': n} for n in range(11)}}), 'https://example.org/c.json')
        self.assertIn('$.counties.C7.km', [f['cale'] for f in small])

    def test_an_object_with_year_keys_is_a_keyed_collection_from_two_members_and_its_years_are_not_field_names(self):
        years = {str(y): {'deficit': y, 'venituri': y + 1} for y in range(2015, 2026)}
        fields = observed_fields({'years': years, 'meta': {'source': 'x'}})
        self.assertEqual([f['cale'] for f in fields], ['$.years{*}', '$.years{*}.deficit', '$.years{*}.venituri', '$.meta.source'])
        self.assertEqual((fields[0]['rol'], fields[0]['numar_chei']), ('colectie-cu-chei', 11))
        self.assertFalse([f for f in fields if '2015' in f['cale'] or '2015' in f['nume']], 'a year is a value, never a field name')
        two = observed_fields({'a': {'2014': {'v': 1}, '2015': {'v': 2}}})
        self.assertEqual([f['cale'] for f in two], ['$.a{*}', '$.a{*}.v'])
        # One year is not a collection; a key that is not a year, or values of two kinds, keep the record.
        self.assertEqual([f['cale'] for f in observed_fields({'a': {'2014': {'v': 1}}})], ['$.a.2014.v'])
        self.assertEqual([f['cale'] for f in observed_fields({'a': {'2014': {'v': 1}, 'total': {'v': 2}}})], ['$.a.2014.v', '$.a.total.v'])
        self.assertEqual([f['cale'] for f in observed_fields({'a': {'2014': {'v': 1}, '2015': 7}})], ['$.a.2014.v', '$.a.2015'])
        self.assertEqual([f['cale'] for f in observed_fields({'a': {'1899': 1, '1900': 2}})], ['$.a.1899', '$.a.1900'], '1899 is not a year of the rule')
        self.assertEqual([f['cale'] for f in observed_fields({'a': {'2014': 1, '2015': None}})], ['$.a{*}'], 'a null does not make a second kind')

    def test_the_rule_for_a_keyed_collection_is_the_one_of_the_page_script_reader(self):
        def collection(reader, value):
            if reader == 'plain':
                return any(f['rol'] == 'colectie-cu-chei' for f in observed_fields(value))
            return any(f['rol'] == 'colectie-cu-chei' for f in read_literals('<script>const D = ' + json.dumps(value) + ';</script>')[0])

        for count in (11, 12, 99, 100):
            cases = {'values': ({f'Judet {n}': {'v': n} for n in range(count)}, count >= 12),
                     'identifiers': ({f'k{n}': {'v': n} for n in range(count)}, count >= 100),
                     'mixed': ({f'k{n}': ({'v': n} if n % 2 else n) for n in range(count)}, count >= 100)}
            for name, (value, expected) in cases.items():
                for reader in ('plain', 'script'):
                    self.assertEqual(collection(reader, value), expected, (count, name, reader))
        # The two readers share one function: a rule that says "never" changes both.
        with mock.patch.object(inventory_literals, 'keyed_collection', return_value=False):
            value = {f'2015{n}': {'v': n} for n in range(150)}
            self.assertFalse(collection('plain', value))
            self.assertFalse(collection('script', value))

    def test_a_record_whose_keys_are_all_identifiers_stays_a_record_and_an_object_with_value_keys_is_a_collection(self):
        address = {'country': 'RO', 'city': 'Cluj', 'county': 'CJ', 'street': 'x', 'number': '1', 'block': '', 'scara': '', 'floor': '', 'apartment': '',
                   'postalCode': '400001', 'sector': '', 'additional': ''}
        counters = {name: n for n, name in enumerate(['displayedRows', 'uniqueDetailUrls', 'counter_only', 'online2', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'])}
        record = {name: [fields['cale'] for fields in observed_fields({'o': value})] for name, value in (('address', address), ('counters', counters))}
        self.assertEqual(record['address'][:3], ['$.o.country', '$.o.city', '$.o.county'], '12 text members under identifier keys are 12 fields')
        self.assertEqual(len(record['address']), 12)
        self.assertEqual(len(record['counters']), 12)
        self.assertFalse([f for f in observed_fields({'o': address}) if f['rol'] == 'colectie-cu-chei'])
        # Value keys make a collection: county names, codes, ids, dates and keys that are not field names.
        for label, keys in (('counties', ['Alba', 'Arad', 'Argeș', 'Bacău', 'Bihor', 'Brașov', 'Cluj', 'Dolj', 'Galați', 'Iași', 'Mureș', 'Timiș']),
                            ('ids', [f'{n:08d}' for n in range(12)]), ('codes', ['AB', 'AR', 'AG', 'BC', 'BH', 'BV', 'CJ', 'DJ', 'GL', 'IS', 'MS', 'TM']),
                            ('dates', [f'2026-01-{n:02d}' for n in range(1, 13)]), ('hyphen', [f'a-{n}' for n in range(12)]), ('underscore first', [f'_{n}' for n in range(12)])):
            fields = observed_fields({'o': {key: {'v': 1} for key in keys}})
            self.assertEqual([f['cale'] for f in fields], ['$.o{*}', '$.o{*}.v'], label)
        # One key that is not an identifier is enough; 11 identifiers and one county make a collection.
        mixed = {**{f'k{n}': 1 for n in range(11)}, 'Alba': 1}
        self.assertEqual([f['cale'] for f in observed_fields({'o': mixed})], ['$.o{*}'])
        # The identifier rule stops at 99 members; the year rule comes first.
        self.assertFalse([f for f in observed_fields({'o': {f'k{n}': 1 for n in range(99)}}) if f['rol'] == 'colectie-cu-chei'])
        self.assertTrue([f for f in observed_fields({'o': {f'k{n}': 1 for n in range(100)}}) if f['rol'] == 'colectie-cu-chei'])
        self.assertEqual([f['cale'] for f in observed_fields({'o': {str(y): 1 for y in range(2010, 2022)}})], ['$.o{*}'])
        # Fewer than 12 members: an object with value keys stays a record, as before.
        self.assertEqual(len(observed_fields({'o': {key: 1 for key in ['Alba', 'Arad', 'Cluj']}})), 3)
        # The page-script reader gives the same answers.
        for value, expected in ((address, False), (mixed, True), ({key: 1 for key in ['Alba', 'Arad', 'Argeș', 'Bacău', 'Bihor', 'Brașov', 'Cluj', 'Dolj', 'Galați', 'Iași', 'Mureș', 'Timiș']}, True)):
            fields = read_literals('<script>const D = ' + json.dumps({'o': value}) + ';</script>')[0]
            self.assertEqual(any(f['rol'] == 'colectie-cu-chei' for f in fields), expected)

    def test_a_year_collection_is_sampled_and_the_limit_says_so(self):
        years = {str(y): {'v': y} for y in range(1990, 2025)}  # 35 years
        _, fields, limited = parse_source(json.dumps({'t': years}), 'https://example.org/t.json')
        self.assertEqual([f['cale'] for f in fields], ['$.t{*}', '$.t{*}.v'])
        self.assertTrue(limited, 'only the first 25 values of a collection are read')
        _, fields, limited = parse_source(json.dumps({'t': {str(y): {'v': y} for y in range(2015, 2026)}}), 'https://example.org/t.json')
        self.assertFalse(limited)

    def test_rows_of_one_width_without_names_give_one_field_for_each_position(self):
        fields = observed_fields({'p': [[1, 'Alba', 2.5, None], [2, 'Arad', 3.5, 'x']], 'q': [[1, 2], [3]]})
        self.assertEqual([f['cale'] for f in fields], ['$.p[][0]', '$.p[][1]', '$.p[][2]', '$.p[][3]', '$.q[][]'], 'rows of two widths are not positional')
        positions = {f['cale']: f for f in fields}
        self.assertEqual(positions['$.p[][3]']['tipuri_observate'], ['null', 'string'])
        self.assertEqual(positions['$.p[][2]']['pointer'], '/p/0/2')
        self.assertTrue(all(f['rol'] == 'camp-date' and 'descriere' not in f for f in fields), 'a position has no name and no meaning')
        # Width 12 is the limit of the page-script reader; a row of 13 cells, a row that holds a list and a width of one are not positional.
        self.assertEqual(len(observed_fields([[0] * 12, [1] * 12])), 12)
        self.assertEqual([f['cale'] for f in observed_fields([[0] * 13, [1] * 13])], ['$[][]'])
        self.assertEqual([f['cale'] for f in observed_fields([[0, [1]], [1, [2]]])], ['$[][]', '$[][][]'])
        self.assertEqual([f['cale'] for f in observed_fields([[0], [1]])], ['$[][]'])
        self.assertEqual([f['cale'] for f in observed_fields([[0, 1], 'x'])], ['$[][]', '$[]'])
        script = read_literals('<script>const ROWS = [[1, "a", 2], [3, "b", 4]];</script>')[0]
        self.assertEqual([f['cale'] for f in script], ['ROWS[][0]', 'ROWS[][1]', 'ROWS[][2]'], 'the page-script reader names the positions the same way')

    def test_the_coordinates_of_a_polygon_are_positions_and_a_point_is_a_list(self):
        geometry = {'features': [{'geometry': {'type': 'Polygon', 'coordinates': [[[26.1, 44.4], [26.2, 44.5], [26.3, 44.6]]]}},
                                 {'geometry': {'type': 'Point', 'coordinates': [26.1, 44.4]}}]}
        paths = [f['cale'] for f in observed_fields(geometry)]
        self.assertIn('$.features[].geometry.coordinates[][][0]', paths)
        self.assertIn('$.features[].geometry.coordinates[][][1]', paths)
        self.assertIn('$.features[].geometry.coordinates[]', paths, 'the numbers of a point are elements, not rows')

    def test_an_empty_list_or_object_is_a_field_with_zero_elements_and_a_null_is_a_null(self):
        fields = {f['cale']: f for f in observed_fields({'eu_branches': [], 'info': None, 'extra': {}, 'rows': [{'a': 1, 'tags': []}, {'a': 2, 'tags': ['x']}]})}
        self.assertEqual((fields['$.eu_branches']['tipuri_observate'], fields['$.eu_branches']['numar_elemente']), (['array'], 0))
        self.assertEqual((fields['$.extra']['tipuri_observate'], fields['$.extra']['numar_elemente']), (['object'], 0))
        self.assertEqual(fields['$.info']['tipuri_observate'], ['null'])
        self.assertNotIn('numar_elemente', fields['$.info'], 'a null is not an empty container')
        self.assertEqual(fields['$.rows[].tags']['numar_elemente'], 0)
        self.assertIn('$.rows[].tags[]', fields, 'the same key with elements in another record still gives its element path')
        self.assertEqual(fields['$.eu_branches']['pointer'], '/eu_branches')
        self.assertEqual(fields['$.eu_branches']['rol'], 'camp-date')
        # A whole document that is an empty list says so, and a field that is null in one record and empty in another has both types.
        self.assertEqual([(f['cale'], f['numar_elemente']) for f in observed_fields([])], [('$', 0)])
        both = observed_fields([{'x': None}, {'x': []}])
        self.assertEqual((both[0]['tipuri_observate'], both[0]['numar_elemente']), (['null', 'array'], 0))

    def test_the_new_shapes_keep_the_pointers_of_the_retained_body(self):
        body = json.dumps({'years': {'2014': {'v': 1}, '2015': {'v': 2}}, 'p': [[1, 'a'], [2, 'b']], 'none': [], 'empty': {}})
        response = {'url': 'https://example.org/shapes.json', 'final_url': 'https://example.org/shapes.json', 'state': 'ok', 'body': body}
        source = analyse_source(response)
        self.assertEqual([f['cale'] for f in source['campuri']], ['$.years{*}', '$.years{*}.v', '$.p[][0]', '$.p[][1]', '$.none', '$.empty'])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            path = out / source['snapshot']; path.parent.mkdir()
            path.write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            (out / 'seturi-date.json').write_text(json.dumps({'surse': [source]}))
            self.assertEqual(check_inventory(out, out), [], 'every pointer of a collection, a position and an empty container resolves in the body')

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
