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

  function getProjectId(explicitId) {
    const explicit = (explicitId || "").trim();
    if (explicit) {
      return explicit;
    }
    const bodyId = (document.body && document.body.dataset.sidebarId) || "";
    return bodyId.trim();
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

  async function fetchProjectInfo(projectId) {
    const pid = (projectId || "").trim();
    if (!pid) {
      throw new Error("Project is required.");
    }
    if (OPTIONS_CACHE.has(pid)) {
      return OPTIONS_CACHE.get(pid);
    }
    const params = new URLSearchParams();
    params.set("project_id", pid);
    const request = fetch(`/notes/api/new-note-options?${params.toString()}`)
      .then(async (resp) => {
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.error || "Unable to fetch note folders.");
        }
        return data;
      })
      .catch((err) => {
        OPTIONS_CACHE.delete(pid);
        throw err;
      });
    OPTIONS_CACHE.set(pid, request);
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

  async function setDefaultFolder(projectFolderId) {
    const resp = await fetch(`/projects/api/folders/${projectFolderId}/set-default`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Unable to set default folder.");
    }
    return data;
  }

  async function addDefaultFolder(projectId, pathPrefix) {
    const resp = await fetch("/projects/api/folders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        path_prefix: pathPrefix,
        folder_role: "default",
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Unable to add default folder.");
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

  function openModal(options, title, projectId, resolvedLabel) {
    if (!STATE.modal || !STATE.backdrop) {
      return;
    }
    STATE.options = options.slice(0, MAX_OPTIONS);
    STATE.pendingTitle = title;
    STATE.pendingSidebar = projectId;
    STATE.titleEl.textContent = `Title: ${title}`;
    if (STATE.projectEl) {
      STATE.projectEl.textContent = `Project: ${projectId}`;
    }
    if (STATE.writeRootEl) {
      STATE.writeRootEl.textContent = resolvedLabel ? `Choose default folder` : "";
      STATE.writeRootEl.style.display = resolvedLabel ? "" : "none";
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
      if (option.project_folder_id) {
        await setDefaultFolder(option.project_folder_id);
      }
      const result = await createNote({
        title: STATE.pendingTitle,
        project_id: STATE.pendingSidebar,
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
    const projectId = getProjectId(sidebarLabel);
    if (!projectId) {
      alert("Select a project first.");
      return;
    }
    const title = promptForTitle(defaultTitle);
    if (!title) {
      return;
    }
    let data;
    try {
      data = await fetchProjectInfo(projectId);
    } catch (err) {
      alert(err.message || "Unable to fetch note folders.");
      return;
    }
    const folders = (data.folders || []).filter((opt) => opt.path_prefix && opt.is_enabled !== 0);
    const defaultFolder = data.default_folder ? data.default_folder.path_prefix : "";
    if (defaultFolder) {
      try {
        const result = await createNote({
          title: title,
          project_id: projectId,
          path_prefix: defaultFolder,
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
    if (folders.length) {
      openModal(folders, title, projectId, "choose");
      return;
    }
    const newPath = window.prompt("No default folder set. Enter a folder path:");
    if (!newPath) {
      return;
    }
    try {
      await addDefaultFolder(projectId, newPath);
      const result = await createNote({
        title: title,
        project_id: projectId,
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
      const projectId = getProjectId();
      if (projectId) {
        fetchProjectInfo(projectId).catch(() => {});
      }
    }
    window.create_new_note = create_new_note;
  });
})();
