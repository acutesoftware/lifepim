(function () {
  function draw({ ctx, canvas, timeData, now, live }) {
    const width = canvas.width;
    const height = canvas.height;
    const data = timeData || new Uint8Array(256);
    ctx.fillStyle = "rgba(2, 15, 13, 0.9)";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "rgba(25, 243, 176, 0.18)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    ctx.beginPath();
    const points = live ? data.length : 256;
    for (let i = 0; i < points; i += 1) {
      const value = live ? data[i] : 128 + Math.sin(now / 90 + i * 0.08) * 55;
      const x = (i / (points - 1)) * width;
      const y = (value / 255) * height;
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.shadowColor = "#19f3b0";
    ctx.shadowBlur = 14;
    ctx.strokeStyle = "#19f3b0";
    ctx.lineWidth = Math.max(2, width * 0.005);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  window.LifePimAudioViz.register("scope", { draw });
})();
