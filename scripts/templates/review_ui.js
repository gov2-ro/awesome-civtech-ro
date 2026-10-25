'use strict';

/* Local review interface. Every dynamic string reaches the page as text (h() uses text nodes), never as HTML. No external request. */
const TOKEN = document.querySelector('meta[name="review-token"]').content;
const $ = selector => document.querySelector(selector);
const narrow = window.matchMedia('(max-width: 800px)');

const STATE = {deschis: 'Deschis', acceptat: 'Acceptat', respins: 'Respins', amanat: 'Amânat', tehnic: 'Închis tehnic', propus: 'Propus',
  revizuit: 'Revizuit', confirmat: 'Confirmat', exclus: 'Exclus', verificat: 'verificat', schimbat: 'schimbat', indisponibil: 'indisponibil local',
  'fara-amprenta': 'fără amprentă', 'fragment-lipsa': 'fragment lipsă'};
const BASIS = {'declaratie-directa': 'declarație directă', 'observatie-esantion': 'observație din eșantion', 'deductie-din-dovezi': 'deducție din dovezi',
  'parafraza-editoriala': 'parafrază editorială'};
const COPY = {sursa: 'sursă păstrată', documentatie: 'text colectat din documentație', cache: 'pagină din cache'};
const CATEGORY = {identificator: 'Identificator', dimensiune: 'Dimensiune', masura: 'Măsură', 'iesire-derivata': 'Valoare calculată', 'intrare-utilizator': 'Intrare a utilizatorului'};
const OPEN = {providers: new Set(['deschis', 'amanat']), groups: new Set(['propus', 'amanat'])};
const DECIDED = {providers: new Set(['acceptat', 'respins', 'tehnic']), groups: new Set(['revizuit', 'respins'])};
const FILTERS = ['open', 'all', 'decided'];

let state = null;           // /api/state
let filter = 'open';
let current = null;         // {kind, id, data}: the item on the right
let form = {};              // the unsaved input of the provider form
let ticks = new Set();      // ticked deductions of the current group
let notes = {};             // unsaved member notes
let groupNote = '';
let flash = null;           // the message of the last decision, shown under the decision panel until the selection changes

try { const saved = sessionStorage.getItem('review-filter'); if (FILTERS.includes(saved)) filter = saved; } catch (e) { /* storage may be blocked */ }

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'text') el.textContent = value;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, value);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false || kid === '') continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const safeHref = value => /^https?:\/\//i.test(value || '') ? value : '#';
const ext = (url, text) => h('a', {href: safeHref(url), target: '_blank', rel: 'noopener noreferrer'}, text || url, ' ↗');
const chip = (stateKey, text) => h('span', {class: 'chip', dataset: {state: stateKey}}, text || STATE[stateKey] || stateKey);
const basisLabel = key => h('span', {class: 'basis', dataset: {basis: key}}, BASIS[key] || key);

async function api(path, body) {
  const options = body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Review-Token': TOKEN}, body: JSON.stringify(body)};
  const response = await fetch(path, options);
  let data;
  try { data = await response.json(); } catch (e) { data = {error: 'HTTP ' + response.status}; }
  if (!response.ok) throw Object.assign(new Error(data.error || 'HTTP ' + response.status), {reload: !!data.reload, status: response.status});
  return data;
}

function banner(message, reload) {
  const box = $('#banner');
  box.replaceChildren();
  if (!message) { box.hidden = true; return; }
  box.append(message);
  if (reload) box.append(h('button', {type: 'button', class: 'btn', onclick: () => { banner(''); start(); }}, 'Reîncarcă datele'));
  box.hidden = false;
  if (box.scrollIntoView) box.scrollIntoView({block: 'nearest'});
}

// ---- routing: the hash keeps the queue and the selected item ------------------------------------------------------------------------------

function route() {
  const [head, id] = location.hash.slice(1).split('/');
  if (head === 'verificari') return {view: 'checks'};
  if (head === 'grup' || head === 'grupuri') return {view: 'groups', id: head === 'grup' ? id : null};
  return {view: 'providers', id: head === 'furnizor' ? id : null};
}

