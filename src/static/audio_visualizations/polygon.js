(function () {
  function poly(ctx, cx, cy, sides, radius, values, spin, color) {
    ctx.beginPath();
    for (let i = 0; i <= sides; i += 1) {
      const v = values[i % values.length] || 0;
      const a = spin + i / sides * Math.PI * 2;
      const r = radius * (0.72 + v * 0.55);
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = color;
    ctx.stroke();
  }
  function draw({ ctx, canvas, frequencyData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    T.fade(ctx, canvas, 0.22);
    ctx.lineWidth = Math.max(2, Math.min(w, h) * 0.006);
    const vals = Array.from({ length: 12 }, (_, i) => T.avg(frequencyData, i * 10, i * 10 + 12));
    poly(ctx, cx, cy, 5, Math.min(w, h) * 0.34, vals, now * 0.00035, "#19f3b0");
    poly(ctx, cx, cy, 6, Math.min(w, h) * 0.24, vals.slice(3), -now * 0.00048, "#f0d34c");
    poly(ctx, cx, cy, 3, Math.min(w, h) * 0.15, vals.slice(6), now * 0.0007, "#3ad6ff");
  }
  window.LifePimAudioViz.register("polygon", { draw });
})();
