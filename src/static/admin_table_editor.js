(function () {
  function toCode(value) {
    return String(value || "")
      .trim()
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function optionList(values) {
    return (values || []).map((value) => ({ value: value, label: value }));
  }

  function idString(value) {
    return value === null || value === undefined ? "" : String(value);
  }

  class AdminTableEditor {
    constructor(root, config) {
      this.root = root;
      this.config = config;
      this.rows = [];
      this.filteredRows = [];
      this.search = "";
      this.tbody = root.querySelector("[data-editor-body]");
      this.thead = root.querySelector("[data-editor-head]");
      this.status = root.querySelector("[data-editor-status]");
      this.searchInput = root.querySelector("[data-editor-search]");
      this.addButton = root.querySelector("[data-editor-add]");
      this.renderHeader();
      this.bind();
    }

    bind() {
      this.searchInput.addEventListener("input", () => {
        this.search = this.searchInput.value.trim().toLowerCase();
        this.renderRows();
      });
      this.addButton.addEventListener("click", () => this.addRow());
      this.root.addEventListener("click", (event) => {
        const toggle = event.target.closest("[data-picker-toggle]");
        if (toggle) {
          event.preventDefault();
          event.stopPropagation();
          const picker = toggle.closest(".admin-popup-multiselect");
          this.closePickers(picker);
          picker.classList.toggle("open");
          return;
        }
        if (!event.target.closest(".admin-popup-multiselect")) {
          this.closePickers();
        }
      });
      this.tbody.addEventListener("keydown", (event) => {
        const input = event.target.closest("input, select, textarea");
        if (!input) return;
        const row = input.closest("tr");
        if (event.key === "Enter" && input.tagName !== "TEXTAREA") {
          event.preventDefault();
          this.saveRow(row);
        } else if (event.key === "Escape") {
          event.preventDefault();
          this.restoreRow(row);
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          this.moveVertical(input, event.key === "ArrowDown" ? 1 : -1);
        }
      });
      this.tbody.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button) return;
        const row = button.closest("tr");
        if (button.dataset.action === "save") this.saveRow(row);
        if (button.dataset.action === "remove") this.removeRow(row);
      });
      this.tbody.addEventListener("input", (event) => {
        const input = event.target.closest("input, textarea");
        if (!input) return;
        if (input.dataset.field === this.config.codeField) return;
        if (input.dataset.field === "name") {
          const row = input.closest("tr");
          const codeInput = row.querySelector(`[data-field="${this.config.codeField}"]`);
          if (codeInput && !codeInput.dataset.touched && !codeInput.value) {
            codeInput.value = toCode(input.value);
          }
        }
      });
      this.tbody.addEventListener("change", (event) => {
        const input = event.target.closest("input, select, textarea");
        const picker = event.target.closest(".admin-popup-multiselect");
        if (picker) {
          this.updatePickerLabel(picker);
        }
        if (input && input.dataset.field === this.config.codeField) {
          input.dataset.touched = "1";
          input.value = toCode(input.value);
        }
      });
    }

    closePickers(exceptPicker) {
      this.root.querySelectorAll(".admin-popup-multiselect.open").forEach((picker) => {
        if (picker !== exceptPicker) {
          picker.classList.remove("open");
        }
      });
    }

    pickerLabels(picker) {
      const labels = Array.from(picker.querySelectorAll('input[type="checkbox"]:checked')).map((checkbox) => checkbox.dataset.label || checkbox.value);
      return labels;
    }

    updatePickerLabel(picker) {
      const label = picker.querySelector("[data-picker-label]");
      const labels = this.pickerLabels(picker);
      if (!label) {
        return;
      }
      label.textContent = labels.length ? labels.join(", ") : "None";
      label.title = label.textContent;
    }

    renderHeader() {
      const tr = document.createElement("tr");
      tr.appendChild(this.th("Actions"));
      this.config.columns.forEach((column) => tr.appendChild(this.th(column.label)));
      this.thead.replaceChildren(tr);
    }

    th(label) {
      const th = document.createElement("th");
      th.textContent = label;
      return th;
    }

    async load(params) {
      const query = new URLSearchParams(params || {});
      const suffix = query.toString() ? `?${query.toString()}` : "";
      const response = await fetch(this.config.endpoint + suffix);
      const payload = await response.json();
      if (!payload.ok) throw new Error(payload.error || "Load failed.");
      this.rows = payload.rows || [];
      this.renderRows();
      return payload;
    }

    rowMatches(row) {
      if (!this.search) return true;
      const haystack = this.config.searchFields
        .map((field) => idString(row[field]))
        .join(" ")
        .toLowerCase();
      return haystack.includes(this.search);
    }

    renderRows() {
      this.filteredRows = this.rows.filter((row) => this.rowMatches(row));
      const fragment = document.createDocumentFragment();
      this.filteredRows.forEach((row) => fragment.appendChild(this.renderRow(row, false)));
      this.tbody.replaceChildren(fragment);
    }

    addRow() {
      const row = Object.assign({}, this.config.defaults || {});
      const tr = this.renderRow(row, true);
      this.tbody.prepend(tr);
      const first = tr.querySelector("input:not([type=hidden]), select, textarea");
      if (first) first.focus();
    }

    renderRow(row, isNew) {
      const tr = document.createElement("tr");
      tr.dataset.newRow = isNew ? "1" : "0";
      tr.dataset.recordId = idString(row[this.config.idField]);
      tr.dataset.original = JSON.stringify(row);

      const actionCell = document.createElement("td");
      actionCell.className = "admin-editor-actions";
      actionCell.innerHTML = '<button type="button" data-action="save">Save</button><button type="button" class="admin-editor-delete-button" data-action="remove" title="Delete this row" aria-label="Delete this row">&#128465;</button><div class="admin-editor-row-error" data-row-error></div>';
      tr.appendChild(actionCell);

      this.config.columns.forEach((column) => {
        const td = document.createElement("td");
        td.appendChild(this.control(column, row));
        tr.appendChild(td);
      });
      return tr;
    }

    control(column, row) {
      let input;
      const value = row[column.field];
      if (column.type === "select") {
        input = document.createElement("select");
        if (!column.required) input.appendChild(new Option("", ""));
        (column.options || []).forEach((option) => input.appendChild(new Option(option.label, option.value)));
        input.value = idString(value);
      } else if (column.type === "multiselect") {
        input = document.createElement("select");
        input.multiple = true;
        input.size = Math.min(5, Math.max(3, (column.options || []).length));
        const selected = new Set((value || []).map(idString));
        (column.options || []).forEach((option) => {
          const opt = new Option(option.label, option.value);
          opt.selected = selected.has(idString(option.value));
          input.appendChild(opt);
        });
      } else if (column.type === "popup-multiselect") {
        input = document.createElement("div");
        input.className = "admin-popup-multiselect";
        input.dataset.field = column.field;
        const selected = new Set((value || []).map(idString));
        const labels = (column.options || [])
          .filter((option) => selected.has(idString(option.value)))
          .map((option) => option.label);
        input.innerHTML = '<button type="button" class="admin-picker-button" data-picker-toggle>...</button><span class="admin-picker-label" data-picker-label></span><div class="admin-picker-popup"></div>';
        const label = input.querySelector("[data-picker-label]");
        label.textContent = labels.length ? labels.join(", ") : "None";
        label.title = label.textContent;
        const popup = input.querySelector(".admin-picker-popup");
        (column.options || []).forEach((option) => {
          const row = document.createElement("label");
          row.className = "admin-picker-option";
          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.value = option.value;
          checkbox.dataset.label = option.label;
          checkbox.checked = selected.has(idString(option.value));
          row.appendChild(checkbox);
          row.appendChild(document.createTextNode(option.label));
          popup.appendChild(row);
        });
      } else if (column.type === "textarea") {
        input = document.createElement("textarea");
        input.rows = column.rows || 3;
        input.value = value || "";
      } else if (column.type === "checkbox") {
        input = document.createElement("input");
        input.type = "checkbox";
        input.checked = value === 1 || value === true || value === "1";
      } else {
        input = document.createElement("input");
        input.type = column.type || "text";
        input.value = value || "";
      }
      if (!input.dataset.field) {
        input.dataset.field = column.field;
      }
      if (column.required) input.dataset.required = "1";
      if (column.json) input.dataset.json = "1";
      return input;
    }

    valuesFromRow(tr) {
      const values = {};
      this.config.columns.forEach((column) => {
        const input = tr.querySelector(`[data-field="${column.field}"]`);
        if (!input) return;
        if (column.type === "multiselect") {
          values[column.field] = Array.from(input.selectedOptions).map((opt) => opt.value);
        } else if (column.type === "popup-multiselect") {
          values[column.field] = Array.from(input.querySelectorAll('input[type="checkbox"]:checked')).map((checkbox) => checkbox.value);
        } else if (column.type === "checkbox") {
          values[column.field] = input.checked ? 1 : 0;
        } else {
          values[column.field] = input.value;
        }
      });
      return values;
    }

    validate(values) {
      for (const column of this.config.columns) {
        if (column.required && !idString(values[column.field]).trim()) {
          throw new Error(`${column.label} is required.`);
        }
        if (column.code) {
          const code = toCode(values[column.field]);
          if (!/^[A-Z0-9_]+$/.test(code)) throw new Error(`${column.label} must use A-Z, 0-9, and underscores.`);
          values[column.field] = code;
        }
        if (column.json && idString(values[column.field]).trim()) {
          JSON.parse(values[column.field]);
        }
      }
      return values;
    }

    setError(tr, message) {
      const box = tr.querySelector("[data-row-error]");
      if (box) box.textContent = message || "";
    }

    async saveRow(tr) {
      try {
        this.setError(tr, "");
        const values = this.validate(this.valuesFromRow(tr));
        const isNew = tr.dataset.newRow === "1";
        const url = isNew ? this.config.endpoint : `${this.config.endpoint}/${tr.dataset.recordId}`;
        const response = await fetch(url, {
          method: isNew ? "POST" : "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(values),
        });
        const payload = await response.json();
        if (!payload.ok) throw new Error(payload.error || "Save failed.");
        this.flash("Saved.");
        await this.load(this.config.getParams ? this.config.getParams() : {});
        if (this.config.onSaved) await this.config.onSaved(payload, this);
      } catch (error) {
        this.setError(tr, error.message);
      }
    }

    async removeRow(tr) {
      if (tr.dataset.newRow === "1") {
        tr.remove();
        return;
      }
      try {
        const response = await fetch(`${this.config.endpoint}/${tr.dataset.recordId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "remove" }),
        });
        const payload = await response.json();
        if (!payload.ok) throw new Error(payload.error || "Remove failed.");
        this.flash(payload.deactivated ? "Deactivated." : "Removed.");
        await this.load(this.config.getParams ? this.config.getParams() : {});
        if (this.config.onRemoved) await this.config.onRemoved(payload, this);
      } catch (error) {
        this.setError(tr, error.message);
      }
    }

    restoreRow(tr) {
      if (tr.dataset.newRow === "1") {
        tr.remove();
        return;
      }
      const row = JSON.parse(tr.dataset.original || "{}");
      tr.replaceWith(this.renderRow(row, false));
    }

    moveVertical(input, direction) {
      const td = input.closest("td");
      const tr = input.closest("tr");
      if (!td || !tr) return;
      const index = Array.from(tr.children).indexOf(td);
      const next = direction > 0 ? tr.nextElementSibling : tr.previousElementSibling;
      if (!next) return;
      const nextCell = next.children[index];
      const nextInput = nextCell ? nextCell.querySelector("input, select, textarea") : null;
      if (nextInput) nextInput.focus();
    }

    flash(message) {
      this.status.textContent = message;
      window.setTimeout(() => {
        if (this.status.textContent === message) this.status.textContent = "";
      }, 1600);
    }
  }

  function escapeHtml(value) {
    return idString(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function initCatalog() {
    const shell = document.querySelector(".content-catalog-admin");
    if (!shell) return;
    let config = JSON.parse(shell.dataset.config || "{}");
    let summary = JSON.parse(shell.dataset.summary || "{}");
    const filterEls = Array.from(shell.querySelectorAll("[data-kind-filter]"));
    const matrixFilters = Array.from(shell.querySelectorAll("[data-matrix-filter]"));
    const panels = Array.from(shell.querySelectorAll("[data-mode-panel]"));
    const modeLinks = Array.from(shell.querySelectorAll("[data-catalog-mode]"));
    const reportGroups = shell.querySelector("[data-report-groups]");
    const editorTableControls = shell.querySelector("[data-editor-table-controls]");
    const editorTableSelect = shell.querySelector("[data-editor-table-select]");
    const editorTableName = shell.querySelector("[data-editor-table-name]");
    const summaryStats = shell.querySelector("[data-catalog-summary-stats]");
    const editorFilterBanner = shell.querySelector("[data-editor-filter-banner]");
    const initialUrl = new URL(window.location.href);
    const initialTable = initialUrl.searchParams.get("table");
    let currentMode = shell.dataset.initialMode || "matrix";
    let currentEditorTable = ["content-kinds", "patterns", "templates", "views"].includes(initialTable) ? initialTable : "content-kinds";
    let currentReportGroup = "by-tab";

    function selectOptions(select, values) {
      if (!select) return;
      values.forEach((item) => {
        if (typeof item === "string") {
          select.appendChild(new Option(item, item));
        } else {
          select.appendChild(new Option(item.label || item.area_name || item.value, item.value || item.area_id));
        }
      });
    }
    selectOptions(shell.querySelector('[data-kind-filter="area_id"]'), (config.areas || []).map((area) => ({ value: area.area_id, label: area.area_name || area.area_id })));
    selectOptions(shell.querySelector('[data-kind-filter="tab_code"]'), config.tabCodes || []);
    selectOptions(shell.querySelector('[data-matrix-filter="area_id"]'), (config.areas || []).map((area) => ({ value: area.area_id, label: area.area_name || area.area_id })));
    selectOptions(shell.querySelector('[data-matrix-filter="tab_code"]'), config.tabCodes || []);

    function kindParams() {
      const params = {};
      filterEls.forEach((el) => {
        if (el.value) params[el.dataset.kindFilter] = el.value;
      });
      return params;
    }

    function matrixParams(extra) {
      const params = Object.assign({}, extra || {});
      matrixFilters.forEach((el) => {
        if (el.value) params[el.dataset.matrixFilter] = el.value;
      });
      return params;
    }

    function renderSummary() {
      const box = shell.querySelector("[data-catalog-summary]");
      const statsBox = shell.querySelector("[data-catalog-summary-stats]");
      const stats = [
        `<span class="content-catalog-summary-stat">Total (${summary.total || 0})</span>`,
        `<span class="content-catalog-summary-stat">Complete (${summary.complete || 0})</span>`,
        `<span class="content-catalog-summary-stat">Missing Area (${summary.missing_area || 0})</span>`,
        `<span class="content-catalog-summary-stat">Missing Tab (${summary.missing_tab || 0})</span>`,
        `<span class="content-catalog-summary-stat">Missing Both (${summary.missing_both || 0})</span>`,
      ];
      box.innerHTML = `<span class="content-catalog-summary-filter">Catalog coverage</span>`;
      if (statsBox) {
        statsBox.innerHTML = stats.join("");
      }
    }
    renderSummary();

    const kindOptions = () => (config.contentKinds || []).map((item) => ({ value: item.value, label: item.label }));
    const templateOptions = () => (config.templates || []).map((item) => ({ value: item.value, label: item.label }));
    const viewOptions = () => (config.views || []).map((item) => ({ value: item.value, label: item.label }));
    const areaOptions = () => (config.areas || []).map((item) => ({ value: item.area_id, label: item.area_name || item.area_id }));

    function updateColumnOptions(editor, field, options) {
      const column = editor.config.columns.find((item) => item.field === field);
      if (column) column.options = options;
    }

    function updateEditorOptionSources() {
      updateColumnOptions(editors["content-kinds"], "area_id", areaOptions());
      updateColumnOptions(editors["content-kinds"], "tab_code", optionList(config.tabCodes));
      updateColumnOptions(editors.patterns, "content_kind_id", kindOptions());
      updateColumnOptions(editors.patterns, "default_area_id", areaOptions());
      updateColumnOptions(editors.patterns, "default_template_id", templateOptions());
      updateColumnOptions(editors.patterns, "default_view_id", viewOptions());
      updateColumnOptions(editors.templates, "template_type_code", optionList(config.templateTypeCodes));
      updateColumnOptions(editors.templates, "target_object_type", optionList(config.objectTypeCodes));
      updateColumnOptions(editors.templates, "target_tab_code", optionList(config.tabCodes));
      updateColumnOptions(editors.templates, "content_kind_ids", kindOptions());
      updateColumnOptions(editors.templates, "default_content_kind_id", kindOptions());
      updateColumnOptions(editors.views, "tab_code", optionList(config.tabCodes));
      updateColumnOptions(editors.views, "view_type_code", optionList(config.viewTypeCodes));
      updateColumnOptions(editors.views, "content_kind_ids", kindOptions());
      updateColumnOptions(editors.views, "default_content_kind_id", kindOptions());
    }

    async function refreshCatalogConfig() {
      const response = await fetch("/admin/content-catalog/api/config");
      const payload = await response.json();
      if (!payload.ok) return;
      config = payload.config || config;
      summary = payload.summary || summary;
      updateEditorOptionSources();
      renderSummary();
      Object.values(editors).forEach((editor) => editor.renderRows());
      if (currentMode === "matrix") loadMatrix();
      if (currentMode === "report") loadReport();
    }

    const editors = {
      "content-kinds": new AdminTableEditor(document.querySelector('[data-editor="contentKindsEditor"]'), {
        endpoint: "/admin/content-catalog/api/content-kinds",
        idField: "content_kind_id",
        getParams: kindParams,
        searchFields: ["name", "comment"],
        defaults: {},
        columns: [
          { field: "name", label: "Name", required: true },
          { field: "area_id", label: "Area", type: "select", options: areaOptions() },
          { field: "tab_code", label: "Tab", type: "select", options: optionList(config.tabCodes) },
          { field: "comment", label: "Comment", type: "textarea", rows: 1 },
        ],
        onSaved: refreshCatalogConfig,
        onRemoved: refreshCatalogConfig,
      }),
      patterns: new AdminTableEditor(document.querySelector('[data-editor="patternsEditor"]'), {
        endpoint: "/admin/content-catalog/api/patterns",
        idField: "content_pattern_id",
        codeField: "pattern_code",
        searchFields: ["name", "pattern_code", "description", "notes"],
        defaults: { is_active: 1 },
        columns: [
          { field: "name", label: "Name", required: true },
          { field: "pattern_code", label: "Code", required: true, code: true },
          { field: "content_kind_id", label: "Content Kind", type: "select", required: true, options: kindOptions() },
          { field: "default_area_id", label: "Default Area", type: "select", options: areaOptions() },
          { field: "default_template_id", label: "Default Template", type: "select", options: templateOptions() },
          { field: "default_view_id", label: "Default View", type: "select", options: viewOptions() },
          { field: "is_active", label: "Active", type: "checkbox" },
          { field: "notes", label: "Notes" },
          { field: "description", label: "Description" },
          { field: "creation_config", label: "Creation Config", json: true },
          { field: "view_filter_config", label: "View Filter Config", json: true },
        ],
        onSaved: refreshCatalogConfig,
        onRemoved: refreshCatalogConfig,
      }),
      templates: new AdminTableEditor(document.querySelector('[data-editor="templatesEditor"]'), {
        endpoint: "/admin/content-catalog/api/templates",
        idField: "template_id",
        codeField: "template_code",
        searchFields: ["name", "template_code", "description", "notes"],
        defaults: { template_type_code: "NOTE", is_active: 1, content_kind_ids: [] },
        columns: [
          { field: "name", label: "Name", required: true },
          { field: "template_code", label: "Code", required: true, code: true },
          { field: "template_type_code", label: "Template Type", type: "select", required: true, options: optionList(config.templateTypeCodes) },
          { field: "target_object_type", label: "Target Object", type: "select", options: optionList(config.objectTypeCodes) },
          { field: "target_tab_code", label: "Target Tab", type: "select", options: optionList(config.tabCodes) },
          { field: "content_kind_ids", label: "Content Kinds", type: "popup-multiselect", options: kindOptions() },
          { field: "default_content_kind_id", label: "Default For Kind", type: "select", options: kindOptions() },
          { field: "is_active", label: "Active", type: "checkbox" },
          { field: "notes", label: "Notes" },
          { field: "description", label: "Description", type: "textarea", rows: 1 },
          { field: "template_content", label: "Template Content", type: "textarea", rows: 1 },
          { field: "template_config", label: "Template Config", type: "textarea", rows: 1, json: true },
        ],
        onSaved: refreshCatalogConfig,
        onRemoved: refreshCatalogConfig,
      }),
      views: new AdminTableEditor(document.querySelector('[data-editor="viewsEditor"]'), {
        endpoint: "/admin/content-catalog/api/views",
        idField: "content_view_id",
        codeField: "view_code",
        searchFields: ["name", "view_code", "description", "notes"],
        defaults: { view_type_code: "LIST", is_active: 1, content_kind_ids: [] },
        columns: [
          { field: "name", label: "Name", required: true },
          { field: "view_code", label: "Code", required: true, code: true },
          { field: "tab_code", label: "Tab", type: "select", options: optionList(config.tabCodes) },
          { field: "view_type_code", label: "View Type", type: "select", required: true, options: optionList(config.viewTypeCodes) },
          { field: "content_kind_ids", label: "Content Kinds", type: "popup-multiselect", options: kindOptions() },
          { field: "default_content_kind_id", label: "Default For Kind", type: "select", options: kindOptions() },
          { field: "is_active", label: "Active", type: "checkbox" },
          { field: "notes", label: "Notes" },
          { field: "description", label: "Description", type: "textarea", rows: 1 },
          { field: "view_config", label: "View Config", type: "textarea", rows: 1, json: true },
        ],
        onSaved: refreshCatalogConfig,
        onRemoved: refreshCatalogConfig,
      }),
    };

    async function loadKinds() {
      const payload = await editors["content-kinds"].load(kindParams());
      if (payload.summary) {
        summary = payload.summary;
        renderSummary();
      }
    }

    function setMode(mode) {
      currentMode = mode || "matrix";
      panels.forEach((panel) => {
        panel.hidden = panel.dataset.modePanel !== currentMode;
      });
      modeLinks.forEach((link) => link.classList.toggle("active", link.dataset.catalogMode === currentMode));
      if (reportGroups) {
        reportGroups.hidden = currentMode !== "report";
      }
      if (editorTableControls) {
        editorTableControls.hidden = currentMode !== "editor";
      }
      if (summaryStats) {
        summaryStats.hidden = currentMode === "editor";
      }
      const url = new URL(window.location.href);
      url.searchParams.set("mode", currentMode);
      window.history.replaceState({}, "", url);
      if (currentMode === "matrix") loadMatrix();
      if (currentMode === "report") loadReport();
      if (currentMode === "editor") setEditorTable(currentEditorTable);
    }

    function setEditorFilters(filters) {
      filterEls.forEach((el) => {
        const value = filters[el.dataset.kindFilter];
        el.value = value !== undefined ? value : "";
      });
      const labels = filters._labels || {};
      if (editorFilterBanner && (labels.area || labels.tab)) {
        editorFilterBanner.innerHTML = `Filtered to: Area = ${escapeHtml(labels.area || "Any")}, Tab = ${escapeHtml(labels.tab || "Any")} <button type="button" data-clear-editor-filters>Clear</button>`;
        editorFilterBanner.hidden = false;
      }
      loadKinds();
    }

    function clearEditorFilters() {
      filterEls.forEach((el) => {
        el.value = "";
      });
      if (editorFilterBanner) {
        editorFilterBanner.hidden = true;
        editorFilterBanner.innerHTML = "";
      }
      loadKinds();
    }

    async function loadMatrix() {
      const response = await fetch(`/admin/content-catalog/api/matrix?${new URLSearchParams(matrixParams()).toString()}`);
      const payload = await response.json();
      if (!payload.ok) return;
      renderMatrix(payload.matrix);
    }

    function renderMatrix(matrix) {
      const meta = shell.querySelector("[data-matrix-meta]");
      const wrap = shell.querySelector("[data-matrix-wrap]");
      meta.textContent = `${matrix.totals.unique_kinds} catalog items; ${matrix.totals.assigned_area_mappings} with Area; ${matrix.totals.unassigned_kind_placements} missing Area`;
      const header = matrix.tabs.map((tab) => `<th>${escapeHtml(tab.label)}<span>${tab.total || 0}</span></th>`).join("");
      const rows = matrix.areas.map((area) => {
        const cells = matrix.tabs.map((tab) => {
          const key = `${area.area_id}|${tab.code}`;
          const cell = matrix.cells[key] || { total: 0, items: [] };
          if (!cell.total) {
            return '<td class="matrix-empty"></td>';
          }
          const names = (cell.items || []).map((name) => `<span>${escapeHtml(name)}</span>`).join("");
          const more = cell.total > (cell.items || []).length ? `<em>+ ${cell.total - cell.items.length} more</em>` : "";
          return `<td><button type="button" class="matrix-cell" data-area-id="${escapeHtml(area.area_id)}" data-area-label="${escapeHtml(area.label)}" data-tab-code="${escapeHtml(tab.code)}" data-tab-label="${escapeHtml(tab.label)}"><strong>${cell.total}</strong>${names}${more}</button></td>`;
        }).join("");
        return `<tr><th class="matrix-area">${escapeHtml(area.label)}<span>${area.total || 0}</span></th>${cells}<td class="matrix-total">${area.total || 0}</td></tr>`;
      }).join("");
      const totals = matrix.tabs.map((tab) => `<td class="matrix-total">${tab.total || 0}</td>`).join("");
      wrap.innerHTML = `<table class="content-catalog-matrix"><thead><tr><th class="matrix-area">Area</th>${header}<th>Total</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><th class="matrix-area">Total</th>${totals}<td class="matrix-total">${matrix.totals.matrix_placements}</td></tr></tfoot></table>`;
    }

    async function openCell(button) {
      const params = matrixParams({
        area_id: button.dataset.areaId,
        tab_code: button.dataset.tabCode,
      });
      const response = await fetch(`/admin/content-catalog/api/cell?${new URLSearchParams(params).toString()}`);
      const payload = await response.json();
      if (!payload.ok) return;
      const drawer = shell.querySelector("[data-catalog-drawer]");
      const title = shell.querySelector("[data-drawer-title]");
      const body = shell.querySelector("[data-drawer-body]");
      title.textContent = `${button.dataset.areaLabel} -> ${button.dataset.tabLabel}`;
      const items = (payload.rows || []).map((row) => {
        const template = row.default_template ? row.default_template.name : "";
        const view = row.default_view ? row.default_view.name : "";
        return `<article class="drawer-kind-item">
          <button type="button" data-open-kind="${escapeHtml(row.content_kind_id)}">${escapeHtml(row.name)}</button>
          <span>${escapeHtml(row.comment || "")}</span>
          <dl>
            <dt>Area</dt><dd>${escapeHtml(row.area_name || row.area_id || "")}</dd>
            <dt>Tab</dt><dd>${escapeHtml(row.tab_code || "")}</dd>
            <dt>Template</dt><dd>${escapeHtml(template)}</dd>
            <dt>View</dt><dd>${escapeHtml(view)}</dd>
          </dl>
        </article>`;
      }).join("");
      body.innerHTML = `<p>${payload.rows.length} content kinds</p><button type="button" data-open-filtered-editor>Open Filtered Editor</button>${items || '<p class="settings-empty">No content kinds.</p>'}`;
      body.querySelector("[data-open-filtered-editor]").addEventListener("click", () => {
        setEditorTable("content-kinds");
        setEditorFilters({
          area_id: button.dataset.areaId,
          tab_code: button.dataset.tabCode,
          _labels: {
            area: button.dataset.areaLabel,
            tab: button.dataset.tabLabel,
          },
        });
        setMode("editor");
      });
      body.querySelectorAll("[data-open-kind]").forEach((itemButton) => {
        itemButton.addEventListener("click", () => {
          setEditorTable("content-kinds");
          setMode("editor");
          const row = editors["content-kinds"].rows.find((item) => idString(item.content_kind_id) === itemButton.dataset.openKind);
          editors["content-kinds"].searchInput.value = row ? row.name : itemButton.dataset.openKind;
          editors["content-kinds"].search = editors["content-kinds"].searchInput.value.toLowerCase();
          editors["content-kinds"].renderRows();
        });
      });
      drawer.hidden = false;
    }

    async function loadReport() {
      const params = matrixParams({ group: currentReportGroup });
      const response = await fetch(`/admin/content-catalog/api/report?${new URLSearchParams(params).toString()}`);
      const payload = await response.json();
      if (!payload.ok) return;
      renderReport(payload.report);
    }

    function renderKindSummary(row) {
      const areas = (row.areas || []).map((area) => area.area_name || area.area_id).join(", ");
      const templates = (row.templates || []).map((item) => item.name).join(", ");
      const views = (row.views || []).map((item) => item.name).join(", ");
      return `<article class="report-kind">
        <h5>${escapeHtml(row.name)}</h5>
        <p>Area: ${escapeHtml(areas || "Unassigned")} | Tab: ${escapeHtml(row.tab_code || "No Tab")}</p>
        <p>${escapeHtml(row.comment || "")}</p>
        <p>Templates: ${escapeHtml(templates)}</p>
        <p>Views: ${escapeHtml(views)}</p>
      </article>`;
    }

    function renderReport(report) {
      const body = shell.querySelector("[data-report-body]");
      if (report.group === "by-area") {
        body.innerHTML = report.sections.map((section) => `<section class="report-section"><h4>${escapeHtml(section.label)}</h4>${section.tabs.map((tab) => `<h5>${escapeHtml(tab.label)}</h5>${tab.items.map(renderKindSummary).join("")}`).join("")}</section>`).join("");
        return;
      }
      body.innerHTML = report.sections.map((section) => `<section class="report-section"><h4>${escapeHtml(section.label)}</h4>${(section.areas || []).map((area) => `<h5>${escapeHtml(area.label)}</h5>${area.items.map(renderKindSummary).join("")}`).join("") || '<p class="settings-empty">No items.</p>'}</section>`).join("");
    }

    filterEls.forEach((el) => el.addEventListener("change", () => {
      loadKinds();
    }));

    matrixFilters.forEach((el) => el.addEventListener("input", () => {
      if (currentMode === "matrix") loadMatrix();
      if (currentMode === "report") loadReport();
    }));
    shell.querySelector("[data-matrix-wrap]").addEventListener("click", (event) => {
      const button = event.target.closest(".matrix-cell");
      if (button) openCell(button);
    });
    shell.querySelector("[data-drawer-close]").addEventListener("click", () => {
      shell.querySelector("[data-catalog-drawer]").hidden = true;
    });
    modeLinks.forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        setMode(link.dataset.catalogMode);
      });
    });
    if (editorFilterBanner) {
      editorFilterBanner.addEventListener("click", (event) => {
        if (event.target.closest("[data-clear-editor-filters]")) {
          clearEditorFilters();
        }
      });
    }

    function setEditorTable(tableKey) {
      currentEditorTable = tableKey || "content-kinds";
      if (editorTableSelect) {
        editorTableSelect.value = currentEditorTable;
      }
      const selectedOption = editorTableSelect ? editorTableSelect.selectedOptions[0] : null;
      if (editorTableName) {
        editorTableName.textContent = selectedOption ? selectedOption.dataset.dbName : "lp_content_kind";
      }
      shell.querySelectorAll("[data-catalog-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.catalogPanel !== currentEditorTable;
      });
      const editor = editors[currentEditorTable];
      if (editor && !editor.rows.length) editor.load();
    }

    editorTableSelect.addEventListener("change", () => {
      setEditorTable(editorTableSelect.value);
    });

    reportGroups.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-report-group]");
      if (!button) return;
      currentReportGroup = button.dataset.reportGroup;
      shell.querySelectorAll("[data-report-group]").forEach((btn) => btn.classList.toggle("active", btn === button));
      loadReport();
    });

    setMode(currentMode);
  }

  window.AdminTableEditor = AdminTableEditor;
  document.addEventListener("DOMContentLoaded", initCatalog);
})();