const queueItems = view => view === 'groups' ? state.groups : state.providers;
const itemPass = (view, item) => filter === 'all' || (filter === 'open' ? OPEN[view] : DECIDED[view]).has(item.stare);
const hashFor = (view, id) => '#' + (view === 'groups' ? 'grup' : 'furnizor') + '/' + id;

function neighbour(step) {
  const r = route();
  if (r.view === 'checks') return null;
  const all = queueItems(r.view);
  const at = all.findIndex(item => item.id === r.id);
  const ordered = step > 0 ? all.slice(at + 1) : all.slice(0, Math.max(at, 0)).reverse();
  return ordered.find(item => itemPass(r.view, item)) || null;
}

// ---- header, list ---------------------------------------------------------------------------------------------------------------------

function renderHeader() {
  const p = state.progress.providers, g = state.progress.groups;
  const deferred = n => n ? ` (${n} amânate)` : '';
  $('#progress').textContent = `Furnizori: ${p.decided} / ${p.total} decise${deferred(p.by_state.amanat)} · Grupuri: ${g.decided} / ${g.total} revizuite${deferred(g.by_state.amanat)}`;
  const v = $('#validation');
  v.dataset.ok = String(state.validation.ok);
  v.textContent = state.validation.ok ? 'Validare: fără erori' : `Validare: ${state.validation.count} erori`;
  v.title = state.validation.errors.join('\n');
  const r = route();
  for (const [id, view] of [['#tab-providers', 'providers'], ['#tab-groups', 'groups'], ['#tab-checks', 'checks']]) {
    if (r.view === view) $(id).setAttribute('aria-current', 'page'); else $(id).removeAttribute('aria-current');
  }
  $('#filter').hidden = r.view === 'checks';
  for (const button of document.querySelectorAll('#filter button')) button.setAttribute('aria-pressed', String(button.dataset.filter === filter));
}

function renderList() {
  const r = route(), list = $('#list');
  list.replaceChildren();
  if (r.view === 'checks') { list.hidden = true; return; }
  list.hidden = false;
  const shown = queueItems(r.view).filter(item => itemPass(r.view, item) || item.id === r.id);
  if (!shown.length) list.append(h('p', {class: 'list-empty'}, 'Niciun element în acest filtru.'));
  for (const item of shown) {
    const label = r.view === 'groups' ? item.label : item.project;
    const detail = r.view === 'groups' ? `${item.members} membri · ${item.confirmat} confirmați · ${item.exclus} excluși` : item.proposal;
    const shownState = item.duplicate_of ? 'Duplicat' : STATE[item.stare];
    list.append(h('a', {class: 'row', href: hashFor(r.view, item.id), 'aria-current': String(item.id === r.id)},
      h('span', {class: 'id'}, item.id), h('span', {class: 'what'}, h('span', {class: 'project'}, label), h('span', {class: 'proposal'}, detail)),
      chip(item.stare, shownState)));
  }
  const active = list.querySelector('[aria-current="true"]');
  if (active && active.scrollIntoView) active.scrollIntoView({block: 'nearest'});
}

// ---- evidence ---------------------------------------------------------------------------------------------------------------------------

