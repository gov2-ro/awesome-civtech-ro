#!/usr/bin/env python3
"""Discover site structure separately from site health; stdlib, bounded, explicit output.

python3 scripts/profile_structure.py --out /tmp/structure --seed-pilot docs/reports/site-structure-pilot
python3 scripts/profile_structure.py --out /tmp/structure --only transparenta-eu --offline
python3 scripts/profile_structure.py --out /tmp/structure --only transparenta-eu
python3 scripts/profile_structure.py --out /tmp/structure --check
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit
from xml.etree.ElementTree import ParseError

from common import PUBLIC_ROOT, forbidden, load_catalogue
from structure_discovery import Transport, inferred_patterns, origin, safe_url, signals
from structure_state import (StructureError, begin, check, evidence, finding, finish, key,
                             load, locked, now, project, read, require, save)

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / 'data/taxonomy-v2/observatii/documentare'


def collection_for(p, url, eid, attempt):
    parts = urlsplit(url).path.strip('/').split('/')
    group = parts[0] if parts[0] else 'root'
    return finding(p, 'collections', group, dict(label=group, entity_type='unknown',
                   grouping_basis='URL path only; business meaning unverified', record_grain='unknown',
                   identity_components=[], coverage='unknown'), eid, attempt)


def observe(store, out, slug, url, text, content_type, observed_at, attempt, method='http', **provenance):
    p = store['projects'][slug]
    try:
        found = signals(text, content_type, url)
    except (ValueError, StructureError, ParseError, TypeError, KeyError, AttributeError) as exc:
        p['checks'].append(dict(attempt=attempt, url=url, outcome='invalid', reason=type(exc).__name__))
        return []
    # Persist a structural extract, not arbitrary page bodies or data-record values.
    excerpt = json.dumps(found, ensure_ascii=False, sort_keys=True, indent=2)
    eid = evidence(store, out, slug, url, excerpt, observed_at, method, **provenance)
    sections = ('patterns', 'operations', 'collections')
    for template in found['templates'] + [u for u in found['links'] if '{' in u]:
        col = collection_for(p, template, eid, attempt)
        parts = urlsplit(template)
        variables = [{'name': name, 'location': 'query' if '{'+name+'}' in parts.query else
                      'fragment' if '{'+name+'}' in parts.fragment else 'path', 'namespace': None}
                     for name in re.findall(r'\{([^{}]+)\}', template)]
        finding(p, 'patterns', template, dict(url_template=template, collection=col, basis='declared',
                variables=variables, examples=[], identifier_meaning='unknown'), eid, attempt)
    for template, examples in inferred_patterns(found['sitemap_urls']):
        col = collection_for(p, template, eid, attempt)
        finding(p, 'patterns', template, dict(url_template=template, collection=col, basis='inferred',
                variables=[dict(name='id', location='path', namespace=None)], examples=examples,
                identifier_meaning='unknown'), eid, attempt)
    for form in found['forms']:
        if form['method'] != 'GET' or not form['inputs']:
            continue
        try:
            action = safe_url(urljoin(url, form['action']))
        except (ValueError, StructureError):
            continue
        separator = '&' if '?' in action else '?'
        template = action + separator + '&'.join(name + '={' + name + '}' for name in form['inputs'])
        col = collection_for(p, action, eid, attempt)
        finding(p, 'patterns', template, dict(url_template=template, collection=col, basis='declared',
                variables=[dict(name=n, location='query', namespace=None) for n in form['inputs']],
                examples=[], identifier_meaning='unknown'), eid, attempt)
    for operation in found['operations']:
        col = collection_for(p, operation['url_template'], eid, attempt)
        item = dict(operation, uses=[dict(collection=col, subject_role='unknown', scope='at_least')],
                    basis=['documented'], last_test=dict(outcome='unchecked', reason='An explicit probe is required.'))
        finding(p, 'operations', operation['method']+' '+operation['url_template'], item, eid, attempt)
    if method != 'http':
        # Retained inputs are historical, not a new live confirmation.
        for section in sections:
            for item in p[section].values():
                if item['last_supported_attempt'] == attempt:
                    item['applicability'] = 'historical'
    p['checks'].append(dict(attempt=attempt, url=url, outcome='observed', reason='Structural signals extracted.', evidence=[eid]))
    return found['links'] + found['sitemap_children']


def retained(store, out, slug, attempt):
    index = DOCS / 'index.json'
    if not index.exists():
        return 0
    count = 0
    for entry in read(index).get('entries', []):
        if entry['slug'] != slug:
            continue
        for page in entry.get('pages', []):
            if not page.get('snapshot'):
                continue
            path = (DOCS / page['snapshot']).resolve()
            require(path.is_relative_to(DOCS), 'Retained snapshot leaves its directory.')
            if not path.exists():
                continue
            snapshot = read(path)
            body = snapshot.get('text', '')
            body += '\n' + '\n'.join(link[0] for link in snapshot.get('links', []) if isinstance(link, list) and link)
            observe(store, out, slug, page['url'], body, 'text/plain', page['fetched_at'], attempt, method='retained',
                    provenance=dict(index=str(index.relative_to(REPO)), snapshot=page['snapshot']))
            count += 1
    return count


def document_link(url):
    path = urlsplit(url).path.lower().rstrip('/')
    return bool(re.search(r'llms(?:-full)?\.txt$|(?:openapi|swagger)(?:\.json|\.ya?ml)?$|api-guide\.md$|/(?:api|docs|api-docs|cum-lucram|metodologie|date-deschise)$|/ai/index\.json$', path))


def run_project(store, out, slug, url, transport, budget=20, offline=False, probes=()):
    p = project(store, slug, url)
    attempt = begin(store, slug, budget, 'retained' if offline else 'mixed')
    transport.attempt = attempt
    reasons = ['Browser, repository discovery and domain search are not implemented in this engine.']
    blocked = bool(forbidden(url))
    try:
        imported = retained(store, out, slug, attempt['id'])
        if offline:
            reasons.append('Offline pass; retained observations do not establish current availability.')
            if not imported:
                reasons.append('No retained document body is available.')
            return
        directory = url if url.endswith('/') else url.rsplit('/', 1)[0] + '/'
        queue = list(dict.fromkeys([url, urljoin(directory, 'llms.txt'), urljoin(origin(url), 'llms.txt')]))
        seen, sitemap_count, sitemap_urls = set(), 0, 0
        while queue and transport.used < transport.total_budget and attempt['requests_used'] < budget:
            target = queue.pop(0)
            if target in seen:
                continue
            seen.add(target)
            response = transport.fetch(target)
            p['checks'].append(dict(attempt=attempt['id'], url=target, outcome=response['outcome'], reason=response.get('reason', '')))
            if response['outcome'] != 'observed':
                reasons.append(response.get('reason') or response['outcome'])
                if response.get('reason') == 'colectare-interzisa':
                    blocked = True
                continue
            if response.get('truncated'):
                reasons.append('Body was truncated; no complete-document inference was made.')
                continue
            source = response['url']
            links = observe(store, out, slug, source, response['body'], response['content_type'],
                            response['checked_at'], attempt['id'])
            is_sitemap = 'xml' in response['content_type'] or urlsplit(target).path.endswith('.xml')
            if is_sitemap:
                sitemap_count += 1
            if not is_sitemap:
                queue.extend(link for link in links if document_link(link) and link not in seen)
            # Robots declarations belong to this project's origin; fetch no unrelated host sitemap.
            base = origin(url)
            parser = transport.robots.get(base)
            roots = parser.site_maps() if parser and parser is not False else []
            if not roots:
                roots = [urljoin(base, 'sitemap.xml')]
            sitemap_candidates = list(roots) + [link for link in links if urlsplit(link).path.endswith('.xml')]
            for link in sitemap_candidates:
                if sitemap_count + sum(urlsplit(x).path.endswith('.xml') for x in queue) < 3 and link not in seen and link not in queue:
                    queue.append(link)
            # The document parser caps the inspected URL sample at 200 for each sitemap.
            if is_sitemap:
                sitemap_urls += 1
        if queue:
            reasons.append('Request budget ended before all queued checks.')
        for probe in probes:
            probe_api(store, out, slug, probe, transport, attempt)
    finally:
        finish(store, attempt, reasons, blocked)
        save(store, out)


def probe_api(store, out, slug, url, transport, attempt):
    url = safe_url(url)
    p = store['projects'][slug]
    matches = []
    for operation in p['operations'].values():
        template = operation['url_template']
        target, pattern = urlsplit(url), urlsplit(template)
        regex = re.sub(r'\\\{[^{}]+\\\}', '[^/]+', re.escape(pattern.path))
        if operation['method'] == 'GET' and target.netloc == pattern.netloc and target.scheme == pattern.scheme and re.fullmatch(regex, target.path):
            matches.append(operation)
    if not matches:
        p['checks'].append(dict(attempt=attempt['id'], url=url, outcome='skipped', reason='No known GET operation matches the explicit probe.'))
        return
    operation = matches[0]
    query = dict(parse_qsl(urlsplit(url).query))
    parameters = operation.get('parameters', [])
    missing = any(p.get('required') and p.get('in', p.get('location')) == 'query' and p.get('name') not in query for p in parameters)
    if (operation['security']['declared_requirement'] == 'authenticated'
            or operation.get('authentication') in {'key', 'session', 'oauth'}
            or operation.get('unresolved_parameters') or missing or '{' in url):
        p['checks'].append(dict(attempt=attempt['id'], url=url, outcome='skipped', reason='Authentication or required query arguments are unresolved.'))
        return
    response = transport.fetch(url)
    operation['last_test'] = dict(outcome=response['outcome'], reason=response.get('reason', ''), checked_at=now())
    if response['outcome'] == 'observed' and not response.get('truncated'):
        try:
            value = json.loads(response['body'])
        except ValueError:
            operation['last_test'].update(outcome='invalid', reason='Expected a JSON response, not an HTTP 200 shell.')
            return
        def shape(v, depth=0):
            if depth > 5:
                return 'depth_limit'
            if isinstance(v, dict):
                if len(v) > 1 and any(not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', k) for k in v):
                    return {'{key}': shape(next(iter(v.values())), depth+1)}
                return {k: shape(vv, depth+1) for k, vv in list(v.items())[:30]}
            if isinstance(v, list):
                return [shape(v[0], depth+1)] if v else []
            return type(v).__name__
        eid = evidence(store, out, slug, url, json.dumps(shape(value), ensure_ascii=False, indent=2), response['checked_at'], response_shape_only=True)
        operation['evidence'] = list(dict.fromkeys(operation['evidence']+[eid]))
        operation['security']['observed_enforcement'] = 'anonymous'
        operation['last_test']['evidence'] = eid


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--only', help='comma-separated catalogue slugs; no implicit whole-catalogue run')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--check', action='store_true')
    p.add_argument('--seed-pilot', type=Path)
    p.add_argument('--import-saved', nargs=3, action='append', default=[], metavar=('SLUG','URL','FILE'))
    p.add_argument('--saved-at')
    p.add_argument('--probe', nargs=2, action='append', default=[], metavar=('SLUG','URL'))
    p.add_argument('--max-requests', type=int, default=20)
    p.add_argument('--total-requests', type=int, default=100)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        out = args.out.resolve()
        for protected in [REPO/'site', REPO/'data', REPO/'docs/reports/site-structure-pilot']:
            require(not out.is_relative_to(protected), 'Choose an isolated structure output directory.')
        require(out != REPO and out != REPO/'data', 'Choose a dedicated output directory.')
        if args.check:
            require((out/'store.json').exists(), 'Structure store does not exist.')
            store = load(out)
            require((out/'requests.jsonl').read_text() == ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in store['requests']), 'Request export differs from the store.')
        else:
            require(1 <= args.max_requests <= 100 and 1 <= args.total_requests <= 100, 'Request budgets must be between 1 and 100.')
            require(not (args.offline and args.probe), 'An API probe cannot run in offline mode.')
            selected = args.only.split(',') if args.only else []
            catalogue = {e['slug']: e for e in load_catalogue(PUBLIC_ROOT)}
            require(bool(selected or args.seed_pilot or args.import_saved), 'Select explicit catalogue slugs or import evidence.')
            require(all(s in catalogue for s in selected), 'Unknown catalogue slug.')
            require(all(s in selected for s, _ in args.probe), 'Probe slugs must be selected with --only.')
            with locked(out):
                store = load(out)
                if args.seed_pilot:
                    from structure_state import seed_pilot
                    seed_pilot(store, out, args.seed_pilot)
                for slug, url, filename in args.import_saved:
                    require(slug in catalogue, 'Unknown saved-document project.')
                    url = safe_url(url)
                    from datetime import datetime, timezone
                    require(bool(args.saved_at), 'Saved imports require --saved-at with a timezone.')
                    saved = datetime.fromisoformat(args.saved_at)
                    require(saved.utcoffset() is not None and saved <= datetime.now(timezone.utc), 'Provide a past --saved-at with a timezone.')
                    path = Path(filename)
                    require(path.stat().st_size <= 2*1024*1024, 'Saved document exceeds 2 MiB.')
                    project(store, slug, catalogue[slug]['url'])
                    a = begin(store, slug, 0, 'owner_saved')
                    observe(store, out, slug, url, path.read_text(encoding='utf-8'), 'text/plain', saved.astimezone(timezone.utc).isoformat(), a['id'], method='owner_saved', saved_at=args.saved_at, imported_at=now())
                    finish(store, a, ['Saved evidence; live availability is unverified.'])
                save(store, out)
                transport = Transport(store, lambda: save(store, out), total_budget=args.total_requests)
                for slug in dict.fromkeys(selected):
                    run_project(store, out, slug, catalogue[slug]['url'], transport, args.max_requests, args.offline,
                                [url for s, url in args.probe if s == slug])
                    attempt = store['attempts'][-1]
                    print(f"{slug}: {attempt['outcome']}; {attempt['requests_used']}/{attempt['request_budget']} requests")
                save(store, out)
        print(f"Structure store: {len(store['projects'])} projects, {len(store['evidence'])} evidence records; {out}")
        return 0
    except (StructureError, OSError, ValueError, KeyError) as exc:
        print(f'Structure profiler: {exc}', file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
