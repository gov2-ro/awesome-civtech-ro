'use strict';

const $ = (s, el = document) => el.querySelector(s);
const slot = name => $(`[data-slot="${name}"]`);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const plural = (n, one, many) => n === 1 ? `1 ${one}` : `${n}${n % 100 >= 20 || n % 100 === 0 ? ' de' : ''} ${many}`;
const hue = s => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % 360;
const initials = name => {
  const w = name.replace(/\.(ro|eu|org|com|info|ai|help)$/i, '').split(/[\s\-–—·.:]+/).filter(x => /^[\p{L}\d]/u.test(x));
  return (w.length > 1 ? w[0][0] + w[1][0] : (w[0] || '?').slice(0, 2)).toUpperCase();
};
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const ICON = {
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  out: '<svg viewBox="0 0 24 24"><path d="M7 17 17 7M8 7h9v9"/></svg>',
  code: '<svg viewBox="0 0 24 24"><path d="m8 7-5 5 5 5M16 7l5 5-5 5"/></svg>',
  grid: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/></svg>',
  list: '<svg viewBox="0 0 24 24"><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/></svg>',
  archive: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10h14V9M10 13h4"/></svg>',
};

const TITLES = ['CivTech România', 'Cu datele pe față', 'Soros2 suntem noi', 'Prinosul poporului', 'Programatori pentru patrie',
  'Minirevoluția digitală', 'Împreună suntem mai mulți', 'Guvernul paralel'];

const STATUS = {
  activ: { label: 'Activ', cls: 'ok', group: 'activ' },
  offline: { label: 'Offline', cls: 'bad', group: 'inactiv' },
  arhivat: { label: 'Arhivat', cls: 'bad', group: 'inactiv' },
  necunoscut: { label: 'Neconfirmat', cls: 'warn', group: 'neconfirmat' },
  neverificat: { label: 'Neverificat', cls: 'warn', group: 'neconfirmat' },
};
const SORTS = [['domeniu', 'Pe domenii'], ['az', 'A–Z'], ['top', 'Active și relevante'], ['relevanta', 'Relevanță'], ['nou', 'Cele mai noi'], ['recent', 'Actualizate recent'], ['random', 'Aleatoriu']];
const MIN_Q = 3;
// ina=1 shows inactive projects (hidden by default); a and s are kept for URLs but have no UI for now.
const DEFAULTS = { k: 'proiect', q: '', d: '', t: '', kw: '', c: '', org: '', a: '', s: '', cod: '', civ: '', nou: '', ina: '', v: '', o: '', p: '' };
const FILTERS = ['q', 'd', 't', 'kw', 'c', 'org', 'a', 's', 'cod', 'civ', 'nou', 'ina'];
const FRESH_DAYS = 183, LAUNCH_DAYS = 60;

let DB = null, TAX = null, seed = Math.random();
let title = TITLES[0];
const state = { ...DEFAULTS };
const closed = new Set(store.get('ct.closed', ['cuvinte']));
let lastFocus = null;

const isInactive = it => STATUS[it.status].group === 'inactiv';
const listOf = key => state[key] ? state[key].split(',') : [];
const tips = () => listOf('t');
const kwLabel = k => k.replace(/-/g, ' ');
const query = () => state.q.length >= MIN_Q ? state.q : '';

/* ---------- URL state ---------- */
// Projects read best grouped by domain; the short org/resource lists read best flat.
const defaultSort = () => state.k === 'proiect' ? 'domeniu' : 'az';
function readURL() {
  const u = new URLSearchParams(location.search);
  for (const k of Object.keys(DEFAULTS)) state[k] = u.get(k) ?? DEFAULTS[k];
  if (!state.o) state.o = defaultSort();
}
function writeURL(push = false) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(state)) if (v && v !== (k === 'o' ? defaultSort() : DEFAULTS[k])) u.set(k, v);
  const url = (u.toString() ? '?' + u : location.pathname) + location.hash;
  if (url !== location.search + location.hash) history[push ? 'pushState' : 'replaceState'](null, '', url);
}
const hrefFor = slug => { const u = new URLSearchParams(location.search); u.set('p', slug); return '?' + u; };