function evidencePanel(ev) {
  if (!ev) return h('p', {class: 'muted'}, 'Nicio dovadă legată de acest element.');
  const explain = {
    verificat: 'Amprenta textului păstrat se potrivește cu cea înregistrată, iar fragmentul se află în text.',
    schimbat: `Textul păstrat nu mai are amprenta înregistrată. ${ev.fragment ? (ev.fragment_found ? 'Fragmentul se mai găsește în textul actual; citiți-l din nou.' : 'Fragmentul nu mai apare în textul actual.') : ''}`,
    indisponibil: 'Nu există o copie locală. Deschideți adresa pentru a verifica, apoi decideți.',
    'fara-amprenta': 'Elementul nu înregistrează o amprentă, deci textul păstrat nu poate fi verificat. Evidențierea arată numele furnizorului în text.',
    'fragment-lipsa': 'Amprenta se potrivește, dar fragmentul nu se află în textul păstrat.'};
  const meta = [ev.kind ? 'copie: ' + (COPY[ev.kind] || ev.kind) : null, ev.sha ? 'amprentă text: ' + ev.sha : null, ev.pin ? 'amprentă înregistrată: ' + ev.pin.slice(0, 16) : null].filter(Boolean).join(' · ');
  return h('div', {class: 'evidence', dataset: {state: ev.state}},
    h('div', {class: 'ev-head'}, ext(ev.url), chip(ev.state, ev.label)),
    meta && h('div', {class: 'ev-meta'}, meta),
    ev.fragment && h('p', {class: 'ev-meta'}, 'Fragment înregistrat: ', h('code', {}, ev.fragment)),
    h('p', {class: 'ev-meta'}, explain[ev.state]),
    ev.snippets.map(s => h('pre', {class: 'snippet'}, s.cut_before ? '… ' : '', s.before, h('mark', {}, s.match), s.after, s.cut_after ? ' …' : '')));
}

// ---- providers ---------------------------------------------------------------------------------------------------------------------------

function providerDetail(item) {
  const root = h('div', {});
  root.append(h('a', {class: 'back', href: '#furnizori'}, '← Lista'));
  root.append(h('h2', {}, `${item.id} · ${item.project.name}`));
  root.append(h('div', {class: 'chips'}, chip(item.stare, item.duplicate_of ? 'Duplicat al ' + item.duplicate_of : null), chip('prioritate', 'prioritate ' + item.prioritate),
    item.head.changed && h('span', {class: 'chip', dataset: {changed: '1'}}, 'modificat față de HEAD')));
  root.append(h('div', {class: 'links'}, ext(item.project.catalogue_url, 'Fișa din catalog'), item.project.url && ext(item.project.url, 'Site-ul proiectului')));
  for (const text of item.warnings) root.append(h('p', {class: 'warn'}, text));
  root.append(h('h3', {}, 'Propunere'));
  root.append(h('dl', {class: 'facts'}, h('dt', {}, 'Valoare originală'), h('dd', {}, h('blockquote', {}, item.valoare_originala)),
    h('dt', {}, 'Propunere'), h('dd', {}, item.propunere), h('dt', {}, 'Motiv'), h('dd', {}, item.motiv),
    item.decizie_editor && [h('dt', {}, 'Decizia curentă'), h('dd', {}, item.decizie_editor)]));
  root.append(h('h3', {}, 'Dovadă'), evidencePanel(item.evidence));
  root.append(h('h3', {}, 'Relația în relatii.csv'));
  if (item.row) {
    root.append(h('dl', {class: 'facts'}, h('dt', {}, 'Rând'), h('dd', {}, `${item.row.id} · ${item.row.obiect_literal || item.row.obiect} · ${item.row.stare}`),
      h('dt', {}, 'camp_sursa'), h('dd', {}, item.row.camp_sursa), h('dt', {}, 'valoare_sursa'), h('dd', {}, item.row.valoare_sursa),
      h('dt', {}, 'Origine'), h('dd', {}, item.row_origin === 'propunere' ? 'numit în propunere' : 'adăugat de această decizie')));
  } else {
    root.append(h('p', {}, `Rând nou ${item.new_row_id}: se adaugă în relatii.csv numai dacă acceptați.`));
  }
  root.append(h('h3', {}, 'Elemente înrudite'));
  root.append(item.related.length ? h('ul', {class: 'plain'}, item.related.map(r => h('li', {},
    h('a', {href: hashFor('providers', r.id)}, r.id), ' · ', r.proposal, ' ', chip(r.stare), ' ', r.same_provider && h('span', {class: 'tag'}, 'același furnizor'))))
    : h('p', {class: 'muted'}, 'Niciun alt element pentru acest proiect.'));
  root.append(h('h3', {}, 'Surse acceptate acum pentru proiect'));
  root.append(item.accepted.length ? h('ul', {class: 'plain'}, item.accepted.map(a => h('li', {}, `${a.id} · ${a.name} · `, ext(a.evidence))))
    : h('p', {class: 'muted'}, 'Nicio sursă acceptată încă (lipsa nu înseamnă că proiectul nu are surse).'));
  root.append(h('div', {id: 'decision', class: 'decision'}));
  return root;
}

