(function () {
  "use strict";

  const MAX_OPTIONS = 5;
  const STATE = {
    modal: null,
    backdrop: null,
    titleEl: null,
    projectEl: null,
    writeRootEl: null,
    optionsEl: null,
    cancelBtn: null,
    closeBtn: null,
    contextMenu: null,
    options: [],
    selectedIndex: 0,
    pendingTitle: "",
    pendingSidebar: "",
    open: false,
    creating: false,
  };
  const OPTIONS_CACHE = new Map();

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function activeTabIsNotes() {
    return document.body && document.body.dataset.activeTab === "notes";
  }

  function isEditableTarget(target) {
    if (!target) {
      return false;
    }
    const tag = target.tagName ? target.tagName.toLowerCase() : "";
    if (tag === "input" || tag === "textarea" || tag === "select") {
      return true;
    }
    return Boolean(target.isContentEditable);
  }

  function getSidebarLabel(explicitLabel) {
    const explicit = (explicitLabel || "").trim();
    if (explicit) {
      return explicit;
    }
    const bodyLabel = (document.body && document.body.dataset.sidebarLabel) || "";
    return bodyLabel.trim() || "All Projects";
  }

  function promptForTitle(defaultTitle) {
    const seed = (defaultTitle || "").trim();
    const title = window.prompt("Note title", seed);
    if (title === null) {
      return null;
    }
    const trimmed = title.trim();
    if (!trimmed) {
      return null;
    }
    return trimmed;
  }

  async function fetchOptions(sidebarLabel) {
    const label = (sidebarLabel || "").trim();
    if (OPTIONS_CACHE.has(label)) {
      return OPTIONS_CACHE.get(label);
    }
    const params = new URLSearchParams();
    if (label) {
      params.set("sidebar_label", label);
    }
    const request = fetch(`/notes/api/new-note-options?${params.toString()}`)
      .then(async (resp) => {
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.error || "Unable to fetch note folders.");
        }
        return data;
      })
      .catch((err) => {
        OPTIONS_CACHE.delete(label);
        throw err;
      });
    OPTIONS_CACHE.set(label, request);
    return request;
  }

  async function createNote(payload) {
    const resp = await fetch("/notes/api/create-note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Unable to create note.");
    }
    return data;
  }

  function formatFolderName(pathValue) {
    const path = (pathValue || "").replace(/[\\/]+$/, "");
    if (!path) {
      return "Folder";
    }
    const parts = path.split(/[\\/]/).filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[parts.length - 2]}\\${parts[parts.length - 1]}`;
    }
    return parts[parts.length - 1] || path;
  }

  function highlightOption(index) {
    STATE.selectedIndex = index;
    qsa(".note-option", STATE.optionsEl).forEach((row, idx) => {
      row.classList.toggle("active", idx === index);
    });
  }

  function renderOptions() {
    if (!STATE.optionsEl) {
      return;
    }
    STATE.optionsEl.innerHTML = "";
    const options = STATE.options.slice(0, MAX_OPTIONS);
    options.forEach((opt, idx) => {
      const row = document.createElement("div");
      row.className = "note-option";
      row.dataset.index = String(idx);

      const title = document.createElement("div");
      title.className = "note-option-title";
      title.textContent = formatFolderName(opt.path_prefix);

      const path = document.createElement("div");
      path.className = "note-option-path";
      path.textContent = opt.path_prefix || "";

      row.appendChild(title);
      row.appendChild(path);

      if (opt.notes) {
        const notes = document.createElement("div");
        notes.className = "note-option-notes";
        notes.textContent = opt.notes;
        row.appendChild(notes);
      }

      row.addEventListener("click", () => {
        highlightOption(idx);
        selectOption(idx);
      });

      STATE.optionsEl.appendChild(row);
    });
    highlightOption(0);
  }

  function openModal(options, title, sidebarLabel, resolvedLabel) {
    if (!STATE.modal || !STATE.backdrop) {
      return;
    }
    STATE.options = options.slice(0, MAX_OPTIONS);
    STATE.pendingTitle = title;
    STATE.pendingSidebar = sidebarLabel;
    STATE.titleEl.textContent = `Title: ${title}`;
    if (STATE.projectEl) {
      STATE.projectEl.textContent = `Project: ${sidebarLabel}`;
    }
    if (STATE.writeRootEl) {
      if (resolvedLabel && resolvedLabel.toLowerCase() !== (sidebarLabel || "").toLowerCase()) {
        STATE.writeRootEl.textContent = `Write root: ${resolvedLabel}`;
        STATE.writeRootEl.style.display = "";
      } else {
        STATE.writeRootEl.textContent = "";
        STATE.writeRootEl.style.display = "none";
      }
    }
    renderOptions();
    STATE.modal.classList.add("open");
    STATE.modal.setAttribute("aria-hidden", "false");
    STATE.backdrop.classList.add("open");
    STATE.open = true;
  }

  function closeModal() {
    if (!STATE.modal || !STATE.backdrop) {
      return;
    }
    STATE.modal.classList.remove("open");
    STATE.modal.setAttribute("aria-hidden", "true");
    STATE.backdrop.classList.remove("open");
    STATE.open = false;
  }

  async function selectOption(index) {
    if (STATE.creating) {
      return;
    }
    const option = STATE.options[index];
    if (!option) {
      return;
    }
    STATE.creating = true;
    try {
      const result = await createNote({
        title: STATE.pendingTitle,
        sidebar_label: STATE.pendingSidebar,
        path_prefix: option.path_prefix,
      });
      closeModal();
      if (result.open_url) {
        window.location.href = result.open_url;
      } else if (result.note_id) {
        window.location.href = `/notes/view/${result.note_id}`;
      } else {
        window.location.reload();
      }
    } catch (err) {
      alert(err.message || "Unable to create note.");
    } finally {
      STATE.creating = false;
    }
  }

  async function create_new_note(sidebarLabel, defaultTitle) {
    if (!activeTabIsNotes()) {
      return;
    }
    const label = getSidebarLabel(sidebarLabel);
    const title = promptForTitle(defaultTitle);
    if (!title) {
      return;
    }
    let data;
    try {
      data = await fetchOptions(label);
    } catch (err) {
      alert(err.message || "Unable to fetch note folders.");
      return;
    }
    const options = (data.options || []).filter((opt) => opt.path_prefix);
    const resolvedLabel = (data.sidebar_label || label).trim() || label;
    const projectLabel = label || resolvedLabel;
    if (!options.length) {
      alert("No canonical write root found for this sidebar.");
      return;
    }
    if (options.length === 1) {
      try {
        const result = await createNote({
          title: title,
          sidebar_label: projectLabel,
          path_prefix: options[0].path_prefix,
        });
        if (result.open_url) {
          window.location.href = result.open_url;
        } else if (result.note_id) {
          window.location.href = `/notes/view/${result.note_id}`;
        } else {
          window.location.reload();
        }
      } catch (err) {
        alert(err.message || "Unable to create note.");
      }
      return;
    }
    openModal(options, title, projectLabel, resolvedLabel);
  }

  function initModal() {
    STATE.modal = qs("#note-modal");
    STATE.backdrop = qs("#note-modal-backdrop");
    STATE.titleEl = qs("#note-modal-title");
    STATE.projectEl = qs("#note-modal-project");
    STATE.writeRootEl = qs("#note-modal-write-root");
    STATE.optionsEl = qs("#note-modal-options");
    STATE.cancelBtn = qs("#note-modal-cancel");
    STATE.closeBtn = qs("#note-modal-close");
    if (!STATE.modal || !STATE.backdrop) {
      return;
    }
    if (STATE.cancelBtn) {
      STATE.cancelBtn.addEventListener("click", closeModal);
    }
    if (STATE.closeBtn) {
      STATE.closeBtn.addEventListener("click", closeModal);
    }
    STATE.backdrop.addEventListener("click", closeModal);
  }

  function initButtons() {
    qsa(".new-note-btn").forEach((btn) => {
      btn.addEventListener("click", (evt) => {
        evt.preventDefault();
        const label = btn.dataset.sidebarLabel || "";
        const defaultTitle = btn.dataset.defaultTitle || "";
        create_new_note(label, defaultTitle);
      });
    });
  }

  function initHotkey() {
    document.addEventListener("keydown", (evt) => {
      if (STATE.open) {
        if (evt.key === "Escape") {
          evt.preventDefault();
          closeModal();
          return;
        }
        if (evt.key >= "1" && evt.key <= String(MAX_OPTIONS)) {
          evt.preventDefault();
          selectOption(parseInt(evt.key, 10) - 1);
          return;
        }
      }
      if (!activeTabIsNotes()) {
        return;
      }
      if (evt.ctrlKey && !evt.shiftKey && !evt.altKey && evt.key.toLowerCase() === "n") {
        if (isEditableTarget(evt.target)) {
          return;
        }
        evt.preventDefault();
        create_new_note();
      }
    });
  }

  function initContextMenu() {
    STATE.contextMenu = qs("#note-context-menu");
    if (!STATE.contextMenu) {
      return;
    }
    const action = qs("[data-action='new-note']", STATE.contextMenu);
    if (action) {
      action.addEventListener("click", (evt) => {
        evt.preventDefault();
        hideContextMenu();
        create_new_note();
      });
    }
    document.addEventListener("contextmenu", (evt) => {
      if (!activeTabIsNotes()) {
        return;
      }
      if (isEditableTarget(evt.target)) {
        return;
      }
      const target = evt.target.closest("[data-notes-context='true']");
      if (!target) {
        return;
      }
      evt.preventDefault();
      showContextMenu(evt.clientX, evt.clientY);
    });
    document.addEventListener("click", hideContextMenu);
    window.addEventListener("scroll", hideContextMenu, true);
  }

  function showContextMenu(x, y) {
    if (!STATE.contextMenu) {
      return;
    }
    STATE.contextMenu.style.left = `${x}px`;
    STATE.contextMenu.style.top = `${y}px`;
    STATE.contextMenu.classList.add("open");
    STATE.contextMenu.setAttribute("aria-hidden", "false");
  }

  function hideContextMenu() {
    if (!STATE.contextMenu) {
      return;
    }
    STATE.contextMenu.classList.remove("open");
    STATE.contextMenu.setAttribute("aria-hidden", "true");
  }

  document.addEventListener("DOMContentLoaded", () => {
    initModal();
    initButtons();
    initHotkey();
    initContextMenu();
    if (activeTabIsNotes()) {
      fetchOptions(getSidebarLabel()).catch(() => {});
    }
    window.create_new_note = create_new_note;
  });
})();