/* ---------- filtering ---------- */
function matches(it, skip) {
  if (it.kind !== state.k) return false;
  if (skip !== 'd' && state.d && it.domeniu !== state.d) return false;
  if (skip !== 't' && state.t && !tips().some(t => it.tips.includes(t))) return false;
  if (skip !== 'kw' && state.kw && !listOf('kw').some(k => it.keywords.includes(k))) return false;
  if (skip !== 'c' && state.c && it.oras !== state.c) return false;
  if (skip !== 'org' && state.org && !it._orgs.includes(state.org)) return false;
  if (skip !== 'a' && state.a && it.acoperire !== state.a) return false;
  if (skip !== 's' && state.s && STATUS[it.status].group !== state.s) return false;
  if (skip !== 'cod' && state.cod && !it.code) return false;
  if (skip !== 'civ' && state.civ && !it.civictech) return false;
  if (skip !== 'nou' && state.nou && !isFresh(it)) return false;
  if (skip !== 'ina' && !state.ina && isInactive(it)) return false;
  const q = query();
  if (q) {
    const terms = norm(q).split(/\s+/).filter(Boolean);
    if (!terms.every(t => it._hay.includes(t))) return false;
  }
  return true;
}
const kindItems = () => DB.items.filter(i => i.kind === state.k);
const countBy = (skip, key) => {
  const c = {};
  // key may return several values (an item with two tips counts under both).
  for (const it of DB.items) if (matches(it, skip)) for (const v of [key(it)].flat()) c[v] = (c[v] || 0) + 1;
  return c;
};
const activeFilterCount = () => ['d', 'c', 'org', 'a', 's', 'cod', 'civ', 'nou', 'ina'].filter(k => state[k]).length + tips().length + listOf('kw').length;
const rank = it => ({ activ: 0, neconfirmat: 1, inactiv: 2 })[STATUS[it.status].group];
const byName = (a, b) => a._sort.localeCompare(b._sort);
// Last sign of life: the last update, or the launch date when that is later. A recent launch thus
// sorts like a recent update. Entries with neither go last.
const lastSign = it => [it.updated, isLaunched(it) ? it.since : ''].sort().at(-1) || '';
// "Active și relevante": the build's relevance score, discounted by time since the last sign of life
// (half-life ~8 months; unknown counts as old), plus a small bump for a launch in the last 60 days.
function topScore(it) {
  const d = lastSign(it);
  const recency = d ? Math.exp(-daysSince(d) / 365) : .25;
  return it.score * (.5 + .5 * recency) + (isLaunched(it) ? 8 : 0);
}
function sorted(list) {
  if (state.o === 'random') {
    const r = it => Math.sin(it.id * 9301 + seed * 49297) % 1;
    return [...list].sort((a, b) => r(a) - r(b));
  }
  if (state.o === 'top') return [...list].sort((a, b) => topScore(b) - topScore(a) || byName(a, b));
  if (state.o === 'domeniu') return [...list].sort((a, b) => rank(a) - rank(b) || lastSign(b).localeCompare(lastSign(a)) || byName(a, b));
  if (state.o === 'relevanta') return [...list].sort((a, b) => b.score - a.score || byName(a, b));
  // Entries with no known start date go last.
  if (state.o === 'nou') return [...list].sort((a, b) => (b.since || '0').localeCompare(a.since || '0') || byName(a, b));
  if (state.o === 'recent') return [...list].sort((a, b) => (b.updated || '').localeCompare(a.updated || '') || byName(a, b));
  return [...list].sort((a, b) => rank(a) - rank(b) || byName(a, b));
}

/* ---------- small renderers ---------- */
function media(it) {
  const im = it.img;
  if (im) {
    return `<div class="media media-${im.kind}" style="--c:${im.color}"><img src="${esc(im.src)}" alt="" loading="lazy" decoding="async" width="${im.w}" height="${im.h}"></div>`;
  }
  const icon = it.icon ? `<img class="ico" src="${esc(it.icon)}" alt="" loading="lazy">` : `<span class="mark">${esc(initials(it.name))}</span>`;
  return `<div class="media media-none" style="--h:${hue(it.domain || it.name)}">${icon}<span class="dom">${esc(it.domain || '—')}</span></div>`;
}
function thumb(it) {
  const im = it.img;
  if (im && im.kind !== 'logo') return `<div class="thumb" style="--c:${im.color}"><img src="${esc(im.src)}" alt="" loading="lazy" decoding="async"></div>`;
  if (im) return `<div class="thumb logo" style="--c:${im.color}"><img src="${esc(im.src)}" alt="" loading="lazy"></div>`;
  if (it.icon) return `<div class="thumb icon"><img src="${esc(it.icon)}" alt="" loading="lazy"></div>`;
  return `<div class="thumb none" style="--h:${hue(it.domain || it.name)}" aria-hidden="true">${esc(initials(it.name))}</div>`;
}
const tipLabels = it => it.tips.map(t => TAX.tip[t]?.label).filter(Boolean);
const placeLabel = it => it.acoperire === 'local' ? (it.oras || 'Local') : '';
function metaLine(it, withDomain) {
  const st = STATUS[it.status];
  const parts = [...tipLabels(it), placeLabel(it)];
  if (withDomain) parts.unshift(TAX.domeniu[it.domeniu]?.short);
  let html = parts.filter(Boolean).map(esc).join(' · ');
  if (st.group !== 'activ') html += ` <span class="status-tag ${st.cls}">· ${st.label}</span>`;
  else if (it.stale) html += ` <span class="status-tag warn">· neactualizat din ${it.stale}</span>`;
  return html;
}
const statusDot = it => `<span class="dot ${STATUS[it.status].cls}" title="${STATUS[it.status].label}"></span>`;
const codeTag = it => it.code ? `<span class="code-tag" title="Cod sursă deschis">${ICON.code}cod</span>` : '';
const newTag = it => !isFresh(it) ? ''
  : `<span class="code-tag new-tag${isLaunched(it) ? ' launch' : ''}" title="Apărut acum ${esc(age(it))} · ${esc(ageTitle(it))}">${isLaunched(it) ? 'lansat recent' : 'nou'}</span>`;
const blurb = it => it.tagline || it.desc;
const clip = (s, n) => s.length > n ? s.slice(0, s.lastIndexOf(' ', n) > n * .6 ? s.lastIndexOf(' ', n) : n).replace(/[\s,.;:–-]+$/, '') + '…' : s;
// Native tooltip: the start of the long description, when there is more to say than the tagline.
const hint = it => { const d = it.desc && it.desc !== it.tagline ? it.desc : ''; return d ? ` title="${esc(clip(d, 220))}"` : ''; };

