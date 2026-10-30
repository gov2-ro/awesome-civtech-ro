"""Build a compact, lazy-loaded explorer inventory from draft inventory metadata."""
import html
import json
import hashlib
import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from collect_docs import is_saved
from common import inventory_exclusion, observation_paths, public_reason
from inventory_concepts import PUBLIC_BASIS_LABELS, active_groups, as_list, group_state, selector_matches
from inventory_persons import is_marked


BASIS = {'declarat-in-schema': 'schema', 'declarat-in-metadate': 'metadata',
         'observat-in-esantion-json': 'sample', 'neprecizat-in-antet-csv': 'header',
         'declarat-in-cod-sursa': 'code', 'antet-tabel-html': 'table', 'declarat-in-tabel-documentatie': 'doctable',
         'declarat-in-text-documentatie': 'doctext', 'utilizat-in-cod-pagina': 'pagecode', 'exemplu-in-documentatie': 'docexample',
         'declarat-in-documentatie-api': 'apidoc', 'declarat-in-lista-documentatie': 'doclist', 'declarat-in-lista-baza': 'dblist',
         'adaugat-de-editor': 'editor'}
FORMATS = {'openapi': 'Schemă API', 'json-schema': 'Schemă JSON', 'metadate-ins': 'Metadate de set',
           'json': 'Fișier JSON', 'csv': 'Fișier CSV', 'lista-ins': 'Listă de seturi INS',
           'html-tabele': 'Pagină cu tabele', 'markdown': 'Document Markdown', 'csharp': 'Cod C#', 'sql': 'Cod SQL', 'php': 'Cod PHP',
           'json-comentat': 'Exemple JSON în document', 'js-acces': 'Script de pagină',
           'html-api-docs': 'Documentația API (pagină)', 'html-carduri-csv': 'Pagină cu fișiere CSV descrise',
           'js-literale': 'Date din scriptul paginii', 'html-lista-seturi': 'Pagină cu lista seturilor de date', 'baza-datasette': 'Bază de date Datasette',
           'json-esantion': 'Fișier JSON citit parțial', 'html-glosar': 'Pagină cu glosarul câmpurilor', 'html-tabele-eurostat': 'Tabele Eurostat lipite în pagină',
           'js-pozitii': 'Pozițiile citite de scriptul paginii', 'typescript': 'Tipuri TypeScript'}
SOURCE_LABELS = {
    'Institutul Național de Statistică (INS)': 'INS', 'Ministerul Dezvoltării (MDLPA)': 'MDLPA',
    'Administrația Prezidențială': 'Adm. Prez', 'Monitorul Oficial': 'MO',
    'Camera Deputaților': 'Parlament', 'Senatul României': 'Parlament',
    'Guvernul României': 'Guvern', 'Consiliul Uniunii Europene': 'Consiliul UE',
}


# What the finder leaves out of the variable inventory, by the two reasons that the public pages name, in the order of the note on `/date/lista/`.
# `fara-date` is the group `fara-date` of `common.DATA_GROUPS` (the code `fara-date` and an empty value together); `inactiv` counts every inactive
# project or resource, and `fara-date` counts the active ones. The explorer shows the same sets with `dat=fara-date` and `st=inactiv`.
LEFT_OUT = ('fara-date', 'inactiv')
PAGE_DIR = 'date'  # the folder of the finder; the variables page of an entry is `date/<slug>/`


def scope_reason(item):
    """Why a built item is out of the public inventory, or an empty string when it is in scope (`common.inventory_exclusion`).
    `publish_finder` and `publish_overview` use this one function, so the finder and the list always name the same entries.
    The explorer is not limited by the scope: `publish_preview` gives every entry its „Date & metodă” panel (documentation links,
    sources and fields) when it has one, organisations and entries without data included (owner, 2026-10-27)."""
    return inventory_exclusion(item.get('kind', ''), item.get('status', ''), item.get('dataRelation', ''))


def left_out(items):
    """{reason: {kind: count}} for the projects and resources that the public inventory leaves out, by the two public reasons (`LEFT_OUT`).
    An organisation is not counted: the inventory never lists one."""
    counts = {reason: {'proiect': 0, 'resursa': 0} for reason in LEFT_OUT}
    for item in items:
        reason = public_reason(scope_reason(item))
        if reason in counts:
            counts[reason][item['kind']] += 1
    return counts


def group_hits(slug, fields, sources, concepts):
    """The one matching rule of the groups: [(concept, [(position, selector)])] for the groups that reach at least one field of the project, in the
    order of the dictionary. A field joins a group through a selector of that project; every constraint that the selector supplies (names,
    source, path, role) must match. Generic names such as `id` never create a match by themselves. A rejected group (`stare` = respins) produces
    no match, and an excluded selector (`stare` = exclus) matches no field. `variable_matches`, `field_groups` and the page of a project use this function."""
    urls = {s['id']: s['url'] for s in sources}
    hits = []
    for concept in active_groups(concepts):
        selectors = [r for r in concept['selectors'] if slug in as_list(r['projects'])]
        found = []
        for n, f in enumerate(fields):
            selector = next((r for r in selectors if selector_matches(r, slug, f, urls[f['source']])), None)
            if selector:
                found.append((n, selector))
        if found:
            hits.append((concept, found))
    return hits


