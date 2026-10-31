"""Storage of browser captures for the data inventory (stdlib only).

`render_pages.py` sees a page once. What it saw is a capture: the full render record (page text, controls, data requests, rejected bodies).
A capture stays out of Git, in the ignored directory `inventare/capturi/`, under the name `<sha256>.json`. The name is the SHA-256 of the
exact bytes of the file (see `REPRESENTATION`). A new capture never overwrites a file with another name, and a file is never rewritten.

A manifest is the compact tracked record `inventare/randare/<slug>-<hash>.json`. It keeps the page and data URLs, the time, the outcome and the
data requests that the discovery locators point to (`/cereri_date/N`), and it names its capture (`captura`). It keeps only the keys of
`MANIFEST_KEYS` and `REQUEST_KEYS`. It holds no page text, no title, no control and no response value.

Three states of a manifest: valid (its form is right), verified (a local capture has the recorded hash and agrees with the manifest) and
unavailable (the capture is not in this checkout). A capture whose bytes do not match the recorded hash is an error.
A hash verifies bytes that exist; it does not rebuild bytes that are gone. A browser visit cannot be repeated.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CAPTURE_DIR = 'capturi'
MANIFEST_DIR = 'randare'
MANIFEST_VERSION = 2
ALGORITHM = 'sha256'
REPRESENTATION = 'UTF-8 bytes of the render record as JSON: indent 2, non-ASCII characters kept, one final newline'
REQUEST_KEYS = ('metoda', 'url', 'tip_resursa', 'http_status', 'content_type', 'octeti')
CAPTURE_KEYS = frozenset({'algoritm', 'sha256', 'octeti', 'fisier', 'reprezentare'})
# The keys a manifest may hold. Every one is a structural fact, a URL, a number, a time or a state name.
MANIFEST_KEYS = frozenset({'versiune', 'proiect', 'url_cerut', 'url_final', 'stare', 'http_status', 'randat_la', 'motiv', 'gazda_interzisa',
                           'text_lungime', 'text_sha256', 'controale_numar', 'cereri_date', 'corpuri_pastrate', 'corpuri_omise',
                           'captura', 'capturi_anterioare'})
# Taken from the capture as they are. `captura` and `capturi_anterioare` belong to the manifest.
FROM_RECORD = ('proiect', 'url_cerut', 'url_final', 'stare', 'http_status', 'randat_la', 'motiv', 'gazda_interzisa')
SHA = 64


class CaptureError(Exception):
    pass


def capture_bytes(record):
    """The exact bytes of a capture file."""
    return (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest_text(manifest):
    return json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'


def is_hash(value):
    return isinstance(value, str) and len(value) == SHA and all(c in '0123456789abcdef' for c in value)


def derived(record):
    """The manifest keys that follow from a capture record alone. Allowlist: no other key and no other request field is copied."""
    text = record.get('text_randat')
    if record.get('text_sha256'):
        text_length, text_hash = record.get('text_lungime'), record['text_sha256']
    elif isinstance(text, str):
        text_length, text_hash = len(text), digest(text.encode())
    else:
        text_length = text_hash = None
    result = {key: record[key] for key in FROM_RECORD if key in record}
    result['text_lungime'], result['text_sha256'] = text_length, text_hash
    result['controale_numar'] = len(record.get('controale_vizibile') or [])
    result['cereri_date'] = [{key: item.get(key) for key in REQUEST_KEYS} for item in record.get('cereri_date') or []]
    result['corpuri_pastrate'] = list(record.get('corpuri_pastrate') or [])
    result['corpuri_omise'] = [item['url'] for item in record.get('corpuri_omise') or []]
    return result


def manifest_from(record, raw, previous=()):
    """The compact manifest of a capture record whose file bytes are `raw`. `previous` lists the hashes of earlier captures of the same page."""
    manifest = {'versiune': MANIFEST_VERSION, **derived(record),
                'captura': {'algoritm': ALGORITHM, 'sha256': digest(raw), 'octeti': len(raw), 'fisier': digest(raw) + '.json', 'reprezentare': REPRESENTATION}}
    earlier = [h for h in previous if h != digest(raw)]
    if earlier:
        manifest['capturi_anterioare'] = earlier
    return manifest


def manifest_problems(manifest):
    """Form errors of a manifest (a list of messages). A valid manifest is not a verified capture."""
    if not isinstance(manifest, dict) or manifest.get('versiune') != MANIFEST_VERSION:
        return ['not a version 2 manifest']
    problems = [f'key not allowed: {key}' for key in sorted(set(manifest) - MANIFEST_KEYS)]
    capture = manifest.get('captura')
    if not isinstance(capture, dict) or set(capture) != CAPTURE_KEYS:
        return problems + ['`captura` needs exactly ' + ', '.join(sorted(CAPTURE_KEYS))]
    if capture['algoritm'] != ALGORITHM or not is_hash(capture['sha256']) or capture['fisier'] != capture['sha256'] + '.json' \
            or not isinstance(capture['octeti'], int) or capture['octeti'] <= 0:
        problems.append('`captura` is not a full SHA-256 with its file name')
    if not all(is_hash(h) for h in manifest.get('capturi_anterioare', [])):
        problems.append('`capturi_anterioare` holds full SHA-256 values')
    for item in manifest.get('cereri_date', []):
        if not isinstance(item, dict) or set(item) != set(REQUEST_KEYS):
            problems.append('a data request needs exactly ' + ', '.join(REQUEST_KEYS))
            break
    return problems


def read_manifest(path):
    """The manifest in `path`; None for a legacy record (versiune 1: the whole record is tracked). Raises ValueError or OSError."""
    document = json.loads(Path(path).read_text())
    return document if document.get('versiune') == MANIFEST_VERSION else None


def captures_dir(observations):
    return Path(observations) / 'inventare' / CAPTURE_DIR


def store(directory, raw):
    """Write a capture under its hash name. Returns the path. An existing file with that name must hold the same bytes; it is never rewritten."""
    directory = Path(directory)
    target = directory / (digest(raw) + '.json')
    if target.exists():
        if target.read_bytes() != raw:
            raise CaptureError(f'{target}: a file with this name holds other bytes')
        return target
    directory.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    partial.write_bytes(raw)
    partial.replace(target)
    return target


def verify(directory, manifest):
    """Check the capture of a manifest. Returns ('verified', record), ('unavailable', None) or ('error', message)."""
    capture = manifest['captura']
    path = Path(directory) / capture['fisier']
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return 'unavailable', None
    except OSError as exc:
        return 'error', f'{path.name}: {exc}'
    if digest(raw) != capture['sha256'] or len(raw) != capture['octeti']:
        return 'error', f'{path.name}: the bytes do not match the recorded SHA-256'
    try:
        record = json.loads(raw)
    except ValueError as exc:
        return 'error', f'{path.name}: {exc}'
    expected = {**derived(record)}
    if any(manifest.get(key) != value for key, value in expected.items()):
        return 'error', f'{path.name}: the capture differs from its manifest'
    return 'verified', record


def merged_previous(manifest_path, directory):
    """Hashes of the captures that the manifest at `manifest_path` replaces. A legacy record is kept as a capture first."""
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        return []
    manifest = read_manifest(manifest_path)
    if manifest is None:
        raw = manifest_path.read_bytes()
        store(directory, raw)
        return [digest(raw)]
    return [manifest['captura']['sha256'], *manifest.get('capturi_anterioare', [])]


def write_capture(manifest_dir, directory, name, record):
    """Keep a new capture and write its manifest `manifest_dir/name`. An earlier capture of the page stays in the capture directory. Returns the manifest path."""
    path = Path(manifest_dir) / name
    previous = merged_previous(path, directory) if path.exists() else []
    raw = capture_bytes(record)
    store(directory, raw)
    Path(manifest_dir).mkdir(parents=True, exist_ok=True)
    path.write_text(manifest_text(manifest_from(record, raw, previous)))
    return path


def migrate(manifest_dir, directory, paths):
    """Turn legacy render records into manifests. The original bytes go to the capture directory first and are read back before the manifest replaces the record.
    Returns [(name, 'migrated' | 'already')]. Repeating it changes no byte."""
    results = []
    for path in map(Path, paths):
        raw = path.read_bytes()
        record = json.loads(raw)
        if record.get('versiune') == MANIFEST_VERSION:
            results.append((path.name, 'already'))
            continue
        stored = store(directory, raw)
        if stored.read_bytes() != raw:
            raise CaptureError(f'{path.name}: the stored copy differs from the record')
        path.write_text(manifest_text(manifest_from(record, raw)))
        results.append((path.name, 'migrated'))
    return results


def restore(directory, source, manifests):
    """Import a file that the owner supplies as an original capture. The file must have a hash that a manifest records. Returns the stored path."""
    raw = Path(source).read_bytes()
    wanted = {h for manifest in manifests for h in [manifest['captura']['sha256'], *manifest.get('capturi_anterioare', [])]}
    if digest(raw) not in wanted:
        raise CaptureError(f'{source}: its SHA-256 {digest(raw)} is in no manifest')
    return store(directory, raw)
