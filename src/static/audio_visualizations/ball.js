(function () {
  const state = { x: 0.35, y: 0.35, vx: 0.45, vy: 0.32 };

  function reset() {
    state.x = 0.35;
    state.y = 0.35;
    state.vx = 0.45;
    state.vy = 0.32;
  }

  function draw({ ctx, canvas, frequencyData, delta, now, live }) {
    const width = canvas.width;
    const height = canvas.height;
    const data = frequencyData || new Uint8Array(32);
    let energy = 0.2;
    if (live && data.length) {
      energy = data.reduce((sum, value) => sum + value, 0) / (data.length * 255);
    } else {
      energy = 0.35 + Math.sin(now / 250) * 0.16;
    }
    state.vy += (0.45 + energy * 1.7) * delta;
    state.x += state.vx * delta;
    state.y += state.vy * delta;
    if (state.x < 0.08 || state.x > 0.92) {
      state.vx *= -1;
      state.x = Math.max(0.08, Math.min(0.92, state.x));
    }
    if (state.y > 0.88) {
      state.y = 0.88;
      state.vy = -0.72 - energy * 1.2;
    }
    if (state.y < 0.08) {
      state.y = 0.08;
      state.vy *= -0.6;
    }
    ctx.fillStyle = "rgba(3, 8, 12, 0.34)";
    ctx.fillRect(0, 0, width, height);
    const radius = Math.max(10, height * (0.08 + energy * 0.08));
    const x = state.x * width;
    const y = state.y * height;
    const glow = ctx.createRadialGradient(x, y, radius * 0.1, x, y, radius * 3);
    glow.addColorStop(0, "rgba(25, 243, 176, 0.95)");
    glow.addColorStop(0.35, "rgba(58, 214, 255, 0.4)");
    glow.addColorStop(1, "rgba(58, 214, 255, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, radius * 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#19f3b0";
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255, 255, 255, 0.72)";
    ctx.beginPath();
    ctx.arc(x - radius * 0.32, y - radius * 0.35, radius * 0.24, 0, Math.PI * 2);
    ctx.fill();
  }

  window.LifePimAudioViz.register("ball", { draw, reset });
})();
