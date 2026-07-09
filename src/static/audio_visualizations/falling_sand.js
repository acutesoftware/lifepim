(function () {
  const grains = [];
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, bands = 32;
    T.fade(ctx, canvas, 0.1);
    for (let b = 0; b < bands; b += 1) {
      const v = T.avg(frequencyData, b * 6, b * 6 + 10);
      const count = Math.floor(v * 3);
      for (let i = 0; i < count; i += 1) {
        grains.push({ x: (b + Math.random()) / bands * w, y: h * 0.08, vx: (Math.random() - 0.5) * 30, vy: 30 + Math.random() * 80, life: 1, hue: 155 + b * 4 });
      }
    }
    grains.forEach((g) => {
      g.vy += 180 * delta;
      g.x += g.vx * delta;
      g.y += g.vy * delta;
      g.life -= delta * 0.35;
      if (g.y > h * 0.96) { g.y = h * 0.96; g.vy *= -0.18; g.vx *= 0.82; }
      ctx.fillStyle = `hsla(${g.hue}, 90%, 62%, ${Math.max(0, g.life)})`;
      ctx.fillRect(g.x, g.y, Math.max(1, w * 0.004), Math.max(1, w * 0.004));
    });
    for (let i = grains.length - 1; i >= 0; i -= 1) if (grains[i].life <= 0) grains.splice(i, 1);
  }
  window.LifePimAudioViz.register("falling_sand", { draw });
})();