function flashLine(id) { return h('p', {id, class: 'status', role: 'status', dataset: {kind: flash ? flash.kind : ''}}, flash ? flash.text : ''); }

function consequence(item) {
  const name = form.name || item.prefill.name, project = item.project.name, row = item.row;
  switch (form.action) {
    case 'accept':
      return `Acceptarea adaugă «${name}» ca sursă de date pentru ${project} pe site-ul public. ` +
        (row ? `Rândul ${row.id} din relatii.csv devine «acceptat».` : `Rândul nou ${item.new_row_id} se adaugă în relatii.csv.`);
    case 'reject':
      return `Respingerea nu adaugă nimic pe site-ul public${item.stare === 'acceptat' ? '; sursa acceptată înainte dispare de acolo' : ''}. ` +
        (row ? `Rândul ${row.id} devine «respins» sau, dacă acest element l-a adăugat și nicio înregistrare git nu îl conține, se șterge.` : 'Nu există niciun rând în relatii.csv.');
    case 'defer':
      return 'Amânarea nu schimbă site-ul public. Elementul rămâne în coadă ca «amânat»' + (row ? `; rândul ${row.id} rămâne «propus».` : '.');
    case 'duplicate':
      return `Elementul se închide ca duplicat al lui ${form.other || '…'} (stare «tehnic», fără decizie). Nu se adaugă nicio sursă pe site-ul public.`;
    case 'reset':
      return `Resetarea readuce elementul${row ? ` și rândul ${row.id}` : ''} la valorile din HEAD; un rând adăugat de acest element se șterge.`;
    default:
      return '';
  }
}

function renderDecision(item) {
  const box = $('#decision');
  if (!box) return;
  box.replaceChildren();
  box.append(h('h3', {}, 'Decizie'));
  const buttons = [['accept', 'Accept'], ['reject', 'Resping'], ['defer', 'Amân'], ['duplicate', 'Duplicat…'], ['reset', 'Resetează']];
  box.append(h('div', {class: 'actions', role: 'group', 'aria-label': 'Acțiuni'}, buttons.map(([action, text]) => h('button', {
    type: 'button', class: 'btn', 'aria-pressed': String(form.action === action), dataset: {action},
    disabled: action === 'reset' && !item.head.changed,
    onclick: () => { form.action = form.action === action ? null : action; renderDecision(item); }}, text))));
  if (!item.head.changed) box.append(h('p', {class: 'ev-meta'}, 'Resetează e disponibil după o modificare față de HEAD.'));
  box.append(flashLine('p-status'));
  if (!form.action) return;
  const input = (label, key, props) => {
    const handlers = {oninput: event => { form[key] = event.target.value; $('#consequence').textContent = consequence(item); }};
    return h('label', {class: 'field'}, h('span', {}, label),
      props.tag === 'textarea' ? h('textarea', {...props, ...handlers}, form[key] ?? '') : h('input', {...props, ...handlers, value: form[key] ?? ''}));
  };
  if (form.action === 'accept') {
    form.name ??= item.prefill.name; form.url ??= item.prefill.url;
    box.append(input('Furnizor (nume canonic)', 'name', {type: 'text', id: 'f-name', maxlength: 200, disabled: item.prefill.name_locked}));
    box.append(input('Adresa dovezii', 'url', {type: 'url', id: 'f-url', maxlength: 500}));
  }
  if (form.action === 'duplicate') {
    const options = item.related.filter(r => r.stare !== 'tehnic');
    form.other ??= (options.find(r => r.same_provider) || options[0] || {}).id || '';
    box.append(h('label', {class: 'field'}, h('span', {}, 'Duplicat al elementului'), h('select', {id: 'f-other', onchange: event => { form.other = event.target.value; $('#consequence').textContent = consequence(item); }},
      h('option', {value: ''}, '— alegeți —'), options.map(r => h('option', {value: r.id, selected: r.id === form.other}, `${r.id} · ${r.proposal} (${STATE[r.stare]})`)))));
  }
  if (form.action !== 'reset') box.append(input('Notă (obligatorie)', 'note', {tag: 'textarea', id: 'f-note', maxlength: 1500}));
  box.append(h('p', {id: 'consequence', class: 'consequence', role: 'status'}, consequence(item)));
  box.append(h('div', {class: 'actions'}, h('button', {type: 'button', class: 'btn primary', id: 'f-save', onclick: () => saveProvider(item)}, 'Salvează decizia'),
    h('button', {type: 'button', class: 'btn', onclick: () => { form = {}; renderDecision(item); }}, 'Renunță')));
}

