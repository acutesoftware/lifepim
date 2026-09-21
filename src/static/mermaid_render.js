(function () {
  "use strict";

  const blocks = Array.from(document.querySelectorAll("pre > code.language-mermaid"));
  if (!blocks.length) {
    return;
  }

  const showLoadError = () => {
    blocks.forEach((block) => {
      const pre = block.parentElement;
      if (pre && !pre.previousElementSibling?.classList.contains("mermaid-error")) {
        const message = document.createElement("div");
        message.className = "mermaid-error";
        message.textContent = "Diagram preview could not be loaded; Mermaid source is shown below.";
        pre.before(message);
      }
    });
  };

  import("https://cdn.jsdelivr.net/npm/mermaid@12.0.0/dist/mermaid.esm.min.mjs")
    .then(async ({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "default",
        flowchart: { htmlLabels: true, useMaxWidth: true },
      });

      for (const [index, block] of blocks.entries()) {
        const pre = block.parentElement;
        if (!pre) {
          continue;
        }
        const source = block.textContent || "";
        try {
          const result = await mermaid.render(`lifepim-mermaid-${Date.now()}-${index}`, source);
          const diagram = document.createElement("div");
          diagram.className = "mermaid-diagram";
          diagram.setAttribute("role", "img");
          diagram.setAttribute("aria-label", "Mermaid diagram");
          diagram.innerHTML = result.svg;
          pre.replaceWith(diagram);
          if (result.bindFunctions) {
            result.bindFunctions(diagram);
          }
        } catch (error) {
          const message = document.createElement("div");
          message.className = "mermaid-error";
          message.textContent = `Diagram could not be rendered: ${error?.message || "invalid Mermaid syntax"}`;
          pre.before(message);
        }
      }
    })
    .catch(showLoadError);
})();
