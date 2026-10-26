"""Offline checks for the reader of data literals in page scripts (`js-literale`). The fixture `fixtures/text/pagina-cu-date.html` is a small page made
by hand with the structure of the pages that România Interactivă and Orașe digitale publish (read on 2026-10-26): a data island, top-level
constants with bare keys and single quotes, a keyed collection, equal-width rows, and declarations that are code and must be skipped."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inventory import analyse_source, check_report, parse_source
from inventory_literals import MAX_FIELDS, SAMPLE_ROWS, Parser, NotLiteral, datasets, declarations, decode, measured_variables, read
from inventory_text import js_literale

FIXTURE = Path(__file__).parent / 'fixtures/text/pagina-cu-date.html'
URL = 'https://example.org/probe/'


def body():
    return FIXTURE.read_text()


def cut(text, field):
    start, end = field['pointer'].split(':')[1].split('-')
    return text[int(start):int(end)]


def json_text(n):
    return json.dumps(f'v{n}')


def by_path(fields):
    return {f['cale']: f for f in fields}


class Literals(unittest.TestCase):
    def setUp(self):
        self.body = body()
        self.fields, self.truncated = read(self.body)
        self.paths = by_path(self.fields)
        self.declared = {d['variabila']: d for d in declarations(self.body)}

    def test_a_data_island_is_read_by_its_id_and_json_ld_and_external_scripts_are_not(self):
        self.assertEqual(self.paths['dataScript.cities[].name']['tipuri_observate'], ['string'])
        self.assertEqual(self.paths['dataScript.cities[].t1']['tipuri_observate'], ['number', 'null'], 'a null in the sample is an observed type')
        self.assertEqual(self.paths['dataScript.cities[].c1[]']['tipuri_observate'], ['number', 'integer'])
        self.assertEqual(self.declared['dataScript']['forma-sursa'], 'json-izolat')
        self.assertFalse([d for d in self.declared.values() if 'WebPage' in d['variabila'] or d['variabila'].startswith('json')])
        self.assertFalse([f for f in self.fields if f['cale'].startswith('@')])

    def test_bare_keys_single_quotes_comments_and_trailing_commas_are_literals(self):
        self.assertEqual(self.paths['G[].pm']['tipuri_observate'], ['string'])
        self.assertEqual(self.paths['G[].f']['tipuri_observate'], ['string'], 'a key that only the second row has is still a field')
        self.assertEqual(self.declared['G']['elemente'], 2)
        self.assertEqual(self.declared['G']['comentariu']['valoare'], 's = învestire, e = învestirea următorului guvern')
        self.assertEqual(self.declared['NICE']['comentariu']['valoare'], 'Numele județelor', 'a block comment on the line above is the page\'s own words')

    def test_an_identifier_stays_a_string_with_its_leading_zero(self):
        field = self.paths['SIRUTA_CODES[]']
        self.assertEqual(field['tipuri_observate'], ['string'])
        self.assertEqual(cut(self.body, field), '"010103"')

    def test_a_keyed_collection_keeps_three_example_keys_and_never_makes_a_field_of_a_key(self):
        collection = self.paths['DATA.c{*}']
        self.assertEqual((collection['rol'], collection['numar_chei'], collection['chei_exemplu']), ('colectie-cu-chei', 12, ['Alba', 'Arad', 'Arges']))
        self.assertIn('DATA.c{*}.m[]', self.paths)
        self.assertFalse([f for f in self.fields if 'Alba' in f['cale'] or 'Alba' in f['nume']])
        self.assertEqual(self.paths['DATA.c{*}.d[]']['tipuri_observate'], ['integer', 'null'])

    def test_a_wide_record_stays_a_record_and_only_values_of_one_kind_make_a_collection(self):
        record = ('<script>const R = [{"name": "Abrud", "pop": 4360, "lat": 46.27, "lng": 23.05, "pc": "A", "t1": 25.2, "t2": 45.7, "t3": 72.3, "r1": 260, "r2": 203, "r3": 18, '
                  '"c1": [60.8, 34.4], "c2": [48.1, 37.9], "c3": [81.4, 48.2]}];</script>')
        fields, _ = read(record)
        paths = [f['cale'] for f in fields]
        self.assertEqual(paths, ['R[].name', 'R[].pop', 'R[].lat', 'R[].lng', 'R[].pc', 'R[].t1', 'R[].t2', 'R[].t3', 'R[].r1', 'R[].r2', 'R[].r3', 'R[].c1[]', 'R[].c2[]', 'R[].c3[]'])
        self.assertFalse([f for f in fields if f['rol'] == 'colectie-cu-chei'])
        months = '<script>const M = {' + ', '.join(f'"m{n}": {n}' for n in range(12)) + '};</script>'
        self.assertEqual([(f['cale'], f['rol']) for f in read(months)[0]], [('M{*}', 'colectie-cu-chei')], 'twelve numbers under twelve keys: a collection')
        mixed = '<script>const X = {' + ', '.join(f'"k{n}": {n if n % 2 else json_text(n)}' for n in range(110)) + '};</script>'
        self.assertEqual(read(mixed)[0][0]['numar_chei'], 110)
        self.assertEqual(read(mixed)[0][0]['rol'], 'colectie-cu-chei', '100 members or more is always a collection')
        small = '<script>const S = {' + ', '.join(f'"k{n}": {n if n % 2 else json_text(n)}' for n in range(11)) + '};</script>'
        self.assertFalse([f for f in read(small)[0] if f['rol'] == 'colectie-cu-chei'], 'under 12 members is a record')

    def test_equal_width_rows_give_one_field_for_each_position_and_no_meaning(self):
        names = [f['cale'] for f in self.fields if f['cale'].startswith('ROWS')]
        self.assertEqual(names, ['ROWS[][0]', 'ROWS[][1]', 'ROWS[][2]'])
        self.assertEqual([self.paths[n]['tipuri_observate'] for n in names], [['string'], ['integer'], ['integer']])
        self.assertTrue(all(self.paths[n]['tip_declarat'] is None and 'descriere' not in self.paths[n] for n in names))

    def test_declarations_that_are_code_are_skipped_with_a_reason_and_make_no_field(self):
        reasons = {name: d['motiv'] for name, d in self.declared.items() if not d['citit']}
        self.assertEqual(reasons, {'IND': 'valoare-nelitera', 'MARRIAGES': 'expresie-dupa-literal', 'LAZY': 'expresie-dupa-literal', 'SPREAD': 'valoare-nelitera'})
        self.assertFalse([f for f in self.fields if f['variabila'] in reasons])
        self.assertNotIn('INSIDE', self.declared, 'an indented declaration is not a top-level constant')
        self.assertNotIn('TEMPLATE', self.declared)

    def test_every_locator_cuts_the_text_of_its_first_node_and_a_line_number_matches(self):
        for field in self.fields:
            piece = cut(self.body, field)
            self.assertTrue(piece, field['cale'])
            start = int(field['pointer'].split(':')[1].split('-')[0])
            self.assertEqual(field['linie'], self.body.count('\n', 0, start) + 1, field['cale'])
        self.assertEqual(cut(self.body, self.paths['G[].g']), '"Roman I"')
        self.assertEqual(cut(self.body, self.paths['DATA.years[]']), '1990')
        for row in declarations(self.body):
            if row['citit']:
                piece = cut(self.body, row)
                self.assertTrue(piece[0] in '[{' and piece[-1] in ']}', row['variabila'])

    def test_the_sample_is_bounded_and_the_limit_is_reported(self):
        long_array = 'const SERIES = [' + ','.join(str(n) for n in range(SAMPLE_ROWS + 5)) + '];\n'
        fields, truncated = read(f'<script>{long_array}</script>')
        self.assertTrue(truncated)
        self.assertEqual([f['cale'] for f in fields], ['SERIES[]'])
        small, flag = read('<script>const A = [1, 2, 3];\nconst B = {"x": {"y": {"z": {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}}}};</script>')
        self.assertTrue(flag, 'a literal nested over seven levels is cut')
        many = '<script>' + ''.join(f'const V{n} = {{"a": {n}}};\n' for n in range(MAX_FIELDS + 5)) + '</script>'
        capped, hit = read(many)
        self.assertEqual((len(capped), hit), (MAX_FIELDS, True))
        self.assertTrue(all(f['tip_declarat'] is None for f in fields + small))

    def test_the_same_body_always_gives_the_same_list_and_a_repeated_name_stays_distinct(self):
        self.assertEqual(read(self.body), (self.fields, self.truncated))
        twice = '<script>const A = {"x": 1};</script><script>const A = {"y": 2};</script>'
        self.assertEqual([f['cale'] for f in read(twice)[0]], ['A.x', 'A#2.y'])

    def test_the_reader_makes_no_request_and_does_not_run_the_script(self):
        with patch('socket.socket', side_effect=AssertionError('the reader must not open a connection')):
            read(self.body)
            declarations(self.body)

    def test_a_line_inside_a_literal_is_data_and_not_a_declaration(self):
        inside = '<script>\nconst A = [\n"x",\n"y",\n];\nconst B = [1];\n</script>'
        self.assertEqual([(d['variabila'], d['citit']) for d in declarations(inside)], [('A', True), ('B', True)])
        nested = '<script>\nconst A = {\n"k": [\n1,\n],\n"const C": 1};\nconst B = [1];\n</script>'
        self.assertEqual([d['variabila'] for d in declarations(nested)], ['A', 'B'])
        code = '<script>\nconst A = [\n"x",\nconst B = [1],\n];\n</script>'
        self.assertEqual([(d['variabila'], d['citit'], d.get('motiv')) for d in declarations(code)],
                         [('A', False, 'valoare-nelitera'), ('B', False, 'expresie-dupa-literal')], 'code in the middle of a literal makes it code')


class JsonLd(unittest.TestCase):
    """The page's own schema.org Dataset: what it declares about its data set, never what the data means."""

    def setUp(self):
        self.body = body()
        self.dataset = datasets(self.body)[0]

    def test_only_a_dataset_is_read_and_a_block_that_does_not_parse_is_ignored(self):
        self.assertEqual(len(datasets(self.body)), 1, 'the WebPage of the same graph and the broken block give no data set')
        self.assertEqual(datasets('<script type="application/ld+json">{"@type": "WebPage"}</script>'), [])
        self.assertEqual(datasets('<script type="application/ld+json">[{"@type": "Dataset", "name": "A"}]</script>')[0]['nume']['valoare'], 'A')
        self.assertEqual(datasets('<script type="application/json">{"@type": "Dataset", "name": "A"}</script>'), [], 'a data island is not JSON-LD')

    def test_every_fact_has_its_value_a_locator_and_a_basis_and_a_missing_fact_stays_empty(self):
        d = self.dataset
        self.assertEqual((d['nume']['valoare'], d['perioada']['valoare'], d['licenta']['valoare'], d['acoperire']['valoare']),
                         ('Căsătorii pe județe, 1990–2024', '1990/2025', 'https://creativecommons.org/licenses/by/4.0/', 'România'))
        self.assertEqual([f['valoare'] for f in d['bazat_pe']], ['https://insse.ro/', 'https://ec.europa.eu/eurostat'])
        self.assertEqual([f['valoare'] for f in d['creator']], ['Autor Probă', 'https://example.org/#org'], 'an object without a name keeps its @id')
        self.assertEqual((d['adresa'], d['limba'], d['editor'], d['cuvinte_cheie']), (None, None, [], []))
        self.assertIs(d['gratuit']['valoare'], True)
        for f in (d['nume'], d['perioada'], d['licenta'], d['acoperire'], *d['bazat_pe'], *d['creator']):
            self.assertEqual(f['baza'], 'declarat-in-pagina')
            self.assertEqual(self.body[int(f['pointer'][5:].split('-')[0]):int(f['pointer'].split('-')[1])].strip('"'), f['valoare'])
        self.assertEqual(self.body[int(d['pointer'][5:].split('-')[0]):int(d['pointer'].split('-')[1])][:1], '{')

    def test_a_measured_variable_is_a_field_with_what_the_page_declares_and_nothing_inferred(self):
        fields = measured_variables(self.body)
        self.assertEqual([f['nume'] for f in fields], ['Căsătorii', 'Rata', 'Divorțuri'])
        first, second, third = fields
        self.assertEqual((first['descriere'], first['unitate'], first['rol'], first['stare_tip'], first['tip_declarat']), ('Număr de căsătorii', 'număr', 'masura', 'declarat-in-metadate', None))
        self.assertEqual((second['descriere'], second['unitate']), ('', None), 'no unit unless the page writes unitText')
        self.assertEqual(third['cale'], 'Dataset1.variableMeasured.Divorțuri', 'a bare string is a name')
        self.assertTrue(all(f['grup'] == 'Căsătorii pe județe, 1990–2024' for f in fields))
        self.assertEqual(self.body[int(first['pointer'][5:].split('-')[0]):int(first['pointer'].split('-')[1])][:1], '{')
        self.assertEqual([f['nume'] for f in read(self.body)[0]][:3], ['Căsătorii', 'Rata', 'Divorțuri'], 'the declared variables come first')


