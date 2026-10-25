"""State handling for the variable inventories: the discovery registry, preservation rules, safe writes and the
request log. Stdlib only.

The registry (descoperiri.json) records which structured source belongs to which project and why. It is separate
from the per-run fetch limit: a smaller limit never deletes a discovery. Nothing here fetches or parses a source.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

REGISTRY = 'descoperiri.json'
STATES = ('activ', 'descoperit', 'retras')
METHODS = ('link-in-documentatie', 'url-in-text', 'dovada-pilot', 'adaugat-explicit', 'repo-la-revizie', 'membru-anterior')
OUTPUTS = ('proiecte.json', 'seturi-date.json', REGISTRY, 'rezumat.csv', 'campuri.csv', 'intrari-utilizator.csv')
LOG_COLUMNS = ['lot', 'la', 'metoda', 'url', 'stare', 'http_status', 'octeti', 'cache', 'scop']


class StateError(Exception):
    """The tracked state is unreadable or a proposed state is invalid. Raised before any file is replaced."""


SECRET_SHAPES = (
    re.compile(r'\bpat[A-Za-z0-9]{10,}\.[A-Fa-f0-9]{32,}\b'),
    re.compile(r'''(?i)((?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|secret|password|bearer)['"]?\s*[:=]\s*['"])([^'"\s]{16,})(['"])'''),
)
SCRIPT_TYPES = ('text/html', 'application/javascript', 'text/javascript', 'application/x-javascript')


def protect(response):
    """Mask credentials that a public page embeds in its scripts, before the body is stored or hashed.
    The inventory never keeps or uses a credential. `redactari` counts the masked values."""
    if response.get('state') != 'ok' or response.get('content_type') not in SCRIPT_TYPES:
        return response
    body, count = response.get('body', ''), 0
    for shape in SECRET_SHAPES:
        body, n = shape.subn(lambda m: (m.group(1) + '[REDACTED]' + m.group(3)) if m.lastindex == 3 else '[REDACTED]', body)
        count += n
    if count:
        response = {**response, 'body': body, 'redactari': count}
    return response


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def source_id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def priority(url):
    """Rank a structured source: API contracts first, then CSV, then other files. English variants rank lower."""
    low = url.lower()
    rank = 0 if 'openapi' in low or 'swagger' in low else 1 if '.csv' in low else 2
    return rank + (3 if '/en/' in url else 0)


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def usable(source):
    """A source record holds field evidence when its body was parsed. A failed or unparsed fetch holds none."""
    return bool(source) and source.get('stare') == 'analizat' and bool(source.get('sha256'))


def counted_fields(source):
    """The fields that count. A field that restates a record of another source (`in_contract`: an API reference page that repeats its
    OpenAPI contract) is more evidence for that record, not another field."""
    return [f for f in source.get('campuri', []) if not f.get('in_contract')]


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise StateError(f'Cannot read {path}: {exc}') from exc


def load_previous(out):
    """Read the tracked inventory state. Missing files give an empty state; corrupt files raise before any write."""
    out = Path(out)
    previous = {'profiles': {}, 'sources': {}, 'discoveries': [], 'registry': False}
    if (out / 'proiecte.json').exists():
        previous['profiles'] = {p['slug']: p for p in read_json(out / 'proiecte.json').get('proiecte', [])}
    if (out / 'seturi-date.json').exists():
        previous['sources'] = {s['id']: s for s in read_json(out / 'seturi-date.json').get('surse', [])}
    if (out / REGISTRY).exists():
        previous['registry'] = True
        previous['discoveries'] = read_json(out / REGISTRY).get('descoperiri', [])
    return previous


def new_discovery(slug, url, method, *, state='descoperit', parent=None, evidence=None, original=None,
                  discovered_at=None, rank=None, note=None, extra=None, reading=None):
    """A registry record. `locator_stare` says whether the original discovery locator is known."""
    record = {'proiect': slug, 'url': url, 'sursa_id': source_id(url), 'stare': state, 'metoda': method,
              'parinte': parent, 'link_original': original or url, 'dovada': evidence,
              'locator_stare': 'cunoscut' if evidence else 'necunoscut', 'descoperit_la': discovered_at,
              'prioritate': priority(url) if rank is None else rank, 'retras': None, 'istoric': []}
    if note:
        record['nota'] = note
    if extra:
        record['dovezi_suplimentare'] = extra
    if reading:
        record['citire'] = reading
    return record


def member_order(record):
    return (record['prioritate'], record['url'])


def registry_map(discoveries):
    return {(d['proiect'], d['url']): d for d in discoveries}


def sorted_registry(registry):
    return sorted(registry.values(), key=lambda d: (d['proiect'], d['url']))


def active_members(registry, slug):
    return sorted((d for (p, _), d in registry.items() if p == slug and d['stare'] == 'activ'), key=member_order)


def seed_registry(previous, found):
    """Add a record for every membership that the tracked profiles hold and the registry lacks.
    `found` maps (slug, url) to a re-derived discovery. An unrecoverable locator stays unknown."""
    registry = registry_map(previous['discoveries'])
    for slug, profile in previous['profiles'].items():
        for ident in profile.get('surse_structurate', []):
            source = previous['sources'].get(ident)
            if not source:
                continue
            key = (slug, source['url'])
            if key in registry:
                if registry[key]['stare'] == 'descoperit':
                    registry[key]['stare'] = 'activ'
                continue
            record = found.get(key)
            if record:
                record = {**record, 'stare': 'activ'}
            else:
                record = new_discovery(slug, source['url'], 'membru-anterior', state='activ')
            registry[key] = record
    return registry


def admit(registry, slug, maximum):
    """Admit the best new discoveries of a project until it has `maximum` active members. Never removes a member."""
    admitted = []
    free = maximum - len(active_members(registry, slug))
    waiting = sorted((d for (p, _), d in registry.items() if p == slug and d['stare'] == 'descoperit'), key=member_order)
    for record in waiting[:max(free, 0)]:
        record['stare'] = 'activ'
        admitted.append(record)
    return admitted


def retire(registry, slug, url, reason, when):
    """Retire a membership with a recorded reason. The record and its history stay in the registry."""
    if not reason or not reason.strip():
        raise StateError('Retiring a source needs a reason.')
    record = registry.get((slug, url))
    if not record:
        raise StateError(f'No discovery for {slug} {url}.')
    record['retras'] = {'motiv': reason.strip(), 'la': when, 'stare_anterioara': record['stare']}
    record['istoric'].append({'eveniment': 'retras', 'la': when, 'motiv': reason.strip()})
    record['stare'] = 'retras'
    return record


def validate_state(profiles, sources, registry, previous=None):
    """Structural checks on a proposed state. Returns messages; an empty list means the state may be written."""
    errors = []
    ids = [s['id'] for s in sources]
    if len(set(ids)) != len(ids):
        errors.append('Duplicate source IDs.')
    known = set(ids)
    for source in sources:
        if source_id(source['url']) != source['id']:
            errors.append('Source ID does not match URL: ' + source['url'])
    active = {}
    for (slug, url), record in registry.items():
        if record['stare'] not in STATES:
            errors.append(f'Unknown registry state for {slug} {url}: {record["stare"]}')
        if record['sursa_id'] != source_id(url):
            errors.append(f'Registry ID does not match URL: {slug} {url}')
        if record['stare'] == 'retras' and not (record.get('retras') or {}).get('motiv'):
            errors.append(f'Retired source without a reason: {slug} {url}')
        if record['stare'] == 'activ':
            active.setdefault(slug, set()).add(record['sursa_id'])
            if record['sursa_id'] not in known:
                errors.append(f'Active discovery without a source record: {slug} {url}')
        if record['locator_stare'] == 'cunoscut' and not record.get('dovada'):
            errors.append(f'Known locator without evidence: {slug} {url}')
    for profile in profiles:
        refs = profile.get('surse_structurate', [])
        for ref in refs:
            if ref not in known:
                errors.append(f'Unknown source reference: {profile["slug"]} {ref}')
        if set(refs) != active.get(profile['slug'], set()):
            errors.append('Profile sources differ from the registry: ' + profile['slug'])
        if len(set(refs)) != len(refs):
            errors.append('Duplicate source reference: ' + profile['slug'])
    if previous:
        by_id = {s['id']: s for s in sources}
        for ident, old in previous['sources'].items():
            if usable(old):
                new = by_id.get(ident)
                if not usable(new):
                    errors.append('Field evidence would be lost: ' + old['url'])
                elif new['sha256'] != old['sha256'] and old['sha256'] not in [v['sha256'] for v in new.get('versiuni_anterioare', [])]:
                    errors.append('Previous evidence version not retained: ' + old['url'])
    return errors


def check_text(name, text):
    """Parse a proposed file. A JSON or CSV file that cannot be read back never replaces a tracked one."""
    if name.endswith('.json'):
        try:
            json.loads(text)
        except ValueError as exc:
            raise StateError(f'Proposed {name} is not valid JSON: {exc}') from exc
    elif name.endswith('.csv'):
        try:
            rows = list(csv.reader(io.StringIO(text)))
        except csv.Error as exc:
            raise StateError(f'Proposed {name} is not valid CSV: {exc}') from exc
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise StateError(f'Proposed {name} has no header or ragged rows.')


def write_atomic(out, texts):
    """Write all files or none. Each file goes to a temporary name first; all are replaced only after every write
    and every parse check succeeded."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in texts.items():
        check_text(name, text)
    temporary = {}
    try:
        for name, text in texts.items():
            path = out / (name + f'.tmp{os.getpid()}')
            path.write_text(text)
            temporary[name] = path
        for name, path in temporary.items():
            os.replace(path, out / name)
    finally:
        for path in temporary.values():
            if path.exists():
                path.unlink()