def variable_matches(slug, fields, sources, concepts):
    """Match a project's fields to the proposed groups (`group_hits`) and keep a few of them as the evidence of each group."""
    matches = []
    urls = {s['id']: s['url'] for s in sources}
    for concept, found in group_hits(slug, fields, sources, concepts):
        evidence = []
        for n, selector in found:
            f = fields[n]
            item = dict(name=f['name'], path=f['path'], role=f['role'], basis=f['basis'],
                        declaredType=f['declaredType'], observedTypes=f['observedTypes'], unit=f['unit'],
                        description=f['description'], url=urls[f['source']], reference=f['reference'], location=f.get('location'))
            if selector.get('context'):
                item['context'] = selector['context']
            if selector.get('fapte'):
                item['facts'] = [{'key': x['cheie'], 'value': x['valoare'], 'basis': x['baza']} for x in selector['fapte']]
            evidence.append(item)
        # Show examples from different sources first; the count keeps every matching field.
        seen, first, rest = set(), [], []
        for item in evidence:
            (rest if item['url'] in seen else first).append(item)
            seen.add(item['url'])
        matches.append({'id': concept['id'], 'count': len(evidence), 'evidence': (first + rest)[:3]})
    return matches


def publish_finder(items, root, site, projections, vocabulary=None, entity_lookup=False):
    """Write the discovery index, finder, project list and each entry's variable page."""
    concept_path = root.parent / 'inventar-concepte.json'
    document = json.loads(concept_path.read_text()) if concept_path.exists() else {}
    concepts, families = document.get('concepte', []), document.get('familii', [])
    for item in items:
        if has_page(item, projections):
            # The explorer links the page from the „Date & metodă” panel, so the key goes into data.json (build.py writes it after this call).
            item.setdefault('inventory', {})['page'] = f'{PAGE_DIR}/{item["slug"]}/'
    entries = []
    for item in items:
        if scope_reason(item):
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
    index = {'partial': True, 'factBasis': PUBLIC_BASIS_LABELS, 'concepts': [{'id': c['id'], 'scheme': c['scheme'], 'label': c['label']}
                                         for c in (vocabulary or {}).get('concepts', []) if c['scheme'] in ('subiect', 'institutie')],
             'families': [{'id': f['id'], 'label': f['label']} for f in families],
             'variables': [{**{k: c[k] for k in ('id', 'label', 'definition')}, 'category': c.get('categorie'), 'family': c.get('familie'),
                            'state': group_state(c),
                            'basis': c.get('baza_definitiei'), 'ambiguities': c.get('ambiguitati', []),
                            'proofs': [{'url': e['sursa'], 'fragment': e['fragment'][:200], 'basis': e['baza']} for e in c.get('dovezi', [])]}
                           for c in active_groups(concepts)],
             'leftOut': left_out(items),
             'entries': entries}
    (site / 'inventar/index.json').write_text(json.dumps(index, ensure_ascii=False, separators=(',', ':')))
    template = Path(__file__).parent / 'templates/inventory.html'
    doc = template.read_text()
    doc = doc.replace('<!--ENTITY_LOOKUP-->',
        '<a class="finder-back" href="entitati/" data-entity-lookup>Entități între proiecte →</a>' if entity_lookup else '')
    for asset in ('style.css', 'inventory.css', 'inventory.js'):
        digest = hashlib.sha1((site / asset).read_bytes()).hexdigest()[:10]
        doc = doc.replace(f'{asset}?v=BUILD', f'{asset}?v={digest}')
    page = site / 'date'
    page.mkdir(exist_ok=True)
    (page / 'index.html').write_text(doc)
    publish_overview(items, site, projections, concepts, families)
    publish_variable_pages(items, site, projections, concepts, families, vocabulary)


def field_groups(slug, fields, sources, concepts):
    """{field position: group id} for one project, with the same selector rules as `variable_matches`; the first group that matches wins."""
    found = {}
    for concept, hits in group_hits(slug, fields, sources, concepts):
        for n, _ in hits:
            found.setdefault(n, concept['id'])
    return found


def family_columns(concepts, families):
    """The families of the page `/date/lista/`, in its order: [(id, label)], then (None, 'Fără familie') when a group has no known family.
    The page of a project (`/date/<slug>/`) lists its families in the same order."""
    columns = [(f['id'], f['label']) for f in families]
    if any(not c.get('familie') or c['familie'] not in dict(columns) for c in active_groups(concepts)):
        columns.append((None, 'Fără familie'))
    return columns


def ro_count(n, one, many):
    """`1 proiect`, `5 proiecte`, `20 de proiecte`: the Romanian count phrase, as `plural` in site/app.js."""
    return f'1 {one}' if n == 1 else f'{n}{" de" if n % 100 >= 20 or n % 100 == 0 else ""} {many}'


