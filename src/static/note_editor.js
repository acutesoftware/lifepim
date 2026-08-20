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
  const wikiPopup = qs("#note-wiki-popup");
  const previewEl = qs("#note-editor-preview");
  const metadataInputs = Array.from(document.querySelectorAll("[data-note-metadata-field]"));
  const noteId = editor.dataset.noteId || "";
  const saveUrl = editor.dataset.saveUrl || "";
  const uploadImageUrl = editor.dataset.uploadImageUrl || "";
  const wikiSearchUrl = editor.dataset.wikiSearchUrl || "";
  const wikiPreviewUrl = editor.dataset.wikiPreviewUrl || "";
  const saveDelayMs = 1500;
  const previewDelayMs = 450;
  const draftKey = noteId ? `lifepim.noteDraft.${noteId}` : "";

  let saveTimer = null;
  let previewTimer = null;
  let inflight = false;
  let pending = false;
  let wikiSearchToken = 0;
  let wikiPopupState = null;
  let lastSaved = editor.value;
  let lastSavedMetadata = metadataPayload();
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

  function metadataPayload() {
    const payload = {};
    metadataInputs.forEach((input) => {
      const field = input.dataset.noteMetadataField || "";
      if (field) {
        payload[field] = input.checked;
      }
    });
    return payload;
  }

  function metadataChanged() {
    return JSON.stringify(metadataPayload()) !== JSON.stringify(lastSavedMetadata || {});
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

  function hideWikiPopup() {
    wikiPopupState = null;
    if (wikiPopup) {
      wikiPopup.hidden = true;
      wikiPopup.innerHTML = "";
    }
  }

  function activeWikiQuery() {
    const cursor = selection().start;
    const before = editor.value.slice(0, cursor);
    const start = before.lastIndexOf("[[");
    if (start < 0) {
      return null;
    }
    const between = before.slice(start + 2);
    if (between.includes("]]") || between.includes("\n")) {
      return null;
    }
    return { start, end: cursor, query: between };
  }

  function textareaCaretRect(position) {
    const editorRect = editor.getBoundingClientRect();
    const style = window.getComputedStyle(editor);
    const mirror = document.createElement("div");
    const trackedStyles = [
      "boxSizing",
      "width",
      "height",
      "borderTopWidth",
      "borderRightWidth",
      "borderBottomWidth",
      "borderLeftWidth",
      "paddingTop",
      "paddingRight",
      "paddingBottom",
      "paddingLeft",
      "fontFamily",
      "fontSize",
      "fontWeight",
      "fontStyle",
      "letterSpacing",
      "textTransform",
      "wordSpacing",
      "textIndent",
      "lineHeight",
      "tabSize",
    ];
    trackedStyles.forEach((name) => {
      mirror.style[name] = style[name];
    });
    mirror.style.position = "absolute";
    mirror.style.visibility = "hidden";
    mirror.style.whiteSpace = "pre-wrap";
    mirror.style.overflowWrap = "break-word";
    mirror.style.top = "0";
    mirror.style.left = "-9999px";
    mirror.textContent = editor.value.slice(0, position);
    const marker = document.createElement("span");
    marker.textContent = editor.value.slice(position, position + 1) || ".";
    mirror.appendChild(marker);
    document.body.appendChild(mirror);
    const markerRect = marker.getBoundingClientRect();
    const mirrorRect = mirror.getBoundingClientRect();
    const left = editorRect.left + (markerRect.left - mirrorRect.left) - editor.scrollLeft;
    const top = editorRect.top + (markerRect.top - mirrorRect.top) - editor.scrollTop;
    const height = markerRect.height || parseFloat(style.lineHeight) || 18;
    document.body.removeChild(mirror);
    return { left, top, height };
  }

  function positionWikiPopup(state) {
    if (!wikiPopup) {
      return;
    }
    const caret = textareaCaretRect(state.end);
    const popupWidth = Math.min(420, Math.max(260, editor.getBoundingClientRect().width * 0.45));
    const gap = 8;
    let left = caret.left + gap;
    let top = caret.top - 4;
    if (left + popupWidth > window.innerWidth - 8) {
      left = Math.max(8, caret.left - popupWidth - gap);
    }
    const maxTop = window.innerHeight - 80;
    top = Math.max(8, Math.min(top, maxTop));
    wikiPopup.style.left = `${left + window.scrollX}px`;
    wikiPopup.style.top = `${top + window.scrollY}px`;
    wikiPopup.style.width = `${popupWidth}px`;
  }

  function renderWikiPopup(state, results) {
    if (!wikiPopup) {
      return;
    }
    wikiPopupState = {
      start: state.start,
      end: state.end,
      query: state.query,
      results,
      index: 0,
    };
    wikiPopup.innerHTML = "";
    if (!results.length) {
      const empty = document.createElement("div");
      empty.className = "note-wiki-empty";
      empty.textContent = "No matching notes";
      wikiPopup.appendChild(empty);
    } else {
      results.forEach((item, index) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = index === 0 ? "note-wiki-option active" : "note-wiki-option";
        row.dataset.index = String(index);
        const title = document.createElement("span");
        title.className = "note-wiki-title";
        title.textContent = item.title || item.file_name || "Untitled";
        const meta = document.createElement("span");
        meta.className = "note-wiki-meta";
        meta.textContent = item.path || item.area || "";
        row.appendChild(title);
        row.appendChild(meta);
        row.addEventListener("mousedown", (evt) => {
          evt.preventDefault();
          insertWikiResult(index);
        });
        wikiPopup.appendChild(row);
      });
    }
    positionWikiPopup(state);
    wikiPopup.hidden = false;
  }

  function updateWikiActiveOption() {
    if (!wikiPopup || !wikiPopupState) {
      return;
    }
    Array.from(wikiPopup.querySelectorAll(".note-wiki-option")).forEach((row, index) => {
      row.classList.toggle("active", index === wikiPopupState.index);
    });
  }

  function insertWikiResult(index) {
    if (!wikiPopupState || !wikiPopupState.results.length) {
      return;
    }
    const item = wikiPopupState.results[index] || wikiPopupState.results[0];
    const replacement = item.path_wiki_link || item.markdown_link || item.wiki_link || `[[${item.title || item.file_name || ""}]]`;
    const cursor = wikiPopupState.start + replacement.length;
    replaceSelection(wikiPopupState.start, selection().start, replacement, cursor, cursor);
    hideWikiPopup();
    schedulePreview();
  }

  async function refreshWikiPopup() {
    const state = activeWikiQuery();
    if (!state || !wikiSearchUrl) {
      hideWikiPopup();
      return;
    }
    const token = ++wikiSearchToken;
    const params = new URLSearchParams();
    params.set("q", state.query);
    params.set("exclude_id", noteId);
    params.set("limit", "12");
    try {
      const resp = await fetch(`${wikiSearchUrl}?${params.toString()}`);
      const data = await resp.json();
      if (token !== wikiSearchToken) {
        return;
      }
      renderWikiPopup(state, data.results || []);
    } catch (err) {
      hideWikiPopup();
    }
  }

  function wikiLinkAtCursor() {
    const cursor = selection().start;
    const text = editor.value;
    const re = /\[\[([^\]\n]+)\]\]/g;
    let match;
    while ((match = re.exec(text)) !== null) {
      if (cursor >= match.index && cursor <= match.index + match[0].length) {
        const parts = match[1].split("|").map((part) => part.trim());
        const notePart = parts.find((part) => /^note:\d+$/i.test(part));
        if (notePart) {
          return `/notes/view/${notePart.split(":", 2)[1]}`;
        }
      }
    }
    return "";
  }

  function openWikiLinkAtCursor() {
    const url = wikiLinkAtCursor();
    if (url) {
      window.location.href = url;
      return true;
    }
    return false;
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

  function browseForImage() {
    if (!uploadImageUrl) {
      insertImage(false);
      return;
    }
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file) {
        void uploadImage(file);
      }
    });
    input.click();
  }

  async function uploadImage(file) {
    const form = new FormData();
    form.append("image", file);
    setStatus("Uploading image...");
    try {
      const resp = await fetch(uploadImageUrl, {
        method: "POST",
        body: form,
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Unable to upload image.");
      }
      insertBlock(data.markdown || `![image](${data.path})`);
      setStatus("Image inserted.");
    } catch (err) {
      setStatus(err.message || "Image upload failed.", true);
    }
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
    } else if (action === "browse-image") {
      browseForImage();
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
      if (editor.value === lastSaved && !metadataChanged()) {
        return;
      }
      void doSave();
    }, saveDelayMs);
    schedulePreview();
  }

  function schedulePreview() {
    if (!previewEl || !wikiPreviewUrl) {
      return;
    }
    if (previewTimer) {
      clearTimeout(previewTimer);
    }
    previewTimer = setTimeout(() => {
      void refreshPreview();
    }, previewDelayMs);
  }

  async function refreshPreview() {
    if (!previewEl || !wikiPreviewUrl) {
      return;
    }
    try {
      const resp = await fetch(wikiPreviewUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editor.value }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Unable to render preview.");
      }
      previewEl.innerHTML = data.html || "";
    } catch (err) {
      previewEl.textContent = "";
    }
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
    const metadata = metadataPayload();
    if (content === lastSaved && !metadataChanged()) {
      return;
    }
    inflight = true;
    setStatus("Saving...");
    try {
      writeDraft();
      const resp = await fetch(saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, metadata, base_mtime_ns: fileMtimeNs, base_hash: fileHash }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Unable to save note.");
      }
      lastSaved = content;
      lastSavedMetadata = metadata;
      if (data.mtime_ns !== undefined) {
        fileMtimeNs = String(data.mtime_ns || "");
        editor.dataset.fileMtimeNs = fileMtimeNs;
      }
      if (data.sha256 !== undefined) {
        fileHash = String(data.sha256 || "");
        editor.dataset.fileHash = fileHash;
      }
      if (data.link_count !== undefined) {
        editor.dataset.linkCount = String(data.link_count || 0);
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
  schedulePreview();
  editor.addEventListener("input", () => {
    scheduleSave();
    void refreshWikiPopup();
  });
  editor.addEventListener("click", (evt) => {
    if ((evt.ctrlKey || evt.metaKey) && openWikiLinkAtCursor()) {
      evt.preventDefault();
    }
  });
  editor.addEventListener("touchend", () => {
    window.setTimeout(openWikiLinkAtCursor, 0);
  });
  editor.addEventListener("keyup", (evt) => {
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(evt.key)) {
      void refreshWikiPopup();
    }
  });
  editor.addEventListener("keydown", (evt) => {
    if (!wikiPopupState || (wikiPopup && wikiPopup.hidden)) {
      return;
    }
    if (evt.key === "Escape") {
      evt.preventDefault();
      hideWikiPopup();
    } else if (evt.key === "ArrowDown") {
      evt.preventDefault();
      wikiPopupState.index = Math.min(wikiPopupState.results.length - 1, wikiPopupState.index + 1);
      updateWikiActiveOption();
    } else if (evt.key === "ArrowUp") {
      evt.preventDefault();
      wikiPopupState.index = Math.max(0, wikiPopupState.index - 1);
      updateWikiActiveOption();
    } else if (evt.key === "Enter" && wikiPopupState.results.length) {
      evt.preventDefault();
      insertWikiResult(wikiPopupState.index);
    }
  });
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
  metadataInputs.forEach((input) => {
    input.addEventListener("change", () => {
      scheduleSave();
    });
  });
  if (previewEl) {
    previewEl.addEventListener("click", (evt) => {
      const link = evt.target.closest("a.wiki-link");
      if (!link) {
        return;
      }
      if (evt.ctrlKey || evt.metaKey || window.matchMedia("(pointer: coarse)").matches) {
        return;
      }
      evt.preventDefault();
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