/* ---------- dates ---------- */
const DAY = 864e5;
function span(days) {
  if (days < 1) return 'azi';
  if (days < 31) return plural(Math.floor(days), 'zi', 'zile');
  if (days < 365) return plural(Math.floor(days / 30.4), 'lună', 'luni');
  return plural(Math.floor(days / 365.25), 'an', 'ani');
}
const daysSince = d => (Date.now() - Date.parse(d)) / DAY;
// "Fresh": first seen less than FRESH_DAYS ago, by the same date the Vechime column shows.
const isFresh = it => !!it.since && daysSince(it.since) < FRESH_DAYS;
const isLaunched = it => !!it.since && daysSince(it.since) < LAUNCH_DAYS;
const age = it => it.since ? span(daysSince(it.since)) : '';
const updatedLabel = it => !it.updated ? '' : daysSince(it.updated) < 1 ? 'azi' : `acum ${span(daysSince(it.updated))}`;
const UPDATED_SRC = { cod: 'ultimul commit', sitemap: 'sitemap', server: 'antetul Last-Modified', arhiva: 'ultima arhivare Wayback' };
const SINCE_SRC = { arhiva: 'prima arhivare Wayback', cod: 'crearea depozitului de cod', certificat: 'primul certificat TLS al domeniului' };
const ageTitle = it => !it.since ? 'Necunoscut' : it.sinceSrc ? `${it.since} · după ${SINCE_SRC[it.sinceSrc] || it.sinceSrc}` : it.since;
const updatedTitle = it => it.updated ? `${it.updated} · după ${UPDATED_SRC[it.updatedSrc] || it.updatedSrc}` : 'Necunoscut';

// Cards and rows are not links themselves: the name is (stretched over the whole item, opening the
// detail panel), so the project's own site can sit inside as a second, real link.
const extHref = it => (!isInactive(it) && it.url) || it.wayback || '';
function extLink(it, label, cls = '') {
  const href = extHref(it);
  if (!href) return label ? `<span class="${cls}">${label}</span>` : '';
  const title = isInactive(it) ? 'Vezi în arhivă' : `Deschide ${it.domain}`;
  return `<a class="ext ${cls}" href="${esc(href)}" target="_blank" rel="noopener" title="${esc(title)}"${label ? '' : ` aria-label="${esc(title)}"`}>${label}${ICON.out}</a>`;
}
const nameLink = it => `<a class="stretch" href="${hrefFor(it.slug)}">${esc(it.name)}</a>`;

function card(it, withDomain) {
  return `<div class="card${isInactive(it) ? ' inactive' : ''}" data-open="${it.slug}"${hint(it)}>
    ${media(it)}
    <div class="card-body">
      <div class="meta">${metaLine(it, withDomain)}</div>
      <h3>${nameLink(it)}</h3>
      ${blurb(it) ? `<p class="tagline">${esc(blurb(it))}</p>` : ''}
      <div class="foot">${statusDot(it)}${extLink(it, `<span class="dom">${esc(it.domain)}</span>`)}${newTag(it)}${codeTag(it)}</div>
    </div>
  </div>`;
}
function row(it, withDomain) {
  const desc = it.tagline && it.desc && it.desc !== it.tagline ? it.desc : '';
  const dates = [age(it) && `${age(it)} vechime`, updatedLabel(it) && `actualizat ${updatedLabel(it)}`].filter(Boolean).join(' · ');
  return `<div class="row${isInactive(it) ? ' inactive' : ''}" data-open="${it.slug}"${hint(it)}>
    ${thumb(it)}
    <div class="row-main">
      <div class="row-title">${nameLink(it)} ${statusDot(it)} ${newTag(it)} ${codeTag(it)} ${extLink(it, '', 'ext-m')}</div>
      ${blurb(it) ? `<div class="row-tag">${esc(blurb(it))}</div>` : ''}
      ${desc ? `<div class="row-desc">${esc(clip(desc, 160))}</div>` : ''}
      ${it.keywords.length ? `<div class="row-kw">${it.keywords.map(k => `<span>#${esc(kwLabel(k))}</span>`).join('')}</div>` : ''}
      <div class="meta meta-m">${metaLine(it, withDomain)}${dates ? ` · ${esc(dates)}` : ''}</div>
    </div>
    <div class="row-side" title="${esc(ageTitle(it))}">${esc(age(it) || '—')}</div>
    <div class="row-side${it.updatedSrc === 'arhiva' ? ' faint' : ''}" title="${esc(updatedTitle(it))}">${esc(updatedLabel(it) || '—')}</div>
    <div class="row-side">${extLink(it, `<span class="dom">${esc(it.domain)}</span>`)}</div>
  </div>`;
}
const LIST_HEAD = '<div class="list-head" aria-hidden="true"><span>Proiect</span><span>Vechime</span><span>Actualizat</span><span>Site</span></div>';

/* ---------- filters ---------- */
function renderTabs() {
  // Counters show what is alive, not what was ever catalogued.
  const c = {};
  for (const it of DB.items) if (!isInactive(it)) c[it.kind] = (c[it.kind] || 0) + 1;
  slot('tabs').innerHTML = DB.taxonomy.kinds.map(k =>
    `<button class="tab" data-act="kind" data-val="${k.key}" ${state.k === k.key ? 'aria-current="page"' : ''}>${esc(k.label)}<span class="n">${c[k.key] || 0}</span></button>`
  ).join('');
}

