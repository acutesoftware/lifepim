(function () {
  function reel(ctx, x, y, r, spin, energy) {
    ctx.fillStyle = "#111820";
    ctx.strokeStyle = "#6b858a";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    for (let i = 0; i < 6; i += 1) {
      const a = spin + i * Math.PI / 3;
      ctx.strokeStyle = `rgba(25, 243, 176, ${0.35 + energy * 0.5})`;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + Math.cos(a) * r * 0.82, y + Math.sin(a) * r * 0.82);
      ctx.stroke();
    }
  }
  function draw({ ctx, canvas, frequencyData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const e = T.overall(frequencyData);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#151d25";
    ctx.strokeStyle = "#394c55";
    ctx.lineWidth = 3;
    ctx.fillRect(w * 0.12, h * 0.18, w * 0.76, h * 0.58);
    ctx.strokeRect(w * 0.12, h * 0.18, w * 0.76, h * 0.58);
    reel(ctx, w * 0.34, h * 0.45, Math.min(w, h) * 0.16, now * 0.002, e);
    reel(ctx, w * 0.66, h * 0.45, Math.min(w, h) * 0.16, -now * 0.0023, e);
    ctx.fillStyle = "#0a1016";
    ctx.fillRect(w * 0.26, h * 0.66, w * 0.48, h * 0.08);
    ctx.fillStyle = "#19f3b0";
    ctx.fillRect(w * 0.28, h * 0.68, w * 0.44 * e, h * 0.035);
  }
  window.LifePimAudioViz.register("cassette", { draw });
})();
