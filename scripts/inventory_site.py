"""Build a compact, lazy-loaded explorer preview from draft inventory metadata."""
import html
import json
import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from collect_docs import is_saved
from common import observation_paths
from inventory_concepts import active_groups, as_list, group_state, selector_matches


BASIS = {'declarat-in-schema': 'schema', 'declarat-in-metadate': 'metadata',
         'observat-in-esantion-json': 'sample', 'neprecizat-in-antet-csv': 'header',
         'declarat-in-cod-sursa': 'code', 'antet-tabel-html': 'table', 'declarat-in-tabel-documentatie': 'doctable',
         'declarat-in-text-documentatie': 'doctext', 'utilizat-in-cod-pagina': 'pagecode', 'exemplu-in-documentatie': 'docexample',
         'declarat-in-documentatie-api': 'apidoc', 'declarat-in-lista-documentatie': 'doclist'}
FORMATS = {'openapi': 'Schemă API', 'json-schema': 'Schemă JSON', 'metadate-ins': 'Metadate de set',
           'json': 'Fișier JSON', 'csv': 'Fișier CSV', 'lista-ins': 'Listă de seturi INS',
           'html-tabele': 'Pagină cu tabele', 'markdown': 'Document Markdown', 'csharp': 'Cod C#', 'sql': 'Cod SQL', 'php': 'Cod PHP',
           'json-comentat': 'Exemple JSON în document', 'js-acces': 'Script de pagină',
           'html-api-docs': 'Documentația API (pagină)', 'html-carduri-csv': 'Pagină cu fișiere CSV descrise'}
SOURCE_LABELS = {
    'Institutul Național de Statistică (INS)': 'INS', 'Ministerul Dezvoltării (MDLPA)': 'MDLPA',
    'Administrația Prezidențială': 'Adm. Prez', 'Monitorul Oficial': 'MO',
    'Camera Deputaților': 'Parlament', 'Senatul României': 'Parlament',
    'Guvernul României': 'Guvern', 'Consiliul Uniunii Europene': 'Consiliul UE',
}


def variable_matches(slug, fields, sources, concepts):
    """Match a project's fields to the proposed groups. A field joins a group through a selector of that project; every constraint that
    the selector supplies (names, source, path, role) must match. Generic names such as `id` never create a match by themselves.
    A rejected group (`stare` = respins) produces no match, and an excluded selector (`stare` = exclus) matches no field."""
    matches = []
    source_map = {s['id']: s for s in sources}
    for concept in active_groups(concepts):
        selectors = [r for r in concept['selectors'] if slug in as_list(r['projects'])]
        evidence = []
        for f in fields:
            url = source_map[f['source']]['url']
            selector = next((r for r in selectors if selector_matches(r, slug, f, url)), None)
            if not selector:
                continue
            item = dict(name=f['name'], path=f['path'], role=f['role'], basis=f['basis'],
                        declaredType=f['declaredType'], observedTypes=f['observedTypes'], unit=f['unit'],
                        description=f['description'], url=url, reference=f['reference'], location=f.get('location'))
            if selector.get('context'):
                item['context'] = selector['context']
            if selector.get('fapte'):
                item['facts'] = [{'key': x['cheie'], 'value': x['valoare'], 'basis': x['baza']} for x in selector['fapte']]
            evidence.append(item)
        if evidence:
            # Show examples from different sources first; the count keeps every matching field.
            seen, first, rest = set(), [], []
            for item in evidence:
                (rest if item['url'] in seen else first).append(item)
                seen.add(item['url'])
            matches.append({'id': concept['id'], 'count': len(evidence), 'evidence': (first + rest)[:3]})
    return matches


def publish_finder(items, root, site, projections, vocabulary=None):
    """Write a cross-project discovery index and its isolated page."""
    concept_path = root.parent / 'inventar-concepte.json'
    document = json.loads(concept_path.read_text()) if concept_path.exists() else {}
    concepts, families = document.get('concepte', []), document.get('familii', [])
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
             'families': [{'id': f['id'], 'label': f['label']} for f in families],
             'variables': [{**{k: c[k] for k in ('id', 'label', 'definition')}, 'category': c.get('categorie'), 'family': c.get('familie'),
                            'state': group_state(c),
                            'basis': c.get('baza_definitiei'), 'ambiguities': c.get('ambiguitati', []),
                            'proofs': [{'url': e['sursa'], 'fragment': e['fragment'][:200], 'basis': e['baza']} for e in c.get('dovezi', [])]}
                           for c in active_groups(concepts)],
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
    publish_overview(items, site, projections, concepts, families)


