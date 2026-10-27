(function () {
  "use strict";
  var T = { loading: "Se încarcă {n} localități", note: 'a } b' };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return "&#" + c.charCodeAt(0) + ";"; }); }
  // a comment with a brace { that must not open an object
  var half = total / 2 / 3;
  function load(d) {
    rows = d.rows.map(function (a, i) {
      return { i: i, name: a[0], county: a[1], kind: a[2], pop: a[3],
               x: a[4] / 10, bb: a[5].map(function (b) { return b / 10; }), key: fold(a[0]) };
    });
    tags = d.tags.map(function (a) {
      return { title: a[0], count: a[1], share: a[2], pair: [a[2], a[3]] };
    });
    var small = { first: p[0], second: p[1] };
    var other = d.rows.map(function (r) { return { id: r[0], label: r[1], size: r[2] }; });
    return { total: rows.length, text: `x {y} ${z}` };
  }
})();
