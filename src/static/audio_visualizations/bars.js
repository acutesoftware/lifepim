(function () {
  function draw({ ctx, canvas, frequencyData, now, live }) {
    const width = canvas.width;
    const height = canvas.height;
    const data = frequencyData || new Uint8Array(32);
    ctx.clearRect(0, 0, width, height);
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, "#19f3b0");
    gradient.addColorStop(0.55, "#f0d34c");
    gradient.addColorStop(1, "#0c7b67");
    const bars = 32;
    const gap = Math.max(2, width * 0.006);
    const barWidth = (width - gap * (bars - 1)) / bars;
    const usableBins = Math.max(1, Math.floor(data.length * 0.42));
    const step = Math.max(1, Math.floor(usableBins / bars));
    for (let i = 0; i < bars; i += 1) {
      const index = Math.min(usableBins - 1, i * step);
      const raw = live ? data[index] || 0 : 35 + Math.sin(now / 260 + i) * 20;
      const barHeight = Math.max(height * 0.08, (raw / 255) * height * 0.94);
      const x = i * (barWidth + gap);
      const y = height - barHeight;
      ctx.fillStyle = gradient;
      ctx.fillRect(x, y, barWidth, barHeight);
      ctx.fillStyle = "rgba(255, 255, 255, 0.18)";
      ctx.fillRect(x, y, barWidth, Math.min(4, barHeight));
    }
  }

  window.LifePimAudioViz.register("bars", { draw });
})();