class Parsing(unittest.TestCase):
    def parse(self, text):
        return Parser(text).value()

    def test_strings_decode_only_when_a_key_needs_it(self):
        self.assertEqual(decode(r'a\"bă\x41\n'), 'a"bă' + 'A' + '\n')
        node = self.parse('{"Mărișel": 1, \'it\\\'s\': 2, 3: 4}')
        self.assertEqual([k for k, _ in node.payload], ['Mărișel', "it's", '3'])

    def test_code_is_refused_and_never_guessed(self):
        for text, reason in (('{a: x => 1}', 'valoare-nelitera'), ('[foo]', 'valoare-nelitera'), ('[`t`]', 'valoare-nelitera'), ('{a, b}', 'cheie-fara-valoare'),
                             ('{...x}', 'cheie-nelitera'), ('{[k]: 1}', 'cheie-nelitera'), ('[1, 2', 'literal-neterminat'), ('["a]', 'sir-neinchis'),
                             ('[1px]', 'numar-neinteles'), ('[undefined]', 'valoare-nelitera'), ('[1 2]', 'sintaxa'), ('[/* open', 'comentariu-neinchis')):
            with self.assertRaises(NotLiteral, msg=text) as raised:
                self.parse(text)
            self.assertEqual(raised.exception.reason, reason, text)
        with self.assertRaises(NotLiteral) as deep:
            self.parse('[' * 60 + ']' * 60)
        self.assertEqual(deep.exception.reason, 'literal-prea-adanc')

    def test_numbers_keywords_and_comments(self):
        node = self.parse('[1, -2.5, .5, 1e3, +4, true, false, null, // end\n "x" /* c */]')
        self.assertEqual([n.kind for n in node.payload], ['intreg', 'numar', 'numar', 'numar', 'intreg', 'logic', 'logic', 'nul', 'text'])


