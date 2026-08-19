(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  const editor = qs("#note-popout-editor");
  const viewer = qs("#note-popout-viewer");
  const statusEl = qs("#note-popout-status");
  const viewBtn = qs("#note-popout-view");
  const editBtn = qs("#note-popout-edit");
  const saveBtn = qs("#note-popout-save");
  const closeBtn = qs("#note-popout-close");

  if (!editor || !viewer) {
    if (closeBtn) {
      closeBtn.addEventListener("click", () => window.close());
    }
    return;
  }

  const saveUrl = editor.dataset.saveUrl || "";
  const previewUrl = editor.dataset.previewUrl || "";
  const csrfMeta = qs("meta[name='csrf-token']");
  const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

  let lastSaved = editor.value;
  let fileMtimeNs = editor.dataset.fileMtimeNs || "";
  let fileHash = editor.dataset.fileHash || "";
  let mode = "view";
  let inflight = false;

  function setStatus(text, isError) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = text;
    statusEl.classList.toggle("is-error", Boolean(isError));
  }

  function isDirty() {
    return editor.value !== lastSaved;
  }

  function requestHeaders() {
    const headers = new Headers({ "Content-Type": "application/json" });
    if (csrfToken) {
      headers.set("X-CSRFToken", csrfToken);
    }
    return headers;
  }

  async function responseJson(resp) {
    try {
      return await resp.json();
    } catch (err) {
      return {};
    }
  }

  function setMode(nextMode) {
    mode = nextMode === "edit" ? "edit" : "view";
    const editing = mode === "edit";
    editor.hidden = !editing;
    viewer.hidden = editing;
    if (viewBtn) {
      viewBtn.classList.toggle("active", !editing);
    }
    if (editBtn) {
      editBtn.classList.toggle("active", editing);
    }
    if (editing) {
      editor.focus();
    }
  }

  async function refreshViewer() {
    if (!previewUrl) {
      viewer.textContent = editor.value;
      return;
    }
    try {
      const resp = await fetch(previewUrl, {
        method: "POST",
        headers: requestHeaders(),
        body: JSON.stringify({ content: editor.value, body_only: true }),
      });
      const data = await responseJson(resp);
      if (!resp.ok) {
        throw new Error(data.error || "Unable to render note.");
      }
      viewer.innerHTML = data.html || "";
    } catch (err) {
      viewer.textContent = editor.value;
      setStatus(err.message || "View render failed.", true);
    }
  }

  async function saveNote(forceStatus) {
    if (!saveUrl || inflight) {
      return;
    }
    if (!isDirty()) {
      if (forceStatus) {
        setStatus("Saved");
      }
      return;
    }
    const content = editor.value;
    inflight = true;
    setStatus("Saving...");
    try {
      const resp = await fetch(saveUrl, {
        method: "POST",
        headers: requestHeaders(),
        body: JSON.stringify({ content, base_mtime_ns: fileMtimeNs, base_hash: fileHash }),
      });
      const data = await responseJson(resp);
      if (!resp.ok) {
        throw new Error(data.error || "Save failed.");
      }
      lastSaved = content;
      if (data.mtime_ns !== undefined) {
        fileMtimeNs = String(data.mtime_ns || "");
        editor.dataset.fileMtimeNs = fileMtimeNs;
      }
      if (data.sha256 !== undefined) {
        fileHash = String(data.sha256 || "");
        editor.dataset.fileHash = fileHash;
      }
      setStatus(editor.value === lastSaved ? "Saved" : "Unsaved changes");
      if (mode === "view") {
        await refreshViewer();
      }
    } catch (err) {
      setStatus(err.message || "Save failed.", true);
    } finally {
      inflight = false;
    }
  }

  function confirmDiscardUnsaved() {
    if (!isDirty()) {
      return true;
    }
    return window.confirm("This note has unsaved changes. Close without saving?");
  }

  if (viewBtn) {
    viewBtn.addEventListener("click", async () => {
      await refreshViewer();
      setMode("view");
      if (isDirty()) {
        setStatus("Unsaved changes");
      }
    });
  }

  if (editBtn) {
    editBtn.addEventListener("click", () => setMode("edit"));
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      void saveNote(true);
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      if (confirmDiscardUnsaved()) {
        window.close();
      }
    });
  }

  editor.addEventListener("input", () => {
    setStatus(isDirty() ? "Unsaved changes" : "Saved");
  });

  editor.addEventListener("keydown", (evt) => {
    if ((evt.ctrlKey || evt.metaKey) && !evt.shiftKey && !evt.altKey && evt.key.toLowerCase() === "s") {
      evt.preventDefault();
      void saveNote(true);
    }
  });

  window.addEventListener("beforeunload", (evt) => {
    if (!isDirty()) {
      return;
    }
    evt.preventDefault();
    evt.returnValue = "";
  });

  setMode("view");
})();
