"""The four views of the data finder by source (docs/briefs/source-views.md): `date/furnizori/`, `date/formate/`, `date/licente/` and `date/gazde/`.

Each view groups the entries of `date/lista/` (the scope rule `scope_reason`) by a property of their sources and ends with the note of the entries that the
inventory leaves out. A page is static HTML: it needs no script. It shows names, formats, hosts, licences and counts, and no value of a data body.
`inventory_site.publish_finder` calls `publish_source_views` and the entry pages link to the anchors written here.
"""
import html
import re
from urllib.parse import urlsplit

from common import PROVIDER_TYPES
from inventory_site import (FORMAT_KIND_OF, FORMAT_KINDS, FORMATS, OTHER_KIND, PAGE_DIR, entry_providers, ext_link, format_anchor, has_page, left_out,
                            left_out_section, provider_slug, relation_labels, resolve_provider, ro_count, scope_reason, write_view)

TYPE_LABELS = {'institutie-publica': 'Instituții publice', 'ue-international': 'Uniunea Europeană și organizații internaționale', 'ong': 'ONG-uri',
               'companie': 'Companii', 'comunitate': 'Comunități', 'autor': 'Autori (datele proprii)', '': 'Neclasificat'}
NO_LICENCE = 'Licență nedeclarată'

# The hosts of `date/gazde/` are grouped by registered domain. The project has no dependencies, so a short list of two-level suffixes stands in for the
# public suffix list. A platform hosts the pages of many unrelated owners: it is never grouped, and each full host stands alone.
TWO_LEVEL_SUFFIXES = ('gov.ro', 'com.ro', 'org.ro', 'github.io', 'co.uk')
PLATFORMS = ('github.io', 'vercel.app', 'githubusercontent.com')


def scoped(items):
    """The entries of the inventory (`scope_reason`), by name: the same set as `date/lista/`."""
    return sorted((i for i in items if not scope_reason(i)), key=lambda i: i['name'].casefold())


def entry_line(item, projections, relations):
    """One entry for a list: its name (a link to the explorer) and a small line with the kind, the relation to data and the link to its variables page."""
    e = html.escape
    parts = ['proiect' if item['kind'] == 'proiect' else 'resursă']
    if relations.get(item.get('dataRelation')):
        parts.append(e(relations[item['dataRelation']].lower()))
    if has_page(item, projections):
        parts.append(f'<a href="{PAGE_DIR}/{e(item["slug"])}/">Toate variabilele</a>')
    return f'<li><a href="{e(item["kind"])}/{e(item["slug"])}/">{e(item["name"])}</a> <small>{" · ".join(parts)}</small></li>'


def entry_list(entries, projections, relations):
    return f'<ul class="ov-entries">{"".join(entry_line(i, projections, relations) for i in entries)}</ul>'


def no_source_section(entries, projections, what):
    """The entries in scope that have no source of the kind this page counts. A short line, like „De analizat” of `date/lista/`."""
    if not entries:
        return ''
    e = html.escape
    links = ', '.join(f'<a href="{e(i["kind"])}/{e(i["slug"])}/">{e(i["name"])}</a>' for i in entries)
    return (f'<section class="ov-bare"><h2>Fără {what} ({len(entries)})</h2><p>{links}</p>'
            f'<p class="ov-note">Lipsa surselor în inventar nu înseamnă lipsa datelor: inventarul acestor intrări nu a fost făcut.</p></section>')


# --- date/furnizori/ ----------------------------------------------------------------------------------------------------------------------

def provider_groups(entries, table):
    """({provider id: {id, name, type, accepted, names, entries}}, [entries without an accepted `date_din` relation]). `names` are the names of the relations that
    stand for the provider; an entry counts once for a provider that two of its names stand for."""
    found, bare = {}, []
    for item in entries:
        providers = entry_providers(item, table)
        if not providers:
            bare.append(item)
        for provider in providers:
            record = found.setdefault(provider['id'], {**provider, 'names': [], 'entries': []})
            record['entries'].append(item)
    for item in entries:
        for source in item.get('dataSources', []):
            record = found[resolve_provider(source['name'], table)['id']]
            if source['name'] not in record['names']:
                record['names'].append(source['name'])
    return found, bare


