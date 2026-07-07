/**
 * Greedy longest-match labeling demo (mirrors label_bouts_with_grammar).
 */
(function () {
  var RULES = [
    { pattern: [3, 7, 7], name: "groom", priority: 30 },
    { pattern: [3], name: "locomote", priority: 10 },
    { pattern: [12], name: "pause", priority: 10 },
  ];

  var SEQUENCE = [3, 7, 7, 3, 12, 3, 7, 7];

  function sortKey(rule) {
    return [-rule.pattern.length, -rule.priority, rule.pattern.join(",")];
  }

  function label(ids, rules) {
    var n = ids.length;
    var out = new Array(n).fill(null);
    var ordered = rules.slice().sort(function (a, b) {
      var ka = sortKey(a);
      var kb = sortKey(b);
      for (var i = 0; i < 3; i++) {
        if (ka[i] !== kb[i]) return ka[i] < kb[i] ? -1 : 1;
      }
      return 0;
    });
    var i = 0;
    while (i < n) {
      var matched = false;
      for (var r = 0; r < ordered.length; r++) {
        var pat = ordered[r].pattern;
        var span = pat.length;
        if (i + span > n) continue;
        var ok = true;
        for (var j = 0; j < span; j++) {
          if (ids[i + j] !== pat[j]) {
            ok = false;
            break;
          }
        }
        if (ok) {
          for (j = 0; j < span; j++) out[i + j] = ordered[r].name;
          i += span;
          matched = true;
          break;
        }
      }
      if (!matched) i += 1;
    }
    return out;
  }

  function render(container) {
    var labels = label(SEQUENCE, RULES);
    var html = '<div class="sequence-row" aria-label="Syllable bout ids">';
    for (var k = 0; k < SEQUENCE.length; k++) {
      var cls = labels[k] ? "seq-cell labeled" : "seq-cell";
      var sub = labels[k]
        ? '<span class="sub">' + labels[k] + "</span>"
        : '<span class="sub">—</span>';
      html +=
        '<div class="' +
        cls +
        '">' +
        SEQUENCE[k] +
        sub +
        "</div>";
    }
    html += "</div>";
    html +=
      '<p class="seq-legend">Top row: syllable id per bout. Bottom: behavior after longest-match apply.</p>';
    html += "<p><strong>Rules</strong></p><ul class=\"rule-list\">";
    RULES.slice()
      .sort(function (a, b) {
        return sortKey(a)[0] - sortKey(b)[0];
      })
      .forEach(function (rule) {
        html +=
          "<li><code>" +
          JSON.stringify(rule.pattern) +
          "</code> → <strong>" +
          rule.name +
          "</strong></li>";
      });
    html += "</ul>";
    container.innerHTML = html;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var el = document.getElementById("grammar-match-demo");
    if (el) render(el);
  });
})();