LEFT_OUT_TEXT = {'fara-date': ('Fără date', 'intrări fără un set de date de extras: ghid, curs, campanie, articol sau listă de linkuri', 'dat=fara-date'),
                 'inactiv': ('Inactive', 'proiecte și resurse arhivate sau offline', 'st=inactiv')}


def left_out_section(counts):
    """The note of `/date/lista/` about the entries that the inventory leaves out: a count and an explorer link for each reason and kind.
    `fara-date` counts active entries only, so a link shows the same number that the note gives (the explorer hides inactive entries)."""
    total = sum(n for reason in counts.values() for n in reason.values())
    if not total:
        return ''
    items = []
    for reason in LEFT_OUT:
        n = sum(counts[reason].values())
        if not n:
            continue
        title, meaning, query = LEFT_OUT_TEXT[reason]
        links = ' · '.join(f'<a href="./?{"k=resursa&amp;" if kind == "resursa" else ""}{query}">{ro_count(counts[reason][kind], one, many)}</a>'
                           for kind, one, many in (('proiect', 'proiect', 'proiecte'), ('resursa', 'resursă', 'resurse')) if counts[reason][kind])
        items.append(f'<li data-reason="{reason}"><strong>{title}</strong> ({n}): {meaning}. În explorator: {links}.</li>')
    return (f'<section class="ov-left"><h2>Lăsate pe dinafară ({total})</h2>'
            f'<p class="ov-note">Inventarul listează numai proiectele și resursele active care au date, calcule sau formulare. '
            f'Intrările de mai jos lipsesc din tabel și din căutarea în date. „Fără date” numără numai intrările active; '
            f'cele inactive sunt la „Inactive”.</p><ul>{"".join(items)}</ul></section>')


def publish_overview(items, site, projections, concepts, families):
    """Write `date/lista/`: a table with one row per project or resource that has extracted fields, one column per family of variables,
    and a last column for the fields in no group. A cell lists the group labels (the normalised names), not the source field names;
    those belong to the project's own page (`/date/<slug>/`, linked from each row). Entries without fields are named once below the table. The entries that the inventory leaves out
    are counted by reason below that, with links to the explorer that show them. A static page: it needs no script."""
    e = html.escape
    labels = {c['id']: c['label'] for c in concepts}
    family_of = {c['id']: c.get('familie') for c in concepts}
    columns = family_columns(concepts, families)
    rows, bare = [], []
    totals = {fam: 0 for fam, _ in columns}
    entries = sorted((i for i in items if not scope_reason(i)), key=lambda i: i['name'].casefold())
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
        all_link = f'<a href="{PAGE_DIR}/{e(item["slug"])}/">Toate variabilele</a>'
        rows.append(f'<tr id="{e(item["slug"])}"><th scope="row">{link}<small>{kind} · {len(sources)} {"sursă" if len(sources) == 1 else "surse"} · {all_link}</small></th>'
                    f'{"".join(tds)}<td class="ov-other">{other or ""}</td></tr>')
    head = ''.join(f'<th scope="col">{e(label)}<small>{totals[fam]}</small></th>' for fam, label in columns)
    proposed = sum(group_state(c) == 'propus' for c in active_groups(concepts))
    groups = 'grupurile revizuite' if not proposed else f'grupuri; {proposed} încă propuse'
    content = (f'<p class="ov-note">{len(rows)} proiecte și resurse cu câmpuri extrase, din {len(entries)}. O celulă numește variabilele normalizate '
               f'({groups}); numărul de sub fiecare coloană spune câte intrări au cel puțin una. „Altele” numără câmpurile care nu sunt în niciun grup. '
               f'Același nume nu înseamnă că datele se pot combina.</p>'
               f'<div class="ov-scroll"><table class="ov-table"><thead><tr><th scope="col">Proiect<small>{len(rows)}</small></th>{head}'
               f'<th scope="col">Altele<small>câmpuri</small></th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
               f'<section class="ov-bare"><h2>De analizat ({len(bare)})</h2><p>{", ".join(bare)}</p>'
               f'<p class="ov-note">Lipsa câmpurilor nu înseamnă lipsa datelor: inventarul acestor intrări nu a fost făcut.</p></section>'
               f'{left_out_section(left_out(items))}')
    doc = (Path(__file__).parent / 'templates/inventory-list.html').read_text().replace('<!--LISTA-->', content)
    for asset in ('style.css', 'inventory.css'):
        digest = hashlib.sha1((site / asset).read_bytes()).hexdigest()[:10]
        doc = doc.replace(f'{asset}?v=BUILD', f'{asset}?v={digest}')
    page = site / 'date' / 'lista'
    page.mkdir(parents=True, exist_ok=True)
    (page / 'index.html').write_text(doc)