def provider_order(record):
    return (-len(record['entries']), record['name'].casefold())


def provider_label(name, short, href=None):
    """A provider in the header of the matrix: the short name, with the full name in `title` and, for a screen reader, in hidden text. The list below the matrix
    keeps the full name. `href` makes the label a link."""
    e = html.escape
    if short == name:
        inner, title = e(name), ''
    else:
        inner, title = f'<span aria-hidden="true">{e(short)}</span><span class="sr">{e(name)}</span>', f' title="{e(name, quote=True)}"'
    return f'<a href="{href}"{title}>{inner}</a>' if href else f'<span{title}>{inner}</span>'


MARK = '<td class="ov-mark" data-sort="1"><span aria-hidden="true">✓</span><span class="sr">da</span></td>'
NO_MARK = '<td data-sort="0"></td>'


def matrix_section(ranked, entries, bare):
    """The matrix of `date/furnizori/` in two orientations, both in the HTML: the entries in rows and the providers in columns, and the pivot. Every provider is
    in it, sorted by the count of entries then the name (`provider_order`); the entries are those with a provider, sorted by name. The headers use the short names.
    The script `inventory-tables.js` shows one orientation and makes the columns sortable; without it both tables show, one after the other."""
    e = html.escape
    if not ranked:
        return ''
    used = {r['id']: {i['slug'] for i in r['entries']} for r in ranked}
    users = [i for i in entries if i not in bare]
    provider_head = ''.join(
        f'<th scope="col" data-sort-type="num">{provider_label(r["name"], r["short"], f"{PAGE_DIR}/furnizori/#f-{e(r["id"])}")}<small>{len(r["entries"])}</small></th>' for r in ranked)
    rows = ''.join(
        f'<tr id="m-{e(i["slug"])}"><th scope="row" data-sort="{e(i["name"].casefold(), quote=True)}"><a href="{e(i["kind"])}/{e(i["slug"])}/">{e(i["name"])}</a></th>'
        + ''.join(MARK if i['slug'] in used[r['id']] else NO_MARK for r in ranked) + '</tr>' for i in users)
    by_entries = (f'<table class="ov-table ov-matrix ov-sortable" data-matrix="entries"><caption class="sr">Intrări pe rânduri, furnizori pe coloane</caption>'
                  f'<thead><tr><th scope="col">Intrare<small>{len(users)}</small></th>{provider_head}</tr></thead><tbody>{rows}</tbody></table>')
    entry_head = ''.join(
        f'<th scope="col" class="ov-vert" data-sort-type="num"><a href="{e(i["kind"])}/{e(i["slug"])}/"><span>{e(i["name"])}</span></a></th>' for i in users)
    pivot_rows = ''.join(
        f'<tr id="mp-{e(r["id"])}"><th scope="row" data-sort="{e(r["short"].casefold(), quote=True)}">{provider_label(r["name"], r["short"], f"{PAGE_DIR}/furnizori/#f-{e(r["id"])}")}</th>'
        f'<td class="ov-count" data-sort="{len(r["entries"])}">{len(r["entries"])}</td>'
        + ''.join(MARK if i['slug'] in used[r['id']] else NO_MARK for i in users) + '</tr>' for r in ranked)
    by_providers = (f'<table class="ov-table ov-matrix ov-sortable" data-matrix="providers"><caption class="sr">Furnizori pe rânduri, intrări pe coloane</caption>'
                    f'<thead><tr><th scope="col">Furnizor<small>{len(ranked)}</small></th><th scope="col" data-sort-type="num">Intrări</th>{entry_head}</tr></thead>'
                    f'<tbody>{pivot_rows}</tbody></table>')
    toggle = ('<div class="ov-orient" role="group" aria-label="Orientarea matricei" data-orient-toggle hidden>'
              '<button type="button" data-show="entries" aria-pressed="true">Intrări pe rânduri</button>'
              '<button type="button" data-show="providers" aria-pressed="false">Furnizori pe rânduri</button></div>')
    return (f'<section class="ov-matrix-box" id="matrice"><h2>Toți cei {len(ranked)} furnizori, pe {len(users)} intrări</h2>'
            f'<p class="ov-note">Numele din antet sunt prescurtate; numele întreg stă în titlul lor și în lista de mai jos. O bifă înseamnă că intrarea are furnizorul. '
            f'Un clic pe un antet sortează coloana: la un furnizor, intrările lui vin primele.</p>{toggle}'
            f'<div data-orient="entries"><h3 class="ov-orient-title">Intrări pe rânduri</h3><div class="ov-scroll ov-wide">{by_entries}</div></div>'
            f'<div data-orient="providers"><h3 class="ov-orient-title">Furnizori pe rânduri</h3><div class="ov-scroll ov-wide">{by_providers}</div></div></section>')


