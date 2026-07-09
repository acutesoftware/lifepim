(function () {
  const logs = [];
  let beat = 0;
  function draw({ ctx, canvas, frequencyData, timeData, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const bass = T.band(frequencyData, 0, 0.1), mid = T.band(frequencyData, 0.12, 0.35), high = T.band(frequencyData, 0.38, 0.7);
    if (bass > beat + 0.16) logs.unshift("BASS PEAK " + Math.round(bass * 99));
    if (high > 0.52 && logs[0] !== "HIGH ENERGY") logs.unshift("HIGH ENERGY");
    beat = beat * 0.94 + bass * 0.06;
    logs.splice(8);
    ctx.fillStyle = "#061015";
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "#1c4a52";
    ctx.fillStyle = "#9ad0d8";
    ctx.font = `${Math.max(10, h * 0.045)}px monospace`;
    [["RMS", T.overall(frequencyData)], ["BASS", bass], ["MID", mid], ["HIGH", high]].forEach((row, i) => {
      const y = h * (0.12 + i * 0.12);
      ctx.fillText(row[0], w * 0.06, y);
      ctx.strokeRect(w * 0.22, y - h * 0.04, w * 0.28, h * 0.045);
      ctx.fillStyle = "#19f3b0";
      ctx.fillRect(w * 0.22, y - h * 0.04, w * 0.28 * row[1], h * 0.045);
      ctx.fillStyle = "#9ad0d8";
    });
    ctx.beginPath();
    for (let i = 0; i < 100; i += 1) {
      const x = w * 0.55 + i / 99 * w * 0.38;
      const y = h * 0.35 + T.wave(timeData, i * 5) * h * 0.12;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = "#19f3b0";
    ctx.stroke();
    logs.forEach((log, i) => ctx.fillText(log, w * 0.56, h * (0.58 + i * 0.055)));
    ctx.fillText("CENTROID " + Math.round((mid + high * 2) * 1000), w * 0.06, h * 0.78);
  }
  window.LifePimAudioViz.register("cyber_dashboard", { draw });
})();
