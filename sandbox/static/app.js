"use strict";

// Monaco is loaded from a CDN; without network the editor falls back to a textarea.
const MONACO_BASE = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min";
const RECENT_KEY = "search-intent-sandbox:recent";

const $ = (sel) => document.querySelector(sel);

const state = {
  collections: [],   // details from the API: summary + validation
  open: null,        // collection expanded in the sidebar
  file: null,        // { collection, stem, present }
  savedText: "",
  editor: null,
};

// --- API -------------------------------------------------------------------
async function api(method, path, body) {
  const resp = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    let detail = data.detail ?? resp.statusText;
    if (Array.isArray(detail)) detail = detail.map((d) => `${d.loc?.slice(1).join(".")}: ${d.msg}`).join("; ");
    throw new Error(detail);
  }
  return data;
}

function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = "toast" + (isError ? " error" : "");
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.hidden = true), isError ? 6000 : 2500);
}

// --- Editor ----------------------------------------------------------------
function textareaEditor(container) {
  const ta = document.createElement("textarea");
  ta.className = "fallback";
  ta.spellcheck = false;
  container.replaceChildren(ta);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      ta.setRangeText("  ", ta.selectionStart, ta.selectionEnd, "end");
      ta.dispatchEvent(new Event("input"));
    }
  });
  return {
    get: () => ta.value,
    set: (text) => { ta.value = text; },
    focus: () => ta.focus(),
    onChange: (fn) => ta.addEventListener("input", fn),
  };
}

function loadMonaco(container) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("timeout")), 8000);
    window.MonacoEnvironment = {
      getWorkerUrl: () =>
        "data:text/javascript;charset=utf-8," +
        encodeURIComponent(
          `self.MonacoEnvironment={baseUrl:'${MONACO_BASE}/'};importScripts('${MONACO_BASE}/vs/base/worker/workerMain.js');`
        ),
    };
    const script = document.createElement("script");
    script.src = `${MONACO_BASE}/vs/loader.min.js`;
    script.onerror = () => { clearTimeout(timer); reject(new Error("load failed")); };
    script.onload = () => {
      window.require.config({ paths: { vs: `${MONACO_BASE}/vs` } });
      window.require(["vs/editor/editor.main"], () => {
        clearTimeout(timer);
        const dark = matchMedia("(prefers-color-scheme: dark)");
        container.replaceChildren();
        const ed = monaco.editor.create(container, {
          language: "json",
          automaticLayout: true,
          minimap: { enabled: false },
          tabSize: 2,
          fontSize: 13,
          scrollBeyondLastLine: false,
          theme: dark.matches ? "vs-dark" : "vs",
        });
        dark.addEventListener("change", (e) => monaco.editor.setTheme(e.matches ? "vs-dark" : "vs"));
        ed.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => save());
        resolve({
          get: () => ed.getValue(),
          set: (text) => ed.setValue(text),
          focus: () => ed.focus(),
          onChange: (fn) => ed.onDidChangeModelContent(fn),
        });
      }, reject);
    };
    document.head.appendChild(script);
  });
}

async function initEditor() {
  const container = $("#editor");
  try {
    state.editor = await loadMonaco(container);
  } catch {
    state.editor = textareaEditor(container);
  }
  state.editor.onChange(updateDirty);
}

const isDirty = () => state.file !== null && state.editor.get() !== state.savedText;

function updateDirty() {
  const dirty = isDirty();
  $("#dirty").hidden = !dirty;
  $("#save").disabled = !state.file || (!dirty && state.file.present);
  $("#revert").disabled = !dirty;
}

function confirmDiscard() {
  return !isDirty() || confirm("Discard unsaved changes to this file?");
}

// --- Collections sidebar ---------------------------------------------------
const collection = (name) => state.collections.find((c) => c.name === name);

function statusOf(details) {
  const v = details.validation;
  if (!v.ok) return { cls: "error", title: v.error };
  if (v.warnings.length) return { cls: "warn", title: `${v.warnings.length} warning(s)` };
  return { cls: "", title: "Valid" };
}

