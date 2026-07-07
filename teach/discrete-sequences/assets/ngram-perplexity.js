/**
 * Bigram transition toy: edit counts, see occupancy + perplexity shift.
 */
(function () {
  var DEFAULT = {
    labels: ["3", "7", "5", "12"],
    counts: {
      "3|7": 40,
      "7|5": 35,
      "5|12": 10,
      "12|3": 8,
      "3|3": 5,
      "7|7": 4,
    },
    merge: false,
  };

  function mergedLabel(id) {
    if (!state.merge) return id;
    if (id === "3" || id === "7") return "M";
    return id;
  }

  function parseStream(text) {
    return text
      .split(/[\s,]+/)
      .map(function (s) {
        return s.trim();
      })
      .filter(Boolean);
  }

  function bigramCounts(stream) {
    var counts = {};
    for (var i = 0; i < stream.length - 1; i++) {
      var a = mergedLabel(stream[i]);
      var b = mergedLabel(stream[i + 1]);
      var key = a + "|" + b;
      counts[key] = (counts[key] || 0) + 1;
    }
    return counts;
  }

  function unigramCounts(stream) {
    var counts = {};
    stream.forEach(function (sym) {
      var m = mergedLabel(sym);
      counts[m] = (counts[m] || 0) + 1;
    });
    return counts;
  }

  function occupancy(stream) {
    var uni = unigramCounts(stream);
    var total = stream.length;
    var rows = [];
    Object.keys(uni)
      .sort()
      .forEach(function (k) {
        rows.push({
          label: k,
          frac: uni[k] / total,
          n: uni[k],
        });
      });
    return rows;
  }

  function perplexity(stream) {
    if (stream.length < 2) return null;
    var bi = bigramCounts(stream);
    var uni = unigramCounts(stream);
    var logSum = 0;
    var n = 0;
    Object.keys(bi).forEach(function (key) {
      var parts = key.split("|");
      var from = parts[0];
      var c = bi[key];
      var denom = uni[from] || 1;
      var p = c / denom;
      logSum += c * Math.log(p);
      n += c;
    });
    return Math.exp(-logSum / n);
  }

  var state = {
    stream: ["3", "7", "5", "3", "7", "5", "12", "3", "7", "7", "5", "12"],
    merge: false,
  };

  function render(container) {
    var occ = occupancy(state.stream);
    var ppl = perplexity(state.stream);
    var bi = bigramCounts(state.stream);
    var html = "<table><thead><tr><th>symbol</th><th>occupancy</th><th>frames</th></tr></thead><tbody>";
    occ.forEach(function (row) {
      html +=
        "<tr><td>" +
        row.label +
        "</td><td>" +
        (row.frac * 100).toFixed(1) +
        "%</td><td>" +
        row.n +
        "</td></tr>";
    });
    html += "</tbody></table>";
    html +=
      '<p class="seq-legend">Bigram perplexity (train=test on this snippet): <strong>' +
      (ppl !== null ? ppl.toFixed(2) : "—") +
      "</strong> — lower = more predictable transitions.</p>";
    html += "<p><strong>Top bigrams</strong></p><ul class=\"rule-list\">";
    Object.keys(bi)
      .sort(function (a, b) {
        return bi[b] - bi[a];
      })
      .slice(0, 6)
      .forEach(function (k) {
        html += "<li><code>" + k + "</code> × " + bi[k] + "</li>";
      });
    html += "</ul>";
    if (state.merge) {
      html +=
        '<p class="seq-legend">Merge active: syllables <code>3</code> and <code>7</code> → <code>M</code> (memoryless id collapse).</p>';
    }
    container.innerHTML = html;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var streamInput = document.getElementById("lm-stream-input");
    var mergeToggle = document.getElementById("lm-merge-toggle");
    var out = document.getElementById("lm-demo-out");
    if (!streamInput || !out) return;

    function update() {
      state.stream = parseStream(streamInput.value);
      state.merge = mergeToggle.checked;
      render(out);
    }
    streamInput.addEventListener("input", update);
    mergeToggle.addEventListener("change", update);
    update();
  });
})();
