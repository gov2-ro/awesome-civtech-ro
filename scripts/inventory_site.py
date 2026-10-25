"""Build a compact, lazy-loaded explorer preview from draft inventory metadata."""
import json
import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from common import observation_paths


BASIS = {'declarat-in-schema': 'schema', 'declarat-in-metadate': 'metadata',
         'observat-in-esantion-json': 'sample', 'neprecizat-in-antet-csv': 'header'}
FORMATS = {'openapi': 'Schemă API', 'json-schema': 'Schemă JSON', 'metadate-ins': 'Metadate de set',
           'json': 'Fișier JSON', 'csv': 'Fișier CSV'}
SOURCE_LABELS = {
    'Institutul Național de Statistică (INS)': 'INS', 'Ministerul Dezvoltării (MDLPA)': 'MDLPA',
    'Administrația Prezidențială': 'Adm. Prez', 'Monitorul Oficial': 'MO',
    'Camera Deputaților': 'Parlament', 'Senatul României': 'Parlament',
    'Guvernul României': 'Guvern', 'Consiliul Uniunii Europene': 'Consiliul UE',
}


def variable_matches(slug, fields, sources, concepts):
    """Use explicit project/name selectors. Never equate arbitrary field names."""
    matches = []
    source_map = {s['id']: s for s in sources}
    for concept in concepts:
        names = {name for rule in concept['selectors'] if slug in rule['projects'] for name in rule['names']}
        evidence = [dict(name=f['name'], path=f['path'], role=f['role'], basis=f['basis'],
                         declaredType=f['declaredType'], observedTypes=f['observedTypes'], unit=f['unit'],
                         description=f['description'], url=source_map[f['source']]['url'],
                         reference=f['reference'], location=f.get('location'))
                    for f in fields if f['name'] in names]
        if evidence:
            matches.append({'id': concept['id'], 'count': len(evidence), 'evidence': evidence[:3]})
    return matches


def publish_finder(items, root, site, projections, vocabulary=None):
    """Write a cross-project discovery index and its isolated page."""
    concept_path = root.parent / 'inventar-concepte.json'
    concepts = json.loads(concept_path.read_text())['concepte'] if concept_path.exists() else []
    entries = []
    for item in items:
        if item.get('kind') not in ('proiect', 'resursa'):
            continue
        fields, sources = projections.get(item['slug'], ([], []))
        providers = {}
        for provider in item.get('dataSources', []):
            url = http_url(provider.get('evidence'))
            if not url:
                continue
            label = SOURCE_LABELS.get(provider['name'], provider['name'])
            providers.setdefault(label, []).append({'name': provider['name'], 'url': url})
        entries.append({'slug': item['slug'], 'name': item['name'], 'kind': item['kind'],
                        'description': item.get('desc') or item.get('tagline', ''),
                        'href': f"{item['kind']}/{item['slug']}/", 'url': http_url(item.get('url')), 'status': item.get('status'),
                        'subjects': list(dict.fromkeys(item.get('subjects', []) + item.get('topics', []))),
                        'institutions': item.get('institutions', []), 'providers': providers,
                        'variables': variable_matches(item['slug'], fields, sources, concepts),
                        'inventory': {k: v for k, v in item.get('inventory', {}).items() if k != 'keywords'},
                        'keywords': item.get('inventory', {}).get('keywords', '')})
    index = {'partial': True, 'concepts': [{'id': c['id'], 'scheme': c['scheme'], 'label': c['label']}
                                         for c in (vocabulary or {}).get('concepts', []) if c['scheme'] in ('subiect', 'institutie')],
             'variables': [{k: c[k] for k in ('id', 'label', 'definition')} for c in concepts],
             'entries': entries}
    (site / 'inventar/index.json').write_text(json.dumps(index, ensure_ascii=False, separators=(',', ':')))
    template = Path(__file__).parent / 'templates/inventory.html'
    doc = template.read_text()
    for asset in ('style.css', 'inventory.css', 'inventory.js'):
        digest = hashlib.sha1((site / asset).read_bytes()).hexdigest()[:10]
        doc = doc.replace(f'{asset}?v=BUILD', f'{asset}?v={digest}')
    page = site / 'date'
    page.mkdir(exist_ok=True)
    (page / 'index.html').write_text(doc)


def http_url(value):
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ('https', 'http') and parsed.hostname else ''
    except (ValueError, TypeError):
        return ''


def document_links(record):
    found = {}
    for page in record.get('pages', []):
        if page.get('state') != 'colectat' or page.get('scope') != 'proiect':
            continue
        kind = page.get('kind')
        if kind in ('llms', 'metodologie', 'despre', 'pagina-date'):
            url = http_url(page.get('final_url', ''))
            if url:
                title = {'llms': 'llms.txt', 'metodologie': 'Metodologie', 'despre': 'Despre proiect', 'pagina-date': 'Date pe site'}[kind]
                found[url] = {'url': url, 'label': title, 'title': page.get('title') or title}
        for section in page.get('sections', []):
            url = http_url(section.get('url') or page.get('final_url', ''))
            if url and section.get('kind') in ('metodologie', 'despre'):
                found.setdefault(url, {'url': url, 'label': section.get('heading', 'Documentație'), 'title': section.get('heading', '')})
    links = list(found.values())[:8]
    labels = [d['label'] for d in links]
    for link in links:
        if labels.count(link['label']) > 1 and link.get('title'):
            link['label'] = link['title']
    return links


