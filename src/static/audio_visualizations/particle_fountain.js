(function () {
  const particles = [];
  const bands = [
    { name: "bass", from: 0, to: 0.12, x: 0.28, hue: 24, avg: 0, carry: 0, spread: 0.55, lift: 0.98 },
    { name: "mid", from: 0.12, to: 0.38, x: 0.5, hue: 165, avg: 0, carry: 0, spread: 0.38, lift: 0.78 },
    { name: "treble", from: 0.38, to: 0.78, x: 0.72, hue: 215, avg: 0, carry: 0, spread: 0.28, lift: 0.58 }
  ];

  function spawn(w, h, band, amount, power, burst) {
    for (let i = 0; i < amount; i += 1) {
      const side = (Math.random() - 0.5);
      particles.push({
        x: w * band.x + side * w * 0.025,
        y: h * (0.9 + Math.random() * 0.035),
        vx: side * w * band.spread * (0.25 + Math.random() * 0.8) * (burst ? 1.35 : 0.75),
        vy: -h * (0.16 + Math.random() * band.lift + power * 0.72) * (burst ? 1.16 : 0.82),
        life: 0.75 + Math.random() * 0.55 + power * 0.35,
        hue: band.hue + (Math.random() - 0.5) * 28,
        r: 0.006 + Math.random() * 0.008 + power * 0.006,
        drag: 0.985 - power * 0.025
      });
    }
    if (particles.length > 520) {
      particles.splice(0, particles.length - 520);
    }
  }

  function draw({ ctx, canvas, frequencyData, delta }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height;
    T.fade(ctx, canvas, 0.16);
    bands.forEach((band) => {
      const value = T.band(frequencyData, band.from, band.to);
      const hit = Math.max(0, value - band.avg);
      band.carry += delta * (value * 32 + hit * 60);
      while (band.carry >= 1) {
        spawn(w, h, band, 1, value, false);
        band.carry -= 1;
      }
      if (hit > 0.065 || value > 0.58) {
        spawn(w, h, band, 6 + Math.floor(hit * 85 + value * 8), value + hit * 1.5, true);
      }
      band.avg = band.avg * 0.88 + value * 0.12;
      drawEmitter(ctx, w, h, band, value, hit);
    });
    particles.forEach((p) => {
      p.vy += h * 0.72 * delta;
      p.vx *= p.drag;
      p.x += p.vx * delta;
      p.y += p.vy * delta;
      p.life -= delta * 0.68;
      const alpha = Math.max(0, Math.min(1, p.life));
      ctx.fillStyle = `hsla(${p.hue}, 95%, 62%, ${alpha * 0.86})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(1.6, Math.min(w, h) * p.r * alpha), 0, Math.PI * 2);
      ctx.fill();
    });
    for (let i = particles.length - 1; i >= 0; i -= 1) if (particles[i].life <= 0) particles.splice(i, 1);
  }

  function drawEmitter(ctx, w, h, band, value, hit) {
    const x = w * band.x;
    const y = h * 0.92;
    const radius = Math.min(w, h) * (0.018 + value * 0.035 + hit * 0.08);
    const glow = ctx.createRadialGradient(x, y, radius * 0.2, x, y, radius * 4);
    glow.addColorStop(0, `hsla(${band.hue}, 95%, 62%, ${0.45 + value * 0.35})`);
    glow.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, radius * 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `hsla(${band.hue}, 95%, 65%, ${0.55 + value * 0.35})`;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  window.LifePimAudioViz.register("particle_fountain", { draw });
})();
