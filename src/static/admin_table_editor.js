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
      tr.appendChild(this.th("Save"));
      this.config.columns.forEach((column) => tr.appendChild(this.th(column.label)));
      tr.appendChild(this.th(""));
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
      actionCell.innerHTML = '<button type="button" data-action="save">Save</button><div class="admin-editor-row-error" data-row-error></div>';
      tr.appendChild(actionCell);

      this.config.columns.forEach((column) => {
        const td = document.createElement("td");
        td.appendChild(this.control(column, row));
        tr.appendChild(td);
      });
      const deleteCell = document.createElement("td");
      deleteCell.className = "admin-editor-delete";
      deleteCell.innerHTML = '<button type="button" data-action="remove" title="Remove this row">x</button>';
      tr.appendChild(deleteCell);
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
    const config = JSON.parse(shell.dataset.config || "{}");
    let summary = JSON.parse(shell.dataset.summary || "{}");
    const filterEls = Array.from(shell.querySelectorAll("[data-kind-filter]"));
    const matrixFilters = Array.from(shell.querySelectorAll("[data-matrix-filter]"));
    const matrixToggles = Array.from(shell.querySelectorAll("[data-matrix-toggle]"));
    const panels = Array.from(shell.querySelectorAll("[data-mode-panel]"));
    const modeLinks = Array.from(shell.querySelectorAll("[data-catalog-mode]"));
    let currentMode = shell.dataset.initialMode || "matrix";
    let currentReportGroup = "by-tab";
    let summaryFilter = {};

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
    selectOptions(shell.querySelector('[data-kind-filter="object_type_code"]'), config.objectTypeCodes || []);
    selectOptions(shell.querySelector('[data-kind-filter="canonical_tab_code"]'), config.tabCodes || []);
    selectOptions(shell.querySelector('[data-kind-filter="mapping_status_code"]'), config.mappingStatusCodes || []);
    selectOptions(shell.querySelector('[data-kind-filter="area_id"]'), (config.areas || []).map((area) => ({ value: area.area_id, label: area.area_name || area.area_id })));
    selectOptions(shell.querySelector('[data-matrix-filter="object_type_code"]'), config.objectTypeCodes || []);
    selectOptions(shell.querySelector('[data-matrix-filter="mapping_status_code"]'), config.mappingStatusCodes || []);

    function kindParams() {
      const params = {};
      filterEls.forEach((el) => {
        if (el.value) params[el.dataset.kindFilter] = el.value;
      });
      return params;
    }

    function matrixParams(extra) {
      const params = Object.assign({}, summaryFilter, extra || {});
      matrixFilters.forEach((el) => {
        if (el.value) params[el.dataset.matrixFilter] = el.value;
      });
      matrixToggles.forEach((el) => {
        if (el.checked && el.dataset.matrixToggle !== "show_status_counts") {
          params[el.dataset.matrixToggle] = "1";
        }
      });
      return params;
    }

    function showStatusCounts() {
      const el = shell.querySelector('[data-matrix-toggle="show_status_counts"]');
      return !el || el.checked;
    }

    function renderSummary() {
      const box = shell.querySelector("[data-catalog-summary]");
      const statusLabels = {
        CONFIRMED: "Confirmed",
        NEEDS_TEMPLATE: "Need Templates",
        NEEDS_VIEW: "Need Views",
        NEEDS_OBJECT: "Need Objects",
        UNDECIDED: "Undecided",
      };
      const buttons = [
        `<button type="button" data-summary-filter="" data-summary-value="">${summary.total || 0} Content Kinds</button>`,
        `<button type="button" data-summary-filter="" data-summary-value="">${summary.mappings || 0} Area-Tab Mappings</button>`,
      ];
      Object.keys(statusLabels).forEach((code) => {
        buttons.push(`<button type="button" data-summary-filter="mapping_status_code" data-summary-value="${code}">${(summary.statuses || {})[code] || 0} ${statusLabels[code]}</button>`);
      });
      buttons.push(`<button type="button" data-summary-filter="active" data-summary-value="0">${summary.inactive || 0} Inactive</button>`);
      (config.tabCodes || []).forEach((code) => {
        buttons.push(`<button type="button" data-summary-filter="canonical_tab_code" data-summary-value="${code}">${(summary.tabs || {})[code] || 0} ${code}</button>`);
      });
      box.innerHTML = buttons.join("");
    }
    renderSummary();

    const kindOptions = () => (config.contentKinds || []).map((item) => ({ value: item.value, label: item.label }));
    const templateOptions = () => (config.templates || []).map((item) => ({ value: item.value, label: item.label }));
    const viewOptions = () => (config.views || []).map((item) => ({ value: item.value, label: item.label }));
    const areaOptions = () => (config.areas || []).map((item) => ({ value: item.area_id, label: item.area_name || item.area_id }));

    const editors = {
      "content-kinds": new AdminTableEditor(document.querySelector('[data-editor="contentKindsEditor"]'), {
        endpoint: "/admin/content-catalog/api/content-kinds",
        idField: "content_kind_id",
        codeField: "kind_code",
        getParams: kindParams,
        searchFields: ["name", "kind_code", "description", "notes", "canonical_table_name"],
        defaults: { object_type_code: "NOTE", date_behaviour_code: "NONE", mapping_status_code: "UNDECIDED", is_active: 1, area_ids: [] },
        columns: [
          { field: "name", label: "Name", required: true },
          { field: "kind_code", label: "Code", required: true, code: true },
          { field: "parent_content_kind_id", label: "Parent", type: "select", options: kindOptions() },
          { field: "object_type_code", label: "Object Type", type: "select", required: true, options: optionList(config.objectTypeCodes) },
          { field: "canonical_tab_code", label: "Tab", type: "select", options: optionList(config.tabCodes) },
          { field: "canonical_table_name", label: "Canonical Table" },
          { field: "subtype_code", label: "Subtype", code: true },
          { field: "date_behaviour_code", label: "Date Behaviour", type: "select", required: true, options: optionList(config.dateBehaviourCodes) },
          { field: "area_ids", label: "Areas", type: "popup-multiselect", options: areaOptions() },
          { field: "default_area_id", label: "Default Area", type: "select", options: areaOptions() },
          { field: "mapping_status_code", label: "Mapping Status", type: "select", required: true, options: optionList(config.mappingStatusCodes) },
          { field: "is_active", label: "Active", type: "checkbox" },
          { field: "notes", label: "Notes" },
        ],
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
      const url = new URL(window.location.href);
      url.searchParams.set("mode", currentMode);
      window.history.replaceState({}, "", url);
      if (currentMode === "matrix") loadMatrix();
      if (currentMode === "report") loadReport();
      if (currentMode === "editor" && !editors["content-kinds"].rows.length) loadKinds();
    }

    function setEditorFilters(filters) {
      filterEls.forEach((el) => {
        const value = filters[el.dataset.kindFilter];
        if (value !== undefined) el.value = value;
      });
      loadKinds();
    }

    function renderStatusLine(statuses) {
      if (!showStatusCounts()) return "";
      const confirmed = statuses.CONFIRMED || 0;
      const needsTemplate = statuses.NEEDS_TEMPLATE || 0;
      const needsView = statuses.NEEDS_VIEW || 0;
      const needsObject = statuses.NEEDS_OBJECT || 0;
      const undecided = statuses.UNDECIDED || 0;
      return `<span class="matrix-cell-status">C${confirmed} T${needsTemplate} V${needsView} O${needsObject} ?${undecided}</span>`;
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
      meta.textContent = `${matrix.totals.unique_kinds} unique content kinds; ${matrix.totals.area_tab_mappings} Area-Tab mappings`;
      const header = matrix.tabs.map((tab) => `<th>${escapeHtml(tab.label)}<span>${tab.total || 0}</span></th>`).join("");
      const rows = matrix.areas.map((area) => {
        const cells = matrix.tabs.map((tab) => {
          const key = `${area.area_id}|${tab.code}`;
          const cell = matrix.cells[key] || { total: 0, statuses: {} };
          if (!cell.total) {
            return '<td class="matrix-empty"></td>';
          }
          return `<td><button type="button" class="matrix-cell" data-area-id="${escapeHtml(area.area_id)}" data-area-label="${escapeHtml(area.label)}" data-tab-code="${escapeHtml(tab.code)}" data-tab-label="${escapeHtml(tab.label)}"><strong>${cell.total}</strong>${renderStatusLine(cell.statuses || {})}</button></td>`;
        }).join("");
        return `<tr><th class="matrix-area">${escapeHtml(area.label)}<span>${area.total || 0}</span></th>${cells}<td class="matrix-total">${area.total || 0}</td></tr>`;
      }).join("");
      const totals = matrix.tabs.map((tab) => `<td class="matrix-total">${tab.total || 0}</td>`).join("");
      wrap.innerHTML = `<table class="content-catalog-matrix"><thead><tr><th class="matrix-area">Area</th>${header}<th>Total</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><th class="matrix-area">Total</th>${totals}<td class="matrix-total">${matrix.totals.area_tab_mappings}</td></tr></tfoot></table>`;
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
          <button type="button" data-open-kind="${escapeHtml(row.kind_code)}">${escapeHtml(row.name)}</button>
          <span>${escapeHtml(row.mapping_status_code)}</span>
          <dl>
            <dt>Code</dt><dd>${escapeHtml(row.kind_code)}</dd>
            <dt>Parent</dt><dd>${escapeHtml(row.parent_name || "")}</dd>
            <dt>Object</dt><dd>${escapeHtml(row.object_type_code)}</dd>
            <dt>Template</dt><dd>${escapeHtml(template)}</dd>
            <dt>View</dt><dd>${escapeHtml(view)}</dd>
          </dl>
        </article>`;
      }).join("");
      body.innerHTML = `<p>${payload.rows.length} content kinds</p><button type="button" data-open-filtered-editor>Open Filtered Editor</button>${items || '<p class="settings-empty">No content kinds.</p>'}`;
      body.querySelector("[data-open-filtered-editor]").addEventListener("click", () => {
        setMode("editor");
        setEditorFilters({
          area_id: button.dataset.areaId === config.unassignedAreaId ? "" : button.dataset.areaId,
          canonical_tab_code: button.dataset.tabCode === config.noTabCode ? "" : button.dataset.tabCode,
        });
      });
      body.querySelectorAll("[data-open-kind]").forEach((itemButton) => {
        itemButton.addEventListener("click", () => {
          setMode("editor");
          editors["content-kinds"].searchInput.value = itemButton.dataset.openKind;
          editors["content-kinds"].search = itemButton.dataset.openKind.toLowerCase();
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
        <p>Code: ${escapeHtml(row.kind_code)} | Parent: ${escapeHtml(row.parent_name || "")} | Object type: ${escapeHtml(row.object_type_code)} | Status: ${escapeHtml(row.mapping_status_code)}</p>
        <p>Canonical table: ${escapeHtml(row.canonical_table_name || "")}</p>
        <p>Areas: ${escapeHtml(areas)}</p>
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
      body.innerHTML = report.sections.map((section) => `<section class="report-section"><h4>${escapeHtml(section.label)} <span>${(section.items || []).length}</span></h4>${(section.items || []).map(renderKindSummary).join("") || '<p class="settings-empty">No items.</p>'}</section>`).join("");
    }

    filterEls.forEach((el) => el.addEventListener("change", loadKinds));
    matrixFilters.forEach((el) => el.addEventListener("input", () => {
      if (currentMode === "matrix") loadMatrix();
      if (currentMode === "report") loadReport();
    }));
    matrixToggles.forEach((el) => el.addEventListener("change", () => {
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
    shell.querySelector("[data-catalog-summary]").addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      if (currentMode === "matrix" || currentMode === "report") {
        summaryFilter = {};
        if (button.dataset.summaryFilter && !["mapping_status_code", "object_type_code", "active"].includes(button.dataset.summaryFilter)) {
          summaryFilter[button.dataset.summaryFilter] = button.dataset.summaryValue;
        }
        matrixFilters.forEach((el) => {
          if (!button.dataset.summaryFilter) el.value = "";
          if (el.dataset.matrixFilter === button.dataset.summaryFilter) el.value = button.dataset.summaryValue;
        });
        if (currentMode === "matrix") loadMatrix();
        if (currentMode === "report") loadReport();
        return;
      }
      filterEls.forEach((el) => {
        if (!button.dataset.summaryFilter) el.value = el.dataset.kindFilter === "active" ? "all" : "";
        if (el.dataset.kindFilter === button.dataset.summaryFilter) el.value = button.dataset.summaryValue;
      });
      loadKinds();
    });

    shell.querySelector("[data-mode-panel='editor'] .content-catalog-compact-tabs").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-catalog-tab]");
      if (!button) return;
      shell.querySelectorAll("[data-catalog-tab]").forEach((btn) => btn.classList.toggle("active", btn === button));
      shell.querySelectorAll("[data-catalog-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.catalogPanel !== button.dataset.catalogTab;
      });
      const editor = editors[button.dataset.catalogTab];
      if (editor && !editor.rows.length) editor.load();
    });

    shell.querySelector("[data-mode-panel='report'] .content-catalog-compact-tabs").addEventListener("click", (event) => {
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
