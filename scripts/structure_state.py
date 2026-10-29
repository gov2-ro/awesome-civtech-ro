"""Version-2 structure store, immutable evidence and offline integrity checks. Stdlib only."""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from common import forbidden

SECTIONS = ('patterns', 'operations', 'identifier_rules', 'collections', 'namespaces', 'relationships')


class StructureError(ValueError):
    """A structure store or input cannot be used safely."""


def require(condition, message):
    if not condition:
        raise StructureError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise StructureError(f'Cannot read {Path(path).name}: {exc}') from exc


def atomic(path, text):
    path = Path(path)
    temporary = path.with_name(path.name + '.new')
    with temporary.open('w', encoding='utf-8') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@contextmanager
def locked(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / '.structure.lock'
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StructureError('Another structure writer holds the output lock.') from exc
    try:
        os.close(fd)
        yield
    finally:
        path.unlink()


def blank():
    return dict(schema_version=2, projects={}, attempts=[], evidence={}, requests=[], records=[], assertions=[])


def load(root):
    root = Path(root)
    if not (root / 'store.json').exists():
        require(not any(root.glob('*.json')), 'Output contains unrelated JSON files; select a separate directory.')
        return blank()
    store = read(root / 'store.json')
    check(store, root)
    return store


def save(store, root):
    root = Path(root)
    check(store, root)
    atomic(root / 'store.json', json.dumps(store, ensure_ascii=False, indent=2) + '\n')
    atomic(root / 'requests.jsonl', ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in store['requests']))
    # This file belongs to the owner. Never replace an existing file, even an empty one.
    if not (root / 'decisions.json').exists():
        with (root / 'decisions.json').open('x', encoding='utf-8') as stream:
            stream.write('[]\n')


def project(store, slug, url):
    if slug not in store['projects']:
        store['projects'][slug] = dict(slug=slug, input_url=url, checks=[], latest_attempt=None,
                                      **{section: {} for section in SECTIONS})
    return store['projects'][slug]


def evidence(store, root, slug, source, text, observed_at, method='http', **metadata):
    text = '\n'.join(line.rstrip() for line in text.splitlines()).rstrip() + '\n'
    digest = hashlib.sha256(text.encode()).hexdigest()
    eid = key(slug, source, digest, observed_at, method)
    path = Path(root) / 'evidence' / (digest + '.txt')
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Existing evidence was modified.')
    else:
        atomic(path, text)
    store['evidence'].setdefault(eid, dict(id=eid, project=slug, source=source, method=method,
                                         observed_at=observed_at, artifact=str(path.relative_to(root)),
                                         sha256=digest, **metadata))
    return eid


def finding(p, section, identity, item, eid, attempt):
    fid = key(p['slug'], section, identity)
    old = p[section].get(fid)
    if old:
        if section == 'operations' and any(old.get(k) != item.get(k) for k in ('security', 'parameters')):
            old.setdefault('declaration_history', []).append(json.loads(json.dumps({k: old.get(k) for k in ('security', 'parameters', 'evidence')})))
            old['security'], old['parameters'] = item['security'], item['parameters']
        if section == 'operations':
            old['unresolved_parameters'] = item.get('unresolved_parameters', False)
        if eid not in old['evidence']:
            old['evidence'].append(eid)
        old['applicability'] = 'current'
        old['last_supported_attempt'] = attempt
    else:
        p[section][fid] = dict(item, id=fid, evidence=[eid], applicability='current',
                              last_supported_attempt=attempt, state='proposed')
    return fid


def begin(store, slug, budget, method):
    aid = key(slug, now(), len(store['attempts']))
    attempt = dict(id=aid, project=slug, started_at=now(), finished_at=None, method=method,
                   request_budget=budget, requests_used=0, outcome='partial',
                   incomplete_reasons=['Attempt has not completed.'])
    store['attempts'].append(attempt)
    p = store['projects'][slug]
    p['latest_attempt'] = aid
    for section in SECTIONS:
        for f in p[section].values():
            f['applicability'] = 'stale'
    return attempt


def finish(store, attempt, reasons, blocked=False):
    attempt.update(finished_at=now(), outcome='blocked' if blocked else 'partial' if reasons else 'observed',
                   incomplete_reasons=list(dict.fromkeys(reasons)))


def seed_pilot(store, root, pilot):
    """Import checked v1 evidence and observations. Do not import editorial decisions."""
    from check_structure_pilot import validate
    profiles, records, assertions, _ = validate(Path(pilot))
    evidence_ids = {}
    for slug, profile in profiles.items():
        p = project(store, slug, profile['input_url'])
        for e in profile['evidence']:
            text = (Path(pilot) / e['artifact']).read_text()
            eid = evidence(store, root, slug, e['source'], text, e['observed_at'], 'retained',
                           provenance={k: v for k, v in e.items() if k not in {'artifact', 'excerpt', 'applicability'}})
            evidence_ids[e['id']] = eid
        for section in SECTIONS:
            for f in profile[section]:
                item = {k: v for k, v in f.items() if k not in {'id', 'evidence', 'applicability'}}
                item['legacy_id'] = f['id']
                for field in ('declaration_evidence', 'read_only_evidence'):
                    if field in item:
                        item[field] = evidence_ids[item[field]]
                if item.get('last_test', {}).get('evidence'):
                    item['last_test'] = dict(item['last_test'], evidence=evidence_ids[item['last_test']['evidence']])
                identity = f.get('url_template', f['id'])
                if section == 'operations':
                    identity = f['method'] + ' ' + f['url_template']
                    item['uses'] = [{'collection': f['collection'], 'subject_role': 'unknown', 'scope': 'at_least'}]
                    item['security'] = dict(declared_requirement='unspecified', schemes=[], documented_authentication=f['authentication'],
                                            observed_enforcement='anonymous' if 'tested' in f['basis'] and f['authentication'] == 'none' else 'unknown')
                if section == 'collections':
                    item.update(record_grain='registration' if f['entity_type'] == 'registration' else 'unknown', identity_components=[])
                if section == 'identifier_rules':
                    item['mapping_basis'] = 'declared'
                for old_eid in f['evidence']:
                    fid = key(slug, section, identity)
                    if fid in p[section]:
                        if evidence_ids[old_eid] not in p[section][fid]['evidence']:
                            p[section][fid]['evidence'].append(evidence_ids[old_eid])
                    else:
                        finding(p, section, identity, item, evidence_ids[old_eid], 'pilot-v1')
                        p[section][fid]['applicability'] = 'historical'
                # Evidence is historical until an independent engine observation supports it.
    for destination, values, identity_field in [('records', records.values(), 'key'), ('assertions', assertions.values(), 'id')]:
        existing = {x[identity_field] for x in store[destination]}
        for value in values:
            if value[identity_field] not in existing:
                value = json.loads(json.dumps(value))
                value['evidence'] = [evidence_ids[e] for e in value['evidence']]
                store[destination].append(value)