def field_groups(slug, fields, sources, concepts):
    """{field position: group id} for one project, with the same selector rules as `variable_matches`; the first group that matches wins."""
    urls = {s['id']: s['url'] for s in sources}
    found = {}
    for concept in active_groups(concepts):
        selectors = [r for r in concept['selectors'] if slug in as_list(r['projects'])]
        for n, f in enumerate(fields):
            if n not in found and any(selector_matches(r, slug, f, urls[f['source']]) for r in selectors):
                found[n] = concept['id']
    return found


def publish_overview(items, site, projections, concepts, families):
    """Write `date/lista/`: a table with one row per project or resource that has extracted fields, one column per family of variables,
    and a last column for the fields in no group. A cell lists the group labels (the normalised names), not the source field names;
    those belong to the project's own page. Entries without fields are named once below the table. A static page: it needs no script."""
    e = html.escape
    labels = {c['id']: c['label'] for c in concepts}
    family_of = {c['id']: c.get('familie') for c in concepts}
    columns = [(f['id'], f['label']) for f in families]
    if any(not family_of.get(c['id']) or family_of[c['id']] not in dict(columns) for c in active_groups(concepts)):
        columns.append((None, 'Fără familie'))
    rows, bare = [], []
    totals = {fam: 0 for fam, _ in columns}
    entries = sorted((i for i in items if i.get('kind') in ('proiect', 'resursa')), key=lambda i: i['name'].casefold())
    for item in entries:
        fields, sources = projections.get(item['slug'], ([], []))
        link = f'<a href="{e(item["kind"])}/{e(item["slug"])}/">{e(item["name"])}</a>'
        if not fields:
            bare.append(link)
            continue
        grouped = field_groups(item['slug'], fields, sources, concepts)
        known = dict(columns)
        cells = {}
        for gid in dict.fromkeys(grouped.values()):
            fam = family_of.get(gid) if family_of.get(gid) in known else None
            cells.setdefault(fam, []).append(labels[gid])
        other = len({f['name'] for n, f in enumerate(fields) if n not in grouped})
        tds = []
        for fam, _ in columns:
            names = sorted(cells.get(fam, []), key=str.casefold)
            totals[fam] += bool(names)
            tds.append(f'<td>{"<ul>" + "".join(f"<li>{e(x)}</li>" for x in names) + "</ul>" if names else ""}</td>')
        kind = 'proiect' if item['kind'] == 'proiect' else 'resursă'
        rows.append(f'<tr id="{e(item["slug"])}"><th scope="row">{link}<small>{kind} · {len(sources)} {"sursă" if len(sources) == 1 else "surse"}</small></th>'
                    f'{"".join(tds)}<td class="ov-other">{other or ""}</td></tr>')
    head = ''.join(f'<th scope="col">{e(label)}<small>{totals[fam]}</small></th>' for fam, label in columns)
    proposed = sum(group_state(c) == 'propus' for c in active_groups(concepts))
    groups = 'grupurile revizuite' if not proposed else f'grupuri; {proposed} încă propuse'
    content = (f'<p class="ov-note">{len(rows)} proiecte și resurse cu câmpuri extrase, din {len(entries)}. O celulă numește variabilele normalizate '
               f'({groups}); numărul de sub fiecare coloană spune câte intrări au cel puțin una. „Altele” numără câmpurile care nu sunt în niciun grup. '
               f'Același nume nu înseamnă că datele se pot combina.</p>'
               f'<div class="ov-scroll"><table class="ov-table"><thead><tr><th scope="col">Proiect<small>{len(rows)}</small></th>{head}'
               f'<th scope="col">Altele<small>câmpuri</small></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
               f'<section class="ov-bare"><h2>Fără câmpuri extrase ({len(bare)})</h2><p>{", ".join(bare)}</p>'
               f'<p class="ov-note">Lipsa câmpurilor nu înseamnă lipsa datelor: inventarul acestor intrări nu a fost făcut.</p></section>')
    doc = (Path(__file__).parent / 'templates/inventory-list.html').read_text().replace('<!--LISTA-->', content)
    for asset in ('style.css', 'inventory.css'):
        digest = hashlib.sha1((site / asset).read_bytes()).hexdigest()[:10]
        doc = doc.replace(f'{asset}?v=BUILD', f'{asset}?v={digest}')
    page = site / 'date' / 'lista'
    page.mkdir(parents=True, exist_ok=True)
    (page / 'index.html').write_text(doc)