def write_file_atomic(path, text):
    path = Path(path)
    temporary = path.with_name(path.name + f'.tmp{os.getpid()}')
    try:
        temporary.write_text(text)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class RequestLog:
    """Append-only CSV log of requests and cache reuse. It holds URLs and outcomes, never headers or credentials."""

    def __init__(self, path, lot):
        self.path, self.lot = Path(path), lot
        self.guard = threading.Lock()

    def rows(self):
        if not self.path.exists():
            return []
        with self.path.open(newline='') as stream:
            return list(csv.DictReader(stream))

    def direct_requests(self):
        """Direct HTTP fetches already logged for this lot, including failed attempts and retries."""
        return sum(1 for r in self.rows() if r['lot'] == self.lot and r['cache'] == 'nu')

    def browser_counts(self):
        """(navigations, data requests) of this lot recorded by render_pages.py. They never count as direct requests."""
        rows = [r for r in self.rows() if r['lot'] == self.lot and r['cache'] == 'browser']
        return sum(r['metoda'] == 'BROWSER' for r in rows), sum(r['metoda'] != 'BROWSER' for r in rows)

    def add(self, method, url, state, status=None, size=None, cache=False, purpose=''):
        """`cache` is True (body reused in the process), False (a direct request) or the string `browser`."""
        origin = cache if isinstance(cache, str) else 'da' if cache else 'nu'
        with self.guard:
            new = not self.path.exists()
            with self.path.open('a', newline='') as stream:
                writer = csv.writer(stream, lineterminator='\n')
                if new:
                    writer.writerow(LOG_COLUMNS)
                writer.writerow([self.lot, now_utc(), method, url, state, '' if status is None else status,
                                 '' if size is None else size, origin, purpose])