def providers_view(items, projections, table, relations):
    e = html.escape
    entries = scoped(items)
    found, bare = provider_groups(entries, table)
    ranked = sorted(found.values(), key=provider_order)
    sections = []
    for tip in (*PROVIDER_TYPES, ''):
        group = [r for r in ranked if r['type'] == tip]
        if not group:
            continue
        rows = []
        for r in group:
            aliases = f'<p class="ov-note">Numele din relații: {e(", ".join(r["names"]))}.</p>' if r['names'] != [r['name']] else ''
            rows.append(f'<li class="ov-provider" id="f-{e(r["id"])}"><h3>{e(r["name"])}<small>{ro_count(len(r["entries"]), "intrare", "intrări")}</small></h3>'
                        f'{aliases}{entry_list(r["entries"], projections, relations)}</li>')
        sections.append(f'<section class="ov-group" id="tip-{e(tip or "neclasificat")}" data-type="{e(tip)}">'
                        f'<h2>{e(TYPE_LABELS[tip])}<small>{ro_count(len(group), "furnizor", "furnizori")}</small></h2><ul class="ov-providers">{"".join(rows)}</ul></section>')
    matrix = matrix_section(ranked, entries, bare)
    none = ''
    if bare:
        links = ', '.join(f'<a href="{e(i["kind"])}/{e(i["slug"])}/">{e(i["name"])}</a>' for i in bare)
        none = (f'<section class="ov-bare" id="fara-furnizor"><h2>Fără furnizor declarat ({len(bare)})</h2><p>{links}</p>'
                f'<p class="ov-note">Lipsa unui furnizor în relații nu înseamnă lipsa datelor: relația „date din” nu a fost completată pentru aceste intrări.</p></section>')
    unmerged = sum(not r['accepted'] for r in found.values())
    note = (f'<p class="ov-note">{len(entries) - len(bare)} intrări din {len(entries)} au cel puțin un furnizor; {ro_count(len(found), "furnizor", "furnizori")}. '
            f'Același furnizor nu înseamnă același set de date. Un nume se unește cu altul numai după un rând acceptat în <code>furnizori.csv</code>; '
            f'{unmerged} dintre furnizori nu au încă un astfel de rând și rămân sub numele din relații, la „Neclasificat”.</p>')
    content = note + matrix + ''.join(sections) + none + left_out_section(left_out(items))
    found_summary = {'groups': len(sections), 'providers': len(found), 'entries': len(entries) - len(bare), 'matrix': len(ranked), 'bare': len(bare)}
    return content, found_summary


# --- date/formate/ ------------------------------------------------------------------------------------------------------------------------

def format_kind(fmt):
    """(key, label) of the kind of a source format, or `OTHER_KIND` for a format that `FORMAT_KIND_OF` does not list."""
    key = FORMAT_KIND_OF.get(fmt)
    return next((k for k in FORMAT_KINDS if k[0] == key), OTHER_KIND)


def entry_formats(fields, sources):
    """{format: number of fields} for one entry, in the order of its sources. A source without a field has the count 0."""
    found = {}
    for source in sources:
        fmt = source.get('format') or ''
        found[fmt] = found.get(fmt, 0) + sum(1 for f in fields if f['source'] == source['id'])
    return found


