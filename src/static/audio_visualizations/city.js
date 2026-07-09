(function () {
  function draw({ ctx, canvas, frequencyData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, bands = 42;
    ctx.fillStyle = "#030912";
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "rgba(255,255,255,0.5)";
    for (let i = 0; i < 40; i += 1) ctx.fillRect((i * 97 + now * 0.02) % w, (i * 37) % (h * 0.45), 2, 2);
    const bw = w / bands;
    for (let b = 0; b < bands; b += 1) {
      const v = T.avg(frequencyData, b * 5, b * 5 + 10);
      const bh = h * (0.18 + v * 0.72);
      const x = b * bw, y = h - bh;
      ctx.fillStyle = `hsl(${210 - v * 70}, 65%, ${18 + v * 20}%)`;
      ctx.fillRect(x + 1, y, bw - 2, bh);
      ctx.fillStyle = `rgba(25, 243, 176, ${0.15 + v * 0.7})`;
      for (let wy = y + 8; wy < h - 4; wy += 12) for (let wx = x + 5; wx < x + bw - 4; wx += 10) ctx.fillRect(wx, wy, 3, 4);
    }
  }
  window.LifePimAudioViz.register("city", { draw });
})();