function facet(id, label, body) {
  return `<details class="facet" data-facet="${id}" ${closed.has(id) ? '' : 'open'}><summary><span class="kicker">${label}</span></summary>${body}</details>`;
}
function facetsHTML() {
  const mine = kindItems();
  const has = (pred) => mine.some(pred);
  const dC = countBy('d', i => i.domeniu), tC = countBy('t', i => i.tips);
  const out = [];

  // Only choices that exist for the current tab are offered.
  const tagFacet = (id, label, key, options, counts) => {
    const sel = listOf(key);
    return facet(id, label, `<div class="tags">${options.map(([val, text]) => {
      const on = sel.includes(val), n = counts[val] || 0;
      return `<button class="tag" data-act="multi" data-key="${key}" data-val="${esc(val)}" aria-pressed="${on}" ${!n && !on ? 'disabled' : ''}>${esc(text)}<span class="n">${n}</span></button>`;
    }).join('')}</div>`);
  };
  const tipList = DB.taxonomy.tipuri.filter(t => has(i => i.tips.includes(t.key)));
  if (tipList.length > 1) out.push(tagFacet('tip', 'Tip', 't', tipList.map(t => [t.key, t.label]), tC));
  const domList = DB.taxonomy.domenii.filter(d => has(i => i.domeniu === d.key));
  if (domList.length > 1) {
    const total = DB.items.filter(i => matches(i, 'd')).length;
    const opt = (val, label, n) => `<button class="fopt radio" data-act="set" data-key="d" data-val="${val}" aria-pressed="${state.d === val}" ${!n && state.d !== val ? 'disabled' : ''}>
      <span class="l">${esc(label)}</span><span class="n">${n || 0}</span></button>`;
    out.push(facet('domeniu', 'Domeniu', `<div class="flist">${opt('', 'Toate', total)}${domList.map(d => opt(d.key, d.label, dC[d.key])).join('')}</div>`));
  }

  const kwC = {};
  for (const it of DB.items) if (matches(it, 'kw')) for (const k of it.keywords) kwC[k] = (kwC[k] || 0) + 1;
  const kwAll = {};
  for (const it of mine) for (const k of it.keywords) kwAll[k] = (kwAll[k] || 0) + 1;
  const kwList = Object.keys(kwAll).sort((a, b) => kwAll[b] - kwAll[a] || a.localeCompare(b));
  if (kwList.length) out.push(tagFacet('cuvinte', 'Cuvinte cheie', 'kw', kwList.map(k => [k, kwLabel(k)]), kwC));

  const toggles = [];
  const toggle = (key, label, checked, n) => toggles.push(`<label class="toggle"><input type="checkbox" data-act="toggle" data-key="${key}" ${checked ? 'checked' : ''}><span class="l">${label}</span>${n != null ? `<span class="n">${n}</span>` : ''}</label>`);
  if (has(i => i.code) && has(i => !i.code)) toggle('cod', 'Doar cu cod sursă deschis', state.cod, DB.items.filter(i => matches(i, 'cod') && i.code).length);
  if (has(isFresh) && has(i => !isFresh(i))) toggle('nou', 'Doar proiecte noi', state.nou, DB.items.filter(i => matches(i, 'nou') && isFresh(i)).length);
  if (has(isInactive)) toggle('ina', 'Ascunde proiecte inactive', !state.ina, null);
  if (has(i => i.civictech) && has(i => !i.civictech)) toggle('civ', 'Doar proiecte civtech', state.civ, DB.items.filter(i => matches(i, 'civ') && i.civictech).length);
  if (toggles.length) out.push(facet('optiuni', 'Opțiuni', toggles.join('')));
  return out.join('');
}

function renderChips() {
  const dC = countBy('d', i => i.domeniu);
  const total = DB.items.filter(i => matches(i, 'd')).length;
  const chip = (val, label, n) => `<button class="chip" data-act="set" data-key="d" data-val="${val}" aria-pressed="${state.d === val}">${esc(label)}<span class="n">${n || 0}</span></button>`;
  slot('chips').innerHTML = chip('', 'Toate', total) + DB.taxonomy.domenii.filter(d => dC[d.key] || state.d === d.key).map(d => chip(d.key, d.short, dC[d.key])).join('');
}

function renderToolbar(n) {
  const pills = [];
  const pill = (key, val, label) => pills.push(`<button class="pill" data-act="unset" data-key="${key}" data-val="${esc(val)}" aria-label="Elimină filtrul ${esc(label)}">${esc(label)}${ICON.x}</button>`);
  if (state.d) pill('d', '', TAX.domeniu[state.d]?.short);
  for (const t of tips()) pill('t', t, TAX.tip[t]?.label || t);
  for (const k of listOf('kw')) pill('kw', k, '#' + kwLabel(k));
  if (state.c) pill('c', '', state.c);
  if (state.org) pill('org', '', state.org);
  if (state.a) pill('a', '', state.a);
  if (state.s) pill('s', '', state.s);
  if (state.cod) pill('cod', '', 'Cod deschis');
  if (state.civ) pill('civ', '', 'Civtech');
  if (state.nou) pill('nou', '', 'Noi');
  if (state.ina) pill('ina', '', 'Inclusiv inactive');
  if (query()) pill('q', '', `„${state.q}”`);
  const view = currentView();
  slot('toolbar').innerHTML = `
    <span class="count"><b>${n}</b> ${n === 1 ? 'rezultat' : 'rezultate'}</span>
    ${pills.length ? `<span class="active">${pills.join('')}</span><button class="linkbtn" data-act="reset">Șterge filtrele</button>` : ''}
    <span class="tool-right">
      <label class="sr" for="sort">Ordonare</label>
      <select class="select" id="sort" data-act="sort">${SORTS.map(([k, l]) => `<option value="${k}" ${state.o === k ? 'selected' : ''}>${l}</option>`).join('')}</select>
      <span class="seg" role="group" aria-label="Mod de afișare">
        <button data-act="view" data-val="cards" aria-pressed="${view === 'cards'}" aria-label="Carduri">${ICON.grid}</button>
        <button data-act="view" data-val="list" aria-pressed="${view === 'list'}" aria-label="Listă">${ICON.list}</button>
      </span>
    </span>`;
  slot('fcount').textContent = activeFilterCount() || '';
}

const currentView = () => state.v || 'list';

