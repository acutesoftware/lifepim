(function () {
  function draw({ ctx, canvas, frequencyData, now, live }) {
    const width = canvas.width;
    const height = canvas.height;
    const data = frequencyData || new Uint8Array(64);
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "rgba(3, 10, 15, 0.92)";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "rgba(25, 243, 176, 0.16)";
    ctx.lineWidth = 1;
    for (let y = height * 0.2; y < height; y += height * 0.2) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    ctx.beginPath();
    const points = 96;
    const usableBins = Math.max(1, Math.floor(data.length * 0.42));
    for (let i = 0; i < points; i += 1) {
      const index = Math.min(usableBins - 1, Math.floor((i / (points - 1)) * usableBins));
      const raw = live ? data[index] || 0 : 80 + Math.sin(now / 180 + i * 0.25) * 45;
      const x = (i / (points - 1)) * width;
      const y = height - Math.max(0, Math.min(1, raw / 255)) * height * 0.9 - height * 0.05;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.shadowColor = "#19f3b0";
    ctx.shadowBlur = 12;
    ctx.strokeStyle = "#19f3b0";
    ctx.lineWidth = Math.max(2, width * 0.006);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  window.LifePimAudioViz.register("line", { draw });
})();
