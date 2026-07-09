(function () {
  function draw({ ctx, canvas, frequencyData, timeData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    const r = Math.min(w, h) * 0.42, bass = T.band(frequencyData, 0, 0.1);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#050505"; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "rgba(120, 140, 145, 0.22)";
    for (let i = 1; i < 12; i += 1) { ctx.beginPath(); ctx.arc(cx, cy, r * i / 12, 0, Math.PI * 2); ctx.stroke(); }
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(now * 0.0006);
    ctx.beginPath();
    for (let i = 0; i <= 240; i += 1) {
      const a = i / 240 * Math.PI * 2;
      const rr = r * 0.58 + T.wave(timeData, i * 3) * r * 0.05;
      const x = Math.cos(a) * rr, y = Math.sin(a) * rr;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = "#19f3b0"; ctx.lineWidth = 2; ctx.stroke(); ctx.restore();
    ctx.fillStyle = `hsl(${160 + bass * 80}, 85%, 45%)`; ctx.beginPath(); ctx.arc(cx, cy, r * (0.16 + bass * 0.06), 0, Math.PI * 2); ctx.fill();
  }
  window.LifePimAudioViz.register("vinyl", { draw });
})();