function renderResults() {
  const list = DB.items.filter(i => matches(i));
  renderToolbar(list.length);
  const view = currentView();
  const block = (items, withDomain) => view === 'cards'
    ? `<div class="grid">${items.map(i => card(i, withDomain)).join('')}</div>`
    : `<div class="list">${LIST_HEAD}${items.map(i => row(i, withDomain)).join('')}</div>`;
  let html;
  if (!list.length) {
    html = `<div class="empty"><h3>Niciun rezultat.</h3><p>Încearcă alt termen de căutare sau elimină unul dintre filtre.</p><p><button class="btn btn-outline" data-act="reset">Șterge filtrele</button></p></div>`;
  } else if (state.o === 'domeniu') {
    html = DB.taxonomy.domenii.map(d => {
      const items = sorted(list.filter(it => it.domeniu === d.key));
      if (!items.length) return '';
      return `<section class="group" aria-labelledby="g-${d.key}">
        <div class="group-head"><h2 id="g-${d.key}">${esc(d.label)}</h2><span class="n">${items.length}</span><p>${esc(d.hint)}</p></div>
        ${block(items, false)}</section>`;
    }).join('');
  } else {
    html = block(sorted(list), true);
  }
  slot('results').innerHTML = html;
}

function renderFilters() {
  slot('side').innerHTML = facetsHTML();
  renderChips();
  if (!slot('sheet').hidden) renderSheet();
}

function renderAll() {
  renderTabs();
  renderFilters();
  renderResults();
  const q = slot('q');
  if (q.value !== state.q) q.value = state.q;
}

/* ---------- layers: detail drawer & filter sheet ---------- */
function openLayer(el) {
  lastFocus = document.activeElement;
  slot('scrim').hidden = false;
  el.hidden = false;
  document.body.classList.add('locked');
  requestAnimationFrame(() => $('[data-autofocus]', el)?.focus());
}
function closeLayers() {
  for (const n of ['drawer', 'sheet', 'scrim']) slot(n).hidden = true;
  document.body.classList.remove('locked');
  lastFocus?.focus?.({ preventScroll: true });
}
const current = () => state.p && DB.items.find(i => i.slug === state.p);
const syncTitle = () => { const it = current(); document.title = it ? `${it.name} — ${title}` : title; };

// Manual links come from curation; links found on the homepage may belong to the author rather than the project.
function linkRows(it) {
  const fmt = ls => ls.map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener" title="${esc(l.url)}">${esc(l.role === 'web' ? l.url.replace(/^https?:\/\/(www\.)?/, '') : l.label)}</a>`).join(' · ');
  const man = it.links.filter(l => l.src === 'manual'), site = it.links.filter(l => l.src === 'site');
  return [man.length && ['Linkuri', fmt(man)], site.length && ['Găsite pe site', fmt(site)]];
}