# --- the variables page of one entry: `/date/<slug>/` -------------------------------------------------------------------------------------
# A static page (no script) for every entry in the scope of the inventory that has field records. It lists the source field names of the entry by family of
# variables and by source, with the facts that the field browser shows (names, paths, types, units, descriptions, groups) and no value of a data body.

# The labels of the field browser: `INV_TYPES`, `INV_ROLES` and `INV_BASIS` in site/app.js, and `stateLabels` in site/inventory.js. A test keeps the copies equal.
TYPE_LABELS = {'string': 'Text', 'integer': 'Număr întreg', 'number': 'Număr', 'boolean': 'Da / Nu', 'null': 'Valoare nulă', 'text': 'Text în tabel',
               'forma-numerica': 'Arată ca număr (text)', 'forma-de-data': 'Arată ca dată (text)', 'object': 'Obiect', 'array': 'Listă',
               'geo': 'Arie geografică', 'time': 'Perioadă', 'indicator': 'Indicator', 'unit': 'Unitate de măsură'}
ROLE_LABELS = {'camp-date': 'Date', 'dimensiune': 'Dimensiuni', 'parametru-api': 'Intrări API', 'corp-cerere': 'Conținut cerere API',
               'camp-raspuns': 'Răspunsuri API', 'model-de-date': 'Modele de date', 'camp-dictionar': 'Dicționar de date', 'coloana-sql': 'Coloane în baza de date',
               'camp-model': 'Câmpuri de model', 'cod-enumerare': 'Coduri și valori', 'camp-exemplu': 'Exemple în documentație', 'masura': 'Măsuri',
               'camp-folosit-de-pagina': 'Folosite de pagină', 'colectie-cu-chei': 'Colecții indexate'}
FIELD_BASIS_LABELS = {'schema': 'Descris în schemă', 'metadata': 'Descris în metadate', 'sample': 'Observat în date', 'header': 'Antet CSV',
                      'code': 'Declarat în codul sursă', 'table': 'Antet de tabel HTML', 'doctable': 'Declarat în tabel de documentație',
                      'doctext': 'Declarat în textul documentației', 'pagecode': 'Folosit în codul paginii', 'docexample': 'Exemplu în documentație',
                      'apidoc': 'Declarat în documentația API', 'doclist': 'Declarat în lista de coloane din documentație', 'dblist': 'Declarat în lista bazei de date',
                      'editor': 'adăugat de editor'}
GROUP_STATE_LABELS = {'propus': 'Propus', 'revizuit': 'Revizuit', 'amanat': 'Amânat'}
NOTE_PARTIAL = 'Extrase automat din sursele de mai jos. Proiectul poate folosi și alte date. Un câmp comun nu garantează că seturile se pot combina.'


def type_label(field):
    """The type of a field in the words of the field browser (`inventoryType` in site/app.js): the declared type, else the observed types, else the
    semantic type, else „Tip neprecizat”. JavaScript calls an empty list true, so an empty declared type hides the observed types in both."""
    declared = field.get('declaredType')
    raw = declared if declared not in (None, '', 0, False) else (field.get('observedTypes') or field.get('semanticType'))
    values = raw if isinstance(raw, list) else [raw] if raw else []
    return ' / '.join(TYPE_LABELS.get(t, str(t)) for t in values) if values else 'Tip neprecizat'


def clip(text, limit):
    """`clip` of site/app.js: cut a long text at a word, keep the first `limit` characters at most, and end it with an ellipsis."""
    if len(text) <= limit:
        return text
    space = text.rfind(' ', 0, limit + 1)
    return re.sub(r'[\s,.;:–-]+$', '', text[:space if space > limit * .6 else limit]) + '…'


def has_page(item, projections):
    """True when the entry has a variables page: it is in the scope of the inventory and has field records."""
    return not scope_reason(item) and bool(projections.get(item['slug'], ([], []))[0])


def relation_labels(vocabulary):
    """{code: label} of the list `relatie_date`, from the vocabulary of the build (`dataRelations`)."""
    return {r['key']: r['label'] for r in (vocabulary or {}).get('dataRelations', [])}


def group_rows(fields, positions, titles):
    e = html.escape
    return ('<ul class="vp-rows">' + ''.join(f'<li><span class="vp-from">{e(titles.get(fields[n]["source"], ""))}</span> <code>{e(fields[n]["path"])}</code></li>'
                                              for n in positions) + '</ul>')