def rank_field(field):
    name = field['name'].casefold()
    interesting = bool(re.search(r'cui|cpv|localitat|judet|valoare|buget|denumire|ref_area|time_period|unit_measure|obs_value', name))
    generic = name in {'q', 'limit', 'offset', 'page', 'sort', 'lang', 'format', 'token', 'api_key'}
    return (generic, not interesting, not bool(field['description']), field['path'].count('.'), name)


def group_api_parameters(fields):
    """Collapse repeated parameter declarations for display; preserve their operation contexts."""
    grouped, out = {}, []
    for field in fields:
        if field['role'] != 'parametru-api':
            out.append(field)
            continue
        key = (field['source'], field['name'], json.dumps(field['declaredType']), field['description'],
               field['unit'], field['format'], field.get('location'))
        if key not in grouped:
            grouped[key] = {**field, 'contexts': []}
            out.append(grouped[key])
        target = grouped[key]
        target['contexts'].append({'path': field['path'], 'reference': field['reference'], 'operations': field['operations']})
        target['operations'] = list(dict.fromkeys([*target['operations'], *field['operations']]))
    return out


def publish_preview(items, root, site):
    observations = observation_paths(root)['profile'].parent
    folder = observations / 'inventare'
    profiles_path, sources_path = folder / 'proiecte.json', folder / 'seturi-date.json'
    if not profiles_path.exists() or not sources_path.exists():
        raise ValueError('Inventory preview needs generated proiecte.json and seturi-date.json; run scripts/inventory.py first.')
    profiles = {p['slug']: p for p in json.loads(profiles_path.read_text())['proiecte']}
    sources = {s['id']: s for s in json.loads(sources_path.read_text())['surse']}
    docs_path = observations / 'documentare/index.json'
    docs = {p['slug']: p for p in json.loads(docs_path.read_text())['entries']} if docs_path.exists() else {}
    target = site / 'inventar'
    target.mkdir(exist_ok=True)
    written, projections = set(), {}
    for item in items:
        slug = item['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            raise ValueError('Invalid inventory slug: ' + slug)
        profile = profiles.get(slug, {})
        links = document_links(docs.get(slug, {}))
        fields, source_list = [], []
        for ident in profile.get('surse_structurate', []):
            source = sources.get(ident, {})
            url = http_url(source.get('url', ''))
            if not url or not source.get('campuri'):
                continue
            fmt = source.get('format', '')
            filename = unquote(Path(urlsplit(url).path).name)
            title = FORMATS.get(fmt, 'Sursă de date') + (' · ' + filename if filename else '')
            listed = {'id': ident, 'url': url, 'title': title, 'format': fmt, 'checked': str(source.get('fetched_at', ''))[:10]}
            attempt = source.get('ultima_incercare')
            if attempt:
                # The retained evidence is older than the last attempt. Say so; never present it as freshly verified.
                listed['refreshFailed'] = {'date': str(attempt.get('la', ''))[:10], 'status': attempt.get('http_status'),
                                           'state': attempt.get('stare')}
            source_list.append(listed)
            for field in source['campuri']:
                basis = BASIS.get(field.get('stare_tip'))
                if not basis:
                    continue
                fields.append({'name': field['nume'], 'path': field['cale'], 'description': field.get('descriere') or '',
                               'declaredType': field.get('tip_declarat'), 'observedTypes': field.get('tipuri_observate', []),
                               'semanticType': field.get('tip_semantic'), 'unit': field.get('unitate'), 'format': field.get('format'),
                               'role': field.get('rol', 'camp-date'), 'basis': basis, 'source': ident, 'location': field.get('loc'),
                               'reference': field.get('pointer', ''),
                               'operations': list(dict.fromkeys(a['operatie'] for a in field.get('aparitii', []) if a.get('operatie')))})
        positions = len(fields)
        fields = group_api_parameters(fields)
        fields.sort(key=rank_field)
        projections[slug] = (fields, source_list)
        if not fields and not links:
            continue
        words = list(dict.fromkeys([f['name'] for f in fields] + [f['name'].replace('_', ' ') for f in fields]
                                  + [f['description'] for f in fields if f['description']]))
        examples = list(dict.fromkeys(f['name'] for f in fields if f['name'].casefold() not in {'q', 'limit', 'offset', 'page', 'lang', 'format'}))[:5]
        item['inventory'] = {'count': len(fields), 'sources': len(source_list), 'examples': examples,
                             'keywords': ' '.join(words)[:16000], 'docs': links, 'partial': True, 'positions': positions}
        if any(s.get('refreshFailed') for s in source_list):
            item['inventory']['stale'] = sum(bool(s.get('refreshFailed')) for s in source_list)
        if fields:
            filename = slug + '.json'
            payload = {'slug': slug, 'partial': True, 'sources': source_list, 'fields': fields}
            (target / filename).write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
            written.add(filename)
            item['inventory']['url'] = 'inventar/' + filename
    for stale in target.glob('*.json'):
        if stale.name not in written:
            stale.unlink()
    return projections
