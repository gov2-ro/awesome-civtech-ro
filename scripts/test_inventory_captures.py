"""Browser captures: tracked manifests, ignored originals, migration and verification (offline, temporary directories)."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import types
import unittest
from pathlib import Path

import inventory
import inventory_captures as captures

URL = 'https://ok.example/'
DATA = 'https://ok.example/api/list?token=REDACTED'
TEXT = 'Lista: Ana Exemplu, Ion Fictiv'


def legacy_record(**changes):
    record = {'versiune': 1, 'proiect': 's', 'url_cerut': URL, 'url_final': URL, 'stare': 'ok', 'http_status': 200, 'titlu': 'Ana Exemplu',
              'randat_la': '2026-10-27T17:04:09+00:00', 'text_randat': TEXT,
              'controale_vizibile': [{'tag': 'select', 'name': 'county', 'label': None, 'options': ['Ion Fictiv']}],
              'cereri_date': [{'metoda': 'GET', 'url': DATA, 'tip_resursa': 'fetch', 'http_status': 200, 'content_type': 'application/json', 'octeti': None, 'extra': 'Ion'}],
              'corpuri_pastrate': [DATA], 'corpuri_omise': [{'url': 'https://ok.example/big', 'motiv': 'Ana Exemplu'}], 'nota': 'No click'}
    return {**record, **changes}


class Workspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.obs = Path(self._tmp.name) / 'observatii'
        self.folder = self.obs / 'inventare' / 'randare'
        self.caps = self.obs / 'inventare' / 'capturi'
        self.folder.mkdir(parents=True)

    def legacy(self, name='s-1.json', **changes):
        path = self.folder / name
        path.write_bytes(captures.capture_bytes(legacy_record(**changes)))
        return path

    def migrate(self, *paths):
        return captures.migrate(self.folder, self.caps, paths)

    def locator(self, name='s-1.json'):
        return {'tip': 'randare', 'snapshot': f'inventare/randare/{name}', 'url': URL, 'pointer': '/cereri_date/0', 'valoare': DATA}

    def check(self, name='s-1.json'):
        return inventory.check_locator({'proiect': 's', 'url': DATA}, self.locator(name), self.obs)


class Migration(Workspace):
    def test_a_legacy_record_becomes_a_manifest_and_its_exact_bytes_are_kept_under_their_hash(self):
        path = self.legacy()
        original = path.read_bytes()
        self.assertEqual(self.migrate(path), [('s-1.json', 'migrated')])
        manifest = json.loads(path.read_text())
        self.assertEqual(captures.manifest_problems(manifest), [])
        stored = self.caps / (captures.digest(original) + '.json')
        self.assertEqual(stored.read_bytes(), original)
        self.assertEqual(manifest['captura'], {'algoritm': 'sha256', 'sha256': captures.digest(original), 'octeti': len(original),
                                               'fisier': stored.name, 'reprezentare': captures.REPRESENTATION})
        self.assertEqual(self.check(), '', 'the locator still resolves, and the original is verified')

    def test_the_manifest_holds_no_page_text_no_title_no_control_value_and_no_extra_request_field(self):
        path = self.legacy()
        self.migrate(path)
        raw = path.read_text()
        for value in ('Ana Exemplu', 'Ion Fictiv', 'text_randat', 'controale_vizibile', 'titlu', 'extra'):
            self.assertNotIn(value, raw)
        manifest = json.loads(raw)
        self.assertEqual((manifest['text_lungime'], manifest['controale_numar'], manifest['corpuri_omise']), (len(TEXT), 1, ['https://ok.example/big']))
        self.assertEqual(manifest['cereri_date'][0]['url'], DATA)

    def test_a_record_collected_without_text_keeps_its_length_and_hash_and_no_name(self):
        path = self.legacy(text_randat=None, text_lungime=len(TEXT), text_sha256='a' * 64, titlu='')
        self.migrate(path)
        manifest = json.loads(path.read_text())
        self.assertEqual((manifest['text_lungime'], manifest['text_sha256']), (len(TEXT), 'a' * 64))
        self.assertNotIn('Ana Exemplu', path.read_text())

    def test_repeating_the_migration_changes_no_byte_and_destroys_no_capture(self):
        path = self.legacy()
        self.migrate(path)
        manifest_bytes, files = path.read_bytes(), {p.name: p.read_bytes() for p in self.caps.iterdir()}
        self.assertEqual(self.migrate(path), [('s-1.json', 'already')])
        self.assertEqual(path.read_bytes(), manifest_bytes)
        self.assertEqual({p.name: p.read_bytes() for p in self.caps.iterdir()}, files)

    def test_a_capture_file_is_never_rewritten(self):
        raw = captures.capture_bytes(legacy_record())
        stored = captures.store(self.caps, raw)
        stored.write_bytes(b'other')
        with self.assertRaises(captures.CaptureError):
            captures.store(self.caps, raw)
        self.assertEqual(stored.read_bytes(), b'other')

    def test_a_repeat_capture_of_the_page_keeps_the_original_and_names_it_in_the_manifest(self):
        path = self.legacy()
        first = path.read_bytes()
        self.migrate(path)
        second = legacy_record(randat_la='2026-11-01T10:00:00+00:00')
        captures.write_capture(self.folder, self.caps, path.name, second)
        manifest = json.loads(path.read_text())
        self.assertEqual(manifest['capturi_anterioare'], [captures.digest(first)])
        self.assertEqual((self.caps / (captures.digest(first) + '.json')).read_bytes(), first)
        self.assertEqual(len(list(self.caps.iterdir())), 2)

    def test_a_new_capture_over_a_legacy_record_preserves_the_legacy_bytes_first(self):
        path = self.legacy()
        first = path.read_bytes()
        captures.write_capture(self.folder, self.caps, path.name, legacy_record(randat_la='2026-11-01T10:00:00+00:00'))
        self.assertEqual((self.caps / (captures.digest(first) + '.json')).read_bytes(), first)
        self.assertEqual(json.loads(path.read_text())['capturi_anterioare'], [captures.digest(first)])

    def test_a_record_that_is_not_listed_is_left_alone(self):
        listed, other = self.legacy('s-1.json'), self.legacy('s-2.json', proiect='t')
        before = other.read_bytes()
        self.migrate(listed)
        self.assertEqual(other.read_bytes(), before)
        self.assertEqual(self.check('s-2.json'), '', 'a legacy record still resolves, with its data inline')


class Verification(Workspace):
    def setUp(self):
        super().setUp()
        self.path = self.legacy()
        self.migrate(self.path)
        self.manifest = json.loads(self.path.read_text())
        self.capture = self.caps / self.manifest['captura']['fisier']

    def test_a_missing_original_is_unavailable_and_never_verified(self):
        self.capture.unlink()
        self.assertEqual(self.check(), 'unavailable')
        report = {'errors': [], 'unavailable': []}
        inventory.check_captures(report, self.obs)
        self.assertEqual((report['errors'], report['unavailable']), ([], ['capture: s-1.json']))
        self.assertEqual(report['captures'], {'manifests': 1, 'verified': 0, 'unavailable': 1, 'legacy': 0})

    def test_an_altered_original_is_an_error(self):
        self.capture.write_bytes(self.capture.read_bytes().replace(b'Ana', b'Ona'))
        self.assertIn('do not match the recorded SHA-256', self.check())
        report = {'errors': [], 'unavailable': []}
        inventory.check_captures(report, self.obs)
        self.assertEqual((len(report['errors']), report['unavailable']), (1, []))

    def test_an_original_that_disagrees_with_its_manifest_is_an_error(self):
        other = captures.capture_bytes(legacy_record(url_final='https://elsewhere.example/'))
        self.manifest['captura'].update(sha256=captures.digest(other), octeti=len(other), fisier=captures.digest(other) + '.json')
        captures.store(self.caps, other)
        self.path.write_text(captures.manifest_text(self.manifest))
        self.assertIn('differs from its manifest', self.check())

    def test_a_verified_original_is_counted_apart_from_the_manifest(self):
        report = {'errors': [], 'unavailable': []}
        inventory.check_captures(report, self.obs)
        self.assertEqual(report['captures'], {'manifests': 1, 'verified': 1, 'unavailable': 0, 'legacy': 0})
        self.legacy('s-2.json')
        inventory.check_captures(report, self.obs)
        self.assertEqual((report['captures']['manifests'], report['captures']['legacy']), (1, 1))

    def test_the_locator_must_still_name_the_request_of_the_manifest(self):
        locator = {**self.locator(), 'valoare': 'https://ok.example/other'}
        self.assertIn('render record differs', inventory.check_locator({'proiect': 's', 'url': DATA}, locator, self.obs))

    def test_a_manifest_with_a_key_outside_the_allowlist_is_invalid(self):
        self.manifest['text_randat'] = TEXT
        self.path.write_text(captures.manifest_text(self.manifest))
        self.assertIn('invalid render manifest', self.check())
        self.assertIn('key not allowed: text_randat', captures.manifest_problems(self.manifest))

    def test_a_short_hash_is_invalid(self):
        self.manifest['captura']['sha256'] = self.manifest['captura']['sha256'][:12]
        self.assertTrue(captures.manifest_problems(self.manifest))


class Restore(Workspace):
    def test_the_owner_supplies_the_exact_bytes_and_a_wrong_file_is_refused(self):
        path = self.legacy()
        original = path.read_bytes()
        self.migrate(path)
        manifest = json.loads(path.read_text())
        (self.caps / manifest['captura']['fisier']).unlink()
        supplied = Path(self._tmp.name) / 'copy.json'
        supplied.write_bytes(original + b' ')
        with self.assertRaises(captures.CaptureError):
            captures.restore(self.caps, supplied, [manifest])
        supplied.write_bytes(original)
        captures.restore(self.caps, supplied, [manifest])
        self.assertEqual(self.check(), '')

    def test_the_command_migrates_and_restores_without_a_request(self):
        path = self.legacy()
        args = types.SimpleNamespace(migrate_captures=[str(path)], restore_capture=None)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(inventory.run_captures(args, self.obs), 0)
        self.assertEqual(json.loads(path.read_text())['versiune'], 2)


if __name__ == '__main__':
    unittest.main()
