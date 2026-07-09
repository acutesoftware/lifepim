(function () {
  const sparks = [];
  let bassAvg = 0;
  let flare = 0;

  function draw({ ctx, canvas, frequencyData, delta, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const bass = T.band(frequencyData, 0, 0.12);
    const mid = T.band(frequencyData, 0.12, 0.35);
    const high = T.band(frequencyData, 0.35, 0.75);
    const hit = Math.max(0, bass - bassAvg);
    if (hit > 0.075) {
      flare = Math.min(1, flare + hit * 3.5);
      spawnSparks(w, h, 8 + Math.floor(hit * 70), bass, high);
    } else if (high > 0.42) {
      spawnSparks(w, h, 1 + Math.floor(high * 3), bass, high);
    }
    bassAvg = bassAvg * 0.88 + bass * 0.12;
    flare = Math.max(0, flare - delta * 1.5);

    ctx.fillStyle = `rgba(4, 2, 2, ${0.26 - flare * 0.08})`;
    ctx.fillRect(0, 0, w, h);
    drawGlow(ctx, w, h, bass, flare);
    drawFlames(ctx, w, h, frequencyData, bass, mid, flare, now);
    drawSparks(ctx, h, delta);
  }

  function drawGlow(ctx, w, h, bass, flare) {
    const glow = ctx.createRadialGradient(w / 2, h, h * 0.08, w / 2, h, h * (0.58 + flare * 0.24));
    glow.addColorStop(0, `rgba(255, 115, 20, ${0.38 + bass * 0.28 + flare * 0.22})`);
    glow.addColorStop(0.42, `rgba(210, 35, 5, ${0.18 + bass * 0.2})`);
    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, w, h);
  }

  function drawFlames(ctx, w, h, frequencyData, bass, mid, flare, now) {
    const T = window.LifePimAudioVizTools;
    const tongues = Math.max(14, Math.min(42, Math.floor(w / 34)));
    const step = w / tongues;
    for (let i = 0; i < tongues; i += 1) {
      const v = T.avg(frequencyData, i * 5, i * 5 + 10);
      const x = (i + 0.5) * step;
      const sway = Math.sin(now * 0.003 + i * 1.7) * step * (0.25 + mid);
      const flameH = h * (0.22 + v * 0.38 + bass * 0.22 + flare * 0.22);
      const baseW = step * (1.8 + bass * 1.2);
      drawTongue(ctx, x + sway, h, baseW, flameH, "rgba(255, 55, 0, 0.62)", "rgba(255, 165, 28, 0.38)");
      drawTongue(ctx, x - sway * 0.35, h, baseW * 0.72, flameH * (0.66 + mid * 0.24), "rgba(255, 190, 40, 0.52)", "rgba(255, 236, 122, 0.22)");
      if (i % 3 === 1) {
        drawTongue(ctx, x + sway * 0.2, h, baseW * 0.34, flameH * (0.42 + flare * 0.2), "rgba(255, 245, 170, 0.36)", "rgba(255, 245, 170, 0)");
      }
    }
  }

  function drawTongue(ctx, x, baseY, baseW, height, baseColor, tipColor) {
    const topY = baseY - height;
    const g = ctx.createLinearGradient(0, baseY, 0, topY);
    g.addColorStop(0, baseColor);
    g.addColorStop(0.55, tipColor);
    g.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.moveTo(x - baseW * 0.5, baseY);
    ctx.bezierCurveTo(x - baseW * 0.58, baseY - height * 0.34, x - baseW * 0.18, baseY - height * 0.72, x, topY);
    ctx.bezierCurveTo(x + baseW * 0.26, baseY - height * 0.66, x + baseW * 0.62, baseY - height * 0.32, x + baseW * 0.5, baseY);
    ctx.closePath();
    ctx.fill();
  }

  function spawnSparks(w, h, count, bass, high) {
    for (let i = 0; i < count; i += 1) {
      sparks.push({
        x: w * (0.12 + Math.random() * 0.76),
        y: h * (0.78 + Math.random() * 0.18),
        vx: (Math.random() - 0.5) * w * (0.08 + high * 0.22),
        vy: -h * (0.18 + Math.random() * 0.5 + bass * 0.32 + high * 0.16),
        r: Math.max(1.6, Math.min(w, h) * (0.004 + Math.random() * 0.006)),
        life: 0.7 + Math.random() * 0.6,
        hue: 28 + Math.random() * 30
      });
    }
    if (sparks.length > 180) {
      sparks.splice(0, sparks.length - 180);
    }
  }

  function drawSparks(ctx, h, delta) {
    sparks.forEach((s) => {
      s.x += s.vx * delta;
      s.y += s.vy * delta;
      s.vy += h * 0.32 * delta;
      s.life -= delta;
      const alpha = Math.max(0, Math.min(1, s.life));
      ctx.fillStyle = `hsla(${s.hue}, 95%, 68%, ${alpha * 0.72})`;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r * alpha, 0, Math.PI * 2);
      ctx.fill();
    });
    for (let i = sparks.length - 1; i >= 0; i -= 1) if (sparks[i].life <= 0) sparks.splice(i, 1);
  }
  window.LifePimAudioViz.register("fire", { draw });
})();
