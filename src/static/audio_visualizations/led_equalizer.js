(function () {
  const peaks = [];
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const bands = 24, blocks = 14;
    const dataLen = frequencyData ? frequencyData.length : 256;
    const gap = Math.max(2, w * 0.004);
    const bw = (w - gap * (bands + 1)) / bands;
    const bh = (h - gap * (blocks + 1)) / blocks;
    for (let b = 0; b < bands; b += 1) {
      const v = T.avg(frequencyData, b * (dataLen * 0.5 / bands), (b + 1) * (dataLen * 0.5 / bands));
      const active = Math.round(v * blocks);
      peaks[b] = Math.max(active, (peaks[b] || 0) - delta * 8);
      for (let y = 0; y < blocks; y += 1) {
        const lit = blocks - y <= active;
        const px = gap + b * (bw + gap), py = gap + y * (bh + gap);
        const hue = y < 3 ? 8 : y < 7 ? 48 : 160;
        ctx.fillStyle = lit ? `hsl(${hue}, 95%, 55%)` : "rgba(40, 65, 70, 0.28)";
        ctx.fillRect(px, py, bw, bh);
      }
      const peakY = h - gap - peaks[b] * (bh + gap);
      ctx.fillStyle = "#f7f1a1";
      ctx.fillRect(gap + b * (bw + gap), peakY, bw, Math.max(2, bh * 0.18));
    }
  }
  window.LifePimAudioViz.register("led_equalizer", { draw });
})();
