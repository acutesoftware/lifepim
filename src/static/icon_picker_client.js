(function () {
  "use strict";

  function byId(id) {
    return id ? document.getElementById(id) : null;
  }

  function rememberSelection(el) {
    if (!el || typeof el.selectionStart !== "number") {
      return;
    }
    el.dataset.iconPickerSelectionStart = String(el.selectionStart);
    el.dataset.iconPickerSelectionEnd = String(el.selectionEnd);
  }

  function selectionFor(el) {
    const start = parseInt(el.dataset.iconPickerSelectionStart || "", 10);
    const end = parseInt(el.dataset.iconPickerSelectionEnd || "", 10);
    if (Number.isFinite(start) && Number.isFinite(end)) {
      return { start: Math.max(0, start), end: Math.max(0, end) };
    }
    if (typeof el.selectionStart === "number") {
      return { start: el.selectionStart, end: el.selectionEnd };
    }
    const len = (el.value || "").length;
    return { start: len, end: len };
  }

  function applyIcon(payload) {
    const icon = (payload && payload.icon) || "";
    const targetId = (payload && payload.targetId) || "";
    const mode = (payload && payload.mode) || "replace";
    const target = byId(targetId);
    if (!icon || !target) {
      return;
    }
    if (mode === "insert" && "value" in target) {
      const sel = selectionFor(target);
      const before = target.value.slice(0, sel.start);
      const after = target.value.slice(sel.end);
      target.value = before + icon + after;
      const cursor = sel.start + icon.length;
      target.focus();
      if (typeof target.setSelectionRange === "function") {
        target.setSelectionRange(cursor, cursor);
      }
    } else if ("value" in target) {
      target.value = icon;
      target.focus();
      if (typeof target.select === "function") {
        target.select();
      }
    }
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function openPicker(button) {
    const targetId = button.dataset.iconPickerTarget || "";
    const mode = button.dataset.iconPickerMode || "replace";
    const target = byId(targetId);
    rememberSelection(target);
    const params = new URLSearchParams({ target: targetId, mode });
    window.open(`/icons/picker?${params.toString()}`, "lifepimIconPicker", "width=760,height=720,resizable=yes,scrollbars=yes");
  }

  document.addEventListener("selectionchange", () => {
    const active = document.activeElement;
    if (active && active.matches && active.matches("[data-icon-picker-track-selection], textarea, input[type='text'], input[type='search']")) {
      rememberSelection(active);
    }
  });

  document.addEventListener("click", (evt) => {
    const button = evt.target.closest("[data-icon-picker-target]");
    if (!button) {
      return;
    }
    evt.preventDefault();
    openPicker(button);
  });

  window.LifePIMIconPickerSelect = applyIcon;
})();
