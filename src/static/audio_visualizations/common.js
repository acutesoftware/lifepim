(function () {
  function avg(data, start, end) {
    if (!data || !data.length) {
      return 0;
    }
    const from = Math.max(0, Math.floor(start));
    const to = Math.min(data.length, Math.max(from + 1, Math.floor(end)));
    let sum = 0;
    for (let i = from; i < to; i += 1) {
      sum += data[i];
    }
    return sum / ((to - from) * 255);
  }

  function overall(data) {
    return avg(data, 0, data ? data.length : 0);
  }

  function wave(data, index) {
    if (!data || !data.length) {
      return 0;
    }
    const i = Math.max(0, Math.min(data.length - 1, Math.floor(index)));
    return (data[i] - 128) / 128;
  }

  function fade(ctx, canvas, alpha, color) {
    ctx.fillStyle = color || `rgba(0, 0, 0, ${alpha})`;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  function band(data, fractionStart, fractionEnd) {
    const len = data ? data.length : 0;
    return avg(data, len * fractionStart, len * fractionEnd);
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  window.LifePimAudioVizTools = { avg, overall, wave, fade, band, clamp };
})();