class Integration(unittest.TestCase):
    def setUp(self):
        self.body = body()

    def test_the_hint_selects_the_reader_and_the_tables_come_first_only_when_asked(self):
        plain = parse_source(self.body, URL, 'text/html', {'tip': 'js-literale'})
        with_tables = parse_source(self.body, URL, 'text/html', {'tip': 'js-literale', 'tabele': True})
        self.assertEqual((plain[0], with_tables[0]), ('js-literale', 'js-literale'))
        self.assertFalse([f for f in plain[1] if f['stare_tip'] == 'antet-tabel-html'])
        headers = [f['nume'] for f in with_tables[1] if f['stare_tip'] == 'antet-tabel-html']
        self.assertEqual(headers, ['Județ', 'Căsătorii', 'Căs. ‰'])
        self.assertEqual(with_tables[1][:3], [f for f in with_tables[1] if f['stare_tip'] == 'antet-tabel-html'])
        self.assertEqual(len(with_tables[1]), len(plain[1]) + 3)
        self.assertEqual(js_literale(self.body, {'tabele': [1]})[1], with_tables[1])
        with self.assertRaises(ValueError):
            parse_source(self.body, URL, 'text/html')

    def test_the_source_record_keeps_the_declarations_and_the_basis_of_the_types(self):
        response = {'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/html', 'body': self.body}
        record = analyse_source(response, {'tip': 'js-literale', 'tabele': True})
        self.assertEqual((record['format'], record['baza_tipului'], record['stare']), ('js-literale', 'esantion-date', 'analizat'))
        self.assertEqual(record['declaratii'], declarations(self.body))
        self.assertEqual(record['seturi_ld'], datasets(self.body))
        self.assertIs(record['limita_atinsa'], False, 'the fixture has no array over 25 elements and no literal over seven levels')
        self.assertEqual(record['citire'], {'tip': 'js-literale', 'tabele': True})

    def test_evidence_check_recomputes_fields_and_declarations_from_the_retained_body(self):
        response = {'url': URL, 'final_url': URL, 'state': 'ok', 'content_type': 'text/html', 'body': self.body}
        record = analyse_source(response, {'tip': 'js-literale', 'tabele': True})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / record['snapshot']).parent.mkdir()
            (out / record['snapshot']).write_text(json.dumps(response))
            (out / 'proiecte.json').write_text(json.dumps({'proiecte': []}))
            path = out / 'seturi-date.json'
            state = {'surse': [record]}
            path.write_text(json.dumps(state))
            report = check_report(out, out)
            self.assertEqual((report['errors'], report['verified']), ([], 1))
            record['campuri'][-1]['pointer'] = 'char:1-2'
            path.write_text(json.dumps(state))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']))
            record['campuri'][-1]['pointer'] = analyse_source(response, {'tip': 'js-literale', 'tabele': True})['campuri'][-1]['pointer']
            record['declaratii'][0]['elemente'] += 1
            path.write_text(json.dumps(state))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']), 'a changed declaration list is an error')
            record['declaratii'][0]['elemente'] -= 1
            record['seturi_ld'][0]['perioada']['valoare'] = '1990/2026'
            path.write_text(json.dumps(state))
            self.assertTrue(any('Fields differ from the retained body' in e for e in check_report(out, out)['errors']), 'a changed data set fact is an error')


if __name__ == '__main__':
    unittest.main()
