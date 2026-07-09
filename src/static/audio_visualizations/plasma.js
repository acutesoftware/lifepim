(function () {
  const blobs = Array.from({ length: 7 }, (_, i) => ({ x: Math.random(), y: Math.random(), vx: 0.05 + i * 0.01, vy: 0.04 + i * 0.008, hue: 160 + i * 28 }));
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const volume = T.overall(frequencyData);
    ctx.fillStyle = "rgba(2, 3, 10, 0.28)";
    ctx.fillRect(0, 0, w, h);
    ctx.globalCompositeOperation = "lighter";
    blobs.forEach((b) => {
      b.x += b.vx * delta * (0.8 + volume * 4);
      b.y += b.vy * delta * (0.8 + volume * 4);
      if (b.x < 0 || b.x > 1) b.vx *= -1;
      if (b.y < 0 || b.y > 1) b.vy *= -1;
      const r = Math.min(w, h) * (0.16 + volume * 0.18);
      const x = b.x * w, y = b.y * h;
      const g = ctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, `hsla(${b.hue}, 95%, 58%, 0.45)`);
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(x - r, y - r, r * 2, r * 2);
    });
    ctx.globalCompositeOperation = "source-over";
  }
  window.LifePimAudioViz.register("plasma", { draw });
})();
