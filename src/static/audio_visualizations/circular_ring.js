(function () {
  const smooth = [];
  function draw({ ctx, canvas, frequencyData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    T.fade(ctx, canvas, 0.22);
    const count = 96;
    const base = Math.min(w, h) * 0.22;
    const spin = now * 0.00018;
    for (let i = 0; i < count; i += 1) {
      const idx = Math.floor((i / count) * (frequencyData ? frequencyData.length * 0.48 : 1));
      const value = (frequencyData ? frequencyData[idx] || 0 : 60) / 255;
      smooth[i] = smooth[i] == null ? value : smooth[i] * 0.78 + value * 0.22;
      const angle = spin + (i / count) * Math.PI * 2 - Math.PI / 2;
      const inner = base;
      const outer = base + smooth[i] * Math.min(w, h) * 0.28;
      ctx.strokeStyle = `hsl(${155 + i * 1.8}, 95%, ${45 + smooth[i] * 35}%)`;
      ctx.lineWidth = Math.max(2, Math.min(w, h) * 0.006);
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
      ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
      ctx.stroke();
    }
  }
  window.LifePimAudioViz.register("circular_ring", { draw });
})();
