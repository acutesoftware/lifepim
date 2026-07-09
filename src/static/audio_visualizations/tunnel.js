(function () {
  const rings = Array.from({ length: 24 }, (_, i) => ({ z: i / 24, r: Math.random() * 6 }));
  function draw({ ctx, canvas, frequencyData, delta, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    const bass = T.band(frequencyData, 0, 0.08);
    T.fade(ctx, canvas, 0.28);
    rings.forEach((ring) => {
      ring.z -= delta * (0.18 + bass * 0.7);
      ring.r += delta * (0.7 + bass);
      if (ring.z <= 0.02) {
        ring.z = 1;
        ring.r = 0;
      }
      const scale = 1 / ring.z;
      const size = Math.min(w, h) * 0.08 * scale * (1 + bass * 0.35);
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(ring.r + now * 0.00025);
      ctx.strokeStyle = `hsla(${165 + ring.z * 120}, 95%, 58%, ${1 - ring.z * 0.45})`;
      ctx.lineWidth = Math.max(1, scale * 0.8);
      ctx.strokeRect(-size, -size, size * 2, size * 2);
      ctx.restore();
    });
  }
  window.LifePimAudioViz.register("tunnel", { draw });
})();