def family_section(slug, fields, sources, concepts, families):
    """The part „Pe familii”: a block for each family of `/date/lista/` that the entry reaches, in the order of that page, with the groups of the family and the
    fields that match each group (source title, then path). A field that matches two groups is listed under both. The block „Altele” lists the fields that
    match no group. A family without a field has no block."""
    e = html.escape
    titles = {s['id']: s.get('title', '') for s in sources}
    family_of = {c['id']: c.get('familie') for c in concepts}
    columns = family_columns(concepts, families)
    known = dict(columns)
    hits = group_hits(slug, fields, sources, concepts)
    by_family = {}
    for concept, found in hits:
        by_family.setdefault(family_of.get(concept['id']) if family_of.get(concept['id']) in known else None, []).append((concept, [n for n, _ in found]))
    blocks = []
    for fam, label in columns:
        groups = sorted(by_family.get(fam, []), key=lambda g: g[0]['label'].casefold())
        if not groups:
            continue
        inner = ''.join(
            f'<div class="vp-group" data-group="{e(c["id"])}"><h4><a href="{PAGE_DIR}/?variables={quote(c["id"])}">{e(c["label"])}</a>'
            f'<small class="finder-state" data-state="{e(group_state(c))}">{e(GROUP_STATE_LABELS.get(group_state(c), group_state(c)))}</small>'
            f'<small>{ro_count(len(found), "câmp", "câmpuri")}</small></h4>{group_rows(fields, found, titles)}</div>' for c, found in groups)
        blocks.append(f'<section class="vp-family" data-family="{e(fam or "")}"><h3>{e(label)}<small>{ro_count(len({n for _, f in groups for n in f}), "câmp", "câmpuri")}</small></h3>{inner}</section>')
    matched = {n for _, found in hits for n, _ in found}
    other = [n for n in range(len(fields)) if n not in matched]
    if other:
        blocks.append(f'<section class="vp-family vp-other" data-family="altele"><h3>Altele<small>{ro_count(len(other), "câmp", "câmpuri")}</small></h3>'
                      f'<p class="ov-note">Câmpuri care nu se potrivesc cu niciun grup.</p>{group_rows(fields, other, titles)}</section>')
    return (f'<section class="vp-section" id="pe-familii"><h2>Pe familii</h2>'
            f'<p class="ov-note">Fiecare grup numește o variabilă normalizată. Sub el stau câmpurile surselor care îi corespund. Același nume nu înseamnă că datele se pot combina.</p>'
            f'{"".join(blocks)}</section>')


def source_checked(source):
    """„consultat la 2026-10-26”, or the saved copy of the owner; the same words as the field browser. The failed refresh is said, never hidden."""
    parts = []
    if source.get('checked'):
        parts.append(('copie salvată de proprietar la ' if source.get('savedByOwner') else 'consultat la ') + source['checked'])
    failed = source.get('refreshFailed')
    if failed:
        parts.append('ultima reîmprospătare a eșuat' + (f' la {failed["date"]}' if failed.get('date') else '') + (f' (HTTP {failed["status"]})' if failed.get('status') else '')
                     + '; informațiile pot fi vechi')
    return parts


def ext_link(url, text):
    e = html.escape
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>'


def dataset_html(source):
    """The facts that a metadata source of INS declares about its data set (`dataset`), in the words of the field browser (`inventoryDatasets` in site/app.js)."""
    e = html.escape
    d = source['dataset']
    period = d.get('period') or [None, None]
    parts = [f'perioadă {"?" if period[0] is None else period[0]}–{"?" if period[1] is None else period[1]} (calculată de API)' if period[0] or period[1] else '',
             f'niveluri: {", ".join(map(str, d["levels"]))}' if d.get('levels') else '', f'unitate declarată: {" / ".join(d["units"])}' if d.get('units') else '',
             f'actualizat {d["updated"]}' if d.get('updated') else '', '' if d.get('licence') else 'licență nedeclarată']
    label = f'<span class="inv-basis">{e(d["basis"])}</span>' if d.get('basis') else ''
    return (f'<div class="vp-datasets" data-kind="metadate"><h4>Set de date descris în metadate {label}</h4><ul class="vp-sets"><li class="vp-set">'
            f'<strong>{e(d.get("code") or "")}</strong> {e(d.get("name") or "")} <span class="ov-note">{e(" · ".join(x for x in parts if x))}</span> {ext_link(source["url"], "Metadate")}</li></ul>'
            f'<p class="ov-note">Metadate citite de la ins.gov2.ro, o oglindă a TEMPO. Perioada poate fi mai scurtă decât în sursa originală.</p></div>')


