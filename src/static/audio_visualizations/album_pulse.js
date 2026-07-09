(function () {
  function draw({ ctx, canvas, frequencyData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    const bass = T.band(frequencyData, 0, 0.08);
    const mid = T.band(frequencyData, 0.12, 0.34);
    const high = T.band(frequencyData, 0.35, 0.62);
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, `hsl(${175 + bass * 70}, 75%, ${10 + bass * 25}%)`);
    g.addColorStop(0.5, `hsl(${260 + mid * 80}, 70%, ${12 + mid * 28}%)`);
    g.addColorStop(1, `hsl(${35 + high * 80}, 80%, ${10 + high * 26}%)`);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 4; i += 1) {
      ctx.strokeStyle = `hsla(${170 + i * 45}, 95%, 62%, ${0.22 + bass * 0.45})`;
      ctx.lineWidth = Math.max(2, Math.min(w, h) * 0.006);
      ctx.beginPath();
      ctx.arc(cx, cy, Math.min(w, h) * (0.12 + i * 0.11 + bass * 0.08 + Math.sin(now * 0.001 + i) * 0.015), 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  window.LifePimAudioViz.register("album_pulse", { draw });
})();