def formats_view(items, projections, relations):
    e = html.escape
    entries = scoped(items)
    per_entry, bare = [], []
    for item in entries:
        fields, sources = projections.get(item['slug'], ([], []))
        (per_entry if sources else bare).append((item, entry_formats(fields, sources)))
    kinds = list(FORMAT_KINDS) + ([OTHER_KIND] if any(format_kind(f) == OTHER_KIND for _, fm in per_entry for f in fm) else [])
    totals = {k: sum(any(format_kind(f)[0] == k for f in fm) for _, fm in per_entry) for k, _ in kinds}
    rows = []
    for item, fm in per_entry:
        cells = []
        for key, _ in kinds:
            names = sorted(((FORMATS.get(f, 'Sursă de date'), f, n) for f, n in fm.items() if format_kind(f)[0] == key), key=lambda x: x[0].casefold())
            cells.append(f'<td data-sort="{len(names)}">' + (('<ul>' + ''.join(
                f'<li><a href="{PAGE_DIR}/formate/#{format_anchor(f)}">{e(label)}</a>' + (f' <small>{n}</small>' if n else '') + '</li>' for label, f, n in names)
                + '</ul>') if names else '') + '</td>')
        rows.append(f'<tr id="{e(item["slug"])}"><th scope="row" data-sort="{e(item["name"].casefold(), quote=True)}"><a href="{e(item["kind"])}/{e(item["slug"])}/">{e(item["name"])}</a>'
                    f'<small>{"proiect" if item["kind"] == "proiect" else "resursă"} · {ro_count(len(projections[item["slug"]][1]), "sursă", "surse")}'
                    + (f' · <a href="{PAGE_DIR}/{e(item["slug"])}/">Toate variabilele</a>' if has_page(item, projections) else '') + '</small></th>' + ''.join(cells) + '</tr>')
    head = ''.join(f'<th scope="col" data-sort-type="num">{e(label)}<small>{totals[key]}</small></th>' for key, label in kinds)
    table = (f'<div class="ov-scroll"><table class="ov-table ov-fit ov-formats ov-sortable"><thead><tr><th scope="col">Intrare<small>{len(per_entry)}</small></th>{head}</tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>')
    by_format = {}
    for item, fm in per_entry:
        for fmt in fm:
            by_format.setdefault(fmt, []).append(item)
    order = {name: n for n, name in enumerate(FORMATS)}
    sections = []
    for key, label in kinds:
        formats = sorted((f for f in by_format if format_kind(f)[0] == key), key=lambda f: (-len(by_format[f]), order.get(f, len(order)), f))
        if not formats:
            continue
        inner = ''.join(f'<li class="ov-format" id="{format_anchor(f)}"><h3>{e(FORMATS.get(f, "Sursă de date"))}<small>{ro_count(len(by_format[f]), "intrare", "intrări")}</small></h3>'
                        f'{entry_list(by_format[f], projections, relations)}</li>' for f in formats)
        sections.append(f'<section class="ov-group" id="fel-{e(key)}" data-kind="{e(key)}"><h2>{e(label)}<small>{ro_count(len(formats), "format", "formate")}</small></h2>'
                        f'<ul class="ov-providers">{inner}</ul></section>')
    note = (f'<p class="ov-note">{len(per_entry)} intrări din {len(entries)} au surse structurate. Un format arată cum se citește o sursă, nu ce conține. '
            f'Numărul de sub fiecare coloană spune câte intrări au cel puțin o sursă de acel fel; numărul de lângă un format este numărul de câmpuri extrase din el. '
            f'Același format nu înseamnă același set de date.</p>')
    content = note + table + ''.join(sections) + no_source_section([i for i, _ in bare], projections, 'surse structurate') + left_out_section(left_out(items))
    return content, {'groups': len(sections), 'formats': len(by_format), 'entries': len(per_entry), 'kinds': totals}


# --- date/licente/ ------------------------------------------------------------------------------------------------------------------------

