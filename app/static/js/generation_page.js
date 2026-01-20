// Generation Page (config-driven) UI behavior
// - Typing animation for header
// - Single-open accordions
// - Card selection -> hidden inputs
// - Source mode switching (Text/URL/File) + optional client-side extraction

(function () {
  const STORAGE_KEY = "linkerhero_generation_page_v1";

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function safeJsonParse(s) {
    try {
      return JSON.parse(s);
    } catch (_) {
      return null;
    }
  }

  function loadState() {
    const raw = window.localStorage ? window.localStorage.getItem(STORAGE_KEY) : null;
    return (raw && safeJsonParse(raw)) || {};
  }

  function saveState(patch) {
    try {
      const prev = loadState();
      const next = { ...prev, ...patch, _ts: Date.now() };
      window.localStorage && window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch (_) {
      // ignore storage failures
    }
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

    async function preloadPanel(panel) {
      // Load visuals only once per panel per page session
      if (panel.dataset.preloaded === "1") return;
      panel.dataset.preloaded = "1";

      const imgs = Array.from(panel.querySelectorAll("img.gen-card__img"));
      if (!imgs.length) return;

      const loadingEl = panel.querySelector("[data-panel-loading]");

      // Only eagerly decode the first set (what user sees first). Keep it fast.
      const firstBatch = imgs.slice(0, 12);
      firstBatch.forEach((img) => {
        try {
          img.loading = "eager";
          img.fetchPriority = "high";
        } catch (_) {}
      });

      // Show a lightweight spinner overlay on the panel until decoded.
      const minShowMs = 160;
      const start = Date.now();
      if (loadingEl) loadingEl.classList.remove("hidden");

      const decodePromises = firstBatch.map((img) => {
        if (img.complete && img.naturalWidth > 0) return Promise.resolve();
        if (typeof img.decode === "function") return img.decode().catch(() => {});
        return new Promise((res) => {
          img.addEventListener("load", () => res(), { once: true });
          img.addEventListener("error", () => res(), { once: true });
        });
      });

      await Promise.race([
        Promise.allSettled(decodePromises),
        new Promise((res) => setTimeout(res, 1200)),
      ]);

      const elapsed = Date.now() - start;
      if (elapsed < minShowMs) {
        await new Promise((res) => setTimeout(res, minShowMs - elapsed));
      }
      if (loadingEl) loadingEl.classList.add("hidden");
    }

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

      if (panel) {
        preloadPanel(panel);
      }
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

  function initCarousels() {
    // Carousel removed; keep function for backward compatibility (no-op)
  }

  function initCards() {
    const form = qs("#gen-form");
    if (!form) return;

    function optionLabelFromDom(category, optionId) {
      if (!category || !optionId) return optionId || "";
      if (optionId === "auto") return "Auto";
      const card = qs(`.gen-card[data-category="${category}"][data-option="${optionId}"]`, form);
      const nameEl = card && qs(".gen-card__name", card);
      const label = (nameEl && nameEl.textContent && nameEl.textContent.trim()) || "";
      return label || optionId;
    }

    function setAccordionValue(category, optionId) {
      const el = qs(`[data-accordion-value="${category}"]`, form);
      if (!el) return;
      const label = optionLabelFromDom(category, optionId);
      el.textContent = `Option: ${label}`;
    }

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
      saveState({ [`setting_${category}`]: optionId });
      setAccordionValue(category, optionId);
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
      setAccordionValue(category, "auto");
    });

    // Restore selection state
    const st = loadState();
    ["hook_type", "persona", "tone", "goal", "length", "ending"].forEach((cat) => {
      const v = st[`setting_${cat}`];
      if (typeof v === "string" && v) {
        const hidden = qs(`#field-${cat}`);
        if (hidden) hidden.value = v;
        setSelectedCard(cat, v);
        setAccordionValue(cat, v);
      }
    });
  }

  function initFooterSettings() {
    const emojiHidden = qs("#field-emoji");
    const languageHidden = qs("#field-language");
    const languageSelect = qs("#language_select");
    const modelHidden = qs("#field-model");

    // Emoji toggle
    qsa('[data-toggle="emoji"] .gen-toggle__btn').forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-value") || "no";
        if (emojiHidden) emojiHidden.value = val;
        saveState({ emoji: val });
        qsa('[data-toggle="emoji"] .gen-toggle__btn').forEach((b) => {
          const active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-pressed", active ? "true" : "false");
        });
      });
    });

    // Model toggle
    qsa('[data-toggle="model"] .gen-toggle__btn').forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = (btn.getAttribute("data-value") || "claude-sonnet-4-5").toLowerCase();
        if (modelHidden) modelHidden.value = val;
        saveState({ model: val });
        qsa('[data-toggle="model"] .gen-toggle__btn').forEach((b) => {
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
        saveState({ language: v });
      };
      languageSelect.addEventListener("change", update);
      update();
    }

    // Restore footer settings
    const st = loadState();
    if (emojiHidden && typeof st.emoji === "string") {
      emojiHidden.value = st.emoji;
      qsa('[data-toggle="emoji"] .gen-toggle__btn').forEach((b) => {
        const active = (b.getAttribute("data-value") || "no") === st.emoji;
        b.classList.toggle("is-active", active);
        b.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }
    if (modelHidden && typeof st.model === "string") {
      modelHidden.value = st.model;
      qsa('[data-toggle="model"] .gen-toggle__btn').forEach((b) => {
        const active = (b.getAttribute("data-value") || "").toLowerCase() === st.model.toLowerCase();
        b.classList.toggle("is-active", active);
        b.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }
    if (languageSelect && typeof st.language === "string") {
      languageSelect.value = st.language;
      if (languageHidden) languageHidden.value = st.language;
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

    let suppressClear = false;

    function clearSources() {
      // Keep text persistent; only clear URL/file when switching modes.
      if (suppressClear) return;
      const urlEl = qs('input[name="url"]', form);
      if (urlEl) urlEl.value = "";
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
      toggle(blockFile, mode === "file");

      const urlEl = qs('input[name="url"]', form);
      const textEl = qs('textarea[name="text"]', form);
      if (urlEl) urlEl.disabled = mode !== "url";
      if (textEl) textEl.disabled = false;
      if (fileInput) fileInput.disabled = mode !== "file";

      if (seg) {
        qsa(".gen-segmented__btn", seg).forEach((btn) => {
          const isActive = btn.getAttribute("data-mode") === mode;
          btn.classList.toggle("is-active", isActive);
          btn.setAttribute("aria-selected", isActive ? "true" : "false");
        });
      }

      saveState({ source_mode: mode });

      // Text box is optional ONLY when URL/File is selected.
      // In Text mode, it's the primary input.
      const textLabel = qs('label[for="text_input"]', form);
      if (textLabel) {
        textLabel.textContent = mode === "text" ? "Write/Paste Text" : "Write/Paste Text (optional)";
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
    const st = loadState();
    const restoredMode = (typeof st.source_mode === "string" && st.source_mode) || (sourceMode && sourceMode.value) || "text";
    suppressClear = true;
    setMode(restoredMode);
    suppressClear = false;

    // Restore text/url/prompt fields (file cannot be restored by browser security)
    const urlEl = qs('input[name="url"]', form);
    const textEl = qs('textarea[name="text"]', form);
    if (urlEl && typeof st.url === "string") urlEl.value = st.url;
    if (textEl && typeof st.text === "string") textEl.value = st.text;

    // If we arrived with /generate?url=... (e.g., from Content Fuel), treat it as authoritative:
    // - force URL mode
    // - prefill URL field
    // - persist to localStorage so subsequent navigations keep it
    try {
      const qsUrl = new URLSearchParams(window.location.search || "").get("url");
      const prefillUrl = (qsUrl || (urlEl && urlEl.value) || "").trim();
      if (prefillUrl && urlEl) {
        suppressClear = true;
        setMode("url");
        urlEl.value = prefillUrl;
        saveState({ url: prefillUrl, source_mode: "url" });
        suppressClear = false;
      }
    } catch (_) {
      // ignore
    }

    // Save on input
    urlEl && urlEl.addEventListener("input", () => saveState({ url: urlEl.value || "" }));
    textEl && textEl.addEventListener("input", () => saveState({ text: textEl.value || "" }));
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTyping();
    initAccordions();
    initCarousels();
    initCards();
    initFooterSettings();
    initSourceMode();
  });
})();