function renderDetail() {
  const it = current();
  const drawer = slot('drawer');
  syncTitle();
  if (!it) { if (!drawer.hidden) closeLayers(); return; }
  const dom = TAX.domeniu[it.domeniu];
  const st = STATUS[it.status];
  const alive = !isInactive(it);
  const related = DB.items.filter(i => i.kind === it.kind && i.domeniu === it.domeniu && i.slug !== it.slug && !isInactive(i))
    .sort((a, b) => b.tips.filter(t => it.tips.includes(t)).length - a.tips.filter(t => it.tips.includes(t)).length || byName(a, b)).slice(0, 4);
  const dl = [
    it.org && ['Autor', esc(it.org)],
    it.contact && ['Contact', esc(it.contact)],
    it.url && ['Site', `${alive ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.domain)}</a>` : `<span class="muted">${esc(it.domain)}</span>`}${it.movedFrom ? ` <span class="muted small">(mutat de pe ${esc(it.movedFrom)})</span>` : ''}`],
    ...linkRows(it),
    it.code && ['Cod sursă', `<a href="${esc(it.code)}" target="_blank" rel="noopener">${esc(it.code.replace(/^https?:\/\/(www\.)?/, ''))}</a>`],
    it.wayback && ['Arhivă', `<a href="${esc(it.wayback)}" target="_blank" rel="noopener">Wayback Machine</a>`],
    it.since && ['Vechime', `${esc(age(it))} <span class="muted small mono">· ${esc(ageTitle(it))}</span>`],
    it.updated && ['Actualizat', `${esc(updatedLabel(it))} <span class="muted small mono">· ${esc(it.updated)} după ${esc(UPDATED_SRC[it.updatedSrc] || it.updatedSrc)}</span>`],
    ['Stare', `${statusDot(it)} ${st.label}${it.stale ? ` <span class="muted small">· niciun semn de actualizare după ${it.stale}</span>` : ''}${it.checked ? ` <span class="muted small mono">· verificat ${esc(it.checked)}${it.httpStatus ? ` · HTTP ${it.httpStatus}` : ''}</span>` : ''}`],
  ].filter(Boolean);
  const cta = alive && it.url
    ? `<a class="btn btn-primary" href="${esc(it.url)}" target="_blank" rel="noopener">Deschide ${esc(it.domain)}${ICON.out}</a>`
    : it.wayback ? `<a class="btn btn-primary" href="${esc(it.wayback)}" target="_blank" rel="noopener">${ICON.archive}Vezi în arhivă</a>` : '';
  drawer.innerHTML = `
    <div class="d-bar"><span class="kicker">${esc(dom?.label || '')}</span>
      <button class="btn btn-ghost btn-icon" data-act="close" aria-label="Închide" data-autofocus>${ICON.x}</button></div>
    <div class="d-scroll">
      ${it.img || it.icon ? media(it) : ''}
      <h2 id="d-title">${esc(it.name)}</h2>
      ${cta ? `<div class="d-open">${cta}</div>` : ''}
      ${it.tagline ? `<p class="d-tag">${esc(it.tagline)}</p>` : ''}
      <div class="d-badges">
        <span>${statusDot(it)}${st.label}</span>
        ${tipLabels(it).map(l => `<span>${esc(l)}</span>`).join('')}
        ${placeLabel(it) ? `<span>${esc(placeLabel(it))}</span>` : ''}
        ${isFresh(it) ? `<span class="new${isLaunched(it) ? ' launch' : ''}">${isLaunched(it) ? 'lansat recent' : 'nou'} · ${esc(age(it))}</span>` : ''}
        ${it.code ? `<span>${ICON.code}cod deschis</span>` : ''}
      </div>
      ${it.desc ? `<p class="d-desc">${esc(it.desc)}</p>${it.descSrc === 'site' ? '<p class="d-src">Descriere preluată de pe site-ul proiectului.</p>' : ''}` : ''}
      ${it.keywords.length ? `<div class="tags">${it.keywords.map(k => `<button class="tag" data-act="multi" data-key="kw" data-val="${esc(k)}" aria-pressed="${listOf('kw').includes(k)}">#${esc(kwLabel(k))}</button>`).join('')}</div>` : ''}
      <dl class="dl">${dl.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${related.length ? `<div class="related"><p class="kicker">Tot din ${esc(dom.short)}</p>${related.map(r => row(r, false)).join('')}</div>` : ''}
    </div>`;
  if (drawer.hidden) openLayer(drawer);
  else {
    $('.d-scroll', drawer).scrollTop = 0;
    // The re-render dropped the focused element; keep focus inside the drawer.
    if (!drawer.contains(document.activeElement)) $('[data-autofocus]', drawer)?.focus();
  }
}

function renderSheet() {
  const n = DB.items.filter(i => matches(i)).length;
  slot('sheet').innerHTML = `
    <div class="grab" aria-hidden="true"></div>
    <div class="d-bar"><span class="kicker">Filtre</span><button class="btn btn-ghost btn-icon" data-act="close" aria-label="Închide" data-autofocus>${ICON.x}</button></div>
    <div class="d-scroll">${facetsHTML()}</div>
    <div class="d-cta"><button class="btn btn-outline" data-act="reset">Șterge</button><button class="btn btn-primary" data-act="close">Arată ${plural(n, 'rezultat', 'rezultate')}</button></div>`;
}

/* ---------- autocomplete ---------- */
let SUGGEST = [], acItems = [], acIndex = -1;

function buildSuggestions() {
  const out = [];
  for (const d of DB.taxonomy.domenii) out.push({ g: 'Teme', label: d.label, kind: 'tema', val: d.key });
  for (const t of DB.taxonomy.tipuri) out.push({ g: 'Tipuri', label: t.label, kind: 'tip', val: t.key });
  for (const k of new Set(DB.items.flatMap(i => i.keywords))) out.push({ g: 'Cuvinte cheie', label: kwLabel(k), kind: 'kw', val: k });
  for (const c of new Set(DB.items.map(i => i.oras).filter(Boolean))) out.push({ g: 'Orașe', label: c, kind: 'oras', val: c });
  for (const it of DB.items) out.push({ g: 'Proiecte', label: it.name, kind: 'item', val: it.slug, it });
  for (const o of new Set(DB.items.flatMap(i => i._orgs))) out.push({ g: 'Autori', label: o, kind: 'org', val: o });
  for (const s of out) s._n = norm(s.label);
  return out;
}
const GROUP_LIMIT = { Teme: 3, Tipuri: 3, 'Cuvinte cheie': 4, 'Orașe': 3, Proiecte: 6, Autori: 3 };
function scoreOf(n, q) {
  if (n.startsWith(q)) return 0;
  const i = n.indexOf(q);
  if (i < 0) return -1;
  return /[\s\-–·./(&]/.test(n[i - 1]) ? 1 : 2;
}
function countFor(s) {
  const base = DB.items.filter(i => i.kind === state.k && (state.ina || !isInactive(i)));
  if (s.kind === 'tema') return base.filter(i => i.domeniu === s.val).length;
  if (s.kind === 'tip') return base.filter(i => i.tips.includes(s.val)).length;
  if (s.kind === 'kw') return base.filter(i => i.keywords.includes(s.val)).length;
  if (s.kind === 'oras') return base.filter(i => i.oras === s.val).length;
  if (s.kind === 'org') return DB.items.filter(i => i._orgs.includes(s.val)).length;
  return null;
}
function highlight(label, q) {
  const i = norm(label).indexOf(q);
  if (i < 0) return esc(label);
  return esc(label.slice(0, i)) + '<mark>' + esc(label.slice(i, i + q.length)) + '</mark>' + esc(label.slice(i + q.length));
}
function renderAC() {
  const box = slot('ac'), input = slot('q');
  const q = norm(input.value.trim());
  if (q.length < MIN_Q || document.activeElement !== input) { closeAC(); return; }
  const scored = SUGGEST.map(s => ({ s, sc: scoreOf(s._n, q), n: countFor(s) }))
    .filter(x => x.sc >= 0 && x.n !== 0)
    .sort((a, b) => a.sc - b.sc || a.s.label.length - b.s.label.length);
  const groups = {};
  for (const x of scored) (groups[x.s.g] ??= []).length < GROUP_LIMIT[x.s.g] && groups[x.s.g].push(x);
  acItems = Object.keys(GROUP_LIMIT).flatMap(g => groups[g] || []);
  acIndex = -1;
  if (!acItems.length) {
    box.innerHTML = `<div class="ac-hint">Nicio sugestie. Rezultatele de mai jos conțin textul căutat.</div>`;
  } else {
    let html = '', last = '';
    acItems.forEach((x, i) => {
      if (x.s.g !== last) { html += `<div class="ac-group" role="presentation">${x.s.g}</div>`; last = x.s.g; }
      const it = x.s.it;
      const lead = x.s.kind === 'item'
        ? (it.icon ? `<img class="ico" src="${esc(it.icon)}" alt="">` : '<span class="ico blank"></span>') : '';
      const right = x.s.kind === 'item'
        ? (it.kind !== 'proiect' ? TAX.kind[it.kind].label.toLowerCase() : isInactive(it) ? STATUS[it.status].label.toLowerCase() : TAX.domeniu[it.domeniu]?.short || '')
        : x.n;
      html += `<div class="ac-opt" role="option" id="ac-${i}" data-ac="${i}" aria-selected="false">${lead}<span class="l">${highlight(x.s.label, q)}</span><span class="r">${esc(right)}</span></div>`;
    });
    box.innerHTML = html;
  }
  box.hidden = false;
  input.setAttribute('aria-expanded', 'true');
}
function closeAC() {
  slot('ac').hidden = true;
  slot('q').setAttribute('aria-expanded', 'false');
  slot('q').removeAttribute('aria-activedescendant');
  acIndex = -1;
}
function moveAC(d) {
  if (!acItems.length) return;
  acIndex = (acIndex + d + acItems.length) % acItems.length;
  slot('ac').querySelectorAll('.ac-opt').forEach((el, i) => el.setAttribute('aria-selected', i === acIndex));
  const el = $(`#ac-${acIndex}`);
  el?.scrollIntoView({ block: 'nearest' });
  slot('q').setAttribute('aria-activedescendant', `ac-${acIndex}`);
}
function pickAC(i) {
  const s = acItems[i]?.s;
  if (!s) return;
  const input = slot('q');
  input.value = ''; state.q = '';
  closeAC();
  if (s.kind === 'item') {
    writeURL(); renderFilters(); renderResults();
    input.blur();
    state.p = s.val; writeURL(true); renderDetail();
    return;
  }
  if (s.kind === 'tema') state.d = s.val;
  else if (s.kind === 'tip' || s.kind === 'kw') {
    const key = s.kind === 'tip' ? 't' : 'kw';
    if (!listOf(key).includes(s.val)) state[key] = [...listOf(key), s.val].join(',');
  }
  else if (s.kind === 'oras') state.c = s.val;
  else if (s.kind === 'org') state.org = s.val;
  writeURL(); renderAll();
  input.blur();
}

/* ---------- keyboard navigation ---------- */
// j/k or ←/→ step through the results in the order shown; with the drawer open they step the open entry.
const resultEl = slug => [...slot('results').querySelectorAll('[data-open]')].find(el => el.dataset.open === slug);
function reveal(el) {
  const r = el.getBoundingClientRect(), top = slot('hdr').getBoundingClientRect().bottom;
  if (r.top < top || r.bottom > innerHeight) el.scrollIntoView({ block: 'center' });
}
function step(d) {
  const slugs = [...slot('results').querySelectorAll('[data-open]')].map(el => el.dataset.open);
  if (!slugs.length) return;
  const at = state.p || document.activeElement?.closest?.('[data-slot="results"] [data-open]')?.dataset.open;
  const i = slugs.indexOf(at);
  const next = slugs[i < 0 ? (d > 0 ? 0 : slugs.length - 1) : Math.min(Math.max(i + d, 0), slugs.length - 1)];
  const el = resultEl(next);
  if (state.p) {
    if (next === state.p) return;
    state.p = next; writeURL(); renderDetail();
    lastFocus = $('.stretch', el);  // closing the drawer returns focus to the last entry seen
  } else $('.stretch', el).focus({ preventScroll: true });
  reveal(el);
}
// o opens the entry's own site (or its archive): the open entry, else the focused one.
function openOriginal() {
  const slug = state.p || document.activeElement?.closest?.('[data-open]')?.dataset.open;
  const it = slug && DB.items.find(i => i.slug === slug);
  const href = it && extHref(it);
  if (href) window.open(href, '_blank', 'noopener');
}

/* ---------- rotating title ---------- */
// One span, text swapped while it is hidden; the motion lives in CSS (.out / .in, one effect per swap).
const TITLE_FX = ['rise', 'drop', 'flip', 'wipe', 'zoom', 'slide', 'spread'];
function rotateTitle() {
  const next = TITLES.filter(t => t !== title)[(Math.random() * (TITLES.length - 1)) | 0];
  const box = slot('brand'), el = box.firstElementChild;
  box.dataset.fx = TITLE_FX.filter(f => f !== box.dataset.fx)[(Math.random() * (TITLE_FX.length - 1)) | 0];
  el.classList.add('out');
  setTimeout(() => {
    el.textContent = next;
    el.classList.replace('out', 'in');
    el.offsetWidth; // commit the start position before transitioning back
    el.classList.remove('in');
  }, 420);
  title = next;
  syncTitle();
  setTimeout(rotateTitle, 3000 + Math.random() * 2000);
}

/* ---------- events ---------- */
function setFilter(key, val) {
  state[key] = state[key] === val ? '' : val;
  writeURL();
  renderFilters();
  renderResults();
}

document.addEventListener('click', e => {
  const opt = e.target.closest('[data-ac]');
  if (opt) { pickAC(+opt.dataset.ac); return; }
  if (!e.target.closest('[data-slot="search"]')) closeAC();
  if (e.target.closest('a.ext')) return;  // the project's own site: a plain link
  const open = e.target.closest('[data-open]');
  if (open && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) {
    e.preventDefault();
    state.p = open.dataset.open;
    writeURL(true);
    renderDetail();
    return;
  }
  const a = e.target.closest('[data-act]');
  if (!a || a.tagName === 'INPUT' || a.tagName === 'SELECT') return;
  const { act, key, val } = a.dataset;
  if (act === 'set') setFilter(key, val);
  else if (act === 'multi') {
    const l = listOf(key);
    state[key] = (l.includes(val) ? l.filter(x => x !== val) : [...l, val]).join(',');
    if (a.closest('[data-slot="drawer"]')) { state.p = ''; closeLayers(); syncTitle(); }
    writeURL(); renderFilters(); renderResults();
  } else if (act === 'unset') {
    if (key === 't' || key === 'kw') state[key] = listOf(key).filter(x => x !== val).join(',');
    else state[key] = '';
    writeURL(); renderAll();
  } else if (act === 'reset') { for (const k of FILTERS) state[k] = ''; writeURL(); renderAll(); }
  else if (act === 'kind') { state.k = val; state.o = defaultSort(); for (const k of FILTERS) if (k !== 'q') state[k] = ''; writeURL(); renderAll(); }
  else if (act === 'view') { state.v = val; writeURL(); renderResults(); }
  else if (act === 'sheet') { renderSheet(); openLayer(slot('sheet')); }
  else if (act === 'close') {
    if (!slot('drawer').hidden && state.p) { state.p = ''; writeURL(); }
    closeLayers();
    syncTitle();
  }
});
// Keep focus in the input while choosing a suggestion with the mouse.
slot('ac').addEventListener('mousedown', e => e.preventDefault());
document.addEventListener('change', e => {
  const { act, key } = e.target.dataset;
  if (act === 'sort') { state.o = e.target.value; seed = Math.random(); writeURL(); renderResults(); }
  else if (act === 'toggle') {
    // "Ascunde inactive" is checked by default, so its URL flag means the opposite.
    state[key] = key === 'ina' ? (e.target.checked ? '' : '1') : (e.target.checked ? '1' : '');
    writeURL(); renderFilters(); renderResults();
  }
});
document.addEventListener('toggle', e => {
  const id = e.target.dataset?.facet;
  if (!id) return;
  e.target.open ? closed.delete(id) : closed.add(id);
  store.set('ct.closed', [...closed]);
}, true);

let qTimer;
const qInput = slot('q');
qInput.addEventListener('input', () => {
  renderAC();
  clearTimeout(qTimer);
  qTimer = setTimeout(() => {
    const prev = query();
    state.q = qInput.value.trim();
    if (query() !== prev) { writeURL(); renderFilters(); renderResults(); }
  }, 150);
});
qInput.addEventListener('focus', renderAC);
qInput.addEventListener('blur', () => setTimeout(closeAC, 120));
qInput.addEventListener('keydown', e => {
  const open = !slot('ac').hidden;
  if (e.key === 'ArrowDown') { e.preventDefault(); open ? moveAC(1) : renderAC(); }
  else if (e.key === 'ArrowUp' && open) { e.preventDefault(); moveAC(-1); }
  else if (e.key === 'Enter') {
    e.preventDefault();
    if (open && acIndex >= 0) pickAC(acIndex);
    else { closeAC(); document.getElementById('results').scrollIntoView({ block: 'start' }); }
  } else if (e.key === 'Escape' && open) { e.stopPropagation(); closeAC(); }
});

document.addEventListener('keydown', e => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (e.key === 'Escape' && !slot('scrim').hidden) { $('[data-act="close"]', slot('drawer').hidden ? slot('sheet') : slot('drawer'))?.click(); return; }
  if ((e.key === '/' && !typing) || (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey))) {
    e.preventDefault();
    qInput.focus(); qInput.select();
  }
  if (e.key === 'Tab' && !slot('scrim').hidden) {
    // Keep focus inside the open layer.
    const layer = slot('drawer').hidden ? slot('sheet') : slot('drawer');
    const f = [...layer.querySelectorAll('a[href], button:not([disabled]), input, select, summary')];
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f.at(-1).focus(); }
    else if (!e.shiftKey && document.activeElement === f.at(-1)) { e.preventDefault(); f[0].focus(); }
  }
  if (typing || e.metaKey || e.ctrlKey || e.altKey || !slot('sheet').hidden || !DB) return;
  if (e.key === 'j' || e.key === 'ArrowRight') { e.preventDefault(); step(1); }
  else if (e.key === 'k' || e.key === 'ArrowLeft') { e.preventDefault(); step(-1); }
  else if (e.key === 'o') { e.preventDefault(); openOriginal(); }
});
window.addEventListener('popstate', () => { readURL(); renderAll(); renderDetail(); });

