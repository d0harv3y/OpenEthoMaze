/**
 * AR(1) echo demo: x_t = phi * x_{t-1} + w_t
 * Reads chart colors from CSS custom properties (dark-theme aware).
 */
(function () {
  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return v || fallback;
  }

  function simulate(phi, n, seed) {
    var x = [0];
    var w = 0;
    for (var t = 1; t < n; t++) {
      w = (Math.sin(seed + t * 12.9898) * 43758.5453) % 1;
      w = w * 2 - 1;
      x.push(phi * x[t - 1] + 0.35 * w);
    }
    return x;
  }

  function draw(canvas, phi) {
    var ctx = canvas.getContext("2d");
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.clientWidth;
    var h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    var gridColor = cssVar("--chart-grid", "#3d424d");
    var lineColor = cssVar("--chart-line", "#7eb6ff");
    var labelColor = cssVar("--chart-label", "#9ca3af");
    var bgColor = cssVar("--bg", "#1a1b1e");

    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, w, h);

    var series = simulate(phi, 120, phi * 100);
    var min = Math.min.apply(null, series);
    var max = Math.max.apply(null, series);
    var pad = 12;
    var plotW = w - pad * 2;
    var plotH = h - pad * 2;

    ctx.strokeStyle = gridColor;
    ctx.beginPath();
    ctx.moveTo(pad, h / 2);
    ctx.lineTo(w - pad, h / 2);
    ctx.stroke();

    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (var i = 0; i < series.length; i++) {
      var px = pad + (i / (series.length - 1)) * plotW;
      var py = pad + plotH - ((series[i] - min) / (max - min || 1)) * plotH;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();

    ctx.fillStyle = labelColor;
    ctx.font = "12px Segoe UI, sans-serif";
    ctx.fillText("φ = " + phi.toFixed(2), pad, pad + 4);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var canvas = document.getElementById("ar1-echo-canvas");
    var slider = document.getElementById("ar1-phi-slider");
    if (!canvas || !slider) return;

    function update() {
      draw(canvas, parseFloat(slider.value));
    }
    slider.addEventListener("input", update);
    update();
  });
})();