function renderCollections() {
  const list = $("#collections");
  list.replaceChildren();
  for (const c of state.collections) {
    const li = document.createElement("li");
    li.className = "collection" + (state.open === c.name ? " open" : "");

    const row = document.createElement("div");
    row.className = "row";
    const status = statusOf(c);
    const dot = document.createElement("span");
    dot.className = "dot " + status.cls;
    dot.title = status.title;
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = c.name;
    name.title = c.display_name;
    row.append(dot, name);
    if (!c.protected) {
      const del = document.createElement("button");
      del.className = "icon-btn";
      del.title = `Delete ${c.name}`;
      del.textContent = "✕";
      del.addEventListener("click", (e) => { e.stopPropagation(); deleteCollection(c.name); });
      row.append(del);
    }
    row.addEventListener("click", () => {
      state.open = state.open === c.name ? null : c.name;
      renderCollections();
      if (state.open) setRunCollection(state.open);
    });
    li.append(row);

    if (state.open === c.name) {
      const files = document.createElement("ul");
      files.className = "files";
      for (const f of c.files) {
        const item = document.createElement("li");
        const selected = state.file?.collection === c.name && state.file?.stem === f.stem;
        item.className = (f.present ? "" : "absent") + (selected ? " selected" : "");
        item.title = plain(f.doc.summary);

        const line = document.createElement("div");
        line.className = "line";
        const fname = document.createElement("span");
        fname.className = "fname";
        fname.textContent = `${f.stem}.json`;
        line.append(fname);
        const tagText = !f.present ? "+ add" : f.required ? "required" : "";
        if (tagText) {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = tagText;
          line.append(tag);
        }
        const purpose = document.createElement("div");
        purpose.className = "purpose";
        purpose.textContent = f.doc.purpose;
        item.append(line, purpose);
        item.addEventListener("click", () => openFile(c.name, f.stem));
        files.append(item);
      }
      li.append(files);
    }
    list.append(li);
  }
  renderRunCollections();
}

async function loadCollections() {
  state.collections = await api("GET", "/api/collections");
  renderCollections();
}

function replaceDetails(details) {
  const i = state.collections.findIndex((c) => c.name === details.name);
  if (i >= 0) state.collections[i] = details;
  else state.collections.push(details);
  state.collections.sort((a, b) => a.name.localeCompare(b.name));
  renderCollections();
  if (state.file?.collection === details.name) renderValidation(details.validation);
}

async function deleteCollection(name) {
  if (!confirm(`Delete the collection "${name}" and all of its files?\n\nThis removes config/${name}/ from disk.`)) return;
  try {
    await api("DELETE", `/api/collections/${name}`);
    if (state.file?.collection === name) closeFile();
    if (state.open === name) state.open = null;
    await loadCollections();
    toast(`Deleted ${name}`);
  } catch (err) {
    toast(err.message, true);
  }
}

// --- About this file -------------------------------------------------------
const ABOUT_OPEN_KEY = "search-intent-sandbox:about-open";