async function saveProvider(item) {
  const body = {action: form.action, note: form.note || '', name: form.name || '', url: form.url || '', duplicate_of: form.other || '', hashes: item.hashes};
  $('#f-save').disabled = true;
  try {
    const answer = await api(`/api/provider/${item.id}/decide`, body);
    state = answer.state;
    form = {};
    flash = {text: answer.message, kind: 'ok'};
    current = {kind: 'providers', id: item.id, data: answer.item};
    banner('');
    renderAll();
  } catch (error) {
    $('#f-save').disabled = false;
    flash = {text: error.message, kind: 'error'};
    const status = $('#p-status');
    status.textContent = error.message;
    status.dataset.kind = 'error';
    if (error.reload) banner(error.message, true);
  }
}

// ---- groups --------------------------------------------------------------------------------------------------------------------------------

function exampleTable(reach) {
  if (!reach.examples.length) return h('p', {class: 'muted'}, 'Niciun câmp din inventarul păstrat nu corespunde (membrul poate fi exclus sau câmpul a dispărut).');
  const type = e => e.declared_type ? [e.declared_type].flat().join(', ') : (e.observed_types.length ? 'observat: ' + e.observed_types.join(', ') : 'tip neprecizat');
  return h('table', {class: 'examples'}, h('thead', {}, h('tr', {}, ['Câmp', 'Cale', 'Rol', 'Reprezentare', 'Sursă'].map(t => h('th', {}, t)))),
    h('tbody', {}, reach.examples.map(e => h('tr', {}, h('td', {}, h('code', {}, e.name)), h('td', {}, h('code', {}, e.path)), h('td', {}, e.role),
      h('td', {}, type(e) + (e.unit ? ' · ' + e.unit : '') + (e.format ? ' · ' + e.format : '')), h('td', {}, ext(e.source_url, 'sursă'))))));
}

