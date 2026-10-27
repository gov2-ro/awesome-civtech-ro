'use strict';

/* Cross-project discovery from explicit, evidence-backed draft inventories. */
const root = new URL(document.baseURI);
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const norm = v => String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const url = path => new URL(path, root).href;
const groups = [
  {key:'variables', label:'Variabile', hint:'Toate variabilele selectate trebuie să apară în proiect.'},
  {key:'providers', label:'Surse de date', hint:'Oricare dintre furnizorii selectați.'},
  {key:'subjects', label:'Subiect', hint:'Ce domeniu te interesează?'},
  {key:'institutions', label:'Instituții vizate', hint:'Instituțiile urmărite de proiect, separat de furnizorii datelor.'}
];
const basis = {schema:'Declarat în schemă', metadata:'Declarat în metadate', sample:'Observat într-un eșantion', header:'Antet CSV · tip neprecizat',
  code:'Declarat în codul sursă', table:'Antet de tabel HTML · tip neprecizat', doctable:'Declarat în tabel de documentație', doctext:'Declarat în textul documentației',
  pagecode:'Folosit în codul paginii', docexample:'Exemplu în documentație', apidoc:'Declarat în documentația API', doclist:'Declarat în lista de coloane din documentație', dblist:'Declarat în lista bazei de date', editor:'adăugat de editor'};
const roles = {'parametru-api':'Parametru API', 'corp-cerere':'Corp de cerere', 'camp-raspuns':'Câmp din răspuns', 'camp-date':'Câmp de date', 'dimensiune':'Dimensiune',
  'camp-dictionar':'Dicționar de date', 'coloana-sql':'Coloană în baza de date', 'camp-model':'Câmp de model', 'cod-enumerare':'Cod sau valoare',
  'camp-exemplu':'Exemplu în documentație', masura:'Măsură', 'camp-folosit-de-pagina':'Folosit de pagină', 'colectie-cu-chei':'Colecție indexată'};
const categories = {identificator:'Identificator', dimensiune:'Dimensiune', masura:'Măsură', 'iesire-derivata':'Valoare calculată', 'intrare-utilizator':'Intrare a utilizatorului'};
const stateLabels = {propus:'Propus', revizuit:'Revizuit', amanat:'Amânat'};
const factKeys = {unitate:'Unitate', formula:'Formulă', rol:'Rol', moment_de_referinta:'Moment de referință'};
const factBasis = {'declaratie-directa':'declarat', 'observatie-esantion':'observat în eșantion', 'deductie-din-dovezi':'dedus din dovezi', 'parafraza-editoriala':'formulare editorială'};
let entries = [], labels = {}, definitions = {}, meta = {}, families = [], state, shown = 24;
// Families the visitor opened or closed; the others follow the default (open when one of their variables is common).
const familyOpen = new Map();

function readState() {
  const p = new URLSearchParams(location.search);
  state = {q:p.get('q') || '', resources:p.get('resurse') !== '0'};
  for (const g of groups) state[g.key] = new Set(p.getAll(g.key).filter(v => labels[g.key]?.[v]));
  $('#data-search').value = state.q;
  $('#data-resources').checked = state.resources;
}

function saveState() {
  const p = new URLSearchParams();
  if (state.q) p.set('q', state.q);
  if (!state.resources) p.set('resurse', '0');
  for (const g of groups) for (const v of state[g.key]) p.append(g.key, v);
  history.pushState(null, '', location.pathname + (p.size ? '?' + p : ''));
}

function matches(entry, skip = '') {
  if (!state.resources && entry.kind !== 'proiect') return false;
  if (!norm(state.q).split(/\s+/).filter(Boolean).every(word => entry._text.includes(word))) return false;
  for (const g of groups) {
    if (g.key === skip || !state[g.key].size) continue;
    if (g.key === 'variables') {
      if (![...state.variables].every(v => entry._values.variables.includes(v))) return false;
    } else if (![...state[g.key]].some(v => entry._values[g.key].includes(v))) return false;
  }
  return true;
}

function filterButton(key, value, text) {
  return `<button type="button" class="finder-tag" data-facet="${key}" data-value="${esc(value)}" aria-pressed="${state[key].has(value)}">${esc(text)}</button>`;
}