// Doc text marks code with `backticks`.
const plain = (text) => text.replace(/`/g, "");
const rich = (text) => escapeHtml(text).replace(/`([^`]+)`/g, "<code>$1</code>");

function renderAbout(stem, doc, required) {
  const about = $("#about");
  $("#about-title").innerHTML =
    `About <strong>${stem}.json</strong>: ${escapeHtml(doc.purpose)}` +
    ` <span class="muted">(${required ? "required" : "optional"})</span>`;
  const keys = doc.keys.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${rich(v)}</dd>`).join("");
  const notes = doc.notes.map((n) => `<li>${rich(n)}</li>`).join("");
  $("#about-body").innerHTML =
    `<p>${rich(doc.summary)}</p>` +
    (keys ? `<dl>${keys}</dl>` : "") +
    (notes ? `<ul>${notes}</ul>` : "");
  about.hidden = false;
}

function wireAbout() {
  const about = $("#about");
  try { about.open = localStorage.getItem(ABOUT_OPEN_KEY) !== "0"; } catch { about.open = true; }
  about.addEventListener("toggle", () => {
    try { localStorage.setItem(ABOUT_OPEN_KEY, about.open ? "1" : "0"); } catch { /* storage unavailable */ }
  });
}

// --- Files -----------------------------------------------------------------
async function openFile(name, stem) {
  if (!state.editor || !confirmDiscard()) return;
  const f = collection(name).files.find((x) => x.stem === stem);
  try {
    const text = f.present
      ? (await api("GET", `/api/collections/${name}/files/${stem}`)).text
      : '{\n  "version": "1.0.0"\n}\n';
    state.file = { collection: name, stem, present: f.present, required: f.required };
    // An absent file starts as a template (Revert restores it); Save creates the file.
    state.savedText = text;
    state.editor.set(text);
    $("#editor-title").textContent = `${name} / ${stem}.json` + (f.present ? "" : " (new)");
    $("#format").disabled = false;
    $("#remove-file").hidden = !f.present || f.required;
    renderAbout(stem, f.doc, f.required);
    history.replaceState(null, "", `#${name}/${stem}`);
    renderCollections();
    renderValidation(collection(name).validation);
    updateDirty();
    state.editor.focus();
  } catch (err) {
    toast(err.message, true);
  }
}

function closeFile() {
  state.file = null;
  state.savedText = "";
  state.editor.set("");
  $("#editor-title").textContent = "Select a file";
  $("#format").disabled = true;
  $("#remove-file").hidden = true;
  $("#validation").hidden = true;
  $("#about").hidden = true;
  history.replaceState(null, "", location.pathname);
  updateDirty();
}

async function save() {
  if (!state.file) return;
  const { collection: name, stem } = state.file;
  const text = state.editor.get();
  try {
    const details = await api("PUT", `/api/collections/${name}/files/${stem}`, { text });
    state.savedText = text;
    state.file.present = true;
    $("#editor-title").textContent = `${name} / ${stem}.json`;
    $("#remove-file").hidden = state.file.required;
    replaceDetails(details);
    updateDirty();
    toast(details.validation.ok ? `Saved ${stem}.json` : `Saved, but the collection doesn't load`, !details.validation.ok);
  } catch (err) {
    toast(err.message, true);
  }
}

async function removeFile() {
  const { collection: name, stem } = state.file;
  if (!confirm(`Remove ${name}/${stem}.json from disk?`)) return;
  try {
    const details = await api("DELETE", `/api/collections/${name}/files/${stem}`);
    state.savedText = "";
    replaceDetails(details);
    closeFile();
    toast(`Removed ${stem}.json`);
  } catch (err) {
    toast(err.message, true);
  }
}

function formatJson() {
  try {
    state.editor.set(JSON.stringify(JSON.parse(state.editor.get()), null, 2) + "\n");
  } catch (err) {
    toast(`Can't format: ${err.message}`, true);
  }
}

function renderValidation(v) {
  const el = $("#validation");
  el.hidden = false;
  el.replaceChildren();
  const head = document.createElement("div");
  if (!v.ok) {
    head.className = "err";
    head.textContent = `Collection doesn't load: ${v.error}`;
  } else {
    head.className = "ok";
    head.textContent = v.warnings.length ? "Collection loads, with warnings:" : "Collection loads with no warnings.";
  }
  el.append(head);
  if (v.ok && v.warnings.length) {
    const ul = document.createElement("ul");
    for (const w of v.warnings) {
      const li = document.createElement("li");
      li.textContent = w;
      ul.append(li);
    }
    el.append(ul);
  }
}

// --- New collection dialog -------------------------------------------------
function openNewDialog() {
  const from = $("#new-from");
  from.replaceChildren(new Option("Blank (minimal starter files)", ""));
  for (const c of state.collections) from.append(new Option(`Copy of ${c.name}`, c.name));
  if (state.open) from.value = state.open;
  $("#new-name").value = "";
  $("#new-error").hidden = true;
  $("#new-dialog").showModal();
  $("#new-name").focus();
}

async function submitNewCollection(e) {
  if (e.submitter?.value !== "create") return;
  e.preventDefault();
  const name = $("#new-name").value.trim();
  try {
    const details = await api("POST", "/api/collections", {
      name,
      copy_from: $("#new-from").value || null,
    });
    $("#new-dialog").close();
    state.open = name;
    replaceDetails(details);
    setRunCollection(name);
    openFile(name, "project");
    toast(`Created ${name}`);
  } catch (err) {
    const el = $("#new-error");
    el.textContent = err.message;
    el.hidden = false;
  }
}

// --- Tester ----------------------------------------------------------------
function renderRunCollections() {
  const sel = $("#run-collection");
  const current = sel.value;
  sel.replaceChildren(...state.collections.map((c) => new Option(c.name, c.name)));
  if (collection(current)) sel.value = current;
}

function setRunCollection(name) {
  $("#run-collection").value = name;
}

function readRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; } catch { return []; }
}

