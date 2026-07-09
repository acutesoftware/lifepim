(function () {
  const count = 18;
  const angles = Array.from({ length: count }, (_, i) => i * 0.7);
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    T.fade(ctx, canvas, 0.2);
    for (let i = 0; i < count; i += 1) {
      const v = T.avg(frequencyData, i * 8, i * 8 + 12);
      angles[i] += delta * (0.35 + i * 0.025 + v * 2.2);
      const orbit = Math.min(w, h) * (0.12 + i / count * 0.36);
      const x = cx + Math.cos(angles[i]) * orbit;
      const y = cy + Math.sin(angles[i]) * orbit;
      ctx.strokeStyle = "rgba(60, 110, 120, 0.18)";
      ctx.beginPath();
      ctx.arc(cx, cy, orbit, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = `hsla(${160 + i * 12}, 95%, ${45 + v * 35}%, 0.95)`;
      ctx.beginPath();
      ctx.arc(x, y, Math.max(2, Math.min(w, h) * (0.008 + v * 0.025)), 0, Math.PI * 2);
      ctx.fill();
    }
  }
  window.LifePimAudioViz.register("orbiters", { draw });
})();
