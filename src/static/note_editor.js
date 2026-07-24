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
  const toolbar = qs(".note-markdown-toolbar");
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

  function selection() {
    const start = Math.max(0, editor.selectionStart || 0);
    const end = Math.max(0, editor.selectionEnd || 0);
    return start <= end ? { start, end } : { start: end, end: start };
  }

  function setEditorSelection(start, end) {
    editor.focus();
    editor.setSelectionRange(start, end);
  }

  function replaceSelection(start, end, replacement, cursorStart, cursorEnd) {
    const before = editor.value.slice(0, start);
    const after = editor.value.slice(end);
    editor.value = before + replacement + after;
    setEditorSelection(cursorStart, cursorEnd);
    scheduleSave();
  }

  function needsLeadingNewline(position) {
    return position > 0 && editor.value.charAt(position - 1) !== "\n";
  }

  function needsTrailingNewline(position) {
    return position < editor.value.length && editor.value.charAt(position) !== "\n";
  }

  function wrapSelection(prefix, suffix, placeholder) {
    const sel = selection();
    const selected = editor.value.slice(sel.start, sel.end);
    const inner = selected || placeholder;
    const replacement = prefix + inner + suffix;
    const innerStart = sel.start + prefix.length;
    replaceSelection(sel.start, sel.end, replacement, innerStart, innerStart + inner.length);
  }

  function lineSelection() {
    const sel = selection();
    let start = sel.start;
    let end = sel.end;
    while (start > 0 && editor.value.charAt(start - 1) !== "\n") {
      start -= 1;
    }
    while (end < editor.value.length && editor.value.charAt(end) !== "\n") {
      end += 1;
    }
    return { start, end };
  }

  function prefixSelectedLines(prefix) {
    const sel = lineSelection();
    const selected = editor.value.slice(sel.start, sel.end);
    if (!selected) {
      replaceSelection(sel.start, sel.end, prefix, sel.start + prefix.length, sel.start + prefix.length);
      return;
    }
    const lines = selected.split("\n");
    const replacement = lines.map((line, index) => {
      if (index === lines.length - 1 && line === "") {
        return "";
      }
      return prefix + line;
    }).join("\n");
    replaceSelection(sel.start, sel.end, replacement, sel.start, sel.start + replacement.length);
  }

  function prefixNumberedList() {
    const sel = lineSelection();
    const selected = editor.value.slice(sel.start, sel.end);
    if (!selected) {
      replaceSelection(sel.start, sel.end, "1. ", sel.start + 3, sel.start + 3);
      return;
    }
    let number = 1;
    const lines = selected.split("\n");
    const replacement = lines.map((line, index) => {
      if (index === lines.length - 1 && line === "") {
        return "";
      }
      return `${number++}. ${line}`;
    }).join("\n");
    replaceSelection(sel.start, sel.end, replacement, sel.start, sel.start + replacement.length);
  }

  function wrapBlock(prefix, suffix, placeholder) {
    const sel = selection();
    const selected = editor.value.slice(sel.start, sel.end);
    const inner = selected || placeholder;
    const before = needsLeadingNewline(sel.start) ? "\n" : "";
    const after = needsTrailingNewline(sel.end) ? "\n" : "";
    const replacement = before + prefix + inner + suffix + after;
    const innerStart = sel.start + before.length + prefix.length;
    replaceSelection(sel.start, sel.end, replacement, innerStart, innerStart + inner.length);
  }

  function insertBlock(snippet) {
    const sel = selection();
    const before = needsLeadingNewline(sel.start) ? "\n" : "";
    const after = needsTrailingNewline(sel.end) ? "\n" : "";
    const replacement = before + snippet + after;
    const cursor = sel.start + replacement.length;
    replaceSelection(sel.start, sel.end, replacement, cursor, cursor);
  }

  function insertLink() {
    const url = (window.prompt("Link URL", "https://") || "").trim();
    if (!url) {
      return;
    }
    const sel = selection();
    const label = editor.value.slice(sel.start, sel.end) || "link text";
    const replacement = `[${label}](${url})`;
    replaceSelection(sel.start, sel.end, replacement, sel.start + 1, sel.start + 1 + label.length);
  }

  function insertImage(lifePimTag) {
    const source = (window.prompt("Image source", "image.jpg") || "").trim();
    if (!source) {
      return;
    }
    insertBlock(lifePimTag ? `[img]${source}[/img]` : `![image](${source})`);
  }

  function insertTable() {
    const cols = Math.max(1, Math.min(8, parseInt(window.prompt("Columns", "2") || "2", 10) || 2));
    const rows = Math.max(1, Math.min(20, parseInt(window.prompt("Rows", "4") || "4", 10) || 4));
    const header = Array.from({ length: cols }, (_, idx) => `| Header ${idx + 1} `).join("") + "|";
    const divider = Array.from({ length: cols }, () => "| --- ").join("") + "|";
    const body = Array.from({ length: rows }, () => Array.from({ length: cols }, () => "|  ").join("") + "|").join("\n");
    insertBlock(`${header}\n${divider}\n${body}`);
  }

  function runMarkdownAction(action) {
    if (action === "bold") {
      wrapSelection("**", "**", "bold text");
    } else if (action === "italic") {
      wrapSelection("*", "*", "italic text");
    } else if (action === "strike") {
      wrapSelection("~~", "~~", "struck text");
    } else if (action === "inline-code") {
      wrapSelection("`", "`", "code");
    } else if (action === "h1") {
      prefixSelectedLines("# ");
    } else if (action === "h2") {
      prefixSelectedLines("## ");
    } else if (action === "bullet") {
      prefixSelectedLines("- ");
    } else if (action === "numbered") {
      prefixNumberedList();
    } else if (action === "task") {
      prefixSelectedLines("- [ ] ");
    } else if (action === "quote") {
      prefixSelectedLines("> ");
    } else if (action === "code-block") {
      wrapBlock("```\n", "\n```", "code block");
    } else if (action === "link") {
      insertLink();
    } else if (action === "image") {
      insertImage(false);
    } else if (action === "lifepim-image") {
      insertImage(true);
    } else if (action === "table") {
      insertTable();
    }
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
  if (toolbar) {
    toolbar.addEventListener("click", (evt) => {
      const btn = evt.target.closest("[data-md-action]");
      if (!btn) {
        return;
      }
      evt.preventDefault();
      runMarkdownAction(btn.dataset.mdAction || "");
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
