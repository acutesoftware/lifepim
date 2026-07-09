(function () {
  let left = 0, right = 0;
  function meter(ctx, x, y, w, h, value, label) {
    ctx.fillStyle = "#101820";
    ctx.strokeStyle = "#34505a";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, 8);
    ctx.fill();
    ctx.stroke();
    const cx = x + w / 2, cy = y + h * 0.86, r = w * 0.38;
    for (let i = 0; i <= 10; i += 1) {
      const a = Math.PI * (1.12 + i * 0.076);
      ctx.strokeStyle = i > 7 ? "#d98a36" : "#5b8a91";
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r * 0.78, cy + Math.sin(a) * r * 0.78);
      ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      ctx.stroke();
    }
    const angle = Math.PI * (1.12 + value * 0.76);
    ctx.strokeStyle = "#f6d15b";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(angle) * r * 0.86, cy + Math.sin(angle) * r * 0.86);
    ctx.stroke();
    ctx.fillStyle = "#9ad0d8";
    ctx.font = `${Math.max(10, h * 0.12)}px sans-serif`;
    ctx.fillText(label, x + 10, y + h - 10);
  }
  function draw({ ctx, canvas, timeData }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    let rms = 0;
    if (timeData) {
      for (let i = 0; i < timeData.length; i += 1) {
        const v = T.wave(timeData, i);
        rms += v * v;
      }
      rms = Math.sqrt(rms / timeData.length);
    }
    left = left * 0.82 + rms * 0.9;
    right = right * 0.84 + (rms * 0.86 + Math.sin(Date.now() * 0.004) * 0.04) * 0.16;
    ctx.clearRect(0, 0, w, h);
    meter(ctx, w * 0.06, h * 0.12, w * 0.4, h * 0.76, Math.min(1, left), "LEFT");
    meter(ctx, w * 0.54, h * 0.12, w * 0.4, h * 0.76, Math.min(1, right), "RIGHT");
  }
  window.LifePimAudioViz.register("vu_meter", { draw });
})();