function renderFacets() {
  const expanded = new Set([...document.querySelectorAll('.finder-more[open]')].map(e => e.dataset.group));
  $('#data-facets').innerHTML = groups.map(g => {
    const pool = entries.filter(e => matches(e, g.key));
    const options = Object.keys(labels[g.key]).map(value => {
      const count = pool.filter(e => e._values[g.key].includes(value) &&
        (g.key !== 'variables' || [...state.variables].every(v => e._values.variables.includes(v)))).length;
      return {value, count};
    }).sort((a,b) => b.count-a.count || labels[g.key][a.value].localeCompare(labels[g.key][b.value], 'ro'));
    const option = ({value,count}) => `<label class="finder-option" title="${esc(definitions[g.key]?.[value] || labels[g.key][value])}">
      <input type="checkbox" data-facet="${g.key}" data-value="${esc(value)}" ${state[g.key].has(value) ? 'checked' : ''}>
      <span>${esc(labels[g.key][value])}</span><small>${count}</small></label>`;
    if (g.key === 'variables' && families.length) {
      const known = new Set(families.map(f => f.id));
      const sets = [...families, {id:'', label:'Altele'}].map(f => ({f, opts:options.filter(o => f.id ? meta[o.value]?.family === f.id : !known.has(meta[o.value]?.family))}))
        .filter(x => x.opts.length);
      return `<section class="finder-facet"><h2>${g.label}</h2><p>${g.hint}</p>${sets.map(({f, opts}) => {
        const open = opts.some(o => state.variables.has(o.value)) || (familyOpen.has(f.id) ? familyOpen.get(f.id) : opts.some(o => o.count > 3));
        return `<details class="finder-family" data-family="${esc(f.id)}" ${open ? 'open' : ''}><summary>${esc(f.label)} <small>${opts.length}</small></summary>
          <div class="finder-options">${opts.map(option).join('')}</div></details>`;
      }).join('')}</section>`;
    }
    const primary = options.filter(o => state[g.key].has(o.value) || o.count > 3).slice(0,6);
    // Selected values stay visible even when their count falls or the group grows.
    for (const o of options) if (state[g.key].has(o.value) && !primary.includes(o)) primary.push(o);
    const rest = options.filter(o => !primary.includes(o));
    return `<section class="finder-facet"><h2>${g.label}</h2><p>${g.hint}</p>
      <div class="finder-options">${primary.map(option).join('')}</div>
      ${rest.length ? `<details class="finder-more" data-group="${g.key}" ${expanded.has(g.key) ? 'open' : ''}>
        <summary>Mai multe (${rest.length})</summary><div class="finder-options">${rest.map(option).join('')}</div></details>` : ''}</section>`;
  }).join('');
}

function proof(entry) {
  let html = entry.variables.map(v => {
    const info = meta[v.id] || {};
    return `<div class="finder-proof"><strong>${esc(labels.variables[v.id])}</strong>${info.category ? ` <small class="finder-category">${esc(categories[info.category] || info.category)}</small>` : ''}
    <small class="finder-state" data-state="${esc(info.state)}">${esc(stateLabels[info.state] || info.state)}</small>
    <p>${esc(definitions.variables[v.id])}</p>
    ${info.ambiguities?.length ? `<p class="finder-ambiguity">Neclar: ${info.ambiguities.map(esc).join(' ')}</p>` : ''}
    <ul>${v.evidence.map(e => `<li><code>${esc(e.name)}</code>
      · ${esc(roles[e.role] || e.role)}${e.location ? ' · ' + esc(e.location) : ''}
      ${e.context ? `<p>${esc(e.context)}</p>` : ''}
      <p>${esc(basis[e.basis] || e.basis)}${e.declaredType ? ' · ' + esc([e.declaredType].flat().join(', ')) : e.observedTypes.length ? ' · tipuri observate: ' + esc(e.observedTypes.join(', ')) : ''}${e.unit ? ' · ' + esc(e.unit) : ''}</p>
      ${e.facts?.length ? `<p>${e.facts.map(f => `${esc(factKeys[f.key] || f.key)}: ${esc(f.value)} (${esc(factBasis[f.basis] || f.basis)})`).join(' · ')}</p>` : ''}
      ${e.description ? `<p>${esc(e.description.length > 240 ? e.description.slice(0, 240) + '…' : e.description)}</p>` : ''}
      <a href="${esc(e.url)}" target="_blank" rel="noopener">Sursa câmpului ↗</a>
      <p><code>${esc(e.path)}${e.reference ? ' · ' + esc(e.reference) : ''}</code></p></li>`).join('')}</ul>
      ${v.count > v.evidence.length ? `<p>${v.count} câmpuri sau contexte asociate în inventarul proiectului.</p>` : ''}
      ${info.proofs?.length ? `<details class="finder-basis"><summary>Dovezi pentru definiție (formulare editorială)</summary><ul>${info.proofs.map(p => `<li><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.fragment.length > 90 ? p.fragment.slice(0, 90) + '…' : p.fragment)} ↗</a></li>`).join('')}</ul></details>` : ''}</div>`;
  }).join('');
  const providers = Object.values(entry.providers).flat();
  if (providers.length) html += `<div class="finder-proof"><strong>Proveniența datelor</strong><ul>${providers.map(p => `<li><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)} ↗</a></li>`).join('')}</ul></div>`;
  if (entry.inventory.docs?.length) html += `<div class="finder-proof"><strong>Documentație</strong><ul>${entry.inventory.docs.map(d => `<li><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.label)} ↗</a></li>`).join('')}</ul></div>`;
  return html;
}