def check(store, root):
    require(isinstance(store, dict) and store.get('schema_version') == 2, 'Expected a version-2 structure store.')
    for name, kind in [('projects', dict), ('evidence', dict), ('attempts', list), ('requests', list), ('records', list), ('assertions', list)]:
        require(type(store.get(name)) is kind, f'Invalid store field: {name}')
    for eid, e in store['evidence'].items():
        require(e.get('id') == eid and e.get('project') in store['projects'], 'Invalid evidence reference.')
        path = (Path(root) / e['artifact']).resolve()
        require(path.is_relative_to(Path(root).resolve()), 'Evidence path leaves output directory.')
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == e['sha256'], 'Evidence hash mismatch.')
    attempts = {a['id']: a for a in store['attempts']}
    require(len(attempts) == len(store['attempts']), 'Duplicate attempt IDs.')
    for slug, p in store['projects'].items():
        require(p.get('slug') == slug, 'Invalid project key.')
        require(p.get('latest_attempt') is None or p['latest_attempt'] in attempts, 'Unknown latest attempt.')
        collection_keys = set(p['collections']) | {x['legacy_id'] for x in p['collections'].values() if x.get('legacy_id')}
        for section in SECTIONS:
            require(isinstance(p.get(section), dict), f'Invalid findings: {section}')
            for fid, f in p[section].items():
                require(f.get('id') == fid and f.get('state') == 'proposed', 'Generated findings cannot accept a decision.')
                require(f.get('applicability') in {'current', 'historical', 'stale', 'unknown'}, 'Invalid applicability.')
                require(bool(f.get('evidence')) and all(e in store['evidence'] for e in f['evidence']), 'Missing finding evidence.')
                for field in ('declaration_evidence', 'read_only_evidence'):
                    require(field not in f or f[field] in store['evidence'], 'Unknown supporting evidence.')
                require(not f.get('last_test', {}).get('evidence') or f['last_test']['evidence'] in store['evidence'], 'Unknown API test evidence.')
                if section == 'operations':
                    require(isinstance(f.get('uses'), list) and bool(f['uses']), 'An operation needs collection uses.')
                    require(all(u.get('collection') in collection_keys for u in f['uses']), 'Unknown operation collection.')
                    require(f.get('security', {}).get('declared_requirement') in {'unspecified', 'anonymous', 'authenticated'}, 'Invalid declared security.')
                if section == 'identifier_rules':
                    require(f.get('mapping_basis') in {'declared', 'sampled', 'unknown'}, 'Invalid mapping basis.')
    counts = {}
    for row in store['requests']:
        require(row.get('attempt') in attempts and row.get('project') == attempts[row['attempt']]['project'], 'Unknown request attempt.')
        require(type(row.get('sent')) is bool, 'Request needs a dispatch flag.')
        if row['sent']:
            policy = row.get('policy_hosts')
            require(policy is None or (isinstance(policy, list) and all(isinstance(h, str) for h in policy)), 'Invalid dispatch policy.')
            require(not forbidden(row['url'], [{'gazda': h} for h in policy] if policy is not None else None), 'Forbidden host was requested.')
            counts[row['attempt']] = counts.get(row['attempt'], 0) + 1
    for aid, a in attempts.items():
        require(a['project'] in store['projects'], 'Unknown attempt project.')
        require(0 <= counts.get(aid, 0) == a['requests_used'] <= a['request_budget'] <= 100, 'Invalid request accounting.')
    record_keys = {r['key'] for r in store['records']}
    require(len(record_keys) == len(store['records']), 'Duplicate record keys.')
    assertion_ids = {a['id'] for a in store['assertions']}
    require(len(assertion_ids) == len(store['assertions']), 'Duplicate assertion IDs.')
    for a in store['assertions']:
        require('state' not in a and all(r in record_keys for r in a['records']), 'Invalid proposed assertion.')
    for item in store['records'] + store['assertions']:
        require(all(e in store['evidence'] for e in item['evidence']), 'Unknown record/assertion evidence.')
    for p in store['projects'].values():
        for relationship in p['relationships'].values():
            require(relationship.get('source') in record_keys and relationship.get('target') in record_keys, 'Unknown relationship record.')
    path = Path(root) / 'decisions.json'
    if path.exists():
        decisions = read(path)
        require(isinstance(decisions, list), 'Decisions must be a list.')
        for d in decisions:
            require(d.get('assertion_id') in assertion_ids and d.get('state') in {'accepted', 'rejected', 'deferred'}, 'Invalid owner decision.')
