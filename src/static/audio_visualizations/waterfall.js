(function () {
  function draw({ ctx, canvas, frequencyData }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    ctx.drawImage(canvas, -2, 0, w, h);
    const bands = Math.min(h, 160);
    const x = w - 3;
    for (let y = 0; y < bands; y += 1) {
      const frac = y / bands;
      const idx = Math.floor(Math.pow(frac, 1.8) * (frequencyData ? frequencyData.length * 0.5 : 1));
      const v = frequencyData ? (frequencyData[idx] || 0) / 255 : 0;
      ctx.fillStyle = `hsl(${220 - v * 180}, 95%, ${12 + v * 58}%)`;
      ctx.fillRect(x, h - y * (h / bands), 3, Math.ceil(h / bands) + 1);
    }
    ctx.fillStyle = "rgba(0, 0, 0, 0.05)";
    ctx.fillRect(0, 0, w, h);
  }
  window.LifePimAudioViz.register("waterfall", { draw });
})();
