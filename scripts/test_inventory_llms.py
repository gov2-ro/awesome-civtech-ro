"""Reader `llms-api`: the API section of an llms.txt file (offline, synthetic text)."""
from __future__ import annotations

import unittest

import inventory
from inventory_llms import FORMAT, read

TEXT = '''# Site

> Public data.

## Pages

- [Live](https://x.example/): the page

## API

Endpoints need a key, sent in the header `X-API-Key` (or `?key=`). It is free.

- [Archive](https://x.example/api/archive.php?from=2026-01-01&to=2026-01-31): series on an interval
- [Catalog](https://x.example/api/catalog.php)

## Notes

A `token` here is not read.
'''


class Reader(unittest.TestCase):
    def setUp(self):
        self.fields, _ = read(TEXT)
        self.by = {f['cale']: f for f in self.fields}

    def test_endpoints_parameters_and_key_names(self):
        self.assertEqual([f['cale'] for f in self.fields],
                         ['/api/archive.php', '/api/archive.php?from', '/api/archive.php?to', '/api/catalog.php', 'X-API-Key', '?key='])
        self.assertEqual(self.by['/api/archive.php?from']['exemplu_valoare'], '2026-01-01')
        self.assertEqual((self.by['/api/archive.php']['descriere'], self.by['/api/catalog.php']['descriere']), ('series on an interval', None))
        self.assertEqual(self.by['X-API-Key']['rol'], 'autentificare')

    def test_the_pages_list_and_the_other_sections_are_not_read(self):
        self.assertNotIn('/', self.by)
        self.assertNotIn('token', self.by)

    def test_the_locator_covers_the_item_or_the_name(self):
        for field in self.fields:
            start, end = map(int, field['pointer'].removeprefix('char:').split('-'))
            text = TEXT[start:end]
            if field['rol'] == 'autentificare':
                self.assertEqual(text, field['nume'])
            else:
                self.assertTrue(text.lstrip().startswith('- ['))

    def test_no_section_or_no_endpoint_is_an_error(self):
        for text in ('# T\n\n- [A](https://x/a)\n', '# T\n\n## API\n\nNo list here.\n'):
            with self.assertRaises(ValueError):
                read(text)

    def test_the_reader_is_named_by_citire(self):
        fmt, fields, _ = inventory.parse_source(TEXT, 'https://x.example/llms.txt', 'text/plain', FORMAT)
        self.assertEqual((fmt, len(fields)), (FORMAT, 6))


if __name__ == '__main__':
    unittest.main()
