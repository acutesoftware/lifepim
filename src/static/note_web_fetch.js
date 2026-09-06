(function () {
  "use strict";
  const form = document.querySelector("#web-clip-fetch");
  const status = document.querySelector("#web-fetch-status");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    form.setAttribute("aria-busy", "true");
    status.textContent = "Fetching webpage… Auto may try Reader, Rendered Page, then Web Archive.";
    try {
      const response = await fetch(form.action, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: form.elements.url.value, method: Number(form.elements.method.value) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error([data.error, ...(data.warnings || [])].filter(Boolean).join(" "));
      window.location.href = data.open_url;
    } catch (error) {
      status.textContent = error.message || "Could not fetch webpage.";
      button.disabled = false;
      form.removeAttribute("aria-busy");
    }
  });
})();
