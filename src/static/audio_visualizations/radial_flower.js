(function () {
  function draw({ ctx, canvas, timeData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    T.fade(ctx, canvas, 0.18, "rgba(3, 5, 12, 0.18)");
    const points = 160;
    const base = Math.min(w, h) * 0.24;
    const amp = Math.min(w, h) * 0.18;
    ctx.beginPath();
    for (let i = 0; i <= points; i += 1) {
      const sample = T.wave(timeData, (i / points) * (timeData ? timeData.length - 1 : 1));
      const angle = (i / points) * Math.PI * 2 + now * 0.00012;
      const r = base + sample * amp + Math.sin(now * 0.001 + i * 0.12) * amp * 0.08;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = "rgba(25, 243, 176, 0.13)";
    ctx.strokeStyle = "#19f3b0";
    ctx.lineWidth = Math.max(2, Math.min(w, h) * 0.005);
    ctx.fill();
    ctx.stroke();
  }
  window.LifePimAudioViz.register("radial_flower", { draw });
})();
