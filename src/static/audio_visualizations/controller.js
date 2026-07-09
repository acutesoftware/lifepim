(function () {
  const registry = {};
  const state = {
    audio: null,
    player: null,
    canvas: null,
    ctx: null,
    panel: null,
    select: null,
    labels: {},
    audioCtx: null,
    analyser: null,
    source: null,
    frequencyData: null,
    timeData: null,
    raf: null,
    active: "bars",
    startedAt: 0,
    lastFrame: 0,
    running: false
  };

  function register(id, renderer) {
    registry[id] = renderer;
  }

  function init(options) {
    state.audio = options.audio;
    state.player = options.player;
    state.canvas = options.canvas;
    state.ctx = state.canvas.getContext("2d");
    state.panel = options.panel;
    state.select = options.select;
    state.labels = options.labels || {};
    state.active = registry[options.initial] ? options.initial : "bars";
    state.select.value = state.active;
    resize();
    window.addEventListener("resize", resize);
    state.panel.addEventListener("click", () => cycle());
    state.select.addEventListener("click", (event) => event.stopPropagation());
    state.select.addEventListener("change", () => setActive(state.select.value));
    renderIdle();
  }

  function ensureAnalyser() {
    if (state.analyser) {
      return true;
    }
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      state.audioCtx = state.audioCtx || new AudioContext();
      state.source = state.source || state.audioCtx.createMediaElementSource(state.audio);
      state.analyser = state.audioCtx.createAnalyser();
      state.analyser.fftSize = 1024;
      state.analyser.smoothingTimeConstant = 0.78;
      state.frequencyData = new Uint8Array(state.analyser.frequencyBinCount);
      state.timeData = new Uint8Array(state.analyser.fftSize);
      state.source.connect(state.analyser);
      state.analyser.connect(state.audioCtx.destination);
      state.player.classList.add("live-eq");
      return true;
    } catch (_) {
      return false;
    }
  }

  function start() {
    if (!ensureAnalyser()) {
      return;
    }
    if (state.audioCtx && state.audioCtx.state === "suspended") {
      state.audioCtx.resume();
    }
    state.running = true;
    state.startedAt = performance.now();
    state.lastFrame = state.startedAt;
    if (state.raf) {
      cancelAnimationFrame(state.raf);
    }
    drawLoop();
  }

  function stop() {
    state.running = false;
    if (state.raf) {
      cancelAnimationFrame(state.raf);
      state.raf = null;
    }
    renderIdle();
  }

  function setActive(id) {
    if (!registry[id]) {
      return;
    }
    state.active = id;
    state.select.value = id;
    const renderer = registry[id];
    if (renderer.reset) {
      renderer.reset();
    }
    if (state.running) {
      start();
    } else {
      renderIdle();
    }
  }

  function cycle() {
    const ids = Object.keys(state.labels).filter((id) => registry[id]);
    const current = Math.max(0, ids.indexOf(state.active));
    setActive(ids[(current + 1) % ids.length] || "bars");
  }

  function drawLoop(now) {
    const frameNow = now || performance.now();
    const delta = Math.min(0.08, (frameNow - state.lastFrame) / 1000);
    state.lastFrame = frameNow;
    state.analyser.getByteFrequencyData(state.frequencyData);
    state.analyser.getByteTimeDomainData(state.timeData);
    draw(frameNow, delta, true);
    state.raf = requestAnimationFrame(drawLoop);
  }

  function renderIdle() {
    draw(performance.now(), 0.016, false);
  }

  function draw(now, delta, live) {
    resize();
    const renderer = registry[state.active] || registry.bars;
    renderer.draw({
      ctx: state.ctx,
      canvas: state.canvas,
      frequencyData: state.frequencyData,
      timeData: state.timeData,
      now,
      delta,
      live
    });
  }

  function resize() {
    const rect = state.canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(rect.width * ratio));
    const height = Math.max(1, Math.round(rect.height * ratio));
    if (state.canvas.width !== width || state.canvas.height !== height) {
      state.canvas.width = width;
      state.canvas.height = height;
    }
  }

  window.LifePimAudioViz = {
    register,
    init,
    start,
    stop,
    setActive
  };
})();
