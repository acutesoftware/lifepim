(function () {
  const pts = Array.from({ length: 52 }, () => ({ x: Math.random(), y: Math.random(), vx: Math.random() - 0.5, vy: Math.random() - 0.5 }));
  const bursts = [];
  let bassAvg = 0;
  function spawnBurst(vol, bass) {
    const count = 1 + Math.floor(Math.min(3, bass * 5));
    for (let i = 0; i < count; i += 1) {
      bursts.push({
        x: 0.18 + Math.random() * 0.64,
        y: 0.18 + Math.random() * 0.64,
        vx: (Math.random() - 0.5) * (0.6 + vol * 1.6),
        vy: (Math.random() - 0.5) * (0.6 + vol * 1.6),
        life: 1,
        maxLife: 1.4 + Math.random() * 1.4,
        hue: 155 + Math.random() * 80
      });
    }
    if (bursts.length > 28) {
      bursts.splice(0, bursts.length - 28);
    }
  }
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const vol = T.overall(frequencyData);
    const bass = T.band(frequencyData, 0, 0.12);
    const high = T.band(frequencyData, 0.35, 0.75);
    const hit = Math.max(0, bass - bassAvg);
    if (hit > 0.075) {
      spawnBurst(vol, bass);
    }
    bassAvg = bassAvg * 0.88 + bass * 0.12;
    T.fade(ctx, canvas, 0.18);
    pts.forEach((p) => {
      p.x += p.vx * delta * (0.02 + vol * 0.08);
      p.y += p.vy * delta * (0.02 + vol * 0.08);
      if (p.x < 0 || p.x > 1) p.vx *= -1;
      if (p.y < 0 || p.y > 1) p.vy *= -1;
    });
    bursts.forEach((p) => {
      p.life -= delta / p.maxLife;
      p.x += p.vx * delta * 0.09;
      p.y += p.vy * delta * 0.09;
      if (p.x < 0.02 || p.x > 0.98) p.vx *= -1;
      if (p.y < 0.02 || p.y > 0.98) p.vy *= -1;
    });
    for (let i = bursts.length - 1; i >= 0; i -= 1) {
      if (bursts[i].life <= 0) bursts.splice(i, 1);
    }

    drawLinks(ctx, pts, w, h, Math.min(w, h) * 0.18, 0.15 + high, 25, 243, 176);
    bursts.forEach((burst) => {
      const alpha = Math.max(0, burst.life);
      const nearest = pts
        .map((p) => ({ p, d: distance(burst, p, w, h) }))
        .sort((a, b) => a.d - b.d)
        .slice(0, 4);
      nearest.forEach(({ p, d }) => {
        const reach = Math.min(w, h) * 0.34;
        if (d < reach) {
          ctx.strokeStyle = `hsla(${burst.hue}, 95%, 66%, ${(1 - d / reach) * alpha * 0.7})`;
          ctx.lineWidth = Math.max(1, Math.min(w, h) * 0.0025 * alpha);
          ctx.beginPath();
          ctx.moveTo(burst.x * w, burst.y * h);
          ctx.lineTo(p.x * w, p.y * h);
          ctx.stroke();
        }
      });
    });
    pts.forEach((p) => {
      ctx.fillStyle = `rgba(154, 247, 220, ${0.52 + vol * 0.32})`;
      ctx.beginPath(); ctx.arc(p.x * w, p.y * h, 1.7 + vol * 3.2, 0, Math.PI * 2); ctx.fill();
    });
    bursts.forEach((p) => {
      const alpha = Math.max(0, p.life);
      ctx.fillStyle = `hsla(${p.hue}, 95%, 68%, ${alpha * 0.95})`;
      ctx.beginPath(); ctx.arc(p.x * w, p.y * h, Math.max(2, Math.min(w, h) * 0.012 * alpha), 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = `hsla(${p.hue}, 95%, 68%, ${alpha * 0.42})`;
      ctx.beginPath(); ctx.arc(p.x * w, p.y * h, Math.min(w, h) * 0.045 * (1 - alpha + 0.25), 0, Math.PI * 2); ctx.stroke();
    });
  }

  function drawLinks(ctx, points, w, h, threshold, opacity, r, g, b) {
    for (let i = 0; i < points.length; i += 1) for (let j = i + 1; j < points.length; j += 1) {
      const d = distance(points[i], points[j], w, h);
      if (d < threshold) {
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${(1 - d / threshold) * opacity})`;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(points[i].x * w, points[i].y * h); ctx.lineTo(points[j].x * w, points[j].y * h); ctx.stroke();
      }
    }
  }

  function distance(a, b, w, h) {
    const dx = (a.x - b.x) * w;
    const dy = (a.y - b.y) * h;
    return Math.sqrt(dx * dx + dy * dy);
  }

  window.LifePimAudioViz.register("constellation", { draw });
})();
