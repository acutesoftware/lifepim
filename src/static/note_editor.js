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
  const saveNowBtn = qs("#note-save-now");
  const noteId = editor.dataset.noteId || "";
  const saveUrl = editor.dataset.saveUrl || "";
  const saveDelayMs = 1500;
  const draftKey = noteId ? `lifepim.noteDraft.${noteId}` : "";

  let saveTimer = null;
  let inflight = false;
  let pending = false;
  let lastSaved = editor.value;
  let fileMtimeNs = editor.dataset.fileMtimeNs || "";
  let fileHash = editor.dataset.fileHash || "";

  function draftPayload(content) {
    return {
      content,
      fileMtimeNs,
      fileHash,
      savedContent: lastSaved,
      updatedAt: new Date().toISOString(),
    };
  }

  function writeDraft() {
    if (!draftKey) {
      return;
    }
    try {
      window.localStorage.setItem(draftKey, JSON.stringify(draftPayload(editor.value)));
    } catch (err) {
      // Saving to disk remains the source of truth; local drafts are best-effort.
    }
  }

  function clearDraft() {
    if (!draftKey) {
      return;
    }
    try {
      window.localStorage.removeItem(draftKey);
    } catch (err) {
    }
  }

  function restoreDraftIfNeeded() {
    if (!draftKey) {
      return;
    }
    let draft = null;
    try {
      draft = JSON.parse(window.localStorage.getItem(draftKey) || "null");
    } catch (err) {
      draft = null;
    }
    if (!draft || typeof draft.content !== "string" || draft.content === editor.value) {
      return;
    }
    const ok = window.confirm("A locally saved draft exists for this note. Restore it into the editor?");
    if (ok) {
      editor.value = draft.content;
      setStatus("Restored local draft. Save when ready.", true);
      scheduleSave();
    }
  }

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
    writeDraft();
    if (saveTimer) {
      clearTimeout(saveTimer);
    }
    saveTimer = setTimeout(() => {
      if (editor.value === lastSaved) {
        return;
      }
      void doSave();
    }, saveDelayMs);
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
      writeDraft();
      const resp = await fetch(saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, base_mtime_ns: fileMtimeNs, base_hash: fileHash }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Unable to save note.");
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
      if (sizeEl && data.size !== undefined) {
        sizeEl.textContent = data.size;
      }
      if (modifiedEl && data.date_modified) {
        modifiedEl.textContent = data.date_modified;
      }
      const now = new Date();
      const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setStatus(`Saved ${time}`);
      if (editor.value === lastSaved) {
        clearDraft();
      } else {
        writeDraft();
      }
    } catch (err) {
      writeDraft();
      setStatus(`${err.message || "Save failed."} Local draft kept in this browser.`, true);
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

  restoreDraftIfNeeded();
  editor.addEventListener("input", scheduleSave);
  editor.addEventListener("blur", () => {
    if (editor.value !== lastSaved) {
      void doSave();
    }
  });
  if (saveNowBtn) {
    saveNowBtn.addEventListener("click", () => {
      if (saveTimer) {
        clearTimeout(saveTimer);
        saveTimer = null;
      }
      void doSave();
    });
  }
  window.addEventListener("beforeunload", (evt) => {
    if (editor.value === lastSaved) {
      return;
    }
    writeDraft();
    evt.preventDefault();
    evt.returnValue = "";
  });
})();
