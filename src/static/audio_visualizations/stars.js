(function () {
  const stars = [];
  let bassAvg = 0;
  let spin = 0;
  let spinBurst = 0;
  let beatPulse = 0;
  let spawnCarry = 0;

  function reset() {
    stars.length = 0;
    bassAvg = 0;
    spin = 0;
    spinBurst = 0;
    beatPulse = 0;
    spawnCarry = 0;
  }

  function makeStar() {
    const angle = Math.random() * Math.PI * 2;
    const distance = 0.035 + Math.random() * 0.24;
    return {
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
      z: 0.12 + Math.random() * 0.62,
      hue: 168 + Math.random() * 55
    };
  }

  function draw({ ctx, canvas, frequencyData, delta, now, live }) {
    const width = canvas.width;
    const height = canvas.height;
    const canvasScale = Math.max(1, Math.min(1.45, Math.min(width, height) / 720));
    const data = frequencyData || new Uint8Array(32);
    const targetStars = Math.max(220, Math.floor((width * height) / 4200));
    while (stars.length < targetStars) {
      stars.push(makeStar());
    }
    let energy = 0.25;
    let bass = 0.2;
    if (live && data.length) {
      energy = data.reduce((sum, value) => sum + value, 0) / (data.length * 255);
      const bassBins = Math.max(2, Math.floor(data.length * 0.08));
      bass = data.slice(0, bassBins).reduce((sum, value) => sum + value, 0) / (bassBins * 255);
    } else {
      energy = 0.35 + Math.sin(now / 300) * 0.14;
      bass = energy;
    }
    const bassHit = Math.max(0, bass - bassAvg);
    if (bassHit > 0.07) {
      spinBurst = Math.min(2.2, spinBurst + bassHit * 5.5);
      beatPulse = Math.min(1, beatPulse + bassHit * 3.2);
    }
    bassAvg = bassAvg * 0.88 + bass * 0.12;
    spinBurst = Math.max(0, spinBurst - delta * 2.4);
    beatPulse = Math.max(0, beatPulse - delta * 2.8);
    spin += delta * (0.08 + energy * 0.16 + spinBurst * 1.45);
    spawnCarry += delta * (20 + energy * 24 + beatPulse * 16);
    while (spawnCarry >= 1) {
      stars.push(makeStar());
      spawnCarry -= 1;
    }
    if (stars.length > targetStars + 80) {
      stars.splice(0, stars.length - (targetStars + 80));
    }
    ctx.fillStyle = "rgba(0, 3, 10, 0.42)";
    ctx.fillRect(0, 0, width, height);
    const cx = width / 2;
    const cy = height / 2;
    const speed = delta * (0.45 + energy * 2.3 + beatPulse * 1.4);
    const fieldPulse = 1 + beatPulse * 0.22;
    stars.forEach((star, index) => {
      star.z -= speed;
      if (star.z <= 0.03) {
        stars[index] = makeStar();
        return;
      }
      const scale = 1 / star.z;
      const rotatedX = star.x * Math.cos(spin) - star.y * Math.sin(spin);
      const rotatedY = star.x * Math.sin(spin) + star.y * Math.cos(spin);
      const x = cx + rotatedX * width * scale * fieldPulse;
      const y = cy + rotatedY * height * scale * fieldPulse;
      const size = Math.max(0.8 * canvasScale, (1 - star.z) * 3.2 * canvasScale * (1 + energy * 0.55 + beatPulse * 0.2));
      if (x < -20 || x > width + 20 || y < -20 || y > height + 20) {
        stars[index] = makeStar();
        return;
      }
      const alpha = Math.min(0.58, 0.2 + energy * 0.22 + beatPulse * 0.16);
      ctx.strokeStyle = `hsla(${star.hue + beatPulse * 18}, 72%, 62%, ${alpha})`;
      ctx.lineWidth = size;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(x, y);
      const trail = (10 + energy * 20 + beatPulse * 70) * canvasScale;
      ctx.lineTo(x - rotatedX * trail * fieldPulse, y - rotatedY * trail * fieldPulse);
      ctx.stroke();
    });
    ctx.fillStyle = `rgba(25, 243, 176, ${0.06 + beatPulse * 0.06})`;
    ctx.beginPath();
    ctx.arc(cx, cy, Math.max(width, height) * (0.045 + energy * 0.045 + beatPulse * 0.035), 0, Math.PI * 2);
    ctx.fill();
  }

  window.LifePimAudioViz.register("stars", { draw, reset });
})();
