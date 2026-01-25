(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  const editor = qs("#note-editor");
  if (!editor) {
    return;
  }

  const statusEl = qs("#note-edit-status");
  const sizeEl = qs("#note-meta-size");
  const modifiedEl = qs("#note-meta-modified");
  const saveUrl = editor.dataset.saveUrl || "";

  let saveTimer = null;
  let inflight = false;
  let pending = false;
  let lastSaved = editor.value;

  function setStatus(text, isError) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = text;
    statusEl.style.color = isError ? "#b00020" : "#555";
  }

  function scheduleSave() {
    if (!saveUrl) {
      return;
    }
    if (saveTimer) {
      clearTimeout(saveTimer);
    }
    saveTimer = setTimeout(() => {
      if (editor.value === lastSaved) {
        return;
      }
      void doSave();
    }, 800);
  }

  async function doSave() {
    if (!saveUrl) {
      return;
    }
    if (inflight) {
      pending = true;
      return;
    }
    const content = editor.value;
    if (content === lastSaved) {
      return;
    }
    inflight = true;
    setStatus("Saving...");
    try {
      const resp = await fetch(saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Unable to save note.");
      }
      lastSaved = content;
      if (sizeEl && data.size !== undefined) {
        sizeEl.textContent = data.size;
      }
      if (modifiedEl && data.date_modified) {
        modifiedEl.textContent = data.date_modified;
      }
      const now = new Date();
      const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setStatus(`Saved ${time}`);
    } catch (err) {
      setStatus(err.message || "Save failed.", true);
    } finally {
      inflight = false;
      if (pending) {
        pending = false;
        if (editor.value !== lastSaved) {
          void doSave();
        }
      }
    }
  }

  editor.addEventListener("input", scheduleSave);
  editor.addEventListener("blur", () => {
    if (editor.value !== lastSaved) {
      void doSave();
    }
  });
})();
