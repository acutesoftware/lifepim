
(function () {
  "use strict";

  const LINK_TYPE_ORDER = [
    "related",
    "mentions",
    "attachment",
    "about",
    "assigned_to",
    "depends_on",
    "emails",
    "calls",
    "located_at",
  ];

  const LINK_TYPE_LABELS = {
    related: "Related",
    mentions: "Mentions",
    attachment: "Attachments",
    about: "About",
    assigned_to: "Assigned to",
    depends_on: "Depends on",
    emails: "Emails",
    calls: "Calls",
    located_at: "Located at",
  };

  const STATE = {
    drawer: null,
    drawerHandle: null,
    drawerResizer: null,
    drawerOpen: false,
    drawerFocused: false,
    mode: "outgoing",
    record: null,
    contextType: "",
    links: [],
    summaryCache: new Map(),
    allowedCache: new Map(),
    picker: null,
    selectedRow: null,
  };

  const DRAWER_WIDTH_KEY = "linksDrawerWidth";
  const DRAWER_WIDTH_MIN = 240;
  const DRAWER_WIDTH_MAX = 640;

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function fetchJson(url, options) {
    return fetch(url, options).then((res) => {
      if (!res.ok) {
        return res
          .json()
          .catch(() => ({}))
          .then((data) => {
            throw new Error(data.error || "request_failed");
          });
      }
      return res.json();
    });
  }

  function postJson(url, body) {
    return fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function patchJson(url, body) {
    return fetchJson(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function escapeText(text) {
    return (text || "").toString();
  }

  function formatRecordType(type) {
    const value = (type || "").toString();
    if (!value) {
      return "Record";
    }
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function init() {
    STATE.drawerHandle = qs("#links-drawer-handle");
    if (STATE.drawerHandle) {
      STATE.drawerHandle.addEventListener("click", () => {
        if (STATE.drawer) {
          setDrawerOpen(true);
          STATE.drawer.focus();
        }
      });
    }
    const drawer = qs(".links-drawer");
    if (drawer) {
      initDrawer(drawer);
    } else if (STATE.drawerHandle) {
      STATE.drawerHandle.classList.add("hidden");
    }
    initDragSources();
    initBulkToolbars();
    initMentions();
    initGlobalShortcuts();
  }

  function initDrawer(drawer) {
    STATE.drawer = drawer;
    STATE.record = {
      type: drawer.dataset.recordType,
      id: drawer.dataset.recordId,
      title: drawer.dataset.recordTitle,
    };
    STATE.contextType = drawer.dataset.contextType || "";
    const storedWidth = readDrawerWidth();
    if (storedWidth) {
      applyDrawerWidth(storedWidth);
    }
    setDrawerOpen(true);
    const requestedMode = getRequestedDrawerMode();
    const initialMode =
      requestedMode ||
      (drawer.dataset.mode === "incoming" ? "incoming" : "outgoing");
    setDrawerMode(initialMode, true);

    const addBtn = qs(".link-add", drawer);
    const toggleBtn = qs(".link-toggle", drawer);
    const tabs = qsa(".links-tab", drawer);
    const resizer = qs(".links-drawer-resize", drawer);
    if (resizer) {
      initDrawerResize(resizer);
    }

    addBtn.addEventListener("click", () =>
      openLinkPicker({ mode: "single", contextType: "links_drawer_add" })
    );
    toggleBtn.addEventListener("click", () => setDrawerOpen(!STATE.drawerOpen));
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const mode = tab.dataset.mode;
        if (mode) {
          setDrawerMode(mode);
        }
      });
    });

    drawer.addEventListener("focusin", () => {
      STATE.drawerFocused = true;
    });
    drawer.addEventListener("focusout", (evt) => {
      if (!drawer.contains(evt.relatedTarget)) {
        STATE.drawerFocused = false;
      }
    });
    drawer.addEventListener("click", (evt) => {
      const row = evt.target.closest(".link-row");
      if (row) {
        setSelectedRow(row);
      }
    });

    qsa(".links-section-header", drawer).forEach((header) => {
      header.addEventListener("dragover", (evt) => {
        evt.preventDefault();
        header.classList.add("drop-target");
      });
      header.addEventListener("dragleave", () => header.classList.remove("drop-target"));
      header.addEventListener("drop", (evt) => {
        evt.preventDefault();
        header.classList.remove("drop-target");
        const payload = readDragPayload(evt);
        if (payload.length) {
          handleDrop(payload, header.dataset.dropZone);
        }
      });
    });

  }

  function getRequestedDrawerMode() {
    const params = new URLSearchParams(window.location.search);
    const mode = (params.get("links") || "").toLowerCase();
    if (mode === "incoming" || mode === "outgoing") {
      return mode;
    }
    return "";
  }
  function setDrawerOpen(open) {
    STATE.drawerOpen = open;
    if (!STATE.drawer) {
      return;
    }
    STATE.drawer.classList.toggle("open", open);
    document.body.classList.toggle("has-links-drawer", open);
    if (STATE.drawerHandle) {
      STATE.drawerHandle.classList.toggle("hidden", open);
    }
  }

  function readDrawerWidth() {
    try {
      const raw = localStorage.getItem(DRAWER_WIDTH_KEY);
      const value = parseInt(raw, 10);
      if (!Number.isFinite(value)) {
        return null;
      }
      return value;
    } catch (_) {
      return null;
    }
  }

  function saveDrawerWidth(width) {
    try {
      localStorage.setItem(DRAWER_WIDTH_KEY, String(width));
    } catch (_) {}
  }

  function applyDrawerWidth(width) {
    if (!STATE.drawer || !Number.isFinite(width)) {
      return null;
    }
    const maxWidth = Math.min(DRAWER_WIDTH_MAX, window.innerWidth - 40);
    const clamped = Math.max(DRAWER_WIDTH_MIN, Math.min(maxWidth, width));
    STATE.drawer.style.setProperty("--links-drawer-width", `${clamped}px`);
    return clamped;
  }

  function initDrawerResize(handle) {
    STATE.drawerResizer = handle;
    let resizing = false;
    let startX = 0;
    let startWidth = 0;
    let lastWidth = null;

    handle.addEventListener("mousedown", (evt) => {
      if (!STATE.drawer || evt.button !== 0) {
        return;
      }
      resizing = true;
      startX = evt.clientX;
      startWidth = STATE.drawer.getBoundingClientRect().width;
      document.body.classList.add("links-resizing");
      evt.preventDefault();
    });

    window.addEventListener("mousemove", (evt) => {
      if (!resizing || !STATE.drawer) {
        return;
      }
      const delta = startX - evt.clientX;
      lastWidth = applyDrawerWidth(startWidth + delta);
    });

    window.addEventListener("mouseup", () => {
      if (!resizing) {
        return;
      }
      resizing = false;
      document.body.classList.remove("links-resizing");
      if (lastWidth) {
        saveDrawerWidth(Math.round(lastWidth));
      }
      lastWidth = null;
    });
  }

  function setDrawerMode(mode, force) {
    if (!STATE.drawer || !mode) {
      return;
    }
    if (!force && STATE.mode === mode) {
      return;
    }
    STATE.mode = mode;
    qsa(".links-tab", STATE.drawer).forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.mode === mode);
    });
    loadLinks();
  }

  function loadLinks() {
    if (!STATE.drawer || !STATE.record || !STATE.record.id) {
      return;
    }
    const params = new URLSearchParams();
    let url = "";
    if (STATE.mode === "incoming") {
      params.set("dst_type", STATE.record.type);
      params.set("dst_id", STATE.record.id);
      url = `/links/api/incoming?${params.toString()}`;
    } else {
      params.set("src_type", STATE.record.type);
      params.set("src_id", STATE.record.id);
      url = `/links/api/outgoing?${params.toString()}`;
    }
    setSectionsLoading(true);
    fetchJson(url)
      .then((data) => {
        STATE.links = data.links || [];
        renderLinks();
      })
      .catch(() => {
        STATE.links = [];
        renderLinks();
      })
      .finally(() => {
        setSectionsLoading(false);
      });
  }

  function setSectionsLoading(isLoading) {
    if (!STATE.drawer) {
      return;
    }
    qsa(".links-section", STATE.drawer).forEach((section) => {
      section.classList.toggle("loading", isLoading);
    });
  }

  function renderLinks() {
    if (!STATE.drawer) {
      return;
    }
    const grouped = {};
    LINK_TYPE_ORDER.forEach((type) => {
      grouped[type] = [];
    });
    STATE.links.forEach((link) => {
      const type = link.link_type || "related";
      if (!grouped[type]) {
        grouped[type] = [];
      }
      grouped[type].push(link);
    });
    LINK_TYPE_ORDER.forEach((type) => {
      const section = qs(`.links-section[data-link-type="${type}"]`, STATE.drawer);
      if (!section) {
        return;
      }
      const list = qs(".links-list", section);
      list.innerHTML = "";
      const links = grouped[type] || [];
      qs(".links-count", section).textContent = links.length.toString();
      links.forEach((link) => {
        const row = buildLinkRow(link);
        list.appendChild(row);
      });
      section.classList.toggle("empty", links.length === 0);
    });
  }
  function buildLinkRow(link) {
    const row = document.createElement("li");
    row.className = "link-row";
    row.draggable = true;
    row.dataset.linkId = link.link_id;
    row.dataset.srcType = link.src_type;
    row.dataset.srcId = link.src_id;
    row.dataset.dstType = link.dst_type;
    row.dataset.dstId = link.dst_id;
    row.dataset.linkType = link.link_type;

    const dragHandle = document.createElement("span");
    dragHandle.className = "link-drag";
    dragHandle.textContent = "::";

    const target = document.createElement("span");
    target.className = "link-target";
    const icon = document.createElement("span");
    icon.className = "link-icon";
    const title = document.createElement("span");
    title.className = "link-title";
    title.textContent = "Loading...";
    target.appendChild(icon);
    target.appendChild(title);

    const typeSelect = document.createElement("select");
    typeSelect.className = "link-type-select";
    typeSelect.disabled = true;

    const labelInput = document.createElement("input");
    labelInput.className = "link-label";
    labelInput.type = "text";
    labelInput.placeholder = "Label";
    labelInput.value = link.label || "";

    const actions = document.createElement("span");
    actions.className = "link-actions";
    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "links-btn link-open";
    openBtn.textContent = "Open";
    const unlinkBtn = document.createElement("button");
    unlinkBtn.type = "button";
    unlinkBtn.className = "links-btn link-unlink";
    unlinkBtn.textContent = "Unlink";
    actions.appendChild(openBtn);
    actions.appendChild(unlinkBtn);

    row.appendChild(dragHandle);
    row.appendChild(target);
    row.appendChild(typeSelect);
    row.appendChild(labelInput);
    row.appendChild(actions);

    row.addEventListener("dragstart", handleLinkDragStart);
    row.addEventListener("dragover", handleLinkDragOver);
    row.addEventListener("drop", handleLinkDrop);

    openBtn.addEventListener("click", (evt) => {
      evt.stopPropagation();
      openLinkTarget(link);
    });
    unlinkBtn.addEventListener("click", (evt) => {
      evt.stopPropagation();
      unlinkLink(link, row);
    });
    typeSelect.addEventListener("change", () => {
      const newType = typeSelect.value;
      updateLinkType(link, newType);
    });
    labelInput.addEventListener("keydown", (evt) => {
      if (evt.key === "Enter") {
        evt.preventDefault();
        labelInput.blur();
      }
      if (evt.key === "Escape") {
        evt.preventDefault();
        labelInput.value = link.label || "";
        labelInput.blur();
      }
    });
    labelInput.addEventListener("blur", () => {
      const nextLabel = labelInput.value.trim();
      if (nextLabel !== (link.label || "")) {
        updateLinkLabel(link, nextLabel);
      }
    });

    hydrateLinkRow(link, row, title, icon, typeSelect);
    return row;
  }

  function hydrateLinkRow(link, row, titleEl, iconEl, typeSelect) {
    const perspective = STATE.mode === "incoming" ? "incoming" : "outgoing";
    const other = getOtherRecord(link, perspective);
    const preset = link.other_summary;
    if (preset) {
      titleEl.textContent =
        preset.title || preset.subtitle || `${other.type} ${other.id}`;
      iconEl.textContent = preset.icon || other.type.charAt(0).toUpperCase();
      row.dataset.otherTitle = preset.title || preset.subtitle || "";
    } else {
      getSummary(other.type, other.id)
        .then((summary) => {
          titleEl.textContent =
            summary.title || summary.subtitle || `${other.type} ${other.id}`;
          iconEl.textContent = summary.icon || other.type.charAt(0).toUpperCase();
          row.dataset.otherTitle = summary.title || summary.subtitle || "";
        })
        .catch(() => {
          titleEl.textContent = `${other.type} ${other.id}`;
          iconEl.textContent = other.type.charAt(0).toUpperCase();
        });
    }
    loadAllowedTypes(link.src_type, link.dst_type).then((allowed) => {
      typeSelect.innerHTML = "";
      const set = new Set(allowed);
      LINK_TYPE_ORDER.forEach((linkType) => {
        if (!set.has(linkType)) {
          return;
        }
        const opt = document.createElement("option");
        opt.value = linkType;
        opt.textContent = LINK_TYPE_LABELS[linkType] || linkType;
        typeSelect.appendChild(opt);
      });
      if (!set.has(link.link_type)) {
        const opt = document.createElement("option");
        opt.value = link.link_type;
        opt.textContent = `${LINK_TYPE_LABELS[link.link_type] || link.link_type} (!)`;
        typeSelect.appendChild(opt);
      }
      typeSelect.value = link.link_type;
      typeSelect.disabled = false;
    });
  }

  function getOtherRecord(link, perspective) {
    if (perspective === "incoming") {
      return { type: link.src_type, id: link.src_id };
    }
    return { type: link.dst_type, id: link.dst_id };
  }

  function getSummary(type, id) {
    const key = `${type}:${id}`;
    if (STATE.summaryCache.has(key)) {
      return Promise.resolve(STATE.summaryCache.get(key));
    }
    const params = new URLSearchParams({ type: type, id: id });
    return fetchJson(`/links/api/summary?${params.toString()}`).then((summary) => {
      STATE.summaryCache.set(key, summary);
      return summary;
    });
  }

  function loadAllowedTypes(srcType, dstType) {
    const key = `${srcType}:${dstType}`;
    if (STATE.allowedCache.has(key)) {
      return Promise.resolve(STATE.allowedCache.get(key));
    }
    return postJson("/links/api/resolve", {
      context_type: STATE.contextType || "link_picker",
      src_type: srcType,
      dst_types: [dstType],
    }).then((data) => {
      const allowed =
        (data.resolved && data.resolved[dstType] && data.resolved[dstType].allowed_types) || [];
      STATE.allowedCache.set(key, allowed);
      return allowed;
    });
  }
  function updateLinkType(link, newType) {
    const previousType = link.link_type;
    if (newType === previousType) {
      return;
    }
    patchJson(`/links/api/update/${link.link_id}`, { link_type: newType })
      .then(() => {
        link.link_type = newType;
        renderLinks();
        showToast({
          message: `Updated link type to ${LINK_TYPE_LABELS[newType] || newType}`,
        });
      })
      .catch(() => {
        renderLinks();
        showToast({ message: "Couldn't update link type." });
      });
  }

  function updateLinkLabel(link, label) {
    patchJson(`/links/api/update/${link.link_id}`, { label: label })
      .then(() => {
        link.label = label;
      })
      .catch(() => {
        showToast({ message: "Couldn't update link label." });
      });
  }

  function unlinkLink(link, row) {
    fetchJson(`/links/api/delete/${link.link_id}`, { method: "DELETE" })
      .then(() => {
        row.remove();
        STATE.links = STATE.links.filter((item) => item.link_id !== link.link_id);
        showToast({
          message: `Unlinked ${row.dataset.otherTitle || "item"}`,
          undo: () => restoreLink(link),
        });
      })
      .catch(() => {
        showToast({ message: "Couldn't unlink item." });
      });
  }

  function restoreLink(link) {
    createLink(link).then(() => {
      loadLinks();
    });
  }

  function openLinkTarget(link) {
    const perspective = STATE.mode === "incoming" ? "incoming" : "outgoing";
    const other = getOtherRecord(link, perspective);
    const targetMode = perspective === "incoming" ? "outgoing" : "incoming";
    getSummary(other.type, other.id)
      .then((summary) => {
        if (summary.open_url) {
          window.location.href = appendLinkMode(summary.open_url, targetMode);
        }
      })
      .catch(() => {});
  }

  function appendLinkMode(url, mode) {
    if (!url || !mode) {
      return url;
    }
    const parts = url.split("#");
    const base = parts[0];
    const hash = parts[1] ? `#${parts[1]}` : "";
    const joiner = base.indexOf("?") === -1 ? "?" : "&";
    return `${base}${joiner}links=${encodeURIComponent(mode)}${hash}`;
  }

  function createLink(payload) {
    return postJson("/links/api/create", payload);
  }

  function handleDrop(records, linkType) {
    if (!STATE.record || !STATE.record.id) {
      return;
    }
    if (STATE.mode === "incoming") {
      showToast({ message: "Switch to outgoing to create links." });
      return;
    }
    const items = records.map((rec) => ({
      src_type: STATE.record.type,
      src_id: STATE.record.id,
      dst_type: rec.type,
      dst_id: rec.id,
      link_type: linkType,
      created_by: "ui",
      context_type: "links_drawer_drop",
      context_id: STATE.record.id,
    }));
    postJson("/links/api/bulk", { items: items })
      .then((data) => {
        const results = data.results || [];
        const dupes = results.filter((r) => r.duplicate).length;
        loadLinks();
        if (dupes) {
          showToast({ message: `Already linked ${dupes} item(s).` });
        } else {
          showToast({ message: `Linked ${items.length} item(s).` });
        }
      })
      .catch(() => {
        showToast({ message: "Couldn't create link." });
      });
  }

  function readDragPayload(evt) {
    try {
      const payload = evt.dataTransfer.getData("application/x-lifepim-records");
      if (payload) {
        return JSON.parse(payload);
      }
    } catch (_) {
      return [];
    }
    return [];
  }

  function handleLinkDragStart(evt) {
    evt.dataTransfer.effectAllowed = "move";
    evt.dataTransfer.setData("text/plain", "link-row");
    evt.dataTransfer.setData("application/x-link-row", evt.currentTarget.dataset.linkId);
    evt.currentTarget.classList.add("dragging");
  }

  function handleLinkDragOver(evt) {
    evt.preventDefault();
    evt.dataTransfer.dropEffect = "move";
  }

  function handleLinkDrop(evt) {
    evt.preventDefault();
    const dragging = qs(".link-row.dragging");
    const target = evt.currentTarget;
    if (!dragging || dragging === target) {
      return;
    }
    if (dragging.parentElement !== target.parentElement) {
      return;
    }
    const list = target.parentElement;
    list.insertBefore(dragging, target);
    dragging.classList.remove("dragging");
    updateSortOrder(list);
  }

  function updateSortOrder(listEl) {
    const rows = qsa(".link-row", listEl);
    const updates = rows.map((row, idx) => {
      const linkId = row.dataset.linkId;
      const sortOrder = (idx + 1) * 10;
      return patchJson(`/links/api/update/${linkId}`, { sort_order: sortOrder });
    });
    Promise.all(updates).catch(() => {
      showToast({ message: "Couldn't update link order." });
    });
  }

  function setSelectedRow(row) {
    if (STATE.selectedRow) {
      STATE.selectedRow.classList.remove("selected");
    }
    STATE.selectedRow = row;
    row.classList.add("selected");
  }
  function initLinkPicker() {
    if (STATE.picker) {
      return;
    }
    const modal = qs("#link-picker-modal");
    if (!modal) {
      return;
    }
    const backdrop = qs("#link-picker-backdrop");
    const input = qs(".link-picker-input", modal);
    const results = qs(".link-picker-results", modal);
    const closeBtns = qsa(".link-modal-close", modal);
    const confirmBtn = qs(".link-modal-confirm", modal);

    STATE.picker = {
      modal: modal,
      backdrop: backdrop,
      input: input,
      results: results,
      confirmBtn: confirmBtn,
      mode: "single",
      sources: [],
      srcType: "",
      contextType: "",
      contextId: "",
      selected: null,
    };

    closeBtns.forEach((btn) => btn.addEventListener("click", closeLinkPicker));
    backdrop.addEventListener("click", closeLinkPicker);
    input.addEventListener("input", debounce(() => runPickerSearch(), 200));
    confirmBtn.addEventListener("click", () => confirmPickerSelection());
    input.addEventListener("keydown", (evt) => {
      if (evt.key === "ArrowDown") {
        evt.preventDefault();
        movePickerSelection(1);
      } else if (evt.key === "ArrowUp") {
        evt.preventDefault();
        movePickerSelection(-1);
      } else if (evt.key === "Enter") {
        evt.preventDefault();
        confirmPickerSelection();
      } else if (evt.key === "Escape") {
        closeLinkPicker();
      }
    });
  }

  function openLinkPicker(options) {
    initLinkPicker();
    if (!STATE.picker) {
      return;
    }
    const picker = STATE.picker;
    picker.mode = options.mode || "single";
    picker.sources = options.sources || [];
    picker.srcType = options.srcType || (STATE.record && STATE.record.type);
    picker.contextType = options.contextType || "link_picker";
    picker.contextId = options.contextId || "";
    picker.selected = null;
    picker.input.value = "";
    picker.results.innerHTML = "";
    picker.modal.classList.add("open");
    picker.backdrop.classList.add("open");
    picker.modal.setAttribute("aria-hidden", "false");
    picker.input.focus();
  }

  function closeLinkPicker() {
    if (!STATE.picker) {
      return;
    }
    const picker = STATE.picker;
    picker.modal.classList.remove("open");
    picker.backdrop.classList.remove("open");
    picker.modal.setAttribute("aria-hidden", "true");
  }

  function runPickerSearch() {
    const picker = STATE.picker;
    const query = picker.input.value.trim();
    if (!query) {
      picker.results.innerHTML = "";
      picker.selected = null;
      return;
    }
    const params = new URLSearchParams({ q: query, limit: "30" });
    fetchJson(`/links/api/search?${params.toString()}`)
      .then((data) => renderPickerResults(data.results || []))
      .catch(() => {
        picker.results.textContent = "Search failed.";
      });
  }

  function renderPickerResults(results) {
    const picker = STATE.picker;
    picker.results.innerHTML = "";
    picker.selected = null;
    if (!results.length) {
      picker.results.textContent = "No results.";
      return;
    }
    const dstTypes = Array.from(new Set(results.map((r) => r.type)));
    postJson("/links/api/resolve", {
      context_type: picker.contextType,
      src_type: picker.srcType,
      dst_types: dstTypes,
    }).then((resolved) => {
      const mapping = resolved.resolved || {};
      const grouped = {};
      results.forEach((item) => {
        grouped[item.type] = grouped[item.type] || [];
        grouped[item.type].push(item);
      });
      Object.keys(grouped).forEach((type) => {
        const header = document.createElement("div");
        header.className = "link-picker-group";
        header.textContent = formatRecordType(type);
        picker.results.appendChild(header);
        grouped[type].forEach((item) => {
          const row = document.createElement("div");
          row.className = "link-picker-row";
          row.tabIndex = 0;
          row.dataset.type = item.type;
          row.dataset.id = item.id;
          row.dataset.title = escapeText(item.title || "");
          const title = document.createElement("span");
          title.className = "link-picker-title";
          title.textContent = item.title || `${item.type} ${item.id}`;
          const subtitle = document.createElement("span");
          subtitle.className = "link-picker-subtitle";
          subtitle.textContent = item.subtitle || "";
          const typeSelect = document.createElement("select");
          typeSelect.className = "link-picker-type";
          const resolvedItem = mapping[item.type] || {};
          const allowed = resolvedItem.allowed_types || LINK_TYPE_ORDER;
          const defaultType = resolvedItem.default_type || "related";
          allowed.forEach((linkType) => {
            const opt = document.createElement("option");
            opt.value = linkType;
            opt.textContent = LINK_TYPE_LABELS[linkType] || linkType;
            typeSelect.appendChild(opt);
          });
          typeSelect.value = defaultType;

          row.appendChild(title);
          row.appendChild(subtitle);
          row.appendChild(typeSelect);
          row.addEventListener("click", () => setPickerSelection(row));
          row.addEventListener("dblclick", () => {
            setPickerSelection(row);
            confirmPickerSelection();
          });
          picker.results.appendChild(row);
          if (!picker.selected) {
            setPickerSelection(row);
          }
        });
      });
    });
  }

  function setPickerSelection(row) {
    const picker = STATE.picker;
    qsa(".link-picker-row.selected", picker.results).forEach((el) => el.classList.remove("selected"));
    row.classList.add("selected");
    picker.selected = row;
  }

  function movePickerSelection(delta) {
    const picker = STATE.picker;
    const rows = qsa(".link-picker-row", picker.results);
    if (!rows.length) {
      return;
    }
    let idx = rows.findIndex((row) => row.classList.contains("selected"));
    if (idx === -1) {
      idx = 0;
    } else {
      idx = Math.min(rows.length - 1, Math.max(0, idx + delta));
    }
    setPickerSelection(rows[idx]);
    rows[idx].scrollIntoView({ block: "nearest" });
  }

  function confirmPickerSelection() {
    const picker = STATE.picker;
    if (!picker || !picker.selected) {
      return;
    }
    const row = picker.selected;
    const typeSelect = qs(".link-picker-type", row);
    const linkType = typeSelect.value;
    const payload = {
      dst_type: row.dataset.type,
      dst_id: row.dataset.id,
      link_type: linkType,
      created_by: "ui",
      context_type: picker.contextType,
      context_id: STATE.record ? STATE.record.id : "",
    };
    if (picker.mode === "bulk") {
      const items = picker.sources.map((source) => ({
        src_type: source.type,
        src_id: source.id,
        dst_type: payload.dst_type,
        dst_id: payload.dst_id,
        link_type: payload.link_type,
        created_by: "ui",
        context_type: picker.contextType,
        context_id: picker.contextId || "",
      }));
      postJson("/links/api/bulk", { items: items })
        .then((data) => {
          const results = data.results || [];
          const dupes = results.filter((r) => r.duplicate).length;
          if (dupes) {
            showToast({ message: `Already linked ${dupes} item(s).` });
          } else {
            showToast({ message: `Linked ${items.length} item(s).` });
          }
          closeLinkPicker();
        })
        .catch(() => showToast({ message: "Couldn't create links." }));
      return;
    }
    payload.src_type = picker.srcType || (STATE.record && STATE.record.type);
    payload.src_id = STATE.record && STATE.record.id;
    if (!payload.src_type || !payload.src_id) {
      showToast({ message: "No source record selected." });
      return;
    }
    createLink(payload)
      .then((result) => {
        if (result.duplicate) {
          showToast({ message: `Already linked (${linkType}).` });
        } else {
          const allowedTypes = Array.from(typeSelect.options).map((opt) => opt.value);
          showToast({
            message: `Linked ${STATE.record ? STATE.record.title : "item"} -> ${row.dataset.title} (${linkType})`,
            undo: () => {
              if (result.link_id) {
                fetchJson(`/links/api/delete/${result.link_id}`, { method: "DELETE" });
              }
            },
            typeOptions: allowedTypes,
            typeValue: linkType,
            onTypeChange: (newType) => {
              if (!result.link_id || newType === linkType) {
                return;
              }
              patchJson(`/links/api/update/${result.link_id}`, { link_type: newType })
                .then(() => {
                  loadLinks();
                })
                .catch(() => {
                  showToast({ message: "Couldn't update link type." });
                });
            },
          });
        }
        closeLinkPicker();
        loadLinks();
      })
      .catch(() => {
        showToast({ message: "Couldn't create link." });
      });
  }
  function showToast(options) {
    const container = qs("#link-toast-container");
    if (!container) {
      return;
    }
    const toast = document.createElement("div");
    toast.className = "link-toast";
    const message = document.createElement("span");
    message.textContent = options.message || "";
    toast.appendChild(message);
    if (options.typeOptions && options.onTypeChange) {
      const typeSelect = document.createElement("select");
      typeSelect.className = "link-toast-type";
      options.typeOptions.forEach((linkType) => {
        const opt = document.createElement("option");
        opt.value = linkType;
        opt.textContent = LINK_TYPE_LABELS[linkType] || linkType;
        typeSelect.appendChild(opt);
      });
      typeSelect.value = options.typeValue || typeSelect.value;
      typeSelect.addEventListener("change", () => {
        options.onTypeChange(typeSelect.value);
      });
      toast.appendChild(typeSelect);
    }
    if (options.undo) {
      const undoBtn = document.createElement("button");
      undoBtn.type = "button";
      undoBtn.className = "links-btn link-undo";
      undoBtn.textContent = "Undo";
      undoBtn.addEventListener("click", () => {
        options.undo();
        toast.remove();
      });
      toast.appendChild(undoBtn);
    }
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add("fade");
      setTimeout(() => toast.remove(), 300);
    }, 6000);
  }

  function initDragSources() {
    qsa(".link-draggable").forEach((row) => {
      if (!row.dataset.recordType || !row.dataset.recordId) {
        return;
      }
      row.draggable = true;
      row.addEventListener("dragstart", (evt) => {
        const selected = getSelectedRecords(row);
        const payload = selected.length ? selected : [recordFromRow(row)];
        evt.dataTransfer.effectAllowed = "copy";
        evt.dataTransfer.setData("application/x-lifepim-records", JSON.stringify(payload));
        evt.dataTransfer.setData("text/plain", "record");
      });
    });
  }

  function recordFromRow(row) {
    return {
      type: row.dataset.recordType,
      id: row.dataset.recordId,
      title: row.dataset.recordTitle || "",
    };
  }

  function getSelectedRecords(row) {
    const table = row.closest("table");
    if (!table) {
      return [];
    }
    const selected = qsa("input.link-select:checked", table);
    if (!selected.length) {
      return [];
    }
    return selected.map((checkbox) => ({
      type: checkbox.dataset.recordType,
      id: checkbox.dataset.recordId,
      title: checkbox.dataset.recordTitle || "",
    }));
  }

  function initBulkToolbars() {
    qsa(".link-bulk-toolbar").forEach((toolbar) => {
      const tableId = toolbar.dataset.tableId;
      const table = tableId ? document.getElementById(tableId) : toolbar.nextElementSibling;
      if (!table) {
        return;
      }
      const countEl = qs(".link-bulk-count", toolbar);
      const actionBtn = qs(".link-bulk-open", toolbar);
      const updateCount = () => {
        const selected = qsa("input.link-select:checked", table);
        countEl.textContent = `${selected.length} selected`;
        actionBtn.disabled = selected.length === 0;
      };
      qsa("input.link-select", table).forEach((checkbox) => {
        checkbox.addEventListener("change", updateCount);
      });
      const selectAll = qs("input.link-select-all", table);
      if (selectAll) {
        selectAll.addEventListener("change", () => {
          qsa("input.link-select", table).forEach((checkbox) => {
            checkbox.checked = selectAll.checked;
          });
          updateCount();
        });
      }
      actionBtn.addEventListener("click", () => {
        const selected = qsa("input.link-select:checked", table).map((checkbox) => ({
          type: checkbox.dataset.recordType,
          id: checkbox.dataset.recordId,
          title: checkbox.dataset.recordTitle || "",
        }));
        openLinkPicker({
          mode: "bulk",
          sources: selected,
          srcType: toolbar.dataset.listType,
          contextType: "list_bulk_link",
          contextId: toolbar.dataset.contextId,
        });
      });
      updateCount();
    });
  }

  function initMentions() {
    const popup = qs("#mention-popup");
    if (!popup) {
      return;
    }
    const resultsEl = qs(".mention-results", popup);
    let activeInput = null;
    let mentionRange = null;

    function hidePopup() {
      popup.classList.remove("open");
      resultsEl.innerHTML = "";
      activeInput = null;
      mentionRange = null;
    }

    function showPopup(input, range, results) {
      resultsEl.innerHTML = "";
      if (!results.length) {
        hidePopup();
        return;
      }
      results.forEach((item, idx) => {
        const row = document.createElement("div");
        row.className = "mention-row";
        if (idx === 0) {
          row.classList.add("selected");
        }
        row.textContent = item.title || `${item.type} ${item.id}`;
        row.dataset.type = item.type;
        row.dataset.id = item.id;
        row.dataset.title = item.title || "";
        row.addEventListener("click", () => {
          insertMention(input, range, row.dataset);
          hidePopup();
        });
        resultsEl.appendChild(row);
      });
      const rect = input.getBoundingClientRect();
      popup.style.top = `${rect.bottom + window.scrollY + 6}px`;
      popup.style.left = `${rect.left + window.scrollX}px`;
      popup.classList.add("open");
      activeInput = input;
      mentionRange = range;
    }

    function insertMention(input, range, data) {
      const token = `@[${data.type}:${data.id}|${data.title}]`;
      const value = input.value;
      input.value = value.slice(0, range.start) + token + value.slice(range.end);
      input.focus();
      input.selectionStart = input.selectionEnd = range.start + token.length;
      const recordType = input.dataset.recordType;
      const recordId = input.dataset.recordId;
      if (!recordType || !recordId) {
        return;
      }
      const payload = {
        src_type: recordType,
        src_id: recordId,
        dst_type: data.type,
        dst_id: data.id,
        link_type: "mentions",
        created_by: "ui",
        context_type: "editor_mention",
        context_id: recordId,
      };
      createLink(payload).then((result) => {
        if (result.duplicate) {
          showToast({ message: "Already linked (mentions)." });
        } else {
          showToast({ message: "Mention linked." });
        }
      });
    }

    function findMentionRange(input) {
      const cursor = input.selectionStart;
      const text = input.value.slice(0, cursor);
      const at = text.lastIndexOf("@");
      if (at === -1) {
        return null;
      }
      const query = text.slice(at + 1);
      if (query.includes(" ") || query.includes("\n")) {
        return null;
      }
      return { start: at, end: cursor, query: query };
    }

    qsa("textarea.mention-enabled").forEach((input) => {
      input.addEventListener("input", () => {
        const range = findMentionRange(input);
        if (!range) {
          hidePopup();
          return;
        }
        const params = new URLSearchParams({ q: range.query, limit: "10" });
        fetchJson(`/links/api/search?${params.toString()}`)
          .then((data) => showPopup(input, range, data.results || []))
          .catch(() => hidePopup());
      });
      input.addEventListener("keydown", (evt) => {
        if (!popup.classList.contains("open")) {
          return;
        }
        if (evt.key === "Escape") {
          hidePopup();
        }
        if (evt.key === "Enter") {
          evt.preventDefault();
          const selected = qs(".mention-row.selected", resultsEl);
          if (selected && activeInput && mentionRange) {
            insertMention(activeInput, mentionRange, selected.dataset);
            hidePopup();
          }
        }
        if (evt.key === "ArrowDown" || evt.key === "ArrowUp") {
          evt.preventDefault();
          const rows = qsa(".mention-row", resultsEl);
          if (!rows.length) {
            return;
          }
          let idx = rows.findIndex((row) => row.classList.contains("selected"));
          idx = idx === -1 ? 0 : idx + (evt.key === "ArrowDown" ? 1 : -1);
          idx = Math.max(0, Math.min(rows.length - 1, idx));
          rows.forEach((row) => row.classList.remove("selected"));
          rows[idx].classList.add("selected");
        }
      });
    });
  }
  function initGlobalShortcuts() {
    document.addEventListener("keydown", (evt) => {
      if (evt.key === "Escape" && STATE.picker && STATE.picker.modal.classList.contains("open")) {
        evt.preventDefault();
        closeLinkPicker();
        return;
      }
      if (evt.ctrlKey && evt.shiftKey && evt.key.toLowerCase() === "l") {
        if (STATE.drawer) {
          evt.preventDefault();
          openLinkPicker({ mode: "single" });
        }
      }
      if (evt.ctrlKey && evt.altKey && evt.key.toLowerCase() === "l") {
        if (STATE.drawer) {
          evt.preventDefault();
          setDrawerOpen(!STATE.drawerOpen);
          STATE.drawer.focus();
        }
      }
      if (STATE.drawerFocused) {
        handleDrawerKey(evt);
      }
    });
  }

  function handleDrawerKey(evt) {
    if (evt.key.toLowerCase() === "a") {
      evt.preventDefault();
      openLinkPicker({ mode: "single", contextType: "links_drawer_add" });
      return;
    }
    if (evt.key === "Escape") {
      evt.preventDefault();
      STATE.drawer.blur();
      STATE.drawerFocused = false;
      return;
    }
    if (!STATE.selectedRow) {
      return;
    }
    if (evt.key === "Enter") {
      evt.preventDefault();
      const linkId = STATE.selectedRow.dataset.linkId;
      const link = STATE.links.find((l) => String(l.link_id) === String(linkId));
      if (link) {
        openLinkTarget(link);
      }
    } else if (evt.key === "Delete") {
      evt.preventDefault();
      const linkId = STATE.selectedRow.dataset.linkId;
      const link = STATE.links.find((l) => String(l.link_id) === String(linkId));
      if (link) {
        unlinkLink(link, STATE.selectedRow);
      }
    } else if (evt.key.toLowerCase() === "e") {
      evt.preventDefault();
      const input = qs(".link-label", STATE.selectedRow);
      if (input) {
        input.focus();
        input.select();
      }
    } else if (evt.key.toLowerCase() === "t") {
      evt.preventDefault();
      const select = qs(".link-type-select", STATE.selectedRow);
      if (select) {
        select.focus();
      }
    }
  }

  function debounce(fn, delay) {
    let timer = null;
    return function () {
      const args = arguments;
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(null, args), delay);
    };
  }

  document.addEventListener("dragend", () => {
    qsa(".link-row.dragging").forEach((row) => row.classList.remove("dragging"));
  });

  document.addEventListener("DOMContentLoaded", init);
})();
