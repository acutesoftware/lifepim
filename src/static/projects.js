(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function fetchJson(url, options) {
    return fetch(url, options).then((res) => {
      if (!res.ok) {
        return res.json().catch(() => ({})).then((data) => {
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

  function toast(message) {
    const container = document.getElementById("link-toast-container");
    if (!container) {
      window.alert(message);
      return;
    }
    const item = document.createElement("div");
    item.className = "link-toast";
    item.textContent = message;
    container.appendChild(item);
    setTimeout(() => {
      item.classList.add("fade");
      setTimeout(() => item.remove(), 300);
    }, 3000);
  }

  function initDropZone(root) {
    const dropZone = qs("[data-project-drop-zone]", root);
    if (!dropZone) {
      return;
    }
    const addUrl = root.dataset.addUrl;
    dropZone.addEventListener("dragover", (evt) => {
      evt.preventDefault();
      dropZone.classList.add("drop-target");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drop-target"));
    dropZone.addEventListener("drop", (evt) => {
      evt.preventDefault();
      dropZone.classList.remove("drop-target");
      const items = readDragPayload(evt);
      if (!items.length) {
        toast("No LifePIM records were found in that drop.");
        return;
      }
      postJson(addUrl, { items: items })
        .then((data) => {
          const results = data.results || [];
          const created = results.filter((item) => item.created).length;
          const skipped = results.length - created;
          toast(skipped ? `Added ${created}; ${skipped} already present or failed.` : `Added ${created} item(s).`);
          window.location.reload();
        })
        .catch(() => toast("Could not add items to the Project."));
    });
  }

  function initSearch(root) {
    const input = qs(".project-search-input", root);
    const types = qs(".project-search-types", root);
    const results = qs(".project-search-results", root);
    if (!input || !results) {
      return;
    }
    let timer = null;

    function render(items) {
      results.innerHTML = "";
      if (!items.length) {
        results.textContent = input.value.trim() ? "No matching items." : "";
        return;
      }
      items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "project-search-result";
        const meta = document.createElement("div");
        meta.className = "project-search-result-meta";
        const title = document.createElement("strong");
        title.textContent = item.title || `${item.type} ${item.id}`;
        const subtitle = document.createElement("span");
        subtitle.textContent = [item.type, item.subtitle].filter(Boolean).join(" - ");
        meta.appendChild(title);
        meta.appendChild(subtitle);
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = "Add";
        button.addEventListener("click", () => addItem(item));
        row.appendChild(meta);
        row.appendChild(button);
        results.appendChild(row);
      });
    }

    function search() {
      const query = input.value.trim();
      if (query.length < 2) {
        render([]);
        return;
      }
      const params = new URLSearchParams({ q: query, limit: "30" });
      if (types && types.value) {
        params.set("types", types.value);
      }
      fetchJson(`/projects/api/search?${params.toString()}`)
        .then((data) => render(data.results || []))
        .catch(() => render([]));
    }

    function addItem(item) {
      postJson(root.dataset.addUrl, {
        item_type: item.type,
        item_id: item.id,
        item_title: item.title || "",
      })
        .then(() => {
          toast("Item added to Project.");
          window.location.reload();
        })
        .catch(() => toast("Could not add item to the Project."));
    }

    input.addEventListener("input", () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(search, 250);
    });
    if (types) {
      types.addEventListener("change", search);
    }
  }

  function init() {
    qsa(".project-contents").forEach((root) => {
      initDropZone(root);
      initSearch(root);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
