(function () {
  const layers = [];
  function draw({ ctx, canvas, frequencyData }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    const bands = 64;
    const dataLen = frequencyData ? frequencyData.length : 256;
    const layer = [];
    for (let i = 0; i < bands; i += 1) {
      layer.push(T.avg(frequencyData, i * dataLen * 0.48 / bands, (i + 1) * dataLen * 0.48 / bands));
    }
    layers.unshift(layer);
    if (layers.length > 8) layers.pop();
    ctx.clearRect(0, 0, w, h);
    layers.slice().reverse().forEach((values, age) => {
      const depth = age / layers.length;
      const base = h * (0.88 - depth * 0.52);
      ctx.beginPath();
      ctx.moveTo(0, h);
      values.forEach((v, i) => {
        ctx.lineTo((i / (values.length - 1)) * w, base - v * h * (0.45 - depth * 0.2));
      });
      ctx.lineTo(w, h);
      ctx.closePath();
      ctx.fillStyle = `hsla(${170 + age * 18}, 80%, ${25 + age * 5}%, ${0.32 + (1 - depth) * 0.35})`;
      ctx.fill();
    });
  }
  window.LifePimAudioViz.register("audio_terrain", { draw });
})();