function card(entry) {
  const inv = entry.inventory;
  const evidence = entry.variables.length || Object.keys(entry.providers).length || inv.docs?.length;
  return `<article class="finder-card" data-project="${esc(entry.slug)}">
    <div class="finder-card-head"><span>${entry.kind === 'proiect' ? 'Proiect' : 'Resursă'}${entry.status === 'arhivat' ? ' · Arhivat' : entry.status === 'offline' ? ' · Offline' : ''}</span>
      <span>${inv.count ? 'Inventar parțial' : 'Câmpuri încă neinventariate'}</span></div>
    <h2><a href="${esc(url(entry.href))}">${esc(entry.name)}</a></h2>
    <p class="finder-description">${esc(entry.description)}</p><dl>
    ${entry.variables.length ? `<dt>Variabile${entry.variables.some(v => (meta[v.id]?.state || 'propus') === 'propus') ? ' · asocieri propuse' : ''}</dt><dd>${entry.variables.map(v => filterButton('variables',v.id,labels.variables[v.id])).join('')}</dd>` : ''}
    <dt>Surse de date</dt><dd>${Object.keys(entry.providers).map(v => filterButton('providers',v,v)).join('') || '<span class="finder-unknown">Proveniență încă neverificată</span>'}</dd>
    ${entry.institutions.length ? `<dt>Instituții vizate</dt><dd>${entry.institutions.map(v => filterButton('institutions',v,labels.institutions[v])).join('')}</dd>` : ''}
    </dl>${evidence ? `<details class="finder-evidence"><summary>Vezi datele și sursele</summary>${proof(entry)}</details>` : ''}
    <div class="finder-links"><a href="${esc(url(entry.href))}">Fișa ${entry.kind === 'proiect' ? 'proiectului' : 'resursei'} →</a>
    ${entry.url ? `<a href="${esc(entry.url)}" target="_blank" rel="noopener">Deschide site-ul ↗</a>` : ''}</div></article>`;
}

function render() {
  const focus = document.activeElement;
  const restore = focus?.dataset.facet ? {key:focus.dataset.facet, value:focus.dataset.value, input:focus.tagName === 'INPUT'} : null;
  renderFacets();
  const found = entries.filter(e => matches(e)).sort((a,b) => {
    // Show the entries with evidence first; all catalogue projects remain reachable.
    const score = e => e.variables.length + Object.keys(e.providers).length + (e.inventory.count ? 1 : 0);
    return score(b)-score(a) || a.name.localeCompare(b.name,'ro');
  });
  const n = found.filter(e => e.kind === 'proiect').length;
  $('#data-count').textContent = `${n} ${n === 1 ? 'proiect' : 'proiecte'}${state.resources ? ' · ' + (found.length-n) + ' resurse' : ''}`;
  const active = groups.flatMap(g => [...state[g.key]].map(v =>
    `<button data-facet="${g.key}" data-value="${esc(v)}" aria-label="Elimină ${esc(labels[g.key][v])}">${esc(labels[g.key][v])} ×</button>`));
  if (state.q) active.unshift(`<button data-clear="q" aria-label="Șterge căutarea">${esc(state.q)} ×</button>`);
  $('#data-active').innerHTML = active.length ? active.join('') + '<button class="finder-clear" data-clear="all">Șterge filtrele</button>' : '';
  $('#data-cards').innerHTML = found.slice(0,shown).map(card).join('') || `<div class="finder-empty"><h2>Niciun proiect pentru această selecție.</h2><p>Inventarul este parțial. Încearcă un subiect mai larg sau elimină un filtru.</p></div>`;
  if (found.length > shown) $('#data-cards').insertAdjacentHTML('beforeend', `<button class="btn btn-outline" data-more>Mai multe proiecte (${found.length-shown})</button>`);
  if (restore) {
    const selector = `${restore.input ? 'input' : 'button'}[data-facet="${restore.key}"][data-value="${CSS.escape(restore.value)}"]`;
    (document.querySelector(selector) || $('#data-search')).focus({preventScroll:true});
  }
}

