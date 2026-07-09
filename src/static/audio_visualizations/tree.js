(function () {
  function branch(ctx, x, y, len, angle, depth, sway, glow) {
    if (depth <= 0) return;
    const x2 = x + Math.cos(angle) * len;
    const y2 = y + Math.sin(angle) * len;
    ctx.strokeStyle = depth < 3 ? `rgba(25, 243, 176, ${0.25 + glow})` : "#7cc9a4";
    ctx.lineWidth = depth;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x2, y2); ctx.stroke();
    branch(ctx, x2, y2, len * 0.72, angle - 0.45 - sway, depth - 1, sway, glow);
    branch(ctx, x2, y2, len * 0.72, angle + 0.45 + sway, depth - 1, sway, glow);
  }
  function draw({ ctx, canvas, frequencyData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const bass = T.band(frequencyData, 0, 0.1), high = T.band(frequencyData, 0.35, 0.75);
    ctx.fillStyle = "rgba(3, 9, 10, 0.42)";
    ctx.fillRect(0, 0, w, h);
    branch(ctx, w / 2, h * 0.94, h * (0.2 + bass * 0.08), -Math.PI / 2 + Math.sin(now * 0.001) * bass * 0.2, 8, high * 0.16, high * 0.45);
  }
  window.LifePimAudioViz.register("tree", { draw });
})();
