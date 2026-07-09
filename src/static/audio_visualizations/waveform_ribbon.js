(function () {
  const frames = [];
  function draw({ ctx, canvas, timeData }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const samples = [];
    for (let i = 0; i < 80; i += 1) samples.push(T.wave(timeData, i * ((timeData ? timeData.length : 80) / 80)));
    frames.unshift(samples);
    if (frames.length > 24) frames.pop();
    ctx.clearRect(0, 0, w, h);
    frames.slice().reverse().forEach((frame, age) => {
      const depth = age / frames.length;
      const yBase = h * (0.2 + depth * 0.68);
      const amp = h * (0.22 - depth * 0.14);
      ctx.beginPath();
      frame.forEach((v, i) => {
        const x = w * 0.08 + (i / (frame.length - 1)) * w * 0.84;
        const y = yBase + v * amp;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = `rgba(25, 243, 176, ${0.12 + (1 - depth) * 0.6})`;
      ctx.lineWidth = Math.max(1, (1 - depth) * 4);
      ctx.stroke();
    });
  }
  window.LifePimAudioViz.register("waveform_ribbon", { draw });
})();
