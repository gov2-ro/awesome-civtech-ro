#!/usr/bin/env python3
"""Check the bounded structure pilot offline. This tool never fetches or writes data."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from common import forbidden

REPO = Path(__file__).resolve().parents[1]
DEFAULT = REPO / 'docs/reports/site-structure-pilot'
PROJECTS = {'transparenta-eu', 'sicap-ai', 'registrul-firmelor', 'romania-transparenta'}
CHECK_STATES = {'observed', 'not_found', 'invalid', 'blocked', 'error', 'unchecked', 'skipped'}
ATTEMPT_STATES = {'observed', 'partial', 'blocked', 'error'}


class PilotError(ValueError):
    """A pilot artifact does not satisfy the evidence contract."""


def require(condition, message):
    if not condition:
        raise PilotError(message)


def fields(obj, names, where):
    require(isinstance(obj, dict), f'{where}: expected an object')
    for name, expected in names.items():
        require(name in obj and type(obj[name]) is expected, f'{where}: invalid {name}')


def nonempty(value, where):
    require(isinstance(value, str) and bool(value.strip()), f'{where}: expected nonempty text')


def utc(value):
    try:
        parsed = datetime.fromisoformat(value)
        require(parsed.utcoffset() == timezone.utc.utcoffset(parsed), 'time must have a UTC offset of zero')
        return parsed
    except (TypeError, ValueError) as exc:
        raise PilotError('invalid UTC timestamp') from exc


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise PilotError(f'cannot read {path.name}: {exc}') from exc


def keyed(items, where, key='id'):
    require(isinstance(items, list), f'{where}: expected a list')
    result = {}
    for item in items:
        fields(item, {key: str}, where)
        nonempty(item[key], where)
        require(item[key] not in result, f'{where}: duplicate {item[key]}')
        result[item[key]] = item
    return result


def refs(obj, known, where):
    fields(obj, {'evidence': list}, where)
    require(bool(obj['evidence']), f'{where}: missing evidence')
    require(all(isinstance(x, str) and x in known for x in obj['evidence']), f'{where}: unknown evidence')


def assertion_id(kind, record_keys):
    """Stable under evidence refresh, timestamp changes and pair reversal."""
    value = json.dumps([kind, sorted(record_keys)], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def pointer(document, path):
    require(path == '' or path.startswith('/'), 'invalid JSON pointer')
    value = document
    try:
        for token in path.split('/')[1:] if path else []:
            token = token.replace('~1', '/').replace('~0', '~')
            value = value[int(token)] if isinstance(value, list) else value[token]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PilotError('unresolved JSON pointer') from exc
    return value


def evidence_check(item, root, repo):
    fields(item, {'source': str, 'method': str, 'observed_at': str, 'artifact': str,
                  'sha256': str, 'locator': dict, 'excerpt': str, 'applicability': str}, 'evidence')
    utc(item['observed_at'])
    require(item['method'] in {'http', 'repository', 'retained', 'owner_saved'}, 'unknown acquisition method')
    require(item['applicability'] in {'current', 'historical', 'stale', 'unknown'}, 'invalid applicability')
    nonempty(item['source'], 'evidence source')
    nonempty(item['excerpt'], 'evidence excerpt')
    path = (root / item['artifact']).resolve()
    require(path.is_relative_to(root.resolve()), 'evidence artifact leaves pilot directory')
    try:
        raw = path.read_bytes()
        text = raw.decode('utf-8')
    except (OSError, UnicodeError) as exc:
        raise PilotError('unavailable UTF-8 evidence artifact') from exc
    require(hashlib.sha256(raw).hexdigest() == item['sha256'], 'evidence hash mismatch')
    loc = item['locator']
    fields(loc, {'type': str}, 'locator')
    if loc['type'] == 'text':
        fields(loc, {'start': int, 'end': int}, 'text locator')
        require(0 <= loc['start'] < loc['end'] <= len(text), 'invalid text interval')
        selected = text[loc['start']:loc['end']]
    elif loc['type'] == 'json_pointer':
        fields(loc, {'pointer': str}, 'JSON locator')
        selected = json.dumps(pointer(read_json(path), loc['pointer']), ensure_ascii=False, sort_keys=True)
    else:
        raise PilotError('unsupported pilot locator; use text or json_pointer')
    require(item['excerpt'] in selected, 'excerpt does not occur at locator')
    if item['method'] == 'repository':
        require(bool(re.fullmatch(r'[0-9a-f]{40}', item.get('revision', ''))), 'missing repository revision')
        require(item['revision'] in item['source'], 'repository source is not pinned to revision')
    if item['method'] == 'owner_saved':
        fields(item, {'saved_at': str, 'imported_at': str}, 'saved evidence')
        saved = datetime.fromisoformat(item['saved_at'])
        require(saved.utcoffset() is not None and saved <= utc(item['imported_at']), 'invalid save/import chronology')
    if 'inventory_reference' in item:
        ref = item['inventory_reference']
        fields(ref, {'path': str, 'source_id': str, 'pointer': str}, 'inventory reference')
        p = (repo / ref['path']).resolve()
        require(p.is_relative_to((repo / 'data/taxonomy-v2/observatii').resolve()), 'invalid inventory path')
        source = pointer(read_json(p), ref['pointer'])
        require(isinstance(source, dict) and source.get('id') == ref['source_id'], 'inventory source ID mismatch')
        require(source.get('url') == item['source'], 'inventory source URL mismatch')


def template_check(obj, namespaces, variables_key='variables'):
    fields(obj, {'url_template': str, variables_key: list}, 'template')
    require(urlsplit(obj['url_template']).scheme == 'https', 'template must use HTTPS')
    require(not urlsplit(obj['url_template']).username, 'credentials in template')
    names = set()
    for var in obj[variables_key]:
        fields(var, {'name': str, 'location': str, 'encoding': str}, 'variable')
        require(var['location'] in {'path', 'query', 'fragment', 'body', 'header'}, 'invalid variable location')
        require(var['name'] not in names, 'duplicate variable')
        names.add(var['name'])
        require(var.get('namespace') is None or var['namespace'] in namespaces, 'unknown variable namespace')
        nonempty(var['encoding'], 'variable encoding')
    require(set(re.findall(r'\{([^{}]+)\}', obj['url_template'])) <= names, 'template has undeclared variable')


def profile_check(profile, root, repo):
    fields(profile, {'schema_version': int, 'project_slug': str, 'input_url': str,
                     **{x: list for x in ('attempts', 'collections', 'namespaces', 'patterns', 'operations',
                                         'identifier_rules', 'relationships', 'evidence', 'checks')}}, 'profile')
    require(profile['schema_version'] == 1, 'unsupported schema version')
    require(profile['project_slug'] in PROJECTS, 'unknown pilot project')
    evidence = keyed(profile['evidence'], 'evidence')
    for item in evidence.values():
        evidence_check(item, root, repo)
    attempts = keyed(profile['attempts'], 'attempts')
    require(bool(attempts), 'profile has no attempt')
    for a in attempts.values():
        fields(a, {'started_at': str, 'finished_at': str, 'method': str, 'tool_version': str,
                   'request_budget': int, 'requests_used': int, 'outcome': str, 'incomplete_reasons': list}, 'attempt')
        require(utc(a['started_at']) <= utc(a['finished_at']), 'attempt chronology')
        require(a['method'] in {'http', 'retained', 'mixed'}, 'invalid attempt method')
        require(0 <= a['requests_used'] <= a['request_budget'] <= 30, 'project request budget')
        require(a['outcome'] in ATTEMPT_STATES, 'invalid attempt outcome')
        if a['outcome'] != 'observed':
            require(bool(a['incomplete_reasons']), 'incomplete attempt needs reasons')
    collections = keyed(profile['collections'], 'collections')
    for item in collections.values():
        fields(item, {'label': str, 'entity_type': str, 'coverage': str}, 'collection')
        refs(item, evidence, 'collection')
        nonempty(item['coverage'], 'coverage')
    namespaces = keyed(profile['namespaces'], 'namespaces')
    for ns in namespaces.values():
        fields(ns, {'issuer': str, 'scope': str, 'normalization': str}, 'namespace')
        refs(ns, evidence, 'namespace')
        nonempty(ns['normalization'], 'normalization')
    patterns = keyed(profile['patterns'], 'patterns')
    for pat in patterns.values():
        fields(pat, {'collection': str, 'kind': str, 'basis': str, 'examples': list, 'extraction': str}, 'pattern')
        require(pat['collection'] in collections, 'unknown pattern collection')
        require(pat['kind'] in {'listing', 'search', 'detail', 'pagination', 'download'}, 'invalid pattern kind')
        require(pat['basis'] in {'declared', 'inferred', 'exact'}, 'invalid pattern basis')
        template_check(pat, namespaces)
        refs(pat, evidence, 'pattern')
        require(all(isinstance(x, str) for x in pat['examples']), 'invalid pattern example')
        if pat['basis'] == 'inferred':
            require(len(set(pat['examples'])) >= 2, 'inferred template needs distinct examples')
        if pat['basis'] == 'exact':
            require('{' not in pat['url_template'], 'exact URL contains variables')
        if pat['basis'] == 'declared':
            require(pat.get('declaration_evidence') in pat['evidence'], 'declared template needs route evidence')
        regex = re.escape(pat['url_template'])
        regex = re.sub(r'\\\{[^{}]+\\\}', r'[^/?#]+', regex)
        require(all(re.fullmatch(regex, x) for x in pat['examples']), 'example does not match template')
    operations = keyed(profile['operations'], 'operations')
    for op in operations.values():
        fields(op, {'collection': str, 'method': str, 'purpose': str, 'basis': list,
                    'authentication': str, 'parameters': list, 'request_body': dict,
                    'response_paths': dict, 'pagination': dict, 'headers': list,
                    'content_types': list, 'last_test': dict, 'page_patterns': list}, 'operation')
        require(op['collection'] in collections, 'unknown operation collection')
        require(op['method'] in {'GET', 'POST', 'HEAD'}, 'operation is not read-only')
        if op['method'] == 'POST':
            require(op.get('read_only_evidence') in op['evidence'], 'POST needs read-only evidence')
            query = op['request_body'].get('query', '')
            require(isinstance(query, str) and query.lstrip().startswith('query '), 'POST must contain an explicit read query')
        require(op['purpose'] in {'list', 'search', 'detail', 'schema', 'download'}, 'invalid operation purpose')
        require(op['authentication'] in {'none', 'key', 'session', 'oauth', 'unknown'}, 'invalid authentication')
        require(bool(op['basis']) and set(op['basis']) <= {'documented', 'observed', 'tested'}, 'invalid operation basis')
        template_check(op, namespaces)
        refs(op, evidence, 'operation')
        require(all(x in patterns for x in op['page_patterns']), 'unknown page pattern')
        for param in op['parameters']:
            fields(param, {'name': str, 'location': str, 'required': bool, 'type': str}, 'parameter')
        fields(op['last_test'], {'outcome': str, 'reason': str}, 'operation test')
        require(op['last_test']['outcome'] in CHECK_STATES, 'invalid operation test outcome')
        if 'tested' in op['basis']:
            utc(op['last_test'].get('checked_at'))
            require(op['last_test'].get('evidence') in op['evidence'], 'tested endpoint needs response evidence')
            require(op['last_test']['outcome'] == 'observed', 'tested basis needs usable response')
    for rule in keyed(profile['identifier_rules'], 'identifier rules').values():
        fields(rule, {'collection': str, 'namespace': str, 'location': str, 'subject_role': str,
                      'normalization': str}, 'identifier rule')
        require(rule['collection'] in collections and rule['namespace'] in namespaces, 'unknown identifier scope')
        require(rule['subject_role'] in {'self', 'buyer', 'supplier', 'parent', 'administers', 'other'}, 'invalid subject role')
        require(rule['subject_role'] != 'other' or bool(rule.get('role_description')), 'other role needs description')
        refs(rule, evidence, 'identifier rule')
    for check in keyed(profile['checks'], 'checks').values():
        fields(check, {'attempt': str, 'outcome': str, 'reason': str}, 'check')
        require(check['attempt'] in attempts and check['outcome'] in CHECK_STATES, 'invalid check reference/state')
        if check['outcome'] in {'unchecked', 'error'}:
            require(attempts[check['attempt']]['outcome'] != 'observed', 'uncertain check in observed attempt')
        if check['outcome'] != 'observed':
            nonempty(check['reason'], 'check reason')
    return evidence, namespaces, collections, attempts


def correspondence_check(document, decisions, profiles):
    fields(document, {'schema_version': int, 'records': list, 'assertions': list}, 'correspondences')
    require(document['schema_version'] == 1, 'unsupported correspondence version')
    records = keyed(document['records'], 'records', key='key')
    for r in records.values():
        fields(r, {'project': str, 'collection': str, 'local_namespace': str, 'local_value': str,
                   'entity_type': str, 'locators': list, 'identifiers': list, 'validity': str}, 'record')
        require(r['project'] in profiles, 'unknown record project')
        p = profiles[r['project']]
        ns = {n['id'] for n in p['namespaces']}
        require(r['local_namespace'] in ns, 'unknown record namespace')
        require(r['collection'] in {c['id'] for c in p['collections']}, 'unknown record collection')
        collection = next(c for c in p['collections'] if c['id'] == r['collection'])
        require(r['entity_type'] == collection['entity_type'], 'record and collection subject types differ')
        require(r['key'] == '|'.join([r['project'], r['collection'], r['local_namespace'], r['local_value']]), 'unstable record key')
        refs(r, {e['id'] for e in p['evidence']}, 'record')
        require(bool(r['locators']), 'record needs page/API locator')
        excerpts = '\n'.join(e['excerpt'] for e in p['evidence'] if e['id'] in r['evidence'])
        for i in r['identifiers']:
            fields(i, {'namespace': str, 'value': str, 'raw_value': str, 'subject_role': str}, 'record identifier')
            require(i['namespace'] in ns, 'unknown record identifier namespace')
            require(i['subject_role'] == 'self', 'related identifier cannot identify this record')
            nonempty(i['value'], 'identifier value')
            require(i['raw_value'] in excerpts, 'identifier absent from record evidence')
            if i['value'] != i['raw_value']:
                require(i.get('normalization_evidence') in r['evidence'], 'identifier normalization needs evidence')
            require(not (r['entity_type'] == 'contract' and i['namespace'] == 'ro:cui'), 'a contract cannot identify itself by CUI')
        require(any(i['namespace'] == r['local_namespace'] and i['value'] == r['local_value'] for i in r['identifiers']), 'local key has no self identifier')
    require(all(sum(r['project'] == slug for r in records.values()) <= 10 for slug in profiles), 'too many record samples')
    assertions = keyed(document['assertions'], 'assertions')
    known_evidence = {e['id'] for p in profiles.values() for e in p['evidence']}
    for a in assertions.values():
        fields(a, {'kind': str, 'records': list, 'basis': str, 'limitations': list}, 'assertion')
        require('state' not in a, 'generated assertion must not carry an editorial state')
        require(a['kind'] == 'same_entity' and len(a['records']) == 2 and len(set(a['records'])) == 2, 'invalid identity pair')
        require(all(x in records for x in a['records']), 'unknown assertion record')
        require(a['id'] == assertion_id(a['kind'], a['records']), 'unstable assertion ID')
        require(a['basis'] in {'shared_identifier', 'explicit_mapping', 'explicit_link', 'name_candidate'}, 'invalid assertion basis')
        refs(a, known_evidence, 'assertion')
        left, right = [records[x] for x in a['records']]
        require(all(set(r['evidence']) & set(a['evidence']) for r in (left, right)), 'identity needs evidence from both records')
        require(left['entity_type'] == right['entity_type'], 'incompatible identity subjects')
        if a['basis'] == 'shared_identifier':
            ids = lambda r: {(i['namespace'], i['value']) for i in r['identifiers'] if i['namespace'].startswith('ro:')}
            shared = ids(left) & ids(right)
            require(bool(shared), 'no shared identifier in common namespace')
            for namespace, _ in shared:
                definitions = [next(n for n in profiles[r['project']]['namespaces'] if n['id'] == namespace) for r in (left, right)]
                require(definitions[0]['issuer'] == definitions[1]['issuer'], 'namespace issuer conflict')
    require(isinstance(decisions, list), 'decisions must be a list')
    for d in keyed(decisions, 'decisions', 'assertion_id').values():
        fields(d, {'state': str, 'note': str, 'decided_at': str}, 'decision')
        require(d['assertion_id'] in assertions, 'orphan decision')
        require(d['state'] in {'accepted', 'rejected', 'deferred'}, 'invalid decision state')
        utc(d['decided_at'])
        nonempty(d['note'], 'decision note')
        require(not (d['state'] == 'accepted' and assertions[d['assertion_id']]['basis'] == 'name_candidate'), 'name alone cannot establish identity')
    for p in profiles.values():
        for rel in keyed(p['relationships'], 'relationships').values():
            fields(rel, {'source': str, 'target': str, 'relation': str}, 'relationship')
            require(rel['source'] in records and rel['target'] in records, 'unknown relationship record')
            require(rel['relation'] != 'same_entity', 'identity must use a correspondence')
            refs(rel, known_evidence, 'relationship')
    return records, assertions


def request_check(rows, profiles):
    require(sum(r.get('sent') is True for r in rows) <= 100, 'pilot request budget')
    counts = {}
    stopped = set()
    last_request = {}
    for r in rows:
        fields(r, {'project_slug': str, 'attempt': str, 'url': str, 'method': str, 'channel': str,
                   'checked_at': str, 'sent': bool, 'outcome': str, 'reason': str, 'bytes': int, 'truncated': bool}, 'request')
        utc(r['checked_at'])
        require(r['project_slug'] in profiles, 'unknown request project')
        require(r['attempt'] in {a['id'] for a in profiles[r['project_slug']]['attempts']}, 'unknown request attempt')
        require(r['channel'] in {'direct', 'browser', 'search'}, 'invalid request channel')
        require(r['method'] in {'GET', 'HEAD', 'POST'}, 'invalid request method')
        require(0 <= r['bytes'] <= 2 * 1024 * 1024, 'body cap exceeded')
        if r['sent']:
            require(not forbidden(r['url']), 'forbidden host requested')
            host = urlsplit(r['url']).hostname
            if host in last_request:
                require((utc(r['checked_at']) - last_request[host]).total_seconds() >= 1, 'host pacing violation')
            last_request[host] = utc(r['checked_at'])
            require(host not in stopped, 'request after host stop')
            if r.get('status') in {401, 403, 429} or r['outcome'] == 'blocked':
                stopped.add(host)
            key = (r['project_slug'], r['attempt'])
            counts[key] = counts.get(key, 0) + 1
        elif r['reason'] == 'colectare-interzisa':
            require(bool(forbidden(r['url'])), 'incorrect policy skip')
    for slug, p in profiles.items():
        require(sum(r['sent'] and r['project_slug'] == slug for r in rows) <= 30, 'project total budget')
        require(sum(r['sent'] and r['project_slug'] == slug and r['channel'] == 'search' for r in rows) <= 2, 'search query budget')
        for a in p['attempts']:
            require(counts.get((slug, a['id']), 0) == a['requests_used'], 'request accounting mismatch')


def validate(root=DEFAULT, repo=REPO):
    root = Path(root)
    profiles = {}
    for path in sorted((root / 'profiles').glob('*.json')):
        p = read_json(path)
        profile_check(p, root, repo)
        require(path.stem == p['project_slug'], 'profile filename mismatch')
        require(p['project_slug'] not in profiles, 'duplicate project')
        profiles[p['project_slug']] = p
    require(set(profiles) == PROJECTS, 'pilot needs four profiles')
    doc = read_json(root / 'correspondences.json')
    decisions = read_json(root / 'decisions.json')
    records, assertions = correspondence_check(doc, decisions, profiles)
    try:
        rows = [json.loads(x) for x in (root / 'requests.jsonl').read_text().splitlines()]
    except (OSError, ValueError) as exc:
        raise PilotError('cannot read request log') from exc
    request_check(rows, profiles)
    return profiles, records, assertions, decisions


def validate_refresh(previous, current):
    """Compare validated snapshots. Preserve findings and owner decisions after a failed refresh."""
    old_profiles, old_records, old_assertions, old_decisions = previous
    profiles, records, assertions, decisions = current
    require(old_decisions == decisions, 'refresh changed editorial decisions')
    require(old_records.keys() <= records.keys(), 'refresh lost records')
    require(old_assertions.keys() <= assertions.keys(), 'refresh lost assertions')
    for slug, old in old_profiles.items():
        new = profiles[slug]
        for section in ('patterns', 'operations', 'namespaces', 'identifier_rules', 'evidence', 'attempts'):
            require(keyed(old[section], section).keys() <= keyed(new[section], section).keys(), f'refresh lost {section}')
        new_evidence = keyed(new['evidence'], 'evidence')
        for e in old['evidence']:
            require(all(new_evidence[e['id']].get(k) == v for k, v in e.items() if k != 'applicability'),
                    'refresh overwrote retained evidence')
        if new['attempts'][-1]['outcome'] in {'error', 'blocked', 'partial'}:
            evidence = keyed(new['evidence'], 'evidence')
            for e in old['evidence']:
                require(evidence[e['id']]['applicability'] in {'stale', 'unknown'}, 'failed refresh did not mark prior evidence stale')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT)
    parser.add_argument('--previous', type=Path, help='compare with a preserved pilot snapshot')
    args = parser.parse_args()
    try:
        result = validate(args.root)
        if args.previous:
            validate_refresh(validate(args.previous), result)
    except (PilotError, TypeError, KeyError, ValueError) as exc:
        parser.exit(1, f'Structure pilot: {exc}\n')
    print(f'Structure pilot: {len(result[0])} profiles, {len(result[1])} records, {len(result[2])} proposed correspondences; valid')


if __name__ == '__main__':
    main()