function memberCard(group, member) {
  const open = ['propus', 'amanat'].includes(group.stare);
  const noteInput = h('input', {type: 'text', maxlength: 1500, value: notes[member.number] || '', placeholder: 'Notă (obligatorie la excludere)', 'aria-label': `Notă pentru membrul ${member.number}`,
    oninput: event => { notes[member.number] = event.target.value; }});
  const act = action => async () => {
    try {
      const answer = await api(`/api/group/${group.id}/member/${member.number}`, {action, note: notes[member.number] || '', hashes: group.hashes});
      state = answer.state; delete notes[member.number]; flash = {text: answer.message, kind: 'ok'}; current = {kind: 'groups', id: group.id, data: answer.item}; banner('');
      const y = window.scrollY; renderAll(); window.scrollTo(0, y);
    } catch (error) { flash = {text: error.message, kind: 'error'}; banner(error.message, error.reload); }
  };
  const facts = member.facts.map(f => h('div', {class: f.basis === 'deductie-din-dovezi' ? 'deduction' : ''}, `${f.key}: ${f.value} `, basisLabel(f.basis), evidencePanel(f.evidence)));
  return h('div', {class: 'member', dataset: {state: member.stare, member: String(member.number)}},
    h('h4', {}, `Membrul ${member.number}`, chip(member.stare), member.projects.map(p => h('span', {}, p.name))),
    h('dl', {class: 'facts'},
      member.names.length > 0 && [h('dt', {}, 'Nume'), h('dd', {}, member.names.map(n => h('code', {}, n + ' ')))],
      member.path.length > 0 && [h('dt', {}, 'Cale'), h('dd', {}, member.path.map(n => h('code', {}, n + ' ')))],
      member.source.length > 0 && [h('dt', {}, 'Sursă'), h('dd', {}, member.source.map(u => h('div', {}, ext(u))))],
      member.role.length > 0 && [h('dt', {}, 'Rol'), h('dd', {}, member.role.join(', '))],
      member.context && [h('dt', {}, 'Context'), h('dd', {}, member.context)],
      member.nota && [h('dt', {}, 'Notă'), h('dd', {}, member.nota)],
      member.nota_editor && [h('dt', {}, 'Nota editorului'), h('dd', {}, member.nota_editor)],
      h('dt', {}, 'Câmpuri atinse'), h('dd', {}, `${member.reach.count} în inventarul păstrat (până la 3 exemple)`)),
    exampleTable(member.reach), facts,
    open ? h('div', {class: 'actions'}, noteInput,
      h('button', {type: 'button', class: 'btn', dataset: {act: 'confirm'}, onclick: act('confirm')}, 'Confirm'),
      h('button', {type: 'button', class: 'btn', dataset: {act: 'exclude'}, onclick: act('exclude')}, 'Exclud'),
      member.stare !== 'propus' && h('button', {type: 'button', class: 'btn', dataset: {act: 'reset'}, onclick: act('reset')}, 'Anulează')) : h('p', {class: 'ev-meta'}, 'Membrii se schimbă numai cât timp grupul e «propus» sau «amânat». Resetați grupul întâi.'));
}

function groupDetail(group) {
  const root = h('div', {});
  root.append(h('a', {class: 'back', href: '#grupuri'}, '← Lista'));
  root.append(h('h2', {}, `${group.label} `, h('code', {}, group.id)));
  root.append(h('div', {class: 'chips'}, chip(group.stare), group.categorie && h('span', {class: 'chip'}, CATEGORY[group.categorie] || group.categorie),
    group.head.changed && h('span', {class: 'chip', dataset: {changed: '1'}}, 'modificat față de HEAD'), group.data_revizie && h('span', {class: 'chip'}, 'revizuit la ' + group.data_revizie)));
  root.append(h('h3', {}, 'Definiție'));
  root.append(h('p', {}, group.definition, ' ', basisLabel(group.basis)));
  if (group.decizie_editor) root.append(h('p', {}, h('strong', {}, 'Decizia curentă: '), group.decizie_editor));
  if (group.proofs.length) {
    root.append(h('h3', {}, 'Dovezile definiției'));
    for (const proof of group.proofs) root.append(h('div', {}, basisLabel(proof.basis), evidencePanel(proof.evidence)));
  }
  root.append(h('h3', {}, 'Ambiguități'));
  root.append(group.ambiguities.length ? h('ul', {class: 'plain'}, group.ambiguities.map(a => h('li', {}, a))) : h('p', {class: 'muted'}, 'Nicio ambiguitate notată.'));
  root.append(h('h3', {}, `Membri (${group.members.length})`));
  for (const member of group.members) root.append(memberCard(group, member));
  root.append(h('div', {id: 'decision', class: 'decision'}));
  return root;
}

function unticked(group) { return group.deductions.filter(d => !ticks.has(d.id)); }

function reviewReasons(group) {
  const reasons = [...group.blockers];
  const missing = unticked(group).length;
  if (missing) reasons.push(`${missing} deducții nu sunt bifate ca verificate.`);
  return reasons;
}

