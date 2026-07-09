(function () {
  let bass = 0;
  const waves = [];
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    const next = T.band(frequencyData, 0, 0.08);
    if (next > bass + 0.18) waves.push({ r: Math.min(w, h) * 0.18, a: 0.8 });
    bass = bass * 0.86 + next * 0.14;
    T.fade(ctx, canvas, 0.24);
    const radius = Math.min(w, h) * (0.18 + bass * 0.28);
    const grad = ctx.createRadialGradient(cx, cy, radius * 0.1, cx, cy, radius * 2.2);
    grad.addColorStop(0, "rgba(25, 243, 176, 0.75)");
    grad.addColorStop(1, "rgba(25, 243, 176, 0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 2.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#19f3b0";
    ctx.lineWidth = Math.max(3, Math.min(w, h) * 0.009);
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.stroke();
    waves.forEach((wave) => {
      wave.r += delta * Math.min(w, h) * 0.55;
      wave.a -= delta * 0.8;
      ctx.strokeStyle = `rgba(58, 214, 255, ${Math.max(0, wave.a)})`;
      ctx.lineWidth = Math.max(1, Math.min(w, h) * 0.004);
      ctx.beginPath();
      ctx.arc(cx, cy, wave.r, 0, Math.PI * 2);
      ctx.stroke();
    });
    for (let i = waves.length - 1; i >= 0; i -= 1) if (waves[i].a <= 0) waves.splice(i, 1);
  }
  window.LifePimAudioViz.register("bass_pulse", { draw });
})();