def facts_html(source):
    """The data set facts of one source for the part „Pe surse”: the INS metadata (`dataset`), the data sets that a page lists (`facts.sets`) and the data sets that it
    declares with schema.org (`facts.schema`). Each block names its basis. A description is shown whole. Nothing is shown for a source that declares none."""
    e = html.escape
    blocks = [dataset_html(source)] if source.get('dataset') else []
    facts = source.get('facts') or {}
    label = f'<span class="inv-basis">{e(facts.get("basis", ""))}</span>'
    if facts.get('sets'):
        items = ''.join(
            f'<li class="vp-set"><strong>{e(x["title"])}</strong>' + (f' <span class="vp-cat">{e(x["category"])}</span>' if x.get('category') else '')
            + (f'<p>{e(x["description"])}</p>' if x.get('description') else '')
            + (f'<p class="ov-note">Rapoarte: {", ".join(ext_link(r["url"], r["text"]) for r in x["reports"])}</p>' if x.get('reports') else '') + '</li>' for x in facts['sets'])
        blocks.append(f'<div class="vp-datasets" data-kind="lista"><h4>Seturi de date descrise de pagină {label}</h4><ul class="vp-sets">{items}</ul></div>')
    if facts.get('schema'):
        items = ''.join(
            f'<li class="vp-set"><strong>{e(x.get("name") or "Set de date")}</strong>'
            + (f' <span class="ov-note">perioadă {e(x["period"])}</span>' if x.get('period') else '')
            + (f' <span class="ov-note">licență {ext_link(x["licence"]["url"], x["licence"]["name"]) if x["licence"]["url"] else e(x["licence"]["name"])}</span>' if x.get('licence') else '')
            + (f'<p class="ov-note">Bazat pe: {", ".join(ext_link(u, u) for u in x["basedOn"])}</p>' if x.get('basedOn') else '') + '</li>' for x in facts['schema'])
        blocks.append(f'<div class="vp-datasets" data-kind="schema"><h4>Seturi de date declarate în pagină (schema.org) {label}</h4><ul class="vp-sets">{items}</ul></div>')
    return ''.join(blocks)


def source_section(source, fields, positions, groups_of):
    """One source of the part „Pe surse”: its title, address, format and licence, and a table of its fields."""
    e = html.escape
    rows = []
    for n in positions:
        f = fields[n]
        basis = FIELD_BASIS_LABELS.get(f['basis'], f['basis'])
        unit = f.get('unit')
        table = ''
        if f.get('group'):
            table = f'<small>{e(f["group"])}' + (f' · {ro_count(f["rows"], "rând", "rânduri")}' if isinstance(f.get('rows'), int) else '') + '</small>'
        rows.append(f'<tr><th scope="row"><code>{e(f["name"])}</code><small>{e(ROLE_LABELS.get(f["role"], f["role"]))} · {e(basis)}</small></th>'
                    f'<td><code>{e(f["path"])}</code>{table}</td><td>{e(type_label(f))}</td><td>{e(unit) if unit else ""}</td>'
                    f'<td>{e(f["description"]) if f["description"] else ""}</td><td>{e(", ".join(groups_of.get(n, [])))}</td></tr>')
    facts = [('Adresă', f'<a href="{e(source["url"])}" target="_blank" rel="noopener">{e(source["url"])}</a>'),
             ('Format', e(FORMATS.get(source.get('format'), 'Sursă de date')))]
    licence = source.get('licence')
    if licence:
        name = (f'<a href="{e(licence["url"])}" target="_blank" rel="noopener">{e(licence["name"])}</a>' if licence.get('url') else e(licence['name']))
        facts.append(('Licență', name + (f' · {e(licence["attribution"])}' if licence.get('attribution') else '')))
    checked = source_checked(source)
    if checked:
        facts.append(('Consultare', e(' · '.join(checked))))
    body = (f'<div class="ov-scroll vp-scroll"><table class="vp-table"><thead><tr><th scope="col">Nume</th><th scope="col">Cale</th><th scope="col">Tip</th>'
            f'<th scope="col">Unitate</th><th scope="col">Descriere</th><th scope="col">Grup</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            if rows else '<p class="ov-note">' + ('Pagina nu are câmpuri proprii: descrie seturi de date, iar câmpurile lor sunt în fișierele la care trimite.'
                                                  if source.get('facts') or source.get('dataset')
                                                  else 'Niciun câmp propriu: câmpurile acestei surse repetă înregistrări ale altor surse și sunt arătate la ele.') + '</p>')
    return (f'<section class="vp-source" id="ps-{e(source["id"])}" data-source="{e(source["id"])}"><h3>{e(source.get("title", ""))}</h3>'
            f'<dl class="vp-facts">{"".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)}</dl>{facts_html(source)}'
            f'<p class="ov-note">{ro_count(len(rows), "câmp", "câmpuri")}</p>{body}</section>')


def variable_page(item, fields, sources, concepts, families, relations):
    """The body of `/date/<slug>/`: the header, the part „Pe familii” and the part „Pe surse”."""
    e = html.escape
    slug, kind = item['slug'], item['kind']
    labels = {c['id']: c['label'] for c in concepts}
    groups_of = {}
    for concept, found in group_hits(slug, fields, sources, concepts):
        for n, _ in found:
            groups_of.setdefault(n, []).append(labels[concept['id']])
    by_source = {}
    for n, f in enumerate(fields):
        by_source.setdefault(f['source'], []).append(n)
    relation = item.get('dataRelation', '')
    here = f'{PAGE_DIR}/{e(slug)}/'
    head = (f'<section class="vp-head"><p class="vp-kind">{"Proiect" if kind == "proiect" else "Resursă"}</p><h1>{e(item["name"])}</h1>'
            f'<p class="vp-meta"><span>Relația cu datele: {e(relations.get(relation, relation))}</span><span>{ro_count(len(sources), "sursă", "surse")}</span>'
            f'<span>{ro_count(len(fields), "câmp", "câmpuri")}</span><span class="inv-status">Inventar parțial</span></p>'
            f'<p class="ov-note">{NOTE_PARTIAL}</p>'
            f'<p><a class="vp-open" href="{e(kind)}/{e(slug)}/">Fișa din explorator →</a></p>'
            f'<nav class="vp-nav" aria-label="Pe această pagină"><a href="{here}#pe-familii">Pe familii</a><a href="{here}#pe-surse">Pe surse</a></nav></section>')
    sourced = ''.join(source_section(s, fields, by_source.get(s['id'], []), groups_of) for s in sources)
    return (head + family_section(slug, fields, sources, concepts, families)
            + f'<section class="vp-section" id="pe-surse"><h2>Pe surse</h2>{sourced}</section>')


