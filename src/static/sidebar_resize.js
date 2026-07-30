(function () {
  "use strict";

  const sidebar = document.getElementById("sidebar");
  const widthHandle = document.getElementById("sidebarWidthResizer");
  const projectsHandle = document.getElementById("sidebarProjectsResizer");
  const projectsPanel = document.getElementById("sidebarProjectsPanel");
  let storage = null;
  try {
    storage = window.localStorage;
  } catch (_) {
    storage = null;
  }
  const sidebarWidthKey = "lifepim.sidebar.width";
  const projectsHeightKey = "lifepim.sidebar.projectsHeight";
  const minSidebarWidth = 130;
  const maxSidebarWidth = 480;
  const minProjectsHeight = 92;

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function intValue(value, fallback) {
    const parsed = parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function storedValue(key) {
    if (!storage) {
      return null;
    }
    try {
      return storage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  function storeValue(key, value) {
    if (!storage) {
      return;
    }
    try {
      storage.setItem(key, String(value));
    } catch (_) {
    }
  }

  function setSidebarWidth(value, persist) {
    const width = clamp(Math.round(value), minSidebarWidth, maxSidebarWidth);
    document.documentElement.style.setProperty("--sidebar-width", `${width}px`);
    if (persist) {
      storeValue(sidebarWidthKey, width);
    }
  }

  function maxProjectsHeight() {
    if (!sidebar) {
      return 420;
    }
    const height = sidebar.getBoundingClientRect().height || window.innerHeight || 600;
    return Math.max(minProjectsHeight, Math.min(420, height - 120));
  }

  function setProjectsHeight(value, persist) {
    const height = clamp(Math.round(value), minProjectsHeight, maxProjectsHeight());
    document.documentElement.style.setProperty("--side-project-height", `${height}px`);
    if (persist) {
      storeValue(projectsHeightKey, height);
    }
  }

  function restoreSizes() {
    const storedWidth = intValue(storedValue(sidebarWidthKey), 190);
    const storedHeight = intValue(storedValue(projectsHeightKey), 230);
    setSidebarWidth(storedWidth, false);
    setProjectsHeight(storedHeight, false);
  }

  function dragWidth(startEvent) {
    if (!sidebar) {
      return;
    }
    startEvent.preventDefault();
    const startX = startEvent.clientX;
    const startWidth = sidebar.getBoundingClientRect().width;
    widthHandle.classList.add("active");
    document.body.classList.add("sidebar-resizing");

    function move(evt) {
      setSidebarWidth(startWidth + evt.clientX - startX, false);
    }

    function stop(evt) {
      setSidebarWidth(startWidth + evt.clientX - startX, true);
      widthHandle.classList.remove("active");
      document.body.classList.remove("sidebar-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    }

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  }

  function dragProjectsHeight(startEvent) {
    if (!projectsPanel) {
      return;
    }
    startEvent.preventDefault();
    const startY = startEvent.clientY;
    const startHeight = projectsPanel.getBoundingClientRect().height;
    projectsHandle.classList.add("active");
    document.body.classList.add("project-split-resizing");

    function move(evt) {
      setProjectsHeight(startHeight - (evt.clientY - startY), false);
    }

    function stop(evt) {
      setProjectsHeight(startHeight - (evt.clientY - startY), true);
      projectsHandle.classList.remove("active");
      document.body.classList.remove("project-split-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    }

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  }

  restoreSizes();

  if (widthHandle) {
    widthHandle.addEventListener("pointerdown", dragWidth);
  }
  if (projectsHandle) {
    projectsHandle.addEventListener("pointerdown", dragProjectsHeight);
  }
  window.addEventListener("resize", () => {
    if (projectsPanel) {
      setProjectsHeight(intValue(storedValue(projectsHeightKey), projectsPanel.getBoundingClientRect().height), false);
    }
  });
})();