// Below 1024px the header is taller than one row; stick it so only the search and chips stay visible.
function fitHeader() {
  const hdr = slot('hdr'), search = slot('search');
  hdr.style.top = innerWidth < 1024 ? `-${search.offsetTop - parseFloat(getComputedStyle(search).marginTop)}px` : '0px';
}
new ResizeObserver(fitHeader).observe(slot('hdr'));

/* ---------- boot ---------- */
fetch('data.json').then(r => r.json()).then(db => {
  DB = db;
  const map = arr => Object.fromEntries(arr.map(x => [x.key, x]));
  TAX = { domeniu: map(db.taxonomy.domenii), tip: map(db.taxonomy.tipuri), kind: map(db.taxonomy.kinds) };
  for (const it of db.items) {
    if (!STATUS[it.status]) it.status = 'neverificat';
    it._sort = norm(it.name).replace(/[^a-z0-9]/g, '');
    it._orgs = (it.org || '').split(/\s+[\/&]\s+|,\s*/).map(s => s.trim()).filter(s => s.length > 2);
    it._hay = norm([it.name, it.tagline, it.desc, it.org, it.domain, it.oras, TAX.domeniu[it.domeniu]?.label, ...tipLabels(it), ...it.keywords.map(kwLabel)].join(' '));
  }
  SUGGEST = buildSuggestions();
  readURL();
  if (DB.checked) slot('checked').textContent = `Ultima verificare automată: ${DB.checked} · ${DB.items.length} intrări`;
  renderAll();
  renderDetail();
  fitHeader();
  setTimeout(rotateTitle, 3000 + Math.random() * 2000);
});
