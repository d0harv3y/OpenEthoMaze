/**
 * Overlay gate simulator — mirrors compute_must_review_overlay thresholds.
 */
(function () {
  var GRAY_LO = 0.06;
  var GRAY_HI = 0.14;
  var LOW_SPEED = 0.06;
  var HIGH_DHEADING = 0.25;
  var AMBIG_IQR = 0.08;

  function evaluate(ambiguous, speed, dheading, speedIqr) {
    var reasons = [];
    if (ambiguous) reasons.push("ambiguous bout in a match span");
    if (speedIqr > AMBIG_IQR) reasons.push("bout speed IQR > " + AMBIG_IQR);
    if (speed >= GRAY_LO && speed <= GRAY_HI) {
      reasons.push("mean speed in gray zone (" + GRAY_LO + "–" + GRAY_HI + " m/s)");
    }
    if (speed < LOW_SPEED && dheading >= HIGH_DHEADING) {
      reasons.push("low speed + high |dheading| (pose-shaped still?)");
    }
    return { required: reasons.length > 0, reasons: reasons };
  }

  function renderResult(el, result) {
    if (!result.required) {
      el.innerHTML =
        '<p style="color:var(--correct);margin:0;"><strong>must_review_overlay = 0</strong> — scalars alone may suffice; overlay still wise for pose classes.</p>';
      return;
    }
    var html =
      '<p style="color:var(--wrong);margin:0 0 0.5rem;"><strong>must_review_overlay = 1</strong></p><ul class="rule-list">';
    result.reasons.forEach(function (r) {
      html += "<li>" + r + "</li>";
    });
    html += "</ul>";
    el.innerHTML = html;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var amb = document.getElementById("gate-ambiguous");
    var speed = document.getElementById("gate-speed");
    var dhead = document.getElementById("gate-dheading");
    var iqr = document.getElementById("gate-iqr");
    var out = document.getElementById("gate-result");
    var speedVal = document.getElementById("gate-speed-val");
    var dheadVal = document.getElementById("gate-dheading-val");
    var iqrVal = document.getElementById("gate-iqr-val");

    if (!amb || !speed || !out) return;

    function update() {
      var sp = parseFloat(speed.value);
      var dh = parseFloat(dhead.value);
      var iq = parseFloat(iqr.value);
      speedVal.textContent = sp.toFixed(2);
      dheadVal.textContent = dh.toFixed(2);
      iqrVal.textContent = iq.toFixed(2);
      renderResult(
        out,
        evaluate(amb.checked, sp, dh, iq)
      );
    }

    [amb, speed, dhead, iqr].forEach(function (el) {
      el.addEventListener("input", update);
      el.addEventListener("change", update);
    });
    update();
  });
})();
