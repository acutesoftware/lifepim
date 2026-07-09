(function () {
  const drops = Array.from({ length: 40 }, () => ({ x: Math.random(), y: Math.random(), s: 0.2 + Math.random() }));
  const ripples = [];
  let bass = 0;
  let impact = 0;
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const next = T.band(frequencyData, 0, 0.1);
    const volume = T.overall(frequencyData);
    const hit = Math.max(0, next - bass);
    if (hit > 0.08 || volume > 0.52) {
      const count = 2 + Math.floor((hit + volume) * 8);
      for (let i = 0; i < count; i += 1) {
        ripples.push({
          x: Math.random() * w,
          y: Math.random() * h,
          r: 5 + Math.random() * h * 0.03,
          a: 0.65 + Math.min(0.3, hit),
          speed: h * (0.28 + hit * 1.9 + volume * 0.55)
        });
      }
      drops.push({ x: Math.random(), y: -0.05, s: 0.8 + Math.random() * 1.8 });
      impact = Math.min(1, impact + hit * 3.4 + volume * 0.4);
    }
    bass = bass * 0.88 + next * 0.12;
    impact = Math.max(0, impact - delta * 1.5);
    ctx.fillStyle = `rgba(5, 12, 18, ${0.22 + impact * 0.18})`;
    ctx.fillRect(0, 0, w, h);
    drops.forEach((d) => {
      d.y += delta * (0.04 + d.s * 0.11 + impact * 0.45);
      if (d.y > 1.05) { d.y = -0.05; d.x = Math.random(); }
      ctx.strokeStyle = `rgba(150, 220, 235, ${0.28 + impact * 0.42})`;
      ctx.lineWidth = Math.max(1, d.s * (0.8 + impact));
      ctx.beginPath();
      ctx.moveTo(d.x * w, d.y * h);
      ctx.lineTo(d.x * w + d.s * (8 + impact * 18), d.y * h + d.s * (26 + impact * 45));
      ctx.stroke();
    });
    if (drops.length > 80) drops.splice(0, drops.length - 80);
    ripples.forEach((r) => {
      r.r += delta * r.speed; r.a -= delta * (0.42 - impact * 0.1);
      ctx.lineWidth = Math.max(1, h * 0.004 * (1 + impact));
      ctx.strokeStyle = `rgba(25, 243, 176, ${Math.max(0, r.a)})`;
      ctx.beginPath(); ctx.arc(r.x, r.y, r.r, 0, Math.PI * 2); ctx.stroke();
    });
    for (let i = ripples.length - 1; i >= 0; i -= 1) if (ripples[i].a <= 0) ripples.splice(i, 1);
  }
  window.LifePimAudioViz.register("rain_glass", { draw });
})();
