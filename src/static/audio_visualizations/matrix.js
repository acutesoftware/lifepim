(function () {
  const chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const cols = [];
  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const size = Math.max(10, Math.floor(w / 70));
    const count = Math.ceil(w / size);
    while (cols.length < count) cols.push({ y: Math.random() * h, speed: 40 + Math.random() * 120 });
    ctx.fillStyle = "rgba(0, 5, 5, 0.18)";
    ctx.fillRect(0, 0, w, h);
    ctx.font = `${size}px monospace`;
    for (let i = 0; i < count; i += 1) {
      const v = T.avg(frequencyData, i * 4, i * 4 + 8);
      cols[i].y += (cols[i].speed + v * 260) * delta;
      if (cols[i].y > h + size * 10) cols[i].y = -Math.random() * h * 0.4;
      for (let j = 0; j < 12; j += 1) {
        ctx.fillStyle = `rgba(25, 243, 120, ${Math.max(0, 0.95 - j * 0.08 + v * 0.3)})`;
        ctx.fillText(chars[(i * 7 + j * 13 + Math.floor(cols[i].y / size)) % chars.length], i * size, cols[i].y - j * size);
      }
    }
  }
  window.LifePimAudioViz.register("matrix", { draw });
})();