function updateReviewButton(group) {
  const button = $('#g-revizuit'), reason = $('#g-reason');
  if (!button) return;
  const reasons = reviewReasons(group);
  button.disabled = reasons.length > 0;
  reason.replaceChildren(...reasons.map(text => h('p', {class: 'reason'}, text)));
}

function renderGroupDecision(group) {
  const box = $('#decision');
  box.replaceChildren(h('h3', {}, 'Decizia pentru grup'));
  if (group.deductions.length) {
    box.append(h('p', {}, 'Deducții de verificat înainte de «Revizuit»:'));
    for (const d of group.deductions) {
      box.append(h('label', {class: 'deduction tick'}, h('input', {type: 'checkbox', dataset: {tick: d.id}, checked: ticks.has(d.id),
        onchange: event => { if (event.target.checked) ticks.add(d.id); else ticks.delete(d.id); updateReviewButton(group); }}), ' ', d.text, ' ', basisLabel('deductie-din-dovezi')));
    }
  }
  box.append(h('label', {class: 'field'}, h('span', {}, 'Notă (obligatorie)'), h('textarea', {id: 'g-note', maxlength: 1500, oninput: event => { groupNote = event.target.value; }}, groupNote)));
  const go = action => async () => {
    try {
      const answer = await api(`/api/group/${group.id}/decide`, {action, note: groupNote, ticked: [...ticks], hashes: group.hashes});
      state = answer.state; groupNote = ''; flash = {text: answer.message, kind: 'ok'}; current = {kind: 'groups', id: group.id, data: answer.item}; banner('');
      renderAll();
    } catch (error) {
      flash = {text: error.message, kind: 'error'};
      const status = $('#g-status');
      if (status) { status.textContent = error.message; status.dataset.kind = 'error'; }
      if (error.reload) banner(error.message, true);
    }
  };
  box.append(h('div', {class: 'actions'}, h('button', {type: 'button', class: 'btn primary', id: 'g-revizuit', 'aria-describedby': 'g-reason', onclick: go('revizuit')}, 'Revizuit'),
    h('button', {type: 'button', class: 'btn', id: 'g-respins', onclick: go('respins')}, 'Resping'),
    h('button', {type: 'button', class: 'btn', id: 'g-amanat', onclick: go('amanat')}, 'Amân'),
    h('button', {type: 'button', class: 'btn', id: 'g-reset', disabled: !group.head.changed, onclick: go('reset')}, 'Resetează')));
  box.append(h('div', {id: 'g-reason'}), flashLine('g-status'));
  updateReviewButton(group);
}

// ---- checks ---------------------------------------------------------------------------------------------------------------------------------

async function renderChecks() {
  const detail = $('#detail');
  detail.replaceChildren(h('h2', {}, 'Verificări și consecințe'));
  const results = h('div', {id: 'check-results'});
  const run = h('button', {type: 'button', class: 'btn primary', id: 'run-checks', onclick: async () => {
    run.disabled = true; results.replaceChildren(h('p', {}, 'Se rulează…'));
    try {
      const answer = await api('/api/check', {});
      results.replaceChildren(...answer.checks.map(c => h('div', {class: 'check', dataset: {ok: String(c.code === 0)}},
        h('strong', {}, c.name), ' · cod de ieșire ', h('code', {}, String(c.code)), h('pre', {}, c.tail.join('\n')))));
    } catch (error) { results.replaceChildren(h('p', {class: 'status', dataset: {kind: 'error'}}, error.message)); }
    run.disabled = false;
  }}, 'Rulează verificările');
  detail.append(h('p', {}, 'Rulează validate.py --publication, inventory.py --check și inventory_report.py --check în procese separate.'), run, results);
  const git = h('div', {id: 'git-panel'}, h('p', {class: 'muted'}, 'Se citește git…'));
  detail.append(git);
  try {
    const data = await api('/api/git');
    git.replaceChildren(h('h3', {}, 'Consecința publică'));
    if (!data.available) git.append(h('p', {class: 'muted'}, 'git nu este disponibil aici: nu se poate compara cu HEAD.'));
    else if (!data.public.lines.length) git.append(h('p', {}, 'Nicio schimbare a surselor de date acceptate față de HEAD.'));
    else git.append(h('ul', {class: 'plain', id: 'public-diff'}, data.public.lines.map(l => h('li', {class: l.sign === '+' ? 'diff-add' : 'diff-del'}, `${l.sign} ${l.slug}: ${l.name} (${l.evidence})`))));
    git.append(h('h3', {}, 'Fișiere modificate'));
    git.append(data.files.length ? h('ul', {class: 'plain'}, data.files.map(f => h('li', {}, h('code', {}, `${f.status} ${f.path}`)))) : h('p', {class: 'muted'}, 'Niciun fișier de revizuire modificat față de HEAD.'));
    if (data.stat) git.append(h('pre', {class: 'block'}, data.stat));
    git.append(h('h3', {}, 'Comenzi sugerate (nu se rulează de aici)'), h('pre', {class: 'block', id: 'commands'}, data.commands.join('\n')));
  } catch (error) { git.replaceChildren(h('p', {class: 'status', dataset: {kind: 'error'}}, error.message)); }
}