def declared_licences(source):
    """[{name, url}] that one source declares, with the rules of the variables pages and no rule of its own: the licence of `source_licence` (the key `licence`),
    the licences of the schema.org data sets of `declared_facts` (`facts.schema`), and the licence that an INS metadata source declares (`dataset.licence`)."""
    found = []
    if source.get('licence'):
        found.append({'name': source['licence']['name'], 'url': source['licence'].get('url') or ''})
    for item in (source.get('facts') or {}).get('schema', []):
        if item.get('licence'):
            found.append({'name': item['licence']['name'], 'url': item['licence'].get('url') or ''})
    declared = (source.get('dataset') or {}).get('licence')
    declared = declared.get('valoare') if isinstance(declared, dict) else declared
    if isinstance(declared, str) and declared:
        found.append({'name': declared, 'url': ''})
    unique = {}
    for licence in found:
        unique.setdefault(licence['name'], licence)
    return list(unique.values())


def licences_view(items, projections, relations):
    e = html.escape
    entries = scoped(items)
    groups, bare = {}, []   # licence name -> {url, entries: {slug: (item, [source])}}
    declared_sources = total_sources = 0
    for item in entries:
        fields, sources = projections.get(item['slug'], ([], []))
        if not sources:
            bare.append(item)
        for source in sources:
            total_sources += 1
            licences = declared_licences(source) or [{'name': None, 'url': ''}]
            declared_sources += bool(licences[0]['name'])
            for licence in licences:
                group = groups.setdefault(licence['name'], {'url': licence['url'], 'entries': {}})
                group['url'] = group['url'] or licence['url']
                group['entries'].setdefault(item['slug'], (item, []))[1].append(source)
    order = sorted((n for n in groups if n), key=lambda n: (-len(groups[n]['entries']), n.casefold())) + ([None] if None in groups else [])
    sections = []
    for name in order:
        group = groups[name]
        label = NO_LICENCE if name is None else name
        title = ext_link(group['url'], label) if group['url'] else e(label)
        count = sum(len(s) for _, s in group['entries'].values())
        lines = []
        for item, sources in sorted(group['entries'].values(), key=lambda x: x[0]['name'].casefold()):
            titles = ''.join(
                '<li>' + (f'<a href="{PAGE_DIR}/{e(item["slug"])}/#ps-{e(s["id"])}">{e(s.get("title", ""))}</a>' if has_page(item, projections) else e(s.get('title', ''))) + '</li>'
                for s in sources)
            lines.append(f'<li><a href="{e(item["kind"])}/{e(item["slug"])}/">{e(item["name"])}</a> <small>{ro_count(len(sources), "sursă", "surse")}</small><ul>{titles}</ul></li>')
        sections.append(f'<section class="ov-licence" id="lic-{"nedeclarata" if name is None else provider_slug(name)}" data-licence="{e(label)}">'
                        f'<h3>{title}<small>{ro_count(len(group["entries"]), "intrare", "intrări")} · {ro_count(count, "sursă", "surse")}</small></h3>'
                        f'<ul class="ov-sources">{"".join(lines)}</ul></section>')
    shown = len(order) - (None in groups)
    note = (f'<p class="ov-note">{ro_count(declared_sources, "sursă are", "surse au")} o licență declarată, din {total_sources}; {ro_count(shown, "licență", "licențe")}. '
            f'O licență declarată este ceea ce spune sursa, nu o părere juridică. Numele se arată așa cum le scrie sursa: două nume pot fi aceeași licență. '
            f'O sursă fără licență declarată nu este fără licență.</p>')
    content = note + ''.join(sections) + no_source_section(bare, projections, 'surse structurate') + left_out_section(left_out(items))
    return content, {'groups': len(order), 'licences': shown, 'entries': len(entries) - len(bare), 'declared_sources': declared_sources, 'sources': total_sources,
                     'names': [n for n in order if n]}


# --- date/gazde/ --------------------------------------------------------------------------------------------------------------------------

def source_host(url):
    """The host of a source address in lower case, without `www.`; an empty string when the address has none."""
    host = (urlsplit(url).hostname or '').lower()
    return host[4:] if host.startswith('www.') else host


def host_group(host):
    """The name that a host is grouped under: its registered domain. A platform (`PLATFORMS`) and an IP address stay as the full host. A host under one of the
    `TWO_LEVEL_SUFFIXES` keeps three labels (`data.gov.ro` is a suffix, so `x.y.gov.ro` groups under `y.gov.ro`); any other keeps two."""
    labels = host.split('.')
    if len(labels) < 2 or all(label.isdigit() for label in labels) or any(host == p or host.endswith('.' + p) for p in PLATFORMS):
        return host
    keep = 3 if any(host.endswith('.' + s) for s in TWO_LEVEL_SUFFIXES) else 2
    return '.'.join(labels[-keep:])