function change() { shown=24; saveState(); render(); }
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button || !state) return;
  if (button.dataset.facet) {
    const selected = state[button.dataset.facet], value = button.dataset.value;
    selected.has(value) ? selected.delete(value) : selected.add(value);
    change();
  } else if (button.dataset.clear) {
    state.q = ''; $('#data-search').value = '';
    if (button.dataset.clear === 'all') for (const g of groups) state[g.key].clear();
    change(); $('#data-search').focus();
  } else if (button.hasAttribute('data-more')) {
    shown += 24; render();
    document.querySelectorAll('.finder-card h2 a')[shown-24]?.focus({preventScroll:true});
  }
});
document.addEventListener('change', event => {
  const input = event.target;
  if (!state) return;
  if (input.dataset.facet) {
    const selected = state[input.dataset.facet];
    input.checked ? selected.add(input.dataset.value) : selected.delete(input.dataset.value);
    change();
  } else if (input.id === 'data-resources') { state.resources = input.checked; change(); }
});
let searchTimer;
$('#data-search').addEventListener('input', () => {
  if (!state) return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.q = $('#data-search').value.trim(); change(); }, 150);
});
document.addEventListener('toggle', e => { if (e.target.matches?.('.finder-family')) familyOpen.set(e.target.dataset.family, e.target.open); }, true);
window.addEventListener('popstate', () => { if (state) { clearTimeout(searchTimer); readState(); shown=24; render(); } });

// The entries that the inventory leaves out, by reason, each with a link to the explorer that shows them (the explorer's facets `dat` and `st`).
function showLeftOut(counts) {
  const reasons = [['fara-date', 'fără date', 'dat=fara-date'], ['inactiv', 'inactive', 'st=inactiv']];
  const kinds = [['proiect', 'proiecte', ''], ['resursa', 'resurse', 'k=resursa&']];
  const parts = reasons.map(([key, text, query]) => {
    const links = kinds.filter(([kind]) => Number(counts[key]?.[kind]) > 0)
      .map(([kind, label, prefix]) => `<a href="./?${prefix}${query}">${Number(counts[key][kind])} ${label}</a>`);
    return links.length ? `${text}: ${links.join(', ')}` : '';
  }).filter(Boolean);
  if (!parts.length) return;
  const note = $('#data-left-out');
  note.innerHTML = `Lăsate pe dinafară (vezi în explorator): ${parts.join(' · ')}.`;
  note.hidden = false;
}

async function start() {
  try {
    const response = await fetch(url('inventar/index.json'));
    if (!response.ok) throw new Error('HTTP');
    const inventory = await response.json();
    labels = {variables:{}, providers:{}, subjects:{}, institutions:{}};
    definitions = {variables:{}};
    for (const v of inventory.variables) { labels.variables[v.id]=v.label; definitions.variables[v.id]=v.definition; meta[v.id]={category:v.category, family:v.family, state:v.state || 'propus', ambiguities:v.ambiguities || [], proofs:v.proofs || []}; }
    families = inventory.families || [];
    for (const c of inventory.concepts) {
      if (c.scheme === 'subiect') labels.subjects[c.id]=c.label;
      if (c.scheme === 'institutie') labels.institutions[c.id]=c.label;
    }
    entries = inventory.entries;
    for (const e of entries) {
      e._values = {variables:e.variables.map(v => v.id), providers:Object.keys(e.providers), subjects:e.subjects, institutions:e.institutions};
      for (const p of e._values.providers) labels.providers[p]=p;
      e._text = norm([e.name,e.description,e.keywords,...Object.values(e.providers).flat().map(p => p.name),
        ...groups.flatMap(g => e._values[g.key].map(v => labels[g.key][v]))].join(' '));
    }
    // Do not offer catalogue concepts which no project or resource uses.
    for (const g of groups) for (const v of Object.keys(labels[g.key])) if (!entries.some(e => e._values[g.key].includes(v))) delete labels[g.key][v];
    const projects = entries.filter(e => e.kind === 'proiect').length;
    const fields = entries.filter(e => e.inventory.count).length;
    $('#data-coverage').textContent = `${projects} proiecte · ${entries.length-projects} resurse și liste · ${fields} inventare parțiale`;
    showLeftOut(inventory.leftOut || {});
    readState(); render();
  } catch (error) {
    $('#data-coverage').textContent = 'Inventarul nu s-a putut încărca.';
    $('#data-cards').innerHTML = '<div class="finder-empty"><h2>Datele nu sunt disponibile acum.</h2><p><a href="date/">Încearcă din nou</a> sau <a href="./">revino în explorator</a>.</p></div>';
  }
}
start();
