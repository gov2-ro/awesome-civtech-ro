"""Reader `rsc-json`: the data of a Next.js flight payload (offline, synthetic payloads)."""
from __future__ import annotations

import json
import unittest

import inventory
import inventory_persons
from inventory_rsc import FORMAT, extract

BILLS = {'bills': [{'id': 'B1/2026', 'initiators': ['Ana Exemplu'], 'scor': 3.5, 'press': {'count': 2}}, {'id': 'B2/2026', 'initiators': [], 'scor': 1.0, 'press': {'count': 0}}],
         'mpCount': 471}
PAYLOAD = '\n'.join(['1:"$Sreact.fragment"', '3:I[9766,[],""]', '5:' + json.dumps(['$', '$L23', None, BILLS]),
                     '6:' + json.dumps(['$', 'p', None, {'children': 'short'}]), '7:null', 'not a line'])


class Reader(unittest.TestCase):
    def test_the_largest_props_object_of_a_react_element_is_the_document(self):
        self.assertEqual(extract(PAYLOAD), BILLS)

    def test_a_payload_without_an_element_with_properties_is_an_error(self):
        with self.assertRaises(ValueError):
            extract('1:"$Sreact.fragment"\n7:null')

    def test_the_fields_have_paths_and_types(self):
        fmt, fields, _ = inventory.parse_source(PAYLOAD, 'https://x.example/a.txt?_rsc=1', 'text/plain', FORMAT)
        self.assertEqual(fmt, FORMAT)
        paths = {f['cale'] for f in fields}
        self.assertIn('$.bills[].id', paths)
        self.assertIn('$.bills[].press.count', paths)
        self.assertIn('$.mpCount', paths)

    def test_a_source_with_persons_keeps_no_value(self):
        response = {'url': 'https://x.example/a.txt?_rsc=1', 'final_url': 'https://x.example/a.txt?_rsc=1', 'http_status': 200, 'content_type': 'text/plain',
                    'state': 'ok', 'body': PAYLOAD, 'fetched_at': '2026-10-31T00:00:00+00:00'}
        source = inventory.analyse_source(response, FORMAT, persons=True)
        self.assertEqual((source['stare'], source['format']), ('analizat', FORMAT))
        self.assertNotIn('Ana Exemplu', json.dumps(source, ensure_ascii=False))
        self.assertEqual(inventory_persons.problems(source), [])
        values, names = inventory_persons.body_values(PAYLOAD, FORMAT)
        self.assertIn('Ana Exemplu', values)
        self.assertIn('initiators', names)


if __name__ == '__main__':
    unittest.main()