def hosts_view(items, projections, relations):
    e = html.escape
    entries = scoped(items)
    groups, bare, own = {}, [], 0
    per_entry = {}
    for item in entries:
        fields, sources = projections.get(item['slug'], ([], []))
        hosts = {source_host(s['url']) for s in sources if source_host(s['url'])}
        if not hosts:
            bare.append(item)
            continue
        per_entry[item['slug']] = {host_group(h) for h in hosts}
        for host in hosts:
            group = groups.setdefault(host_group(host), {})
            group.setdefault(host, []).append(item)
    shared = {g: hosts for g, hosts in groups.items() if len({i['slug'] for v in hosts.values() for i in v}) >= 2}
    own = sum(all(g not in shared for g in gs) for gs in per_entry.values())
    sections = []
    ranked = sorted(shared, key=lambda g: (-len({i['slug'] for v in shared[g].values() for i in v}), g))
    for g in ranked:
        everyone = {i['slug'] for v in shared[g].values() for i in v}
        hosts = ''.join(f'<li><code>{e(h)}</code> <small>{ro_count(len(v), "intrare", "intrări")}</small>{entry_list(v, projections, relations)}</li>'
                        for h, v in sorted(shared[g].items(), key=lambda x: (-len(x[1]), x[0])))
        sections.append(f'<section class="ov-host" id="gazda-{provider_slug(g)}" data-host="{e(g)}"><h3><code>{e(g)}</code>'
                        f'<small>{ro_count(len(everyone), "intrare", "intrări")} · {ro_count(len(shared[g]), "gazdă", "gazde")}</small></h3><ul class="ov-sources">{hosts}</ul></section>')
    note = (f'<p class="ov-note">{len(per_entry)} intrări din {len(entries)} au surse structurate. Se arată gazdele care servesc cel puțin două intrări; gazdele unui portal '
            f'sunt grupate după domeniul înregistrat. Platformele (github.io, vercel.app, githubusercontent.com) nu se grupează: fiecare gazdă întreagă stă singură. '
            f'Aceeași gazdă nu înseamnă același set de date.</p>')
    summary = (f'<p class="ov-own" id="domeniu-propriu"><strong>{own}</strong> din {len(per_entry)} intrări au toate sursele pe domeniul propriu, '
               f'care nu servește altă intrare.</p>')
    content = note + ''.join(sections) + summary + no_source_section(bare, projections, 'surse structurate') + left_out_section(left_out(items))
    return content, {'groups': len(sections), 'entries': len({i['slug'] for g in shared.values() for v in g.values() for i in v}), 'own': own,
                     'with_sources': len(per_entry), 'grouped': {g: sorted(shared[g]) for g in ranked if len(shared[g]) > 1}}


# --- the four pages -----------------------------------------------------------------------------------------------------------------------

def publish_source_views(items, site, projections, table, vocabulary=None):
    """Write the four pages beside `date/lista/`. `table` holds the accepted rows of `furnizori.csv`. Returns {page: summary} for the report and the tests."""
    relations = relation_labels(vocabulary)
    pages = (('furnizori', 'Furnizorii datelor', 'Proiectele și resursele grupate după furnizorul datelor lor, așa cum îl spun relațiile „date din”.', providers_view(items, projections, table, relations)),
             ('formate', 'Formatele surselor', 'Proiectele și resursele grupate după formatul surselor lor: API, fișiere, tabele în pagină, scriptul paginii, cod sursă.', formats_view(items, projections, relations)),
             ('licente', 'Licențele surselor', 'Sursele proiectelor grupate după licența pe care o declară.', licences_view(items, projections, relations)),
             ('gazde', 'Gazdele surselor', 'Proiectele care își țin sursele de date pe aceeași gazdă.', hosts_view(items, projections, relations)))
    summary = {}
    for name, title, description, (content, found) in pages:
        write_view(site, name, title, description, content)
        summary[name] = found
    return summary
