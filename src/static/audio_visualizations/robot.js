(function () {
  let bassAvg = 0;
  let stomp = 0;
  let poseFlip = 1;
  function draw({ ctx, canvas, frequencyData, delta, now }) {
    const T = window.LifePimAudioVizTools;
    const w = canvas.width, h = canvas.height, cx = w / 2;
    const bass = T.band(frequencyData, 0, 0.12), mid = T.band(frequencyData, 0.12, 0.35), high = T.band(frequencyData, 0.35, 0.8);
    const hit = Math.max(0, bass - bassAvg);
    if (hit > 0.08) {
      stomp = Math.min(1, stomp + hit * 5);
      poseFlip *= -1;
    }
    bassAvg = bassAvg * 0.88 + bass * 0.12;
    stomp = Math.max(0, stomp - delta * 2.0);
    ctx.fillStyle = `rgba(3, 8, 12, ${0.28 + stomp * 0.18})`;
    ctx.fillRect(0, 0, w, h);
    const beatBounce = stomp * h * 0.15;
    const groove = Math.sin(now * (0.005 + bass * 0.014)) * h * (0.015 + bass * 0.045);
    const y = h * 0.56 - beatBounce - groove;
    const lean = poseFlip * (stomp * 0.28 + mid * 0.16);
    const scale = Math.min(w, h) * (0.18 + stomp * 0.03);
    ctx.save();
    ctx.translate(cx, y);
    ctx.rotate(lean);
    ctx.strokeStyle = "#19f3b0"; ctx.fillStyle = "#101b22"; ctx.lineWidth = Math.max(3, scale * 0.08);
    ctx.fillRect(-scale * 0.5, -scale * 0.7, scale, scale * 0.7); ctx.strokeRect(-scale * 0.5, -scale * 0.7, scale, scale * 0.7);
    ctx.fillRect(-scale * 0.35, -scale * 1.25, scale * 0.7, scale * 0.42); ctx.strokeRect(-scale * 0.35, -scale * 1.25, scale * 0.7, scale * 0.42);
    ctx.fillStyle = "#f0d34c";
    ctx.beginPath(); ctx.arc(-scale * 0.16, -scale * 1.04, 3 + high * 10 + stomp * 8, 0, Math.PI * 2); ctx.arc(scale * 0.16, -scale * 1.04, 3 + high * 10 + stomp * 8, 0, Math.PI * 2); ctx.fill();
    const arm = mid * scale * 0.8 + Math.sin(now * 0.006) * scale * 0.25 + stomp * scale * 0.85;
    ctx.beginPath(); ctx.moveTo(-scale * 0.5, -scale * 0.45); ctx.lineTo(-scale - arm * poseFlip, -scale * (0.2 + stomp * 0.8)); ctx.moveTo(scale * 0.5, -scale * 0.45); ctx.lineTo(scale + arm * poseFlip, -scale * (0.2 - stomp * 0.45)); ctx.stroke();
    const knee = stomp * scale * 0.6 * poseFlip;
    ctx.beginPath(); ctx.moveTo(-scale * 0.24, 0); ctx.lineTo(-scale * 0.44 - knee, scale * (0.75 - stomp * 0.2)); ctx.moveTo(scale * 0.24, 0); ctx.lineTo(scale * 0.44 + knee, scale * (0.75 + stomp * 0.1)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, -scale * 1.25); ctx.lineTo(Math.sin(now * 0.01) * high * scale + stomp * poseFlip * scale * 0.3, -scale * 1.55); ctx.stroke();
    ctx.restore();
    if (stomp > 0.05) {
      ctx.strokeStyle = `rgba(25, 243, 176, ${stomp * 0.6})`;
      ctx.lineWidth = Math.max(2, h * 0.006);
      ctx.beginPath();
      ctx.ellipse(cx, h * 0.82, scale * (1 + stomp * 2.2), scale * (0.18 + stomp * 0.2), 0, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  window.LifePimAudioViz.register("robot", { draw });
})();
