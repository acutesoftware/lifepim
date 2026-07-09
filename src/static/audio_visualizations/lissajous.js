(function () {
  function draw({ ctx, canvas, timeData }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    T.fade(ctx, canvas, 0.16);
    ctx.beginPath();
    const count = Math.min(512, timeData ? timeData.length : 512);
    for (let i = 0; i < count; i += 1) {
      const left = T.wave(timeData, i);
      const right = T.wave(timeData, (i + count * 0.19) % count);
      const x = cx + left * w * 0.38;
      const y = cy + right * h * 0.38;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.shadowColor = "#19f3b0";
    ctx.shadowBlur = 16;
    ctx.strokeStyle = "#19f3b0";
    ctx.lineWidth = Math.max(1.5, Math.min(w, h) * 0.004);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }
  window.LifePimAudioViz.register("lissajous", { draw });
})();
