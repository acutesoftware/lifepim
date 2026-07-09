(function () {
  const glyphs = [];
  const marks = ["+", "x", "o", "#", "*", "<>"];
  let bass = 0;
  let pulse = 0;
  function draw({ ctx, canvas, frequencyData, delta, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const next = T.band(frequencyData, 0, 0.1);
    const mid = T.band(frequencyData, 0.12, 0.35);
    const high = T.band(frequencyData, 0.35, 0.8);
    if (next > bass + 0.12) {
      const amount = 2 + Math.floor(next * 5);
      for (let i = 0; i < amount; i += 1) {
        glyphs.push({
          x: w * (0.18 + Math.random() * 0.64),
          y: h * (0.18 + Math.random() * 0.64),
          s: Math.max(12, Math.min(w, h) * (0.045 + next * 0.04)),
          r: Math.random() * 6,
          a: 1,
          m: marks[Math.floor(Math.random() * marks.length)]
        });
      }
    }
    bass = bass * 0.9 + next * 0.1;
    pulse = pulse * 0.82 + Math.max(next, mid * 0.75, high * 0.55) * 0.18;
    T.fade(ctx, canvas, 0.18);
    drawCore(ctx, w, h, now, pulse, next, mid, high);
    glyphs.forEach((g) => {
      g.s += delta * 80; g.r += delta; g.a -= delta * 0.65;
      ctx.save(); ctx.translate(g.x, g.y); ctx.rotate(g.r);
      ctx.fillStyle = `rgba(25, 243, 176, ${Math.max(0, g.a)})`;
      ctx.font = `${g.s}px monospace`;
      ctx.fillText(g.m, -g.s * 0.35, g.s * 0.35);
      ctx.restore();
    });
    for (let i = glyphs.length - 1; i >= 0; i -= 1) if (glyphs[i].a <= 0) glyphs.splice(i, 1);
  }

  function drawCore(ctx, w, h, now, pulse, bass, mid, high) {
    const cx = w / 2;
    const cy = h / 2;
    const base = Math.min(w, h);
    const bounce = Math.sin(now * 0.006) * base * 0.025 * (0.25 + pulse * 2);
    const rotation = now * (0.00025 + high * 0.0011);
    const radius = base * (0.14 + pulse * 0.18);
    const symbols = ["#", "+", "x", "o"];

    ctx.save();
    ctx.translate(cx, cy + bounce);
    ctx.rotate(rotation);
    for (let i = 0; i < 4; i += 1) {
      const angle = (i / 4) * Math.PI * 2 + mid * 0.9;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      const size = base * (0.08 + pulse * 0.08 + i * 0.008);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(-rotation * 1.7 + i);
      ctx.fillStyle = `hsla(${155 + i * 42}, 95%, ${56 + high * 24}%, ${0.62 + pulse * 0.35})`;
      ctx.font = `${size}px monospace`;
      ctx.fillText(symbols[i], -size * 0.32, size * 0.34);
      ctx.restore();
    }
    ctx.strokeStyle = `rgba(25, 243, 176, ${0.25 + bass * 0.55})`;
    ctx.lineWidth = Math.max(2, base * 0.006);
    ctx.beginPath();
    ctx.arc(0, 0, radius * (0.62 + bass * 0.55), 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  window.LifePimAudioViz.register("glyphs", { draw });
})();
