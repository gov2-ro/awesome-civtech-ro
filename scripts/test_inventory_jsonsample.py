"""Offline checks for the reader of a cut JSON document (`json-esantion`) and for its use in an inventory run.

The bodies are small invented documents with the shapes that three real files have: a GeoJSON file with one feature on each line, a compact
GeoJSON file on one line, and a data file whose first member is a metadata object and whose second member is a list of records.
Every network call is a fake.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from inventory import analyse_source, check_report, git_blob_sha, observed_fields, parse_source, resolve_spec
from inventory_jsonsample import FORMAT, MAX_NESTING, list_sizes, recover
from inventory_state import source_id
from test_inventory_state import Workspace, docs_for, entry

URL = 'https://data.example/map.geojson'
LINES = ('{\n"type": "FeatureCollection",\n"features": [\n'
         '{ "type": "Feature", "properties": { "id": 1, "street": "Alpha", "year": 1934, "height": null }, "geometry": { "type": "Point", "coordinates": [26.1, 44.4] } },\n'
         '{ "type": "Feature", "properties": { "id": 2, "street": "Beta", "year": 1960, "height": 12.5 }, "geometry": { "type": "Point", "coordinates": [26.2, 44.5] } },\n'
         '{ "type": "Feature", "properties": { "id": 3, "street": "Gam')
COMPACT = '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"nr":"1","city":"A"},"geometry":null},{"type":"Feature","properties":{"nr":"2","city'
WHOLE = '{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": 1}, "geometry": null}]}'
RECORDS = '{"metadata": {"note": "n", "sources": ["a", "b"]}, "records": [{"name": "x", "year": 2001}, {"name": "y", "year": 2002}, {"name": "z", "ye'


def response(body, url=URL, partial=True):
    return {'url': url, 'final_url': url, 'state': 'ok', 'http_status': 206 if partial else 200, 'content_type': 'application/octet-stream',
            'body': body, 'fetched_at': '2026-10-27T10:00:00+00:00', **({'partial': True} if partial else {})}


class Recovery(unittest.TestCase):
    def test_a_whole_document_is_read_whole_and_gives_the_fields_of_the_plain_reader(self):
        document, complete = recover(WHOLE)
        self.assertTrue(complete)
        self.assertEqual(document, json.loads(WHOLE))
        self.assertEqual(parse_source(WHOLE, URL, '', FORMAT)[1], observed_fields(json.loads(WHOLE)))

    def test_the_feature_that_the_cut_ended_is_dropped_and_the_complete_ones_stay(self):
        document, complete = recover(LINES)
        self.assertFalse(complete)
        self.assertEqual([f['properties']['id'] for f in document['features']], [1, 2])
        self.assertEqual(list_sizes(document), {'$.features': 2})

    def test_a_compact_file_on_one_line_is_cut_in_the_same_way(self):
        document, complete = recover(COMPACT)
        self.assertFalse(complete)
        self.assertEqual(len(document['features']), 1)
        self.assertEqual(document['features'][0]['properties'], {'nr': '1', 'city': 'A'})

    def test_a_complete_list_before_the_cut_is_kept_and_a_cut_object_is_dropped(self):
        document, complete = recover(RECORDS)
        self.assertFalse(complete)
        self.assertEqual(document['metadata'], {'note': 'n', 'sources': ['a', 'b']})
        self.assertEqual([r['name'] for r in document['records']], ['x', 'y'])
        self.assertEqual(list_sizes(document), {'$.metadata.sources': 2, '$.records': 2})

    def test_a_cut_keyed_collection_keeps_the_members_that_are_whole_records_and_a_cut_record_is_still_dropped(self):
        # A file with a collection of companies keyed by CUI: the read ends inside the collection. Each complete member is a whole record, so it stays. A record of
        # named fields that the cut ended is half a record, and it is dropped as before (the fields list would show its last fields as absent).
        keyed = '{"fields": ["a", "b"], "companii": {' + ', '.join(f'"{1000 + n}": {{"caen": {n}, "y": {{"2020": [1, 2]}}}}' for n in range(14)) + ', "2000": {"caen": 3, "y": {"20'
        document, complete = recover(keyed)
        self.assertFalse(complete)
        self.assertEqual(len(document['companii']), 14, 'the 15th member was cut and is dropped; the 14 whole ones stay')
        self.assertEqual(document['fields'], ['a', 'b'])
        record = '{"id": 1, "meta": {"name": "x", "year": 2001, "kind": "a", "owner": "b", "city": "c", "zone": "d", "code": "e", "tier": "f", "lang": "g", "unit": "h", "note": "i", "pa'
        document, _ = recover(record)
        self.assertEqual(document, {'id': 1}, 'a record with identifier keys is not a keyed collection: its cut half is dropped')
        few = '{"id": 1, "a": {"x": {"k": 1}, "y": {"k": 2}, "z": {"k'
        self.assertEqual(recover(few)[0], {'id': 1}, 'two whole members are not a keyed collection')

    def test_the_keyed_collection_gives_its_own_fields_and_no_key(self):
        keyed = '{"companii": {' + ', '.join(f'"{1000 + n}": {{"caen": {n}, "y": {{"2020": [1, 2], "2021": [3, 4]}}}}' for n in range(14)) + ', "2000": {"caen": 3'
        fields = parse_source(keyed, URL, '', FORMAT)[1]
        self.assertEqual([f['cale'] for f in fields], ['$.companii{*}', '$.companii{*}.caen', '$.companii{*}.y{*}', '$.companii{*}.y{*}[]'])
        self.assertEqual(fields[0]['numar_chei'], 14)
        self.assertNotIn('1000', json.dumps([(f['nume'], f['cale']) for f in fields]), 'a key of the collection never becomes a field name')

    def test_a_string_or_a_number_that_the_cut_ended_is_never_repaired(self):
        self.assertEqual(recover('[1, 2, 3')[0], [1, 2], 'the 3 may be the start of 34')
        self.assertEqual(recover('["abc", "de')[0], ['abc'])
        self.assertEqual(recover('[{"a": 1}, {"a": 2, "b": tr')[0], [{'a': 1}])
        self.assertEqual(recover('{"x": 1, "y": "abc')[0], {'x': 1})

    def test_a_body_with_nothing_complete_is_an_error(self):
        for body in ('', '   ', '{"x": "abc', '{"a": {"b": 1, "c": ', '[', '{', '"just a string"', '12'):
            with self.subTest(body), self.assertRaises(ValueError):
                recover(body)

    def test_text_that_is_not_json_is_an_error_and_not_a_cut(self):
        for body in ('<!doctype html><html>', '[1, 2 3]', '{"a" 1}', '{a: 1}'):
            with self.subTest(body), self.assertRaises(ValueError):
                recover(body)

    def test_a_nesting_deeper_than_the_limit_is_an_error(self):
        with self.assertRaises(ValueError):
            recover('[' * (MAX_NESTING + 5) + '1')

    def test_a_byte_order_mark_is_ignored(self):
        self.assertEqual(recover('﻿[{"a": 1}, {"a"')[0], [{'a': 1}])


class InSource(unittest.TestCase):
    def test_the_reader_gives_one_field_for_each_path_of_the_complete_features_and_no_value(self):
        fmt, fields, truncated = parse_source(LINES, URL, '', FORMAT)
        self.assertEqual((fmt, truncated), (FORMAT, True))
        paths = {f['cale']: f for f in fields}
        for path in ('$.features[].properties.id', '$.features[].properties.street', '$.features[].properties.year', '$.features[].properties.height'):
            self.assertIn(path, paths)
        self.assertEqual(paths['$.features[].properties.height']['tipuri_observate'], ['null', 'number'])
        self.assertEqual(paths['$.features[].properties.year']['tipuri_observate'], ['integer'])
        self.assertNotIn('Gam', json.dumps(fields), 'the feature that the cut ended gives nothing')
        self.assertNotIn('Alpha', json.dumps(fields), 'a field keeps no value')

    def test_a_whole_document_is_not_marked_as_cut(self):
        self.assertFalse(parse_source(WHOLE, URL, '', FORMAT)[2])

    def test_without_the_reader_name_a_cut_file_stays_an_error(self):
        with self.assertRaises(ValueError):
            parse_source(LINES, URL, '', None)

    def test_the_record_of_the_source_has_the_sample_facts_and_the_type_basis(self):
        record = analyse_source(response(LINES), FORMAT)
        self.assertEqual((record['format'], record['stare'], record['baza_tipului'], record['limita_atinsa']), (FORMAT, 'analizat', 'esantion-date', True))
        self.assertEqual(record['esantion'], {'complet': False, 'elemente_citite': {'$.features': 2}})
        self.assertTrue(record['partial'])
        whole = analyse_source(response(WHOLE, partial=False), FORMAT)
        self.assertEqual(whole['esantion'], {'complet': True, 'elemente_citite': {'$.features': 1}})

    def test_a_list_that_the_cut_emptied_is_not_read_as_empty_and_a_list_that_is_empty_in_the_file_is(self):
        def fields_of(body):
            return {f['cale']: f for f in parse_source(body, URL, '', FORMAT)[1]}

        # The cut ended the first feature, so the recovered list is empty. The file may hold many features: the field says nothing.
        cut = fields_of('{"type": "T", "info": [], "features": [{"type": "Feat')
        self.assertNotIn('$.features', cut)
        self.assertEqual((cut['$.info']['tipuri_observate'], cut['$.info']['numar_elemente']), (['array'], 0), 'a list that closed before the cut is empty in the file')
        # An empty list inside a complete record is a fact of that record, whatever the cut does after it.
        inside = fields_of('{"records": [{"a": [], "b": 1}, {"a": [1], "b')
        self.assertEqual(inside['$.records[].a']['numar_elemente'], 0)
        self.assertNotIn('$.records[].a[]', inside, 'the second record, with the element, was the one that the cut ended')
        # A whole document is read whole: its last member can be empty.
        self.assertEqual(fields_of('{"x": 1, "tail": []}')['$.tail']['numar_elemente'], 0)
        self.assertEqual(fields_of('{"x": 1, "tail": {}}')['$.tail']['tipuri_observate'], ['object'])

    def test_rows_without_names_and_year_keys_are_read_in_a_cut_sample_like_in_a_whole_file(self):
        body = '{"p": [[1, "a", 2.5], [2, "b", 3.5], [3, "c", 4'
        self.assertEqual([f['cale'] for f in parse_source(body, URL, '', FORMAT)[1]], ['$.p[][0]', '$.p[][1]', '$.p[][2]'])
        years = '{"years": {"2014": {"v": 1}, "2015": {"v": 2}}, "later": [{"w'
        self.assertEqual([f['cale'] for f in parse_source(years, URL, '', FORMAT)[1]], ['$.years{*}', '$.years{*}.v'])

    def test_a_body_with_nothing_complete_gives_a_parse_error_and_no_field(self):
        record = analyse_source(response('{"features": [{"type": "Feat'), FORMAT)
        self.assertEqual((record['stare'], record['campuri']), ('eroare-parsare', []))


class Run(unittest.TestCase):
    def setUp(self):
        self.work = Workspace(self)
        self.entries = [entry('p', 'https://example.org/')]
        self.docs = {'p': docs_for('p', 'https://example.org/', [URL])}
        self.calls = []

        def net(url, sample=None):
            self.calls.append((url, sample))
            return response(LINES)

        self.net = net
        self.spec = {'url': URL, 'metoda': 'adaugat-explicit', 'citire': FORMAT, 'parinte': 'https://example.org/',
                     'dovada': {'url': 'https://example.org/', 'sha256': 'page-p', 'pointer': '/links/0', 'fragment': URL, 'snapshot': 'documentare/pagini/p.json'}}
        self.state = self.work.run(self.entries, self.docs, self.net, add_sources=[('p', self.spec)])

    def test_the_source_is_kept_with_its_reader_and_its_fields(self):
        source = self.work.sources()[URL]
        self.assertEqual((source['format'], source['citire']), (FORMAT, FORMAT))
        self.assertEqual(source['esantion']['elemente_citite'], {'$.features': 2})
        self.assertTrue(any(f['cale'] == '$.features[].properties.street' for f in source['campuri']))

    def test_a_replay_from_the_cache_gives_the_same_bytes(self):
        before = self.work.files()
        self.work.run(self.entries, self.docs, None, add_sources=[('p', self.spec)], offline=True)
        self.assertEqual(self.work.files(), before)

    def test_the_evidence_check_passes_and_catches_a_changed_field_and_a_changed_sample_fact(self):
        report = check_report(self.work.out, self.work.out.parent)
        self.assertEqual(report['errors'], [])
        for label, change in (('a field', lambda s: s['campuri'][0].update(nume='Other')),
                              ('a sample fact', lambda s: s['esantion'].update(complet=True))):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / 'inventare'
                shutil.copytree(self.work.out, out)
                state = json.loads((out / 'seturi-date.json').read_text())
                change(next(s for s in state['surse'] if s['url'] == URL))
                (out / 'seturi-date.json').write_text(json.dumps(state))
                self.assertTrue(any('differ from the retained body' in e for e in check_report(out, Path(tmp))['errors']))


class RepositoryRange(unittest.TestCase):
    """A range read of a repository file at a recorded commit cannot be the whole blob. The tree entry still locates the file, and the blob hash is not compared.
    A whole read is still compared."""
    TREE_URL = 'https://api.github.com/repos/o/r/git/trees/abc?recursive=1'
    RAW = 'https://raw.githubusercontent.com/o/r/abc/data/x.json'
    FULL = '{"records": [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}]}\n'

    def workspace(self, served, partial):
        work = Workspace(self)
        tree = json.dumps({'tree': [{'path': 'data/x.json', 'type': 'blob', 'sha': git_blob_sha(self.FULL)}]})
        cache = work.out / 'surse'
        cache.mkdir(parents=True)
        (cache / (source_id(self.TREE_URL) + '.json')).write_text(json.dumps(
            {'url': self.TREE_URL, 'final_url': self.TREE_URL, 'state': 'ok', 'http_status': 200, 'content_type': 'application/json', 'body': tree,
             'fetched_at': '2026-10-27T10:00:00+00:00'}))
        spec = resolve_spec({}, 'p', {'url': self.RAW, 'metoda': 'repo-la-revizie', 'citire': FORMAT, 'parinte': 'https://github.com/o/r/tree/abc',
                                      'repo': {'arbore': self.TREE_URL, 'revizie': 'abc', 'cale': 'data/x.json'}}, cache)
        work.run([entry('p', 'https://example.org/')], {'p': docs_for('p', 'https://example.org/', [])}, lambda url, sample=None: response(served, self.RAW, partial),
                 add_sources=[('p', spec)])
        return work

    def test_a_cut_read_of_the_file_passes_the_check_although_it_is_not_the_blob(self):
        cut = self.FULL[:self.FULL.index('{"a": 3}')]
        work = self.workspace(cut, partial=True)
        self.assertNotEqual(git_blob_sha(cut), git_blob_sha(self.FULL))
        self.assertEqual(work.sources()[self.RAW]['esantion']['elemente_citite'], {'$.records': 2})
        self.assertEqual(check_report(work.out, work.out.parent)['errors'], [])

    def test_a_whole_read_that_is_not_the_recorded_blob_is_an_error(self):
        work = self.workspace(self.FULL.replace('4', '5'), partial=False)
        errors = check_report(work.out, work.out.parent)['errors']
        self.assertTrue(any('is not the file data/x.json' in e for e in errors), errors)

    def test_a_whole_read_of_the_recorded_blob_passes(self):
        work = self.workspace(self.FULL, partial=False)
        self.assertEqual(check_report(work.out, work.out.parent)['errors'], [])


if __name__ == '__main__':
    unittest.main()