function pushRecent(query) {
  const list = [query, ...readRecent().filter((q) => q !== query)].slice(0, 8);
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch { /* storage unavailable */ }
  renderRecent();
}

function renderRecent() {
  const el = $("#recent");
  el.replaceChildren(...readRecent().map((q) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = q;
    chip.title = q;
    chip.addEventListener("click", () => { $("#query").value = q; $("#query").focus(); });
    return chip;
  }));
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function highlight(value) {
  const json = escapeHtml(JSON.stringify(value, null, 2));
  return json.replace(
    /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (m) => {
      let cls = "n";
      if (m.startsWith('"')) cls = m.endsWith(":") ? "k" : "s";
      else if (/true|false|null/.test(m)) cls = "l";
      return `<span class="${cls}">${m}</span>`;
    }
  );
}

const result = { data: null, view: "output" };

function renderResult() {
  const out = $("#output");
  out.classList.remove("error");
  const value = result.view === "stages" ? result.data.stages : result.data.output;
  out.innerHTML = highlight(value);
  $("#copy").disabled = false;
}

function setView(view) {
  result.view = view;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  if (result.data) renderResult();
}

const num = (id) => {
  const v = $(id).value.trim();
  return v === "" ? null : Number(v);
};

async function run(e) {
  e?.preventDefault();
  const name = $("#run-collection").value;
  const query = $("#query").value.trim();
  if (!name || !query) return;

  const body = {
    mode: document.querySelector('input[name="mode"]:checked').value,
    query,
    locale: $("#locale").value.trim() || "en",
    limit: num("#limit"),
    offset: num("#offset"),
  };
  const lat = num("#lat"), lng = num("#lng");
  if (lat !== null && lng !== null) {
    body.user_location = { lat, lng, source: "sandbox" };
    const radius = num("#radius");
    if (radius !== null) body.user_location.radius_km = radius;
  }

  const button = $("#run");
  button.disabled = true;
  button.textContent = "Running…";
  $("#elapsed").textContent = "";
  try {
    result.data = await api("POST", `/api/collections/${name}/run`, body);
    $("#stages-tab").hidden = !result.data.stages;
    if (!result.data.stages) result.view = "output";
    setView(result.view);
    $("#elapsed").textContent = `${result.data.elapsed_ms} ms`;
    pushRecent(query);
  } catch (err) {
    result.data = null;
    const out = $("#output");
    out.classList.add("error");
    out.textContent = err.message;
    $("#copy").disabled = true;
  } finally {
    button.disabled = false;
    button.textContent = "Run";
  }
}

async function copyResult() {
  if (!result.data) return;
  const value = result.view === "stages" ? result.data.stages : result.data.output;
  try {
    await navigator.clipboard.writeText(JSON.stringify(value, null, 2));
    toast("Copied JSON");
  } catch {
    toast("Clipboard unavailable", true);
  }
}

// --- Wiring ----------------------------------------------------------------
function wire() {
  wireAbout();
  $("#new-collection").addEventListener("click", openNewDialog);
  $("#new-form").addEventListener("submit", submitNewCollection);
  $("#save").addEventListener("click", save);
  $("#revert").addEventListener("click", () => { state.editor.set(state.savedText); });
  $("#format").addEventListener("click", formatJson);
  $("#remove-file").addEventListener("click", removeFile);
  $("#run-form").addEventListener("submit", run);
  $("#copy").addEventListener("click", copyResult);
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => setView(t.dataset.view)));
  document.querySelectorAll('input[name="mode"]').forEach((r) =>
    r.addEventListener("change", () => { $("#search-note").hidden = r.value !== "search" || !r.checked; })
  );

  document.addEventListener("keydown", (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
    if (mod && e.key === "Enter") { e.preventDefault(); run(); }
  });
  window.addEventListener("beforeunload", (e) => { if (isDirty()) e.preventDefault(); });
}

async function main() {
  wire();
  renderRecent();
  try {
    await loadCollections();
  } catch (err) {
    toast(`Couldn't load collections: ${err.message}`, true);
    return;
  }
  await initEditor();

  const [name, stem] = decodeURIComponent(location.hash.slice(1)).split("/");
  const target = collection(name) ? name : state.collections[0]?.name;
  if (!target) return;
  state.open = target;
  renderCollections();
  setRunCollection(target);
  if (stem && collection(target).files.some((f) => f.stem === stem)) openFile(target, stem);
}

main();
