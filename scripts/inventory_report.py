"""Coverage export and readable report for the inventory expansion. Stdlib only. Writes nothing outside the two outputs.

    python3 scripts/inventory_report.py            # write observatii/inventare/acoperire.csv and docs/reports/inventory-expansion.md
    python3 scripts/inventory_report.py --check    # compare both with a fresh computation; exit 1 on a difference

Every number comes from the tracked inventory files, the request log and the hand-edited notes (`inventar-note.json`).
Raw field totals are source paths, not business variables, and the report keeps them apart from groups, definitions, types and units.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path

from collect_docs import is_saved
from common import ROOT, PUBLIC_ROOT, UNASSESSED, inventory_scope, load_catalogue, observation_paths
from inventory_concepts import (CANDIDATE_STATES, GROUP_STATES, SELECTOR_STATES, active_groups, candidate_items, candidate_label, candidate_state, group_state,
                                repeated_exclusions, selector_matches, selector_state)
from inventory_state import counted_fields
from taxonomy_v2 import HIDDEN

COLUMNS = ['slug', 'tip_entitate', 'investigat_in_lot', 'stare_investigare', 'surse_structurate', 'campuri_din_surse', 'concepte_propuse',
           'campuri_cu_definitie', 'campuri_cu_tip_declarat', 'campuri_cu_tip_observat', 'masuri_cu_unitate', 'masuri_fara_unitate',
           'surse_cu_provenienta_verificata', 'limite', 'blocaj', 'urmatorul_pas']
# The states of `stare_investigare` for an entry without a usable or failed source. An entry out of the variable inventory (common.inventory_exclusion)
# gets the reason as its state: `fara-date`, `inactiv` or `neevaluat` (an empty `relatie_date`). Their `urmatorul_pas` is empty, except `neevaluat`:
# it asks the editor for a value, because the entry leaves /date/ until there is one. An entry with a usable or a failed source keeps `cu-surse-structurate` or `blocat`.
STATES = ('cu-surse-structurate', 'blocat', 'investigat-fara-surse', 'neinvestigat-in-lot', 'fara-date', 'inactiv', UNASSESSED, 'in-afara-ariei')
NEXT_STEP = {'neinvestigat-in-lot': 'Căutați documentație, o schemă sau un export. Lipsa extragerii nu înseamnă lipsa datelor.',
             'investigat-fara-surse': 'Un lot a căutat o sursă structurată publică și nu a găsit niciuna. Un export sau o schemă de la proprietar ar ajuta. Lipsa extragerii nu înseamnă lipsa datelor.',
             UNASSESSED: 'Stabiliți valoarea relatie_date în intrari.csv. Fără ea, intrarea nu apare în /date/.'}
# Measured at the baseline commit (the brief, section 3).
BASELINE = {'entries': 140, 'projects': 106, 'resources': 21, 'organisations': 13, 'finder': 127, 'with_fields': 14, 'without_fields': 113,
            'source_urls': 25, 'parsed': 24, 'failed': 1, 'field_records': 2302, 'schema_declarations': 1312, 'sampled_paths': 904,
            'csv_headers': 82, 'ins_dimensions': 4, 'control_candidates': 308, 'control_entries': 78, 'partial_profiles': 78, 'unconfirmed_profiles': 62,
            'accepted_providers': 26, 'accepted_entries': 11, 'pending_proposals': 15, 'groups': 7, 'tests': 308, 'tests_skipped': 6,
            'explorer_checks': 25, 'finder_checks': 25}
BATCH = ['afacut', 'biografia-localitatii', 'registrul-firmelor', 'dignitas', 'monitorul-ai', 'rezultate-vot', 'votdiaspora', 'aerlive',
         'calitate-aer-radauti', 'banii-nostri', 'europescope', 'despre-femicid']
EXTRA_GAPS = ['companii-de-stat', 'transparenta-eu', 'romania-transparenta', 'codurbanism']
BATCH_C2 = ['data-expertforum', 'bani-partide', 'romania-interactiva']  # lot C2: the three active projects of public-sector data
BATCH_D = ['lista-firme', 'dupa-cutremur', 'reciclare-arad', 'onorata-instanta', 'sondaje-romania', 'guvernezi', 'politicieni-corupti', 'unde-locuiesc',
           'trei-din-patru', 'statul-digital', 'pe-datorie', 'ce-face-statul-cu-1000-de-lei']  # lot D: twelve entries of „De analizat” with the strongest signals
BATCH_E = ['monitor-safe', 'igov', 'companii-publice-ro', 'executii-bugetare', 'ce-cumpara-primaria', 'sicap-ai', 'open-budget', 'monitor-social', 'verifica-psiholog',
           'portal-just-modern', 'cat-de-tare', 'recontorizarea']  # lot E: twelve more entries of „De analizat”
BATCH_G = ['ai-aflat', 'destraja', 'econtractauto', 'monarh-ai', 'monitor-energie', 'radar-digital', 'redirectioneaza', 'semnal-razboiul-hibrid', 'testvot', 'tipizatul']
# The reserve entries of the brief of lot E, in the order of its list. A reserve joins lot E only when a primary entry is blocked: sicap-ai and open-budget are,
# so the first two reserves took their place. They carry the lot code `E` like the primary entries.
RESERVES_E = ['de-unde-vine-apa', 'ani-de-pensie']
INS_USERS = ['ins-gov2', 'constru-pentru-cine', 'orasul-care-se-intinde', 'demoanaf', 'unde-se-termina-asfaltul', 'biografia-localitatii']
MEASURE_CATEGORIES = ('masura', 'iesire-derivata')
REVIEW_STATES = ('deschis', 'acceptat', 'respins', 'amanat', 'tehnic')  # revizuire_stare, in the order the report lists them


def load(root):
    base = observation_paths(root)['profile'].parent
    inv = base / 'inventare'
    read = lambda name: json.loads((inv / name).read_text())
    data = {'entries': load_catalogue(root), 'profiles': {p['slug']: p for p in read('proiecte.json')['proiecte']},
            'sources': {s['id']: s for s in read('seturi-date.json')['surse']}, 'registry': read('descoperiri.json')['descoperiri'],
            'concepts': json.loads((root.parent / 'inventar-concepte.json').read_text())['concepte'],
            'notes': json.loads((root.parent / 'inventar-note.json').read_text()),
            'log': list(csv.DictReader((inv / 'jurnal-cereri.csv').open(newline=''))) if (inv / 'jurnal-cereri.csv').exists() else [],
            'controls': list(csv.DictReader((inv / 'intrari-utilizator.csv').open(newline=''))),
            'review': list(csv.DictReader((root / 'revizuire.csv').open(newline=''))),
            'relations': list(csv.DictReader((root / 'relatii.csv').open(newline='')))}
    data['scope'] = inventory_scope(data['entries'], root)  # slug -> why the entry is out of the variable inventory; '' when in scope
    return data


def field_view(field):
    return {'name': field['nume'], 'path': field['cale'], 'role': field.get('rol', 'camp-date')}


def membership(data):
    """Per project: concept ids, and the (source, path) keys of fields that are measures or have a unit fact."""
    sources, concepts = data['sources'], active_groups(data['concepts'])  # a rejected group (`respins`) has no members
    result = {slug: {'concepts': set(), 'measures': {}} for slug in data['profiles']}
    for slug, profile in data['profiles'].items():
        for ref in profile['surse_structurate']:
            source = sources[ref]
            for field in counted_fields(source):
                view, key = field_view(field), (ref, field['cale'], field['pointer'] if 'pointer' in field else '')
                has_unit = bool(field.get('unitate') or field.get('unitati_declarate'))
                # A measure is a field with the role `masura`, a dictionary-table row (it declares what it measures), or a member of a measure group.
                is_measure = field.get('rol') == 'masura' or field.get('stare_tip') == 'declarat-in-tabel-documentatie' and 'unitate' in field
                for concept in concepts:
                    for selector in concept['selectors']:
                        if selector_matches(selector, slug, view, source['url']):
                            result[slug]['concepts'].add(concept['id'])
                            is_measure = is_measure or concept.get('categorie') in MEASURE_CATEGORIES
                            has_unit = has_unit or any(f['cheie'] == 'unitate' for f in selector.get('fapte', []))
                            break
                if is_measure:
                    result[slug]['measures'][key] = result[slug]['measures'].get(key, False) or has_unit
    return result


def lots(data):
    """Which collection lots touched which entries. C: the primary batch. B: entries given INS dataset records.
    B2: existing inventories that got a source for a named gap. C2: the three active projects of public-sector data (an entry whose host answered 403
    is in the lot, with the state `blocat`). D: twelve entries of „De analizat” (an entry without a usable source has the state `investigat-fara-surse`).
    E: twelve more entries of „De analizat” and the reserve entries that replaced the blocked ones (same states).
    S: entries with a page that the owner saved by hand (no request was possible).
    Entries with fields and no lot come from the baseline pass."""
    touched = {}
    for lot, slugs in (('C', BATCH), ('B', INS_USERS), ('B2', EXTRA_GAPS), ('C2', BATCH_C2), ('D', BATCH_D), ('E', BATCH_E + RESERVES_E), ('G', BATCH_G)):
        for slug in slugs:
            touched.setdefault(slug, set()).add(lot)
    for slug, profile in data['profiles'].items():
        if any(is_saved(data['sources'].get(ref)) for ref in profile['surse_structurate']):
            touched.setdefault(slug, set()).add('S')
    return touched


def coverage_rows(data):
    members, touched = data.setdefault('members', membership(data)), lots(data)
    registry = {}
    for record in data['registry']:
        if record['stare'] == 'activ':
            registry.setdefault(record['proiect'], []).append(record)
    rows = []
    for entry in data['entries']:
        slug, profile = entry['slug'], data['profiles'][entry['slug']]
        sources = [data['sources'][r] for r in profile['surse_structurate']]
        usable = [s for s in sources if s.get('stare') == 'analizat']
        failed = [s for s in sources if s.get('stare') != 'analizat']
        fields = [f for s in usable for f in counted_fields(s)]
        note = data['notes']['note'].get(slug, {})
        if entry['kind'] == 'organizatie':
            state = 'in-afara-ariei'
        elif usable:
            state = 'cu-surse-structurate'
        elif failed or (note.get('blocaj') and not sources):  # a host that refused every request leaves no source record; the notes say why
            state = 'blocat'
        else:
            state = data['scope'][slug] or ('investigat-fara-surse' if touched.get(slug) else 'neinvestigat-in-lot')
        measures = members[slug]['measures']
        known_measures = bool(usable)
        verified = sum(1 for r in registry.get(slug, []) if r['locator_stare'] == 'cunoscut' and r['metoda'] != 'membru-anterior'
                       and ((r.get('dovada') or {}).get('sha256') or (r.get('dovada') or {}).get('blob_sha') or (r.get('dovada') or {}).get('valoare')))
        limits = list(note.get('limite', []))
        if any(s.get('partial') for s in usable):
            limits.append('Unele fișiere sunt citite ca eșantion.')
        if any(s.get('limita_atinsa') for s in usable) and not note.get('limite'):
            limits.append('Extragerea a atins o limită de eșantionare.')
        if any(s.get('ultima_incercare') for s in sources):
            limits.append('Ultima reîmprospătare a unei surse a eșuat; dovada poate fi veche.')
        blocker = note.get('blocaj', '')
        if failed and not blocker:
            blocker = 'HTTP ' + str(failed[0].get('http_status') or '?') + ' la ' + failed[0]['url']
        rows.append([slug, entry['entity_type'], '|'.join(sorted(touched.get(slug, set()))) or ('baza' if usable else ''), state,
                     len(usable), len(fields), len(members[slug]['concepts']) if known_measures else '',
                     sum(1 for f in fields if f.get('descriere')), sum(1 for f in fields if f.get('tip_declarat') is not None),
                     sum(1 for f in fields if f.get('tipuri_observate')),
                     sum(measures.values()) if known_measures else '', sum(1 for v in measures.values() if not v) if known_measures else '',
                     verified if sources else '', ' '.join(limits), blocker,
                     note.get('urmatorul_pas', '' if entry.get('classification_state') == HIDDEN else NEXT_STEP.get(state, ''))])
    return rows


def csv_text(rows):
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return stream.getvalue()


def metrics(data, rows):
    """The measures of section 3, recomputed from the tracked files."""
    entries, profiles, sources = data['entries'], data['profiles'], data['sources']
    finder = [e for e in entries if e['kind'] in ('proiect', 'resursa')]
    with_fields = [e for e in finder if profiles[e['slug']]['campuri_din_surse']]
    kinds = Counter()
    for source in sources.values():
        for field in counted_fields(source):
            kinds[field['stare_tip']] += 1
    parsed = [s for s in sources.values() if s.get('stare') == 'analizat']
    accepted = [(e['slug'], r['name']) for e in entries for r in e['data_sources']]
    log_direct = [r for r in data['log'] if r['cache'] == 'nu']
    public = [e for e in finder if e.get('classification_state') != HIDDEN]  # what /date/ can list: a hidden entry never reaches the site
    reasons = Counter(data['scope'][e['slug']] for e in public)
    return {'entries': len(entries), 'projects': sum(e['kind'] == 'proiect' for e in entries), 'resources': sum(e['kind'] == 'resursa' for e in entries),
            'organisations': sum(e['kind'] == 'organizatie' for e in entries), 'finder': len(finder), 'with_fields': len(with_fields),
            'without_fields': len(finder) - len(with_fields), 'hidden': len(finder) - len(public), 'in_scope': reasons[''],
            'left_out': {reason: reasons[reason] for reason in ('fara-date', UNASSESSED, 'inactiv')}, 'source_urls': len(sources), 'parsed': len(parsed), 'failed': len(sources) - len(parsed),
            'field_records': sum(kinds.values()), 'schema_declarations': kinds['declarat-in-schema'], 'sampled_paths': kinds['observat-in-esantion-json'],
            'csv_headers': kinds['neprecizat-in-antet-csv'], 'ins_dimensions': sum(1 for s in sources.values() for f in s['campuri']
                                                                                     if f.get('rol') == 'dimensiune' and f['stare_tip'] == 'declarat-in-metadate' and 'ACC102B' in s['url']),
            'control_candidates': len(data['controls']), 'control_entries': len({r['slug'] for r in data['controls']}),
            'partial_profiles': sum(p['completitudine'] == 'partial' for p in profiles.values()),
            'unconfirmed_profiles': sum(p['completitudine'] == 'neconfirmat' for p in profiles.values()),
            'accepted_providers': len(accepted), 'accepted_entries': len({s for s, _ in accepted}),
            'pending_proposals': sum(1 for r in data['review'] if r['id'].startswith('D') and int(r['id'][1:]) >= 132 and r['stare'] == 'deschis'),
            'groups': len(data['concepts']), 'kinds': dict(kinds), **review_state(data), 'direct_requests': len(log_direct),
            'browser_navigations': sum(1 for r in data['log'] if r['metoda'] == 'BROWSER'),
            'browser_requests': sum(1 for r in data['log'] if r['cache'] == 'browser' and r['metoda'] != 'BROWSER')}


def review_state(data):
    """Decided provider items and groups by state, counted from the tracked review files."""
    providers = [r for r in data['review'] if r['camp'] == 'surse_date']
    selectors = [s for c in data['concepts'] for s in c['selectors']]
    return {'provider_items': len(providers), 'provider_states': Counter(r['stare'] for r in providers),
            'group_states': Counter(group_state(c) for c in data['concepts']),
            'member_states': Counter(selector_state(s) for s in selectors),
            'candidate_states': Counter(candidate_state(i) for i in candidate_items(data['notes']) if isinstance(i, dict))}


def candidate_lines(notes):
    """Section 5, the candidate members. Only the open candidates are listed (the owner decides them in the review interface); the excluded ones are counted
    in one line, so that a later batch sees the refusal; a candidate that equals an excluded one is named, with the note of the owner."""
    items = [i for i in candidate_items(notes) if isinstance(i, dict)]
    opened = [i for i in items if candidate_state(i) == 'propus']
    excluded = [i for i in items if candidate_state(i) == 'exclus']
    out = []
    if opened:
        out += ['Open candidate members of reviewed groups. They are not in `inventar-concepte.json`: a reviewed group cannot hold a member that the owner has not confirmed. '
                'The owner confirms or excludes each one in the review interface (the queue „Candidați”). Each line is a selector:', '']
        out += [f'- `{i["grup"]}`: `{json.dumps(i["selector"], ensure_ascii=False)}`' for i in opened]
        out.append('')
    if excluded:
        out += [f'Excluded candidates: {len(excluded)}. The owner refused them. They stay in `inventar-note.json` (`stare` `exclus`, with `nota_editor`) so that a later batch sees the refusal: '
                + ', '.join(f'`{candidate_label(i)}`' for i in excluded) + '.', '']
    again = repeated_exclusions(items)
    if again:
        out += ['Candidates proposed again after an exclusion (same group, projects, names, path, role and source). The owner decides again, with the earlier note in view:', '']
        out += [f'- `{candidate_label(new)}`: the owner excluded it with the note „{old.get("nota_editor", "")}”.' for new, old in again]
        out.append('')
    return out


def candidate_sentence(states):
    """The candidate counts for the review-state paragraph of section 1 (empty when no candidate exists)."""
    return f' Candidate members: {count_line(states, CANDIDATE_STATES)}.' if sum(states.values()) else ''


def count_line(counter, states):
    return ', '.join(f'{state} {counter[state]}' for state in states)


def pct(n, d):
    return f'{n} of {d}'


def render_report(data, rows):
    m, notes = metrics(data, rows), data['notes']
    verification = notes.get('verificari', {})
    by_slug = {r[0]: dict(zip(COLUMNS, r)) for r in rows}
    entries = {e['slug']: e for e in data['entries']}
    finder_slugs = [e['slug'] for e in data['entries'] if e['kind'] in ('proiect', 'resursa')]
    out = []
    w = out.append
    w('# Inventory expansion report')
    w('')
    w(f'Generated by `scripts/inventory_report.py` from the tracked inventory files. Baseline: v0.13.0 (commit 99b3e8a). Result: {notes["versiune_raport"]}.')
    w('Inventory assertions are proposals. Raw field totals count source paths, not independent business variables.')
    w('')
    w('## 1. Outcome')
    w('')
    for line in notes['rezumat']:
        w('- ' + line.format(**m))
    w('')
    new_inventories = [s for s in BATCH if by_slug[s]['stare_investigare'] == 'cu-surse-structurate']
    useful = [s for s in new_inventories if by_slug[s]['campuri_cu_definitie'] or by_slug[s]['campuri_cu_tip_declarat'] or by_slug[s]['masuri_cu_unitate'] not in (0, '')
              or int(by_slug[s]['concepte_propuse'] or 0)]
    w(f'**Ten-inventory target:** {len(new_inventories)} of the 12 primary entries have a new structured inventory; {len(useful)} of them carry definitions, declared types, '
      f'a declared unit or a proposed shared group. No reserve entry was needed. Measured: {len(new_inventories)}. '
      + ('The target is met.' if len(useful) >= 10 else 'The target is not met.'))
    described = [s for s in new_inventories if by_slug[s]['campuri_cu_definitie']]
    typed = [s for s in new_inventories if by_slug[s]['campuri_cu_tip_declarat']]
    w('')
    w(f'Field-level meaning is thinner than group-level meaning. Source-declared field descriptions exist for {len(described)} of the {len(new_inventories)} new inventories '
      f'({", ".join(f"`{s}`" for s in described) or "none"}) and declared types for {len(typed)} ({", ".join(f"`{s}`" for s in typed) or "none"}). '
      'Most other fields carry a name and an observed or unknown type. The weakest inventory is `aerlive`: three fields and no group.')
    w('')
    w('| Primary entry | Sources | Field records | Described fields | Declared types | Groups | Measures with / without a unit |')
    w('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
    for slug in BATCH:
        r = by_slug[slug]
        w(f'| `{slug}` | {r["surse_structurate"]} | {r["campuri_din_surse"]} | {r["campuri_cu_definitie"]} | {r["campuri_cu_tip_declarat"]} | {r["concepte_propuse"]} | {r["masuri_cu_unitate"]} / {r["masuri_fara_unitate"]} |')
    w('')
    w('## 2. Coverage before and after')
    w('')
    w(f'The {m["finder"]} projects and resources of the catalogue (the finder lists the {m["in_scope"]} that are in scope):')
    w('')
    w('| Measure | Baseline | Now |')
    w('| --- | ---: | ---: |')
    def line(label, key, extra=''):
        w(f'| {label} | {BASELINE[key]:,} | {m[key]:,}{extra} |')
    line('Catalogue entries', 'entries')
    w(f'| Projects / resources / organisations | {BASELINE["projects"]} / {BASELINE["resources"]} / {BASELINE["organisations"]} | {m["projects"]} / {m["resources"]} / {m["organisations"]} |')
    line('Projects and resources (catalogue, hidden entries included)', 'finder')
    line('Entries with structured field evidence', 'with_fields')
    line('Projects/resources without extracted structured fields', 'without_fields')
    line('Retained structured-source URLs', 'source_urls')
    w(f'| Parsed sources / HTTP failures | {BASELINE["parsed"]} / {BASELINE["failed"]} | {m["parsed"]} / {m["failed"]} |')
    line('Source-scoped field records (paths, not variables)', 'field_records')
    w(f'| Schema declarations / sampled JSON paths / CSV headers / INS dimensions | {BASELINE["schema_declarations"]:,} / {BASELINE["sampled_paths"]:,} / {BASELINE["csv_headers"]} / {BASELINE["ins_dimensions"]}'
      f' | {m["schema_declarations"]:,} / {m["sampled_paths"]:,} / {m["csv_headers"]} / {m["ins_dimensions"]} |')
    w(f'| HTML control candidates / entries with candidates | {BASELINE["control_candidates"]} / {BASELINE["control_entries"]} | {m["control_candidates"]} / {m["control_entries"]} |')
    w(f'| Partial / unconfirmed profiles (all 140 entries) | {BASELINE["partial_profiles"]} / {BASELINE["unconfirmed_profiles"]} | {m["partial_profiles"]} / {m["unconfirmed_profiles"]} |')
    w(f'| Accepted provider relations / entries with accepted providers | {BASELINE["accepted_providers"]} / {BASELINE["accepted_entries"]} | {m["accepted_providers"]} / {m["accepted_entries"]} |')
    w(f'| Pending provider proposals (review items D132 and later) | {BASELINE["pending_proposals"]} | {m["pending_proposals"]} |')
    line('Proposed business-variable groups', 'groups')
    if verification:
        w(f'| Unit tests discovered / skipped | {BASELINE["tests"]} / {BASELINE["tests_skipped"]} | {verification["tests"]} / {verification["tests_skipped"]} |')
        w(f'| Explorer inventory / dedicated finder browser checks | {BASELINE["explorer_checks"]} / {BASELINE["finder_checks"]} | {verification["explorer_checks"]} / {verification["finder_checks"]} |')
    w('')
    w(f'Review state, counted from the tracked files. Provider items (`camp` `surse_date`): {m["provider_items"]} in all; {count_line(m["provider_states"], REVIEW_STATES)}. '
      f'Variable groups: {len(data["concepts"])} in all; {count_line(m["group_states"], GROUP_STATES)}. '
      f'Group members (selectors): {sum(m["member_states"].values())} in all; {count_line(m["member_states"], SELECTOR_STATES)}.' + candidate_sentence(m['candidate_states']))
    w('')
    left = m['left_out']
    w(f'Scope of the data finder (`/date/`): {m["in_scope"]} of the {m["finder"] - m["hidden"]} public projects and resources are in scope. '
      f'An entry is in scope when it is not inactive (`offline`, `arhivat`) and its `relatie_date` is `date-publice`, `date-proprii` or `calcul`. '
      f'The finder leaves out {sum(left.values())}: {left["fara-date"]} without data (`fara-date`), {left[UNASSESSED]} not assessed (empty value), '
      f'{left["inactiv"]} inactive (counted first: an inactive entry is never counted as another reason). '
      f'{m["hidden"]} hidden entries (`ascuns`) are in no count of this paragraph.')
    w('')
    kinds = m['kinds']
    w('Field records by evidence type now: ' + ', '.join(f'{k} {v:,}' for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])) + '.')
    w('')
    w(f'Coverage by measure, for the {len(finder_slugs)} projects and resources (`acoperire.csv` has the rows). A column that counts fields counts source paths:')
    w('')
    def total(column, subset):
        values = [by_slug[s][column] for s in subset if by_slug[s][column] != '']
        return sum(int(v) for v in values), len(values)
    w('| Measure | Entries counted | Total |')
    w('| --- | ---: | ---: |')
    with_sources = [s for s in finder_slugs if by_slug[s]['stare_investigare'] == 'cu-surse-structurate']
    for label, column in (('Structured sources', 'surse_structurate'), ('Field records from sources', 'campuri_din_surse'), ('Entries in at least one proposed group', 'concepte_propuse'),
                          ('Fields with a source-declared description', 'campuri_cu_definitie'), ('Fields with a declared type', 'campuri_cu_tip_declarat'),
                          ('Fields with an observed type', 'campuri_cu_tip_observat'), ('Measures with a unit', 'masuri_cu_unitate'),
                          ('Measures without a unit', 'masuri_fara_unitate'), ('Sources with a verified discovery locator', 'surse_cu_provenienta_verificata')):
        if column == 'concepte_propuse':
            w(f'| {label} | {len(with_sources)} | {len([s for s in with_sources if by_slug[s][column]])} |')
            continue
        value, counted = total(column, with_sources)
        w(f'| {label} | {counted} | {value:,} |')
    w('')
    w('Totals add the per-entry counts. A source that several entries share counts once for each of them, so the field total here is higher than the number of distinct field records above.')
    w('Denominators are defined in `docs/DATA-SCHEMA.md` (Coverage export). Entries without a structured source have an empty (unknown) measure count, not zero.')
    w('')
    w(f'All {len(rows)} catalogue entries (hidden entries included):')
    w('')
    states = Counter(r[3] for r in rows)
    w('| State | Entries |')
    w('| --- | ---: |')
    for state, count in sorted(states.items()):
        w(f'| {state} | {count} |')
    w('')
    w('`in-afara-ariei` entries are organisations: the finder lists projects and resources. An organisation need not expose a dataset. Missing extraction never proves missing data.')
    w('`fara-date`, `inactiv` and `neevaluat` are projects and resources that the finder leaves out and that have no source record. '
      'An entry with a usable source keeps `cu-surse-structurate`, and an entry whose sources failed keeps `blocat`, whatever its scope: the evidence stays in `observatii/`, and only the public output leaves the entry out.')
    w('')
    w('## 3. Outcome per selected project')
    w('')
    def outcome(slug, heading='###', proposals=False):
        r = by_slug[slug]
        note = notes['note'].get(slug, {})
        w(f'{heading} `{slug}` — {entries[slug]["nume"]}')
        w('')
        w(note.get('rezultat', ''))
        w('')
        profile = data['profiles'][slug]
        w(f'- State: {r["stare_investigare"]}. Sources {r["surse_structurate"]}, field records {r["campuri_din_surse"]}, groups {r["concepte_propuse"] or 0}.')
        w(f'- Source URLs: ' + ('; '.join(f'`{data["sources"][ref]["url"]}`' for ref in profile['surse_structurate']) or 'none'))
        groups = sorted(data['members'][slug]['concepts'])
        w('- Proposed groups: ' + (', '.join(f'`{g}`' for g in groups) if groups else 'none'))
        inputs = sorted({f['nume'] for ref in profile['surse_structurate'] for f in data['sources'][ref]['campuri'] if f.get('rol') == 'parametru-api'})
        w('- Documented inputs: ' + (', '.join(f'`{n}`' for n in inputs[:10]) if inputs else 'none documented in the sources read. HTML controls stay candidates.'))
        if proposals:
            items = [x['id'] for x in data['review'] if x['slug'] == slug and x['camp'] == 'surse_date' and x['id'].startswith('D') and int(x['id'][1:]) >= 176]
            w('- Provider proposals: ' + (', '.join(items) if items else 'none') + '.')
            w(f'- Blocker: {note.get("blocaj_en", "none")}')
        w(f'- Limitations: {note.get("limite_en", "")}')
        w(f'- Remaining work: {note.get("urmator_en", "")}')
        w('')

    for slug in BATCH:
        outcome(slug)
    w('Reserve entries of lot C (`ce-fac-politicienii`, `onorata-instanta`, `guvernezi`) were not used: all 12 primary entries produced evidence.')
    w('')
    if notes.get('lot_c2'):
        w('### Batch C2: three active projects that publish public-sector data')
        w('')
        for line in notes['lot_c2']:
            w(line)
            w('')
        for slug in BATCH_C2:
            outcome(slug, '####', proposals=True)
    if notes.get('lot_d'):
        w('### Batch D: twelve entries of „De analizat”')
        w('')
        for line in notes['lot_d']:
            w(line)
            w('')
        for slug in BATCH_D:
            outcome(slug, '####', proposals=True)
    if notes.get('lot_e'):
        w('### Batch E: twelve more entries of „De analizat”')
        w('')
        for line in notes['lot_e']:
            w(line)
            w('')
        for slug in BATCH_E + RESERVES_E:
            outcome(slug, '####', proposals=True)
    if notes.get('lot_g'):
        w('### Batch G: ten more entries of „De analizat”')
        w('')
        for line in notes['lot_g']:
            w(line)
            w('')
        for slug in BATCH_G:
            outcome(slug, '####', proposals=True)
    w('## 4. Existing inventories and INS')
    w('')
    for line in notes['ins']:
        w('- ' + line)
    w('')
    w('Additional sources fetched for named gaps in other existing inventories:')
    w('')
    w('| Entry | Source | Gap |')
    w('| --- | --- | --- |')
    for item in notes['lacune']:
        w(f'| `{item["slug"]}` | `{item["url"]}` | {item["lacuna"]} |')
    w('')
    discovered = [r for r in data['registry'] if r['stare'] == 'descoperit']
    w(f'{len(discovered)} documented candidates remain discovered but not fetched: ' + ', '.join(f'{k} {v}' for k, v in Counter(r['proiect'] for r in discovered).items()) + '.')
    w('')
    w('## 5. Shared groups')
    w('')
    members = data['members']
    w('Groups with at least two project memberships (unique entries). A group is a discovery aid. It is not a join key.')
    w('')
    w('| Group | Category | Entries | Members |')
    w('| --- | --- | ---: | --- |')
    for concept in data['concepts']:
        slugs = sorted(s for s in finder_slugs if concept['id'] in members[s]['concepts'])
        if len(slugs) >= 2:
            w(f'| `{concept["id"]}` {concept["label"]} | {concept.get("categorie", "")} | {len(slugs)} | {", ".join(slugs)} |')
    w('')
    w('Groups with one entry so far (no second project exposes the variable in the sources read): ' + ', '.join(
        f'`{c["id"]}`' for c in data['concepts'] if sum(1 for s in finder_slugs if c['id'] in members[s]['concepts']) == 1) + '.')
    w('')
    w('Ambiguous candidates, kept out of the groups:')
    w('')
    for concept in data['concepts']:
        for text in concept.get('ambiguitati', []):
            w(f'- `{concept["id"]}`: {text}')
    w('')
    for line in candidate_lines(notes):
        w(line)
    w('## 6. Provider proposals')
    w('')
    w('Review items D147 and later hold provider findings from this pass. None changes `relatii.csv`, none closes D132–D146, and the accepted provider facet is unchanged.')
    w('The producer, the distributor and the project author are named apart in each item.')
    w('')
    w('| Item | Entry | Proposal | Priority |')
    w('| --- | --- | --- | --- |')
    for r in data['review']:
        if r['id'].startswith('D') and int(r['id'][1:]) >= 147:
            w(f'| {r["id"]} | `{r["slug"]}` | {r["propunere"].replace("Furnizor propus: ", "")} | {r["prioritate"]} |')
    w('')
    w('## 7. Network, methods and blockers')
    w('')
    by_lot = Counter()
    size = Counter()
    for r in data['log']:
        key = (r['lot'], 'browser' if r['cache'] == 'browser' else 'direct' if r['cache'] == 'nu' else 'cache')
        by_lot[key] += 1
        if r['octeti'] and r['cache'] == 'nu':
            size[r['lot']] += int(r['octeti'])
    w('| Lot | Direct requests | Failed | Bytes read | Browser navigations | Browser data requests |')
    w('| --- | ---: | ---: | ---: | ---: | ---: |')
    for lot in sorted({r['lot'] for r in data['log']}):
        failed = sum(1 for r in data['log'] if r['lot'] == lot and r['cache'] == 'nu' and r['stare'] != 'ok')
        nav = sum(1 for r in data['log'] if r['lot'] == lot and r['metoda'] == 'BROWSER')
        brq = sum(1 for r in data['log'] if r['lot'] == lot and r['cache'] == 'browser' and r['metoda'] != 'BROWSER')
        w(f'| {lot} | {by_lot[(lot, "direct")]} | {failed} | {size[lot]:,} | {nav} | {brq} |')
    w('')
    w(f'Total direct requests: {m["direct_requests"]}. The limit for lot C was 150 including retries; no request was retried. Lot B is the INS listing and five metadata records;'
      ' lot B2 is six gap sources of existing inventories. Elapsed work and workers: requests ran one at a time, so the six-worker and two-per-host limits were never reached.')
    for line in notes.get('retea_c2', []):
        w(line)
    for line in notes.get('retea_d', []):
        w(line)
    for line in notes.get('retea_e', []):
        w(line)
    w('The request log (`observatii/inventare/jurnal-cereri.csv`) lists every request with its outcome, method, bytes and purpose. It holds no headers or credentials.')
    w('')
    w('Methods used: documentation collection with page-link and text discovery; CSV, JSON, JSON Schema and OpenAPI parsers; INS TEMPO metadata facts; readers for HTML tables, markdown tables,'
      ' SQL, C#, Laravel PHP, annotated JSON in documents, page scripts and API reference pages (endpoint cards); repository files pinned to a recorded commit and verified by git blob hash;'
      ' bounded range reads for large CSV files; a headless-browser render of single pages (optional, `scripts/render_pages.py`).')
    w('')
    w('External blockers and security findings:')
    w('')
    for item in notes['blocaje']:
        w('- ' + item)
    w('')
    w('## 8. Verification')
    w('')
    for item in verification.get('rezultate', ['Not recorded yet.']):
        w('- ' + item)
    w('')
    w('## 9. Remaining review work')
    w('')
    for item in notes['de_revizuit']:
        w('- ' + item)
    w('')
    return '\n'.join(out).rstrip('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data-dir', type=Path, default=PUBLIC_ROOT)
    parser.add_argument('--check', action='store_true', help='compare with the tracked files; write nothing')
    args = parser.parse_args()
    data = load(args.data_dir)
    rows = coverage_rows(data)
    csv_path = observation_paths(args.data_dir)['profile'].parent / 'inventare' / 'acoperire.csv'
    report_path = ROOT / 'docs' / 'reports' / 'inventory-expansion.md'
    texts = {csv_path: csv_text(rows), report_path: render_report(data, rows) + '\n'}
    if args.check:
        stale = [str(p) for p, t in texts.items() if not p.exists() or p.read_text() != t]
        for p in stale:
            print('ERROR: out of date: ' + p)
        print(f'{len(stale)} outputs out of date')
        return int(bool(stale))
    for path, text in texts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print('wrote ' + str(path.relative_to(ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