// ---- rendering ----------------------------------------------------------------------------------------------------------------------------------

function renderDetail() {
  const r = route(), detail = $('#detail');
  document.body.dataset.view = r.view === 'checks' ? 'checks' : r.id ? 'detail' : 'list';
  if (r.view === 'checks') { renderChecks(); return; }
  if (!r.id) { detail.replaceChildren(h('p', {class: 'muted'}, 'Alegeți un element din listă. Tastele j și k trec la următorul și la precedentul.')); return; }
  if (!current || current.id !== r.id || current.kind !== r.view) { detail.replaceChildren(h('p', {class: 'muted'}, 'Se încarcă…')); return; }
  if (r.view === 'providers') { detail.replaceChildren(providerDetail(current.data)); renderDecision(current.data); } else { detail.replaceChildren(groupDetail(current.data)); renderGroupDecision(current.data); }
}

function renderAll() { renderHeader(); renderList(); renderDetail(); }

async function select() {
  const r = route();
  if (!state) return;
  if (r.view !== 'checks' && !r.id && !narrow.matches) {
    const first = queueItems(r.view).find(item => itemPass(r.view, item));
    if (first) { history.replaceState(null, '', hashFor(r.view, first.id)); return select(); }
  }
  renderHeader(); renderList();
  if (r.view === 'checks' || !r.id) { renderDetail(); return; }
  if (!current || current.id !== r.id || current.kind !== r.view) {
    form = {}; ticks = new Set(); notes = {}; groupNote = ''; flash = null;
    renderDetail();
    try {
      const data = await api(`/api/${r.view === 'groups' ? 'group' : 'provider'}/${encodeURIComponent(r.id)}`);
      if (route().id !== r.id) return;
      current = {kind: r.view, id: r.id, data};
      banner('');
    } catch (error) { current = null; $('#detail').replaceChildren(h('p', {class: 'status', dataset: {kind: 'error'}}, error.message)); return; }
  }
  renderDetail();
  if (narrow.matches) $('#detail').focus({preventScroll: true});
}

async function start() {
  try {
    state = await api('/api/state');
    current = null;
    banner('');
    await select();
  } catch (error) { banner('Nu s-au putut încărca datele: ' + error.message, true); }
}

window.addEventListener('hashchange', select);
for (const button of document.querySelectorAll('#filter button')) {
  button.addEventListener('click', () => {
    filter = button.dataset.filter;
    try { sessionStorage.setItem('review-filter', filter); } catch (e) { /* ignore */ }
    renderHeader(); renderList();
  });
}
document.addEventListener('keydown', event => {
  if (event.ctrlKey || event.metaKey || event.altKey || !['j', 'k'].includes(event.key)) return;
  const target = event.target;
  if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) return;
  const next = neighbour(event.key === 'j' ? 1 : -1);
  if (next) location.hash = hashFor(route().view, next.id);
});
start();
