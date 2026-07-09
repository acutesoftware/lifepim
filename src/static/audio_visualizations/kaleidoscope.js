(function () {
  function draw({ ctx, canvas, frequencyData, timeData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    const bass = T.band(frequencyData, 0, 0.1);
    T.fade(ctx, canvas, 0.22);
    const wedges = 12;
    for (let k = 0; k < wedges; k += 1) {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate((Math.PI * 2 / wedges) * k + now * 0.00018);
      if (k % 2) ctx.scale(1, -1);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      for (let i = 0; i < 42; i += 1) {
        const r = Math.min(w, h) * (0.08 + i / 50 + Math.abs(T.wave(timeData, i * 7)) * 0.18 * (1 + bass));
        const a = (i / 42) * (Math.PI * 2 / wedges);
        ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
      }
      ctx.closePath();
      ctx.fillStyle = `hsla(${160 + k * 18}, 95%, 55%, 0.13)`;
      ctx.strokeStyle = `hsla(${190 + k * 16}, 95%, 65%, 0.58)`;
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }
  }
  window.LifePimAudioViz.register("kaleidoscope", { draw });
})();
