// Generation Page (config-driven) UI behavior
// - Typing animation for header
// - Single-open accordions
// - Card selection -> hidden inputs
// - Source mode switching (Text/URL/File) + optional client-side extraction

(function () {
  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function initTyping() {
    const el = qs("#gen-typed-word");
    if (!el) return;

    const words = ["Perfect", "Viral", "Engaging", "Trending", "Converting", "Authentic"];

    let wordIdx = 0;
    let charIdx = 0;
    let deleting = false;

    // Show the initial "Per" momentarily to match the spec's "Per_" feel.
    el.textContent = "Per";

    const typeDelay = 85;
    const deleteDelay = 55;
    const pauseDelay = 850;
    const firstPause = 550;

    function tick() {
      const target = words[wordIdx];

      if (!deleting) {
        charIdx = Math.min(target.length, charIdx + 1);
        el.textContent = target.slice(0, charIdx);
        if (charIdx >= target.length) {
          deleting = true;
          window.setTimeout(tick, pauseDelay);
          return;
        }
        window.setTimeout(tick, typeDelay);
        return;
      }

      // deleting
      charIdx = Math.max(0, charIdx - 1);
      el.textContent = target.slice(0, charIdx);
      if (charIdx <= 0) {
        deleting = false;
        wordIdx = (wordIdx + 1) % words.length;
        window.setTimeout(tick, 250);
        return;
      }
      window.setTimeout(tick, deleteDelay);
    }

    window.setTimeout(tick, firstPause);
  }

  function initAccordions() {
    const root = qs("[data-accordion-root]");
    if (!root) return;

    function closeItem(item) {
      const btn = qs("[data-accordion-button]", item);
      const panel = qs("[data-accordion-panel]", item);
      if (btn) btn.setAttribute("aria-expanded", "false");
      if (panel) panel.classList.add("hidden");
      item.classList.remove("is-open");
      if (btn) btn.classList.remove("is-active");
    }

    function openItem(item) {
      const btn = qs("[data-accordion-button]", item);
      const panel = qs("[data-accordion-panel]", item);
      // single-open: close all others
      qsa("[data-accordion-item]", root).forEach((it) => {
        if (it !== item) closeItem(it);
      });
      if (btn) btn.setAttribute("aria-expanded", "true");
      if (panel) panel.classList.remove("hidden");
      item.classList.add("is-open");
      if (btn) btn.classList.add("is-active");
    }

    root.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-accordion-button]");
      if (!btn) return;
      const item = btn.closest("[data-accordion-item]");
      if (!item) return;

      const expanded = btn.getAttribute("aria-expanded") === "true";
      if (expanded) closeItem(item);
      else openItem(item);
    });

    // Open the first accordion by default for discoverability
    const first = qs("[data-accordion-item]", root);
    if (first) openItem(first);
  }

  function initCards() {
    const form = qs("#gen-form");
    if (!form) return;

    // If any card image is missing, gracefully fall back to a stock placeholder with logo in top third.
    const fallbackLogo = (qs("#gen-fallback-logo") && qs("#gen-fallback-logo").value) || "";
    qsa(".gen-card__img", form).forEach((img) => {
      img.addEventListener(
        "error",
        () => {
          const card = img.closest(".gen-card");
          if (card) card.classList.add("is-img-missing");
          if (fallbackLogo) {
            img.src = fallbackLogo;
            img.alt = "LinkerHero";
          } else {
            // last resort: hide broken image
            img.style.display = "none";
          }
        },
        { once: true }
      );
    });

    function setHidden(category, optionId) {
      const field = qs(`#field-${category}`);
      if (field) field.value = optionId;
    }

    function setSelectedCard(category, optionId) {
      qsa(`.gen-card[data-category="${category}"]`).forEach((btn) => {
        const isSel = btn.getAttribute("data-option") === optionId;
        btn.classList.toggle("is-selected", isSel);
        btn.setAttribute("aria-pressed", isSel ? "true" : "false");
      });
    }

    form.addEventListener("click", (e) => {
      const card = e.target.closest(".gen-card");
      if (!card) return;
      const category = card.getAttribute("data-category");
      const optionId = card.getAttribute("data-option");
      if (!category || !optionId) return;

      setHidden(category, optionId);
      setSelectedCard(category, optionId);
    });

    // Initialize default selection (Auto) visually for each category
    qsa(".gen-card[data-option='auto']").forEach((card) => {
      const category = card.getAttribute("data-category");
      if (!category) return;
      setSelectedCard(category, "auto");
    });
  }

  function initFooterSettings() {
    const emojiHidden = qs("#field-emoji");
    const languageHidden = qs("#field-language");
    const languageSelect = qs("#language_select");

    // Emoji toggle
    qsa('[data-toggle="emoji"] .gen-toggle__btn').forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-value") || "no";
        if (emojiHidden) emojiHidden.value = val;
        qsa('[data-toggle="emoji"] .gen-toggle__btn').forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", active ? "true" : "false");
        });
      });
    });

    // Language dropdown -> hidden field (so backend reads consistent name)
    if (languageSelect) {
      const update = () => {
        const v = languageSelect.value || "English";
        if (languageHidden) languageHidden.value = v;
      };
      languageSelect.addEventListener("change", update);
      update();
    }
  }

  function initSourceMode() {
    const form = qs("#gen-form");
    if (!form) return;

    const blockUrl = qs("#block-url");
    const blockText = qs("#block-text");
    const blockFile = qs("#block-file");
    const seg = qs("#source-switch");
    const sourceMode = qs("#source_mode");
    const fileInput = qs("#file_input");
    const dropzone = qs("#dropzone");
    const filePreview = qs("#file_preview");
    const textArea = qs('textarea[name="text"]', form);

    function toggle(el, show) {
      if (!el) return;
      if (show) el.classList.remove("hidden");
      else el.classList.add("hidden");
    }

    function clearSources() {
      const urlEl = qs('input[name="url"]', form);
      const textEl = qs('textarea[name="text"]', form);
      if (urlEl) urlEl.value = "";
      if (textEl) textEl.value = "";
      if (fileInput) {
        fileInput.value = "";
        if (filePreview) {
          filePreview.classList.add("hidden");
          filePreview.textContent = "";
        }
      }
    }

    function setMode(mode) {
      const prev = sourceMode ? sourceMode.value : "";
      if (sourceMode) sourceMode.value = mode;
      if (prev && prev !== mode) clearSources();

      toggle(blockUrl, mode === "url");
      toggle(blockText, mode === "text");
      toggle(blockFile, mode === "file");

      const urlEl = qs('input[name="url"]', form);
      const textEl = qs('textarea[name="text"]', form);
      if (urlEl) urlEl.disabled = mode !== "url";
      if (textEl) textEl.disabled = mode !== "text";
      if (fileInput) fileInput.disabled = mode !== "file";

      if (seg) {
        qsa(".gen-segmented__btn", seg).forEach((btn) => {
          const isActive = btn.getAttribute("data-mode") === mode;
          btn.classList.toggle("is-active", isActive);
          btn.setAttribute("aria-selected", isActive ? "true" : "false");
        });
      }
    }

    if (seg) {
      seg.addEventListener("click", (e) => {
        const btn = e.target.closest(".gen-segmented__btn");
        if (!btn) return;
        setMode(btn.getAttribute("data-mode"));
      });
    }

    // Dropzone interactions
    function openPicker() {
      if (fileInput) fileInput.click();
    }

    function onFilesSelected(files) {
      if (!files || !files.length || !filePreview) return;
      const f = files[0];
      const max = 50 * 1024 * 1024;
      if (f.size > max) {
        alert("File is larger than 50 MB.");
        if (fileInput) fileInput.value = "";
        return;
      }
      filePreview.textContent =
        "Selected: " +
        f.name +
        " (" +
        Math.round((f.size / 1024 / 1024) * 10) / 10 +
        " MB)";
      filePreview.classList.remove("hidden");
    }

    if (dropzone) {
      dropzone.addEventListener("click", () => {
        setMode("file");
        openPicker();
      });
      dropzone.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setMode("file");
          openPicker();
        }
      });
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      });
      dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
      });
      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
          setMode("file");
          try {
            const dt = new DataTransfer();
            dt.items.add(e.dataTransfer.files[0]);
            if (fileInput) fileInput.files = dt.files;
          } catch (_) {
            // ignore assignment restrictions
          }
          onFilesSelected(e.dataTransfer.files);
        }
      });
    }

    // Optional client-side extraction to Text (kept from prior UX)
    async function extractFileToText(file) {
      const name = ((file && file.name) || "").toLowerCase();
      const ext = name.split(".").pop();
      const buf = await file.arrayBuffer();

      try {
        if (ext === "txt") {
          return new TextDecoder("utf-8", { fatal: false }).decode(new Uint8Array(buf));
        }
        if (ext === "pdf" && window.pdfjsLib) {
          const pdf = await window.pdfjsLib.getDocument({ data: buf }).promise;
          let out = "";
          const maxPages = Math.min(pdf.numPages, 50);
          for (let p = 1; p <= maxPages; p++) {
            const page = await pdf.getPage(p);
            const tc = await page.getTextContent();
            const line = tc.items.map((it) => it.str).join(" ");
            out += line + "\n";
            if (out.length > 9000) break;
          }
          return out;
        }
        if (ext === "docx" && window.mammoth) {
          const res = await window.mammoth.extractRawText({ arrayBuffer: buf });
          return (res && res.value) || "";
        }
      } catch (_) {
        return "";
      }
      return "";
    }

    if (window.pdfjsLib && window.pdfjsLib.GlobalWorkerOptions) {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc =
        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.5.136/pdf.worker.min.js";
    }

    if (fileInput) {
      fileInput.addEventListener("change", async (e) => {
        try {
          setMode("file");
          onFilesSelected(e.target.files);
          const f = e.target.files && e.target.files[0];
          if (!f) return;

          const text = ((await extractFileToText(f)) || "").trim();
          if (text.length && textArea) {
            setMode("text");
            textArea.value = text.slice(0, 8000);
            fileInput.value = "";
            if (filePreview) {
              filePreview.textContent = "Extracted " + text.length + " characters to Text.";
              filePreview.classList.remove("hidden");
            }
          }
        } catch (_) {
          // allow normal submit
        }
      });
    }

    // Initial mode
    setMode((sourceMode && sourceMode.value) || "text");
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTyping();
    initAccordions();
    initCards();
    initFooterSettings();
    initSourceMode();
  });
})();

