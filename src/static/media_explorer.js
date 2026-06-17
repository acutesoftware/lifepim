(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function initSelection() {
    const form = qs(".media-actions-form");
    if (!form) {
      return;
    }
    const checkboxes = qsa(".media-select-box", form);
    const selectAll = qs(".media-select-all", form);
    const countEl = qs(".media-selected-count", form);
    const actionSelect = qs(".media-action-select", form);
    const albumSelect = qs(".media-action-album", form);
    const tagsInput = qs(".media-action-tags", form);
    const applyBtn = qs(".media-action-btn", form);

    function selectionCount() {
      return checkboxes.filter((cb) => cb.checked).length;
    }

    function updateCount() {
      const count = selectionCount();
      if (countEl) {
        countEl.textContent = count
          ? `${count} selected`
          : countEl.dataset.empty || "No selection";
      }
      updateActionState();
    }

    function updateActionVisibility() {
      if (!actionSelect) {
        return;
      }
      const action = actionSelect.value;
      const needsAlbum = action === "add_to_album" || action === "remove_from_album";
      if (albumSelect) {
        albumSelect.style.display = needsAlbum ? "inline-block" : "none";
      }
      if (tagsInput) {
        tagsInput.style.display = action === "tag" ? "inline-block" : "none";
      }
    }

    function updateActionState() {
      if (!applyBtn || !actionSelect) {
        return;
      }
      const count = selectionCount();
      const action = actionSelect.value;
      let ready = count > 0 && !!action;
      if (ready && (action === "add_to_album" || action === "remove_from_album")) {
        ready = !!(albumSelect && albumSelect.value);
      }
      if (ready && action === "tag") {
        ready = !!(tagsInput && tagsInput.value.trim());
      }
      applyBtn.disabled = !ready;
    }

    if (selectAll) {
      selectAll.addEventListener("change", () => {
        checkboxes.forEach((cb) => {
          cb.checked = selectAll.checked;
        });
        updateCount();
      });
    }

    checkboxes.forEach((cb) => {
      cb.addEventListener("change", () => {
        if (selectAll && !cb.checked) {
          selectAll.checked = false;
        }
        updateCount();
      });
    });

    function selectedPaths() {
      return checkboxes
        .filter((cb) => cb.checked)
        .map((cb) => cb.dataset.path || "")
        .filter(Boolean);
    }

    if (actionSelect) {
      actionSelect.addEventListener("change", () => {
        updateActionVisibility();
        updateActionState();
      });
    }
    if (albumSelect) {
      albumSelect.addEventListener("change", updateActionState);
    }
    if (tagsInput) {
      tagsInput.addEventListener("input", updateActionState);
    }

    form.addEventListener("submit", (evt) => {
      if (!actionSelect) {
        return;
      }
      if (actionSelect.value === "copy_paths") {
        evt.preventDefault();
        const paths = selectedPaths();
        if (!paths.length || !navigator.clipboard) {
          return;
        }
        navigator.clipboard.writeText(paths.join("\n")).then(() => {
          if (countEl) {
            countEl.textContent = `Copied ${paths.length}`;
          }
          actionSelect.value = "";
          updateActionVisibility();
          updateActionState();
        });
      }
    });

    updateActionVisibility();
    updateCount();
  }

  function initCopyButtons() {
    qsa(".media-copy-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const path = btn.dataset.copyPath || "";
        if (!path || !navigator.clipboard) {
          return;
        }
        navigator.clipboard.writeText(path).then(() => {
          const original = btn.textContent;
          btn.textContent = "Copied";
          setTimeout(() => {
            btn.textContent = original;
          }, 1200);
        });
      });
    });
  }

  function initInspectorResize() {
    const slider = qs(".media-inspector-width");
    const body = qs(".media-body");
    if (!slider || !body) {
      return;
    }
    const storageKey = "lifepim.media.inspectorWidth";
    const min = Number(slider.min) || 220;
    const max = Number(slider.max) || 560;

    function clamp(value) {
      const width = Number(value);
      if (!Number.isFinite(width)) {
        return Number(slider.value) || 280;
      }
      return Math.min(max, Math.max(min, width));
    }

    function applyWidth(value) {
      const width = clamp(value);
      slider.value = String(width);
      body.style.setProperty("--media-inspector-width", `${width}px`);
      try {
        window.localStorage.setItem(storageKey, String(width));
      } catch (err) {
        // Ignore storage failures; the slider should still work for this page.
      }
    }

    try {
      const savedWidth = window.localStorage.getItem(storageKey);
      if (savedWidth) {
        slider.value = String(clamp(savedWidth));
      }
    } catch (err) {
      // Ignore storage failures; use the template default.
    }

    applyWidth(slider.value);
    slider.addEventListener("input", () => applyWidth(slider.value));
  }

  document.addEventListener("DOMContentLoaded", () => {
    initSelection();
    initCopyButtons();
    initInspectorResize();
  });
})();
