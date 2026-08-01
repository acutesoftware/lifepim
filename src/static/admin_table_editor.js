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
        if (button.dataset.action === "deactivate") this.deactivateRow(row);
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
        if (input && input.dataset.field === this.config.codeField) {
          input.dataset.touched = "1";
          input.value = toCode(input.value);
        }
      });
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
      actionCell.innerHTML = '<button type="button" data-action="save">Save</button> <button type="button" data-action="deactivate">Deactivate</button><div class="admin-editor-row-error" data-row-error></div>';
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
      input.dataset.field = column.field;
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

    async deactivateRow(tr) {
      if (tr.dataset.newRow === "1") {
        tr.remove();
        return;
      }
      try {
        const response = await fetch(`${this.config.endpoint}/${tr.dataset.recordId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "deactivate" }),
        });
        const payload = await response.json();
        if (!payload.ok) throw new Error(payload.error || "Deactivate failed.");
        this.flash("Deactivated.");
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

  function initCatalog() {
    const shell = document.querySelector(".content-catalog-admin");
    if (!shell) return;
    const config = JSON.parse(shell.dataset.config || "{}");
    let summary = JSON.parse(shell.dataset.summary || "{}");
    const filterEls = Array.from(shell.querySelectorAll("[data-kind-filter]"));

    function selectOptions(select, values) {
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

    function kindParams() {
      const params = {};
      filterEls.forEach((el) => {
        if (el.value) params[el.dataset.kindFilter] = el.value;
      });
      return params;
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
      const buttons = [`<button type="button" data-summary-filter="" data-summary-value="">Total Kinds <strong>${summary.total || 0}</strong></button>`];
      Object.keys(statusLabels).forEach((code) => {
        buttons.push(`<button type="button" data-summary-filter="mapping_status_code" data-summary-value="${code}">${statusLabels[code]} <strong>${(summary.statuses || {})[code] || 0}</strong></button>`);
      });
      buttons.push(`<button type="button" data-summary-filter="active" data-summary-value="0">Inactive <strong>${summary.inactive || 0}</strong></button>`);
      (config.tabCodes || []).forEach((code) => {
        buttons.push(`<button type="button" data-summary-filter="canonical_tab_code" data-summary-value="${code}">${code} <strong>${(summary.tabs || {})[code] || 0}</strong></button>`);
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
          { field: "area_ids", label: "Areas", type: "multiselect", options: areaOptions() },
          { field: "default_area_id", label: "Default Area", type: "select", options: areaOptions() },
          { field: "mapping_status_code", label: "Mapping Status", type: "select", required: true, options: optionList(config.mappingStatusCodes) },
          { field: "is_active", label: "Active", type: "checkbox" },
          { field: "notes", label: "Notes", type: "textarea", rows: 2 },
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
          { field: "notes", label: "Notes", type: "textarea", rows: 2 },
          { field: "description", label: "Description", type: "textarea", rows: 2 },
          { field: "creation_config", label: "Creation Config", type: "textarea", rows: 3, json: true },
          { field: "view_filter_config", label: "View Filter Config", type: "textarea", rows: 3, json: true },
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
          { field: "content_kind_ids", label: "Content Kinds", type: "multiselect", options: kindOptions() },
          { field: "default_content_kind_id", label: "Default For Kind", type: "select", options: kindOptions() },
          { field: "is_active", label: "Active", type: "checkbox" },
          { field: "notes", label: "Notes", type: "textarea", rows: 2 },
          { field: "description", label: "Description", type: "textarea", rows: 2 },
          { field: "template_content", label: "Template Content", type: "textarea", rows: 6 },
          { field: "template_config", label: "Template Config", type: "textarea", rows: 3, json: true },
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
          { field: "content_kind_ids", label: "Content Kinds", type: "multiselect", options: kindOptions() },
          { field: "default_content_kind_id", label: "Default For Kind", type: "select", options: kindOptions() },
          { field: "is_active", label: "Active", type: "checkbox" },
          { field: "notes", label: "Notes", type: "textarea", rows: 2 },
          { field: "description", label: "Description", type: "textarea", rows: 2 },
          { field: "view_config", label: "View Config", type: "textarea", rows: 4, json: true },
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

    filterEls.forEach((el) => el.addEventListener("change", loadKinds));
    shell.querySelector("[data-catalog-summary]").addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      filterEls.forEach((el) => {
        if (!button.dataset.summaryFilter) el.value = el.dataset.kindFilter === "active" ? "all" : "";
        if (el.dataset.kindFilter === button.dataset.summaryFilter) el.value = button.dataset.summaryValue;
      });
      loadKinds();
    });

    shell.querySelector(".content-catalog-tabs").addEventListener("click", (event) => {
      const button = event.target.closest("button[data-catalog-tab]");
      if (!button) return;
      shell.querySelectorAll("[data-catalog-tab]").forEach((btn) => btn.classList.toggle("active", btn === button));
      shell.querySelectorAll("[data-catalog-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.catalogPanel !== button.dataset.catalogTab;
      });
      const editor = editors[button.dataset.catalogTab];
      if (editor && !editor.rows.length) editor.load();
    });

    loadKinds();
  }

  window.AdminTableEditor = AdminTableEditor;
  document.addEventListener("DOMContentLoaded", initCatalog);
})();
