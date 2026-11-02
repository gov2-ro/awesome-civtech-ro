/* Tables of the data finder (date/lista/, date/furnizori/, date/formate/). No dependency; the pages read without it.
   1. A table with the class `ov-sortable` sorts by a click on a column header: a button in the header, `aria-sort` on the header.
      A header with `data-sort-type="num"` sorts by number (a count: the first click puts the largest first); any other header sorts by name with Romanian collation.
      A cell sorts by its `data-sort`, or by its text.
   2. The matrix of date/furnizori/ shows one of its two orientations; the buttons of `[data-orient-toggle]` choose. */
(function () {
  'use strict';
  var collator = new Intl.Collator('ro');

  function compare(a, b, numeric) {
    if (numeric) return (parseFloat(a) || 0) - (parseFloat(b) || 0);
    return collator.compare(a, b);
  }

  function label(th) {
    var copy = th.cloneNode(true);
    Array.prototype.forEach.call(copy.querySelectorAll('small, button, .sr'), function (n) { n.remove(); });
    return (copy.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function value(row, index) {
    var cell = row.cells[index];
    if (!cell) return '';
    return cell.hasAttribute('data-sort') ? cell.getAttribute('data-sort') : (cell.textContent || '').trim();
  }

  function sortable(table) {
    var body = table.tBodies[0];
    var heads = table.tHead ? table.tHead.rows[0].cells : [];
    if (!body || !heads.length) return;
    Array.prototype.forEach.call(body.rows, function (row, n) { row.setAttribute('data-order', n); });
    Array.prototype.forEach.call(heads, function (th, index) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'ov-sort';
      button.setAttribute('aria-label', 'Sortează după ' + (label(th) || 'coloană'));
      button.innerHTML = '<span aria-hidden="true">↕</span>';
      th.appendChild(button);
      button.addEventListener('click', function () {
        var numeric = th.getAttribute('data-sort-type') === 'num';
        var current = th.getAttribute('aria-sort');
        var direction = current === 'ascending' ? 'descending' : current === 'descending' ? 'ascending' : (numeric ? 'descending' : 'ascending');
        Array.prototype.forEach.call(heads, function (other) { other.removeAttribute('aria-sort'); });
        th.setAttribute('aria-sort', direction);
        var sign = direction === 'ascending' ? 1 : -1;
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          return sign * compare(value(a, index), value(b, index), numeric) || (a.getAttribute('data-order') - b.getAttribute('data-order'));
        });
        rows.forEach(function (row) { body.appendChild(row); });
      });
    });
  }

  function orientation(toggle) {
    var scope = toggle.parentNode;
    var views = scope.querySelectorAll('[data-orient]');
    var buttons = toggle.querySelectorAll('button[data-show]');
    function show(name) {
      Array.prototype.forEach.call(views, function (view) { view.hidden = view.getAttribute('data-orient') !== name; });
      Array.prototype.forEach.call(buttons, function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-show') === name)); });
    }
    Array.prototype.forEach.call(buttons, function (b) { b.addEventListener('click', function () { show(b.getAttribute('data-show')); }); });
    toggle.hidden = false;
    show('entries');
  }

  // A jump list with `data-tabs` shows one section at a time: the section that its link names, or the section that holds the target of the address
  // (for example `#f-ins`, a provider inside its type). Without the script every section shows, one after the other.
  function tabs(nav) {
    var links = Array.prototype.slice.call(nav.querySelectorAll('a[href*="#"]'));
    var panels = links.map(function (a) { return document.getElementById(a.getAttribute('href').split('#')[1]); });
    if (panels.some(function (p) { return !p; })) return;
    function show(id, scroll) {
      var target = id && document.getElementById(id);
      var index = 0;
      panels.forEach(function (p, n) { if (target && (p === target || p.contains(target))) index = n; });
      panels.forEach(function (p, n) { p.hidden = n !== index; });
      links.forEach(function (a, n) { if (n === index) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current'); });
      if (scroll && target) target.scrollIntoView();
    }
    window.addEventListener('hashchange', function () { show(decodeURIComponent(location.hash.slice(1)), true); });
    show(decodeURIComponent(location.hash.slice(1)), true);
  }

  Array.prototype.forEach.call(document.querySelectorAll('table.ov-sortable'), sortable);
  Array.prototype.forEach.call(document.querySelectorAll('[data-orient-toggle]'), orientation);
  Array.prototype.forEach.call(document.querySelectorAll('nav[data-tabs]'), tabs);
}());