def dataset_summary(facts):
    """The few dataset facts that the field browser shows. Values keep the label of their basis: declared, API-computed or counted."""
    def value(key):
        fact = facts.get(key)
        return fact.get('valoare') if isinstance(fact, dict) else None
    period = facts.get('perioada') or {}
    names = facts.get('denumire') or {}
    return {'code': value('cod'), 'name': (names.get('ro') or names.get('en') or {}).get('valoare'), 'updated': value('actualizat'),
            'period': [(period.get('an_min') or {}).get('valoare'), (period.get('an_max') or {}).get('valoare')] if period else None,
            'levels': value('niveluri_geografice'), 'units': [u['cod'] for u in facts.get('unitati', []) if u.get('cod')],
            'dimensions': [d['nume'] for d in facts.get('dimensiuni', [])], 'licence': facts.get('licenta')}


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
            grouped[key].pop('also', None)
            out.append(grouped[key])
        target = grouped[key]
        target['contexts'].append({'path': field['path'], 'reference': field['reference'], 'operations': field['operations']})
        target['operations'] = list(dict.fromkeys([*target['operations'], *field['operations']]))
        if field.get('also'):
            target.setdefault('also', []).extend(field['also'])
    return out


def fold_restatements(fields, sources, listed):
    """A field that restates a record of another listed source (`restates`: an API reference page repeating its OpenAPI contract)
    becomes evidence on that record (`also`) instead of a second field. Without the restated record in the projection, it stays a field."""
    by_pointer = {(f['source'], f['reference']): f for f in fields if not f.get('restates')}
    urls = {s['id']: s['url'] for s in listed}
    titles = {s['id']: s['title'] for s in listed}
    kept = []
    for field in fields:
        link = field.pop('restates', None)
        target = link and by_pointer.get((link.get('sursa_id'), link.get('pointer')))
        if not target:
            kept.append(field)
            continue
        target.setdefault('also', []).append({'url': urls.get(field['source'], ''), 'title': titles.get(field['source'], ''), 'reference': field['reference'],
                                              'description': field['description']})
    return kept


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
            if source.get('set_date'):
                listed['dataset'] = dataset_summary(source['set_date'])
            if is_saved(source):
                # A copy that the owner saved is shown as such; its date is the day of the saving, not of a request.
                listed['savedByOwner'] = True
            if source.get('partial'):
                listed['partial'] = True
            if source.get('via') == 'browser':
                listed['viaBrowser'] = True
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
                record = {'name': field['nume'], 'path': field['cale'], 'description': field.get('descriere') or '',
                          'declaredType': field.get('tip_declarat'), 'observedTypes': field.get('tipuri_observate', []),
                          'semanticType': field.get('tip_semantic'), 'unit': field.get('unitate'), 'format': field.get('format'),
                          'role': field.get('rol', 'camp-date'), 'basis': basis, 'source': ident, 'location': field.get('loc'),
                          'reference': field.get('pointer', ''), 'restates': field.get('in_contract'),
                          'operations': list(dict.fromkeys(a['operatie'] for a in field.get('aparitii', []) if a.get('operatie')))}
                # Declared extras that the field browser shows when present. Empty values stay out of the payload.
                for key, name in (('valori_enum', 'enum'), ('formula_declarata', 'formula'), ('grup', 'group'), ('perioada_declarata', 'period'),
                                  ('valoare', 'value'), ('linie', 'line'), ('expresie', 'expression'), ('obligatoriu', 'required')):
                    if field.get(key) not in (None, '', []):
                        record[name] = field[key]
                fields.append(record)
        fields = fold_restatements(fields, sources, source_list)
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
