/* Exact identifier lookup over observed records and direct owner-accepted pairs. */
'use strict';
(() => {
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const external = url => `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>`;
  const namespace = $('#entity-namespace'), value = $('#entity-value'), results = $('#entity-results'), count = $('#entity-count');
  const types = {company:'Companie', public_institution:'Instituție publică', territory:'Teritoriu', legal_subject:'Persoană juridică', registration:'Înregistrare', contract:'Contract', funding_project:'Proiect de finanțare'};
  let data;
  const confirmedCount = n => `${n} ${n === 1 ? 'corespondență confirmată' : 'corespondențe confirmate'}`;
  function render() {
    const query = value.value.trim(), scope = namespace.value;
    if (!query) { count.textContent = `${data.records.length} înregistrări observate · ${confirmedCount(data.links.length)}. Introdu un identificator.`; results.innerHTML = ''; return; }
    const direct = new Set(data.records.filter(r => r.identifiers.some(i => i.scope === scope && i.value === query)).map(r => r.id));
    // One hop from the original result set. Do not infer transitive identity.
    const links = data.links.filter(l => l.records.some(id => direct.has(id)));
    const shown = new Set([...direct, ...links.flatMap(l => l.records)]);
    const records = data.records.filter(r => shown.has(r.id));
    count.textContent = records.length ? `${records.length} ${records.length === 1 ? 'înregistrare observată' : 'înregistrări observate'} · ${confirmedCount(links.length)}.` : 'Nicio înregistrare observată pentru acest identificator.';
    results.innerHTML = records.map(record => {
      const project = data.projects[record.project];
      const confirmed = links.some(l => l.records.includes(record.id));
      return `<article class="entity-card" data-record="${esc(record.id)}">
        <p class="kicker">${esc(types[record.entityType] || record.entityType)} · ${confirmed ? 'Corespondență confirmată' : 'Înregistrare observată'}</p>
        <h2>${esc(record.label || project.name)}</h2>
        <p><a href="${esc(project.profile)}">${esc(project.name)} · fișa proiectului</a></p>
        ${record.conflict ? '<p class="structure-warning">Identificatori în conflict. Această înregistrare nu confirmă o corespondență.</p>' : ''}
        <dl class="dl">${record.identifiers.map(i => `<dt>${esc(i.label)}</dt><dd><code>${esc(i.value)}</code></dd>`).join('')}</dl>
        ${record.profileUrls.length ? `<h3>Pagini ale entității</h3><ul>${record.profileUrls.map(p => `<li>${external(p.url)} <span class="small muted">· URL construit din tipar; disponibilitate neverificată</span></li>`).join('')}</ul>` : '<p class="small muted">Nu avem un URL distinct pentru pagina acestei înregistrări.</p>'}
        <details><summary>API-uri pentru această colecție</summary><ul>${project.operations.filter(o => o.collectionIds.includes(record.collectionId)).map(o => `<li><code>${esc(o.method)} ${esc(o.url)}</code></li>`).join('') || '<li>Niciun endpoint documentat în acest inventar.</li>'}</ul></details>
        <details><summary>Surse și data observației</summary><ul>${record.sources.map(s => `<li>${s.url ? external(s.url) : 'Sursă locală'} · <time>${esc(s.observedAt)}</time><br><code class="structure-hash">SHA-256 ${esc(s.sha256)}</code></li>`).join('')}</ul></details>
      </article>`;
    }).join('');
  }
  function readURL() {
    const params = new URLSearchParams(location.search);
    const candidates = data.namespaces.filter(n => n.namespace === params.get('namespace'));
    const selected = data.namespaces.find(n => n.id === params.get('namespace')) || (candidates.length === 1 ? candidates[0] : null);
    namespace.value = selected?.id || data.namespaces.find(n => n.namespace === 'ro:cui')?.id || data.namespaces[0]?.id || '';
    value.value = params.get('value') || '';
    if (params.get('namespace') && !selected) {
      count.textContent = 'Tipul de identificator din adresă nu este inclus sau este ambiguu. Selectează un tip pentru căutare.';
      results.innerHTML = ''; return;
    }
    render();
  }
  function search() {
    const selected = data.namespaces.find(n => n.id === namespace.value);
    const url = new URL(location.href);
    const unique = data.namespaces.filter(n => n.namespace === selected?.namespace).length === 1;
    url.search = new URLSearchParams({namespace:selected?.shared && unique ? selected.namespace : namespace.value, value:value.value.trim()});
    history.pushState(null, '', url);
    render();
  }
  $('#entity-search').addEventListener('submit', e => { e.preventDefault(); if (data) search(); });
  $('#entity-examples').addEventListener('click', e => {
    const button = e.target.closest('[data-value]');
    if (!button || !data) return;
    const selected = data.namespaces.find(n => n.namespace === button.dataset.namespace);
    if (!selected) return;
    namespace.value = selected.id; value.value = button.dataset.value; search();
  });
  window.addEventListener('popstate', () => { if (data) readURL(); });
  async function boot() {
    try {
      const response = await fetch(new URL('entitati/data.json', document.baseURI));
      if (!response.ok) throw new Error('Lookup unavailable');
      data = await response.json();
      if (data.schemaVersion !== 1 || !Array.isArray(data.records)) throw new Error('Invalid lookup');
      namespace.innerHTML = data.namespaces.map(n => `<option value="${esc(n.id)}">${esc(n.label)}${n.shared ? '' : ' · ID local'} · ${esc(n.issuer)}</option>`).join('');
      readURL();
    } catch {
      count.textContent = 'Înregistrările nu au putut fi încărcate.';
      results.innerHTML = '<button class="btn btn-outline" id="entity-retry">Încearcă din nou</button>';
      $('#entity-retry').addEventListener('click', boot);
    }
  }
  boot();
})();
