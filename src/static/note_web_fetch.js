(function () {
  "use strict";
  const form = document.querySelector("#web-clip-fetch");
  const status = document.querySelector("#web-fetch-status");
  const progress = document.querySelector("#web-fetch-progress");
  if (!form || !status) return;
  let busy = false;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    const button = form.querySelector("button[type=submit]");
    const fields = Array.from(form.querySelectorAll("input, select"));
    const controller = new AbortController();
    const deadline = window.setTimeout(() => controller.abort(), 180000);
    let ticker;
    try {
      const methodField = form.elements.namedItem("method");
      const method = Number(methodField.value);
      const methodName = methodField.selectedOptions[0].textContent;
      const payload = { url: form.elements.namedItem("url").value, method };
      button.disabled = true;
      button.textContent = "Fetching…";
      fields.forEach((field) => { field.disabled = true; });
      form.setAttribute("aria-busy", "true");
      if (progress) progress.hidden = false;
      const started = Date.now();
      const updateStatus = () => {
        const elapsed = Math.floor((Date.now() - started) / 1000);
        status.textContent = method === 0
          ? `Fetching using Auto — ${elapsed}s elapsed. Reader, Rendered Page and Web Archive will be tried as needed.`
          : `Fetching using ${methodName} — ${elapsed}s elapsed. Please wait for the preview.`;
      };
      updateStatus();
      ticker = window.setInterval(updateStatus, 1000);
      const response = await fetch(form.action, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload), signal: controller.signal,
      });
      if (!(response.headers.get("content-type") || "").includes("application/json")) {
        throw new Error(response.redirected
          ? "Your session may have expired. Reload this page and sign in again."
          : `The server returned an unexpected response (HTTP ${response.status}). Reload the page and try again.`);
      }
      const data = await response.json();
      if (!response.ok || data.success === false) {
        throw new Error([data.error, ...(data.warnings || [])].filter(Boolean).join(" ") || "Could not fetch webpage.");
      }
      if (!data.open_url) throw new Error("The server did not return a preview. Reload the page and try again.");
      status.textContent = "Webpage fetched. Opening preview…";
      window.location.href = data.open_url;
    } catch (error) {
      status.textContent = error.name === "AbortError"
        ? "No response after three minutes. The server may still be finishing the capture; no note has been saved."
        : error.message || "Could not fetch webpage.";
    } finally {
      window.clearTimeout(deadline);
      window.clearInterval(ticker);
      busy = false;
      button.disabled = false;
      button.textContent = "Fetch Page";
      fields.forEach((field) => { field.disabled = false; });
      form.removeAttribute("aria-busy");
      if (progress) progress.hidden = true;
    }
  });
})();
