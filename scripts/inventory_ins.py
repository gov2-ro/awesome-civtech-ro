"""Dataset-level facts from an INS TEMPO metadata record (ins.gov2.ro API). Stdlib only.

The record separates what the response declares from what the API computed and what this script counted:

- `declarat-in-metadate`: a value present in the metadata response (name, definition, note, update date, categories).
- `calculat-de-api`: a value that the API's own profiler derived (period, geographic levels, archetype).
- `observat-in-optiuni`: a value counted from the dimension options in the response body.

Every fact keeps a JSON pointer into the body. An indicator, a dimension and a dimension value are three different things:
the dataset has one indicator (the statistic described by `definitie`), a few dimensions (columns of the cube) and many
dimension values (the code list of each dimension). Values are summarised, never exported as variables.
A fact the response does not declare stays `None` with a reason. Nothing is inferred from magnitude or from the host.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

DECLARED, COMPUTED, COUNTED = 'declarat-in-metadate', 'calculat-de-api', 'observat-in-optiuni'
SAMPLE_CODES = 5


def fact(value, pointer, basis=DECLARED, **extra):
    return {'valoare': value, 'pointer': pointer, 'baza': basis, **extra}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links = [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'a' and dict(attrs).get('href'):
            self.links.append(dict(attrs)['href'])
        if tag in ('br', 'p', 'li'):
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


def plain(text):
    """Strip markup from a declared text and keep its links. The transformation is recorded by the caller."""
    parser = _Text()
    parser.feed(text or '')
    cleaned = re.sub(r'[ \t]+', ' ', ''.join(parser.parts))
    cleaned = re.sub(r'\s*\n\s*', '\n', cleaned).strip()
    return cleaned, parser.links


def text_fact(doc, key):
    """A declared free text. Markup is removed; the pointer still names the original member."""
    raw = doc.get(key)
    if not isinstance(raw, str) or not raw.strip():
        return None
    cleaned, links = plain(raw.replace('\r\n', '\n'))
    marked = cleaned != raw.replace('\r\n', '\n').strip()
    extra = {'transformare': 'marcaj-eliminat'} if marked else {}
    if links:
        extra['legaturi'] = links
    return fact(cleaned, '/' + key, **extra)


def listed(value):
    """The profile member `geo_levels` is a JSON array encoded as a string; keep a plain array if the API changes."""
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return parsed if isinstance(parsed, list) else None


def dimension_summary(dimension, index):
    options = dimension.get('options') or []
    pointer = f'/dimensions/{index}'
    summary = {'nume': dimension.get('dim_column_name'), 'eticheta': dimension.get('dim_label', '').strip(),
               'tip': dimension.get('dim_type'), 'cod_dimensiune': dimension.get('dim_code'),
               'numar_optiuni_declarat': dimension.get('option_count'), 'numar_optiuni_in_raspuns': len(options), 'pointer': pointer,
               'exemple_coduri': [{'cod': o.get('sdmx_value'), 'eticheta': o.get('label'), 'id_sursa': o.get('nom_item_id'),
                                   'pointer': f'{pointer}/options/{n}'} for n, o in enumerate(options[:SAMPLE_CODES])],
               'trunchiat': max(dimension.get('option_count') or 0, len(options)) > min(len(options), SAMPLE_CODES)}
    if dimension.get('dim_type') == 'geo':
        levels = {}
        for option in options:
            level = (option.get('parsed') or {}).get('geo_level')
            if level:
                levels[level] = levels.get(level, 0) + 1
        summary['niveluri_in_optiuni'] = fact(dict(sorted(levels.items())), pointer + '/options/*/parsed/geo_level', COUNTED)
    if dimension.get('dim_type') == 'time':
        years = sorted({(o.get('parsed') or {}).get('year') for o in options} - {None})
        if years:
            summary['ani_in_optiuni'] = fact({'min': years[0], 'max': years[-1], 'numar': len(years)}, pointer + '/options/*/parsed/year', COUNTED)
    return summary


def unit_options(doc):
    """Units declared as dimension options of type `unit`. A unit that the API did not type stays untyped."""
    found = []
    for index, dimension in enumerate(doc.get('dimensions') or []):
        if dimension.get('dim_type') == 'unit' or str(dimension.get('dim_column_name', '')).upper() == 'UNIT_MEASURE':
            for n, option in enumerate(dimension.get('options') or []):
                parsed = option.get('parsed') or {}
                found.append({'cod': option.get('sdmx_value'), 'eticheta': option.get('label'),
                              'tip_unitate': parsed.get('unit_type'), 'scala': parsed.get('unit_scale'),
                              'tip_optiune': option.get('dim_type'), 'pointer': f'/dimensions/{index}/options/{n}', 'baza': DECLARED})
    return found


def ins_dataset(doc):
    """Dataset facts of one metadata record. Returns a dict that `inventory.py --check` can recompute from the body."""
    profile = doc.get('profile') or {}
    out = {'cod': fact(doc.get('matrix_code'), '/matrix_code'),
           'denumire': {lang: fact(doc[key], '/' + key) for lang, key in (('ro', 'matrix_name_ro'), ('en', 'matrix_name')) if doc.get(key)},
           'actualizat': fact(doc.get('ultima_actualizare'), '/ultima_actualizare') if doc.get('ultima_actualizare') else None,
           'categorie': fact([{'cod': c.get('code'), 'nume': c.get('name')} for c in doc.get('context_path') or []], '/context_path')
           if doc.get('context_path') else None,
           'definitie_indicator': text_fact(doc, 'definitie'),
           'metodologie': text_fact(doc, 'metodologie'),
           'observatii': text_fact(doc, 'observatii'),
           'randuri': fact(doc.get('row_count'), '/row_count') if doc.get('row_count') is not None else None,
           'dimensiuni': [dimension_summary(d, n) for n, d in enumerate(doc.get('dimensions') or [])],
           'unitati': unit_options(doc),
           'diviziuni': [{'cod': s.get('matrix_code'), 'randuri': s.get('row_count'), 'dimensiuni': s.get('split_dimensions'),
                          'pointer': f'/splits/{n}'} for n, s in enumerate(doc.get('splits') or [])],
           'licenta': None, 'licenta_motiv': 'Metadata response declares no licence member.'}
    if profile:
        period = {k: fact(profile[k], '/profile/' + k, COMPUTED) for k in ('time_year_min', 'time_year_max', 'time_granularity') if k in profile}
        out['perioada'] = {'an_min': period.get('time_year_min'), 'an_max': period.get('time_year_max'), 'granularitate': period.get('time_granularity')}
        levels = listed(profile.get('geo_levels'))
        out['niveluri_geografice'] = fact(levels, '/profile/geo_levels', COMPUTED) if levels is not None else None
        out['arhetip'] = fact(profile.get('archetype'), '/profile/archetype', COMPUTED) if profile.get('archetype') else None
    return out


CARD_KEYS = ('matrix_code', 'matrix_name', 'context_code', 'ultima_actualizare', 'row_count', 'dim_count', 'archetype', 'has_time',
             'has_geo', 'time_range', 'primary_unit_type', 'time_granularity', 'is_split', 'parent_matrix_code', 'split_count', 'option_count')


def is_listing(doc):
    return (isinstance(doc, dict) and isinstance(doc.get('datasets'), list) and isinstance(doc.get('total'), int)
            and all(isinstance(card, dict) and 'matrix_code' in card for card in doc['datasets']))


def ins_listing(doc):
    """Facts of a dataset listing response: the catalogue total and a bounded sample of dataset cards.
    A listing sample says nothing about datasets that it does not contain."""
    cards = doc['datasets']
    return {'total': fact(doc['total'], '/total'), 'carduri_in_esantion': len(cards), 'complet': len(cards) >= doc['total'],
            'carduri': [{key: fact(card[key], f'/datasets/{n}/{key}') for key in CARD_KEYS if key in card} for n, card in enumerate(cards[:5])]}


OBS_VALUE_DECLARATION = '**OBS_VALUE**: The numeric observation value column in all data responses.'
LLMS_URL = 'https://ins.gov2.ro/llms.txt'


def ins_measure(doc):
    """The measure column of a dataset. The API documentation (llms.txt) names it `OBS_VALUE` for every dataset; the metadata supplies
    the indicator definition and the declared unit options. The name is a documented API fact, not a member of the metadata body,
    so the field points to the definition and keeps the documentation sentence as external evidence."""
    units = [u for u in unit_options(doc)]
    labels = list(dict.fromkeys(u['cod'] for u in units if u.get('cod')))
    name = doc.get('matrix_name_ro') or doc.get('matrix_name') or ''
    definition = text_fact(doc, 'definitie')
    field = {'nume': 'OBS_VALUE', 'cale': 'OBS_VALUE', 'rol': 'masura', 'stare_tip': 'declarat-in-documentatie-api',
             'tip_declarat': None, 'pointer': '/definitie' if definition else '/matrix_name_ro',
             'descriere': (definition['valoare'] if definition else name),
             'unitate': labels[0] if len(labels) == 1 else None,
             'dovada_externa': {'url': LLMS_URL, 'fragment': OBS_VALUE_DECLARATION}}
    if len(labels) > 1:
        field['unitati_declarate'] = labels
    return field
