"""Project retained structure observations into public or preview site builds. No network access."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from structure_curation import apply_recipe, profile_urls
from structure_discovery import safe_url
from structure_state import StructureError, blank, check, key, load, read, require

REPO = Path(__file__).resolve().parents[1]
INPUTS = REPO / 'data/taxonomy-v2/structura'
NAMESPACE_LABELS = {'ro:cui': 'CUI', 'ro:siruta': 'SIRUTA', 'igov:companies:id': 'ID igov', 'ro:onrc:euid': 'EUID ONRC'}


def public_url(value):
    """Allow HTTP source links and templates without embedded credentials."""
    try:
        return safe_url(value, preserve_fragment=True)
    except (StructureError, ValueError, TypeError):
        return ''


def receipts(store, ids):
    result = []
    for eid in dict.fromkeys(ids):
        evidence = store['evidence'][eid]
        url = public_url(evidence['source'])
        # Local paths and raw extracts never reach the browser.
        result.append(dict(url=url, observedAt=evidence['observed_at'], sha256=evidence['sha256'],
                           localOnly=not bool(url)))
    return result


def resolve_collection(project, reference):
    return next((c for cid, c in project['collections'].items()
                 if reference in (cid, c.get('legacy_id'))), {})


def project_structure(store, project):
    collections, patterns, operations = [], [], []
    for collection in project['collections'].values():
        collections.append(dict(id=collection.get('legacy_id', collection['id']), label=collection['label'],
                                entityType=collection['entity_type'], grain=collection['record_grain'],
                                sources=receipts(store, collection['evidence'])))
    for pattern in project['patterns'].values():
        url = public_url(pattern['url_template'])
        if not url:
            continue
        collection = resolve_collection(project, pattern.get('collection'))
        patterns.append(dict(url=url, kind=pattern.get('kind', 'unknown'), collection=collection.get('label', ''),
                             collectionId=collection.get('legacy_id', collection.get('id', '')),
                             variables=[dict(name=v['name'], namespace=v.get('namespace'), location=v.get('location', 'unknown'))
                                        for v in pattern.get('variables', [])],
                             basis=pattern.get('basis', 'unknown'), applicability=pattern['applicability'],
                             sources=receipts(store, pattern['evidence'])))
    for operation in project['operations'].values():
        url = public_url(operation['url_template'])
        if not url:
            continue
        security = operation['security']
        operations.append(dict(method=operation['method'], url=url,
                               collectionIds=sorted({c.get('legacy_id', c.get('id', '')) for u in operation['uses']
                                                     if (c := resolve_collection(project, u['collection']))}),
                               collections=sorted({resolve_collection(project, u['collection']).get('label', '')
                                                   for u in operation['uses']} - {''}),
                               declaredSecurity=security['declared_requirement'],
                               observedSecurity=security.get('observed_enforcement', 'unknown'),
                               unresolvedParameters=operation.get('unresolved_parameters', False),
                               applicability=operation['applicability'],
                               sources=receipts(store, operation['evidence'])))
    return dict(collections=collections, patterns=sorted(patterns, key=lambda p: p['url']),
                operations=sorted(operations, key=lambda o: (o['url'], o['method'])))


def project_preview(items, store, decisions):
    """Keep selected catalogue items and direct accepted edges. Never create entity clusters."""
    visible = {item['slug']: item for item in items}
    projects = {}
    for slug, project in sorted(store['projects'].items()):
        item = visible.get(slug)
        if not item or item['url'] != project['input_url']:
            continue
        structure = project_structure(store, project)
        projects[slug] = dict(name=item['name'], profile=f"{item['kind']}/{slug}/", **structure)
    records, record_ids, namespace_labels = [], {}, {}
    for record in store['records']:
        if record['project'] not in projects:
            continue
        ident = key('preview-record', record['key'])
        record_ids[record['key']] = ident
        project = store['projects'][record['project']]
        identifiers = []
        for identifier in record['identifiers']:
            namespace = identifier['namespace']
            declaration = next(n for nid, n in project['namespaces'].items() if namespace in (nid, n.get('legacy_id')))
            label = NAMESPACE_LABELS.get(namespace, namespace)
            # Include issuer in the lookup scope. Namespace text alone is not a common identity.
            scope = key(namespace, declaration['issuer'], '' if declaration['shared'] else record['project'])
            issuer = {'Romanian fiscal administration': 'Administrația fiscală din România'}.get(declaration['issuer'], declaration['issuer'])
            namespace_labels[scope] = dict(id=scope, namespace=namespace, label=label,
                                           issuer=issuer, shared=declaration['shared'])
            identifiers.append(dict(scope=scope, namespace=namespace, value=identifier['value'], label=label))
        records.append(dict(id=ident, project=record['project'], label=record.get('label', ''),
                            collection=resolve_collection(project, record['collection']).get('label', ''),
                            collectionId=(c := resolve_collection(project, record['collection'])).get('legacy_id', c.get('id', '')),
                            entityType=record['entity_type'], grain=record.get('record_grain', 'unknown'),
                            identifiers=identifiers, conflict=bool(record.get('identity_conflict')),
                            profileUrls=[dict(url=p['url'], basis=p['basis']) for p in profile_urls(store, record)
                                         if public_url(p['url'])], sources=receipts(store, record['evidence'])))
    states = {}
    for decision in decisions:
        require(decision.get('state') in {'accepted', 'rejected', 'deferred'}, 'Invalid owner decision state.')
        require(decision['assertion_id'] not in states, 'Duplicate owner decision.')
        states[decision['assertion_id']] = decision['state']
    conflicted = {r['id'] for r in records if r['conflict']}
    links = []
    for assertion in store['assertions']:
        if states.get(assertion['id']) != 'accepted' or assertion.get('identity_conflict'):
            continue
        refs = [record_ids[r] for r in assertion['records'] if r in record_ids]
        if len(refs) != 2 or conflicted.intersection(refs):
            continue
        links.append(dict(id=assertion['id'], records=refs, state='accepted'))
    return dict(schemaVersion=1, projects=projects, records=records, links=links,
                namespaces=sorted(namespace_labels.values(), key=lambda n: (n['label'], n['issuer'])))


def publish_preview(items, site, store_path=None):
    """Compile tracked recipes or read a checked store, then write structure payloads and lookup pages."""
    decisions = read(INPUTS / 'decisions.json')
    if store_path is not None:
        store = load(store_path)
        require((Path(store_path) / 'store.json').is_file(), 'Structure store does not exist.')
    else:
        store = blank()
        selected = {item['slug']: item for item in items}
        with tempfile.TemporaryDirectory(prefix='civtech-structure-build-') as folder:
            for path in sorted((INPUTS / 'recipes').glob('*.json')):
                recipe = read(path)
                item = selected.get(recipe['project_slug'])
                if not item or item['url'] != recipe['input_url']:
                    continue
                store = apply_recipe(store, Path(folder), recipe, path)
            check(store, Path(folder))
    payload = project_preview(items, store, decisions)
    for item in items:
        structure = payload['projects'].get(item['slug'])
        if structure:
            item['structure'] = {k: structure[k] for k in ('collections', 'patterns', 'operations')}
    folder = site / 'entitati'
    folder.mkdir(exist_ok=True)
    (folder / 'data.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    template = (REPO / 'scripts/templates/entities.html').read_text()
    for asset in ('style.css', 'structure.css', 'entities.js'):
        digest = hashlib.sha1((site / asset).read_bytes()).hexdigest()[:10]
        template = template.replace(asset + '?v=BUILD', asset + '?v=' + digest)
    (folder / 'index.html').write_text(template, encoding='utf-8')
    return payload