def publish_variable_pages(items, site, projections, concepts, families, vocabulary=None):
    """Write `date/<slug>/index.html` for each entry with a page (`has_page`) and remove every page that no entry has now. The pages sit beside
    `date/lista/`, which keeps its name: an entry with the slug `lista` would collide with it. Returns the slugs written."""
    relations = relation_labels(vocabulary)
    template = (Path(__file__).parent / 'templates/inventory-vars.html').read_text()
    digests = {asset: hashlib.sha1((site / asset).read_bytes()).hexdigest()[:10] for asset in ('style.css', 'inventory.css')}
    base = site / PAGE_DIR
    base.mkdir(parents=True, exist_ok=True)
    written = []
    for item in items:
        if not has_page(item, projections):
            continue
        slug = item['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug == 'lista':
            raise ValueError('Invalid or reserved slug for a variables page: ' + slug)
        fields, sources = projections[slug]
        doc = (template.replace('<!--NAME-->', html.escape(item['name'])).replace('<!--PAGE-->', variable_page(item, fields, sources, concepts, families, relations)))
        for asset, digest in digests.items():
            doc = doc.replace(f'{asset}?v=BUILD', f'{asset}?v={digest}')
        folder = base / slug
        folder.mkdir(exist_ok=True)
        (folder / 'index.html').write_text(doc)
        written.append(slug)
    for stale in base.iterdir():
        if stale.is_dir() and stale.name != 'lista' and stale.name not in written:
            shutil.rmtree(stale)
    return written


GOOGLE_EXPORT = re.compile(r'^https://docs\.google\.com/spreadsheets/d/([\w-]+)/export\?(?:[^#]*&)?gid=(\d+)(?:&|$)')


def sheet_titles(profile, sources):
    """Titles for the Google Sheet tabs that a page of the same project lists as data sets (format `html-lista-seturi`).
    The URL of a tab ends in `export`, so it tells a visitor nothing. The page's own title of the data set does. A data set with several links
    adds the label that the page writes for the link (`HG 1088/2021 (Citu)`, `Deconturi`). The result maps a source ID to its title."""
    listed = {}
    for ident in profile.get('surse_structurate', []):
        for dataset in sources.get(ident, {}).get('seturi', []) if sources.get(ident, {}).get('format') == 'html-lista-seturi' else []:
            for link in dataset.get('legaturi', []):
                if link.get('tip') == 'foaie-google' and link.get('id_document') and link.get('gid') is not None:
                    title = dataset['titlu']['valoare']
                    if len(dataset['legaturi']) > 1:
                        label = link['text_dupa'] or link['eticheta']
                        title += ' · ' + label['valoare']
                    listed[(link['id_document'], link['gid'])] = 'Foaie Google · ' + title
    titles = {}
    for ident in profile.get('surse_structurate', []):
        match = GOOGLE_EXPORT.match(sources.get(ident, {}).get('url', ''))
        if match and (match.group(1), match.group(2)) in listed:
            titles[ident] = listed[(match.group(1), match.group(2))]
    return titles


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


def source_licence(source):
    """The licence that every data set of a described-files page declares, with its link and the attribution it asks for.
    A Datasette listing declares one licence for all its tables (`baza.licenta`); its attribution is the declared source, introduced by `Sursa: `.
    None when the sets declare none or disagree: the field browser then names no licence for the page."""
    facts = [(item.get('licenta'), '') for item in source.get('seturi', [])]
    if isinstance(source.get('baza'), dict):
        facts.append((source['baza'].get('licenta'), 'Sursa: '))
    found = set()
    for fact, prefix in facts:
        if not isinstance(fact, dict) or not fact.get('valoare'):
            return None
        credit = (fact.get('atribuire') or {}).get('valoare') or ''
        found.add((fact['valoare'], http_url((fact.get('url') or {}).get('valoare', '')), prefix + credit if credit else ''))
    if len(found) != 1:
        return None
    name, url, attribution = found.pop()
    return {'name': name, 'url': url, 'attribution': attribution}


# The data set facts that a source declares about its own data sets (module docstring of `inventory_setlist` and `inventory_literals`). A fact is shown only when
# the source declares it: its basis is `declarat-in-pagina`, `declarat-in-metadate` or `declarat-in-lista`. A value that an API computed or that the inventory
# counted is not a declaration. The basis is named with the public word for the key `declaratie-directa` (`PUBLIC_BASIS_LABELS`: „declarat”).
DECLARED_BASIS = 'declaratie-directa'
DESCRIPTION_LIMIT = 300  # characters of a description in `inventar/<slug>.json`; the page of the entry keeps the whole text


def declared(fact):
    """The value of a fact that the source declares, or None: a `{valoare, baza}` record whose basis starts with `declarat-in-`, with a value."""
    if isinstance(fact, dict) and str(fact.get('baza', '')).startswith('declarat-in-') and fact.get('valoare') not in (None, '', []):
        return fact['valoare']
    return None


def declared_sets(source):
    """The data sets that a page of described files lists (format `html-lista-seturi`, key `seturi`): title, category, description and related reports.
    A set without a declared title is not listed."""
    found = []
    for item in source.get('seturi', []) if source.get('format') == 'html-lista-seturi' else []:
        title = declared(item.get('titlu'))
        if not title:
            continue
        fact = {'title': title}
        category = ' · '.join(x for x in (declared(item.get('categorie')), declared(item.get('subcategorie'))) if x)
        if category:
            fact['category'] = category
        if declared(item.get('descriere')):
            fact['description'] = declared(item.get('descriere'))
        reports = []
        for report in item.get('rapoarte', []):
            address = http_url(declared(report.get('adresa')) or '')
            if address:
                reports.append({'text': declared(report.get('text')) or address, 'url': address})
        if reports:
            fact['reports'] = reports
        found.append(fact)
    return found


def declared_schema(source):
    """The data sets that a page declares with schema.org `Dataset` (format `js-literale`, key `seturi_ld`): name, period, licence and `isBasedOn`.
    The creator, the editor, the keywords and the measured variables are not shown. A set with none of the four is not listed."""
    found = []
    for item in source.get('seturi_ld', []) if source.get('format') == 'js-literale' else []:
        fact = {}
        for key, field in (('name', 'nume'), ('period', 'perioada')):
            if declared(item.get(field)):
                fact[key] = declared(item[field])
        licence = declared(item.get('licenta'))
        if licence:
            fact['licence'] = {'name': licence, 'url': http_url(licence)}
        based = [url for url in (http_url(declared(b) or '') for b in item.get('bazat_pe', [])) if url]
        if based:
            fact['basedOn'] = based
        if fact:
            found.append(fact)
    return found


def declared_facts(source):
    """The facts of one source for the field browser and the page of the entry: {'basis': label, 'sets': [...], 'schema': [...]} or None.
    A source with persons keeps none (its record holds no such key)."""
    if is_marked(source):
        return None
    facts = {key: found for key, found in (('sets', declared_sets(source)), ('schema', declared_schema(source))) if found}
    return {'basis': PUBLIC_BASIS_LABELS[DECLARED_BASIS], **facts} if facts else None


def compact_facts(facts):
    """The facts as `inventar/<slug>.json` keeps them: a description is cut at `DESCRIPTION_LIMIT` characters."""
    sets = [{**x, 'description': clip(x['description'], DESCRIPTION_LIMIT)} if x.get('description') else x for x in facts.get('sets', [])]
    return {**facts, **({'sets': sets} if sets else {})}


def compact_source(source):
    return {**source, 'facts': compact_facts(source['facts'])} if source.get('facts') else source


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
        sheets = sheet_titles(profile, sources)
        for ident in profile.get('surse_structurate', []):
            source = sources.get(ident, {})
            url = http_url(source.get('url', ''))
            facts = declared_facts(source)
            # A page that lists described data sets has no field of its own (the fields are in the files that it links), but its facts are listed.
            if not url or not (source.get('campuri') or facts):
                continue
            fmt = source.get('format', '')
            filename = unquote(Path(urlsplit(url).path).name)
            title = sheets.get(ident) or FORMATS.get(fmt, 'Sursă de date') + (' · ' + filename if filename else '')
            listed = {'id': ident, 'url': url, 'title': title, 'format': fmt, 'checked': str(source.get('fetched_at', ''))[:10]}
            if source.get('set_date'):
                listed['dataset'] = {**dataset_summary(source['set_date']), 'basis': PUBLIC_BASIS_LABELS[DECLARED_BASIS]}
            if facts:
                listed['facts'] = facts
            licence = source_licence(source)
            if licence:
                listed['licence'] = licence
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
                                  ('randuri_tabel', 'rows'), ('valoare', 'value'), ('linie', 'line'), ('expresie', 'expression'), ('obligatoriu', 'required')):
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
            payload = {'slug': slug, 'partial': True, 'sources': [compact_source(x) for x in source_list], 'fields': fields}
            (target / filename).write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
            written.add(filename)
            item['inventory']['url'] = 'inventar/' + filename
    for stale in target.glob('*.json'):
        if stale.name not in written:
            stale.unlink()
    return projections
