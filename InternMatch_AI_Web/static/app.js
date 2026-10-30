(() => {
  "use strict";

  const MAX_BYTES = 150 * 1024 * 1024;
  const ACCEPT = [".csv", ".tsv", ".txt", ".xlsx", ".xls", ".xlsm", ".json", ".xml"];

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const fmt = (n) => Number(n || 0).toLocaleString("en-IN");

  const state = {
    job: null,          // id of the stored upload on the server
    fileName: "",
    summary: null,      // totals and charts data for the current upload
    firstItems: [],     // first rows returned with the upload
    sampleItems: [],    // preview rows for the sample on the home page
    listings: null,
    evaluation: null,
    pageNo: 1,
    pages: 1,
    size: 50,
    status: "all",
  };

  // ---------- Helpers ----------
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));

  const safeUrl = (url) => (/^https?:\/\//i.test(String(url || "")) ? esc(url) : "#");

  function toast(message, isError = false) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.toggle("is-error", isError);
    el.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.hidden = true; }, 4500);
  }

  function ring(score) {
    if (score === null || score === undefined) return "";
    const r = 22;
    const circ = 2 * Math.PI * r;
    const offset = circ * (1 - score / 100);
    const color = score >= 75 ? "#0E8C8C" : "#F26B5B";
    return `<div class="score"><svg width="52" height="52" viewBox="0 0 52 52" aria-label="${Math.round(score)}% match">
      <circle cx="26" cy="26" r="${r}" fill="none" stroke="#E4ECEB" stroke-width="5"/>
      <circle cx="26" cy="26" r="${r}" fill="none" stroke="${color}" stroke-width="5" stroke-linecap="round"
        stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}" transform="rotate(-90 26 26)"/>
      <text x="26" y="30" text-anchor="middle" font-size="11" font-weight="700" fill="#1C2B33">${Math.round(score)}%</text>
    </svg></div>`;
  }

  function statusPill(status) {
    const cls = status === "High Match" ? "pill-teal" : status === "Good Match" ? "pill-blue" : "pill-coral";
    return `<span class="pill ${cls}">${esc(status)}</span>`;
  }

  // ---------- Table rows ----------
  function rowHtml(s) {
    if (s.status === "Needs fix") {
      return `<tr class="row-fix">
        <td><div class="name">${esc(s.student_name)}</div><div class="sub">Row ${esc(s.row)}</div></td>
        <td colspan="6"><span class="pill pill-coral">Needs fix</span> <span class="small">${esc(s.errors.join("; "))}</span></td>
      </tr>`;
    }
    const count = s.recommended_count;
    const listings = s.recommended.length
      ? s.recommended.map((r) => `<li><strong>${esc(r.title)}</strong> · ${esc(r.company)} · ${esc(r.location)}
          · ${Number(r.match_score).toFixed(1)}% · <a href="${safeUrl(r.source_url)}" target="_blank" rel="noopener">Listing ↗</a></li>`).join("")
      : "<li>No listings match the location and duration filters.</li>";
    return `<tr>
        <td><div class="name">${esc(s.student_name)}</div><div class="sub">${esc(s.education)}</div></td>
        <td><span class="cat">${esc(s.predicted_category)}</span></td>
        <td>${ring(s.match_score)}</td>
        <td class="skills">${esc(s.skills.slice(0, 5).join(", ") || "—")}</td>
        <td class="missing">${esc(s.missing_skills.join(", ") || "None")}</td>
        <td><button class="link-cell" data-toggle type="button">View ${count} listing${count === 1 ? "" : "s"} →</button></td>
        <td>${statusPill(s.status)}</td>
      </tr>
      <tr class="detail-row" hidden><td colspan="7"><strong class="small">Recommended internships (confidence ${esc(s.confidence)}%)</strong><ul>${listings}</ul></td></tr>`;
  }

  // ---------- Rendering ----------
  function renderPreview() {
    const items = state.job ? state.firstItems : state.sampleItems;
    $("#sampleTitle").textContent = state.job ? "Your Results" : "Sample Results";
    $("#sampleSub").textContent = state.job
      ? "The first students from your uploaded file. Open View All Results for the full list."
      : "Here’s how your student data will be analyzed and the results will look.";
    $("#sampleBody").innerHTML = items.slice(0, 4).map(rowHtml).join("")
      || `<tr><td colspan="7" class="empty">Upload a file to see results.</td></tr>`;
  }

  function renderStats() {
    const s = state.summary;
    $("#qsStudents").textContent = s ? fmt(s.total_rows) : 0;
    $("#qsCategories").textContent = s ? s.categories.length : 0;
    $("#qsReady").textContent = s ? fmt(s.analysed) : 0;
    if (state.listings) $("#qsListings").textContent = state.listings.count;
  }

  function renderProblems() {
    const box = $("#problems");
    const s = state.summary;
    if (!s) { box.hidden = true; box.innerHTML = ""; return; }
    const issues = [];
    if (s.columns_missing.length) issues.push(`Columns not found in the file: ${s.columns_missing.join(", ")}. Missing values use defaults.`);
    if (s.truncated) issues.push(`Only the first ${fmt(s.max_rows)} rows were analysed.`);
    if (s.problem_total) {
      issues.push(`${fmt(s.problem_total)} rows need fixing. The first ${s.problems.length} are listed below; filter the table by "Needs fix" to see all of them.`);
      s.problems.forEach((p) => issues.push(p));
    }
    const mapped = (s.mapped_values || []).map(([text, count]) => `<li>${esc(text)} <span class="muted">(${fmt(count)})</span></li>`).join("");
    box.hidden = issues.length === 0 && !mapped;
    const title = [
      s.problem_total ? `${fmt(s.problem_total)} rows need fixing` : "",
      s.mapped_total ? `${fmt(s.mapped_total)} values converted` : "",
    ].filter(Boolean).join(" · ");
    box.innerHTML = `<details ${s.problem_total ? "" : "open"}><summary><strong>Details: ${esc(title || "notes")}</strong></summary>` + [
      issues.length ? `<ul>${issues.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "",
      mapped ? `<p class="small"><strong>Values converted automatically</strong> (edit data/value_map.json to change them)</p><ul>${mapped}</ul>` : "",
    ].join("") + "</details>";
  }

  function barRows(entries, cls) {
    if (!entries.length) return "";
    const max = Math.max(...entries.map((e) => e[1]));
    return entries.map(([label, count]) => `<div class="bar-row">
        <span>${esc(label)}</span>
        <div class="bar-track"><div class="bar-fill ${cls}" style="width:${((count / max) * 100).toFixed(1)}%"></div></div>
        <span class="bar-count">${fmt(count)}</span></div>`).join("");
  }

  function renderGaps() {
    const s = state.summary;
    $("#gapBars").innerHTML = s
      ? (barRows(s.top_gaps, "coral") || '<p class="empty">No skill gaps in the top recommendations.</p>')
      : '<p class="empty">Upload a file to see skill gaps.</p>';
    $("#categoryBars").innerHTML = s
      ? (barRows(s.categories, "") || '<p class="empty">No analysed students yet.</p>')
      : '<p class="empty">Upload a file to see categories.</p>';
  }

  function renderResultsHeader() {
    const s = state.summary;
    $("#exportBtn").disabled = !state.job;
    $("#resultsSub").textContent = s
      ? `${fmt(s.analysed)} of ${fmt(s.total_rows)} students analysed from ${state.fileName}.`
      : "Upload a file on the Upload & Predict page to see results here.";
    renderProblems();
  }

  async function loadResultsPage(page = state.pageNo) {
    const body = $("#resultsBody");
    if (!state.job) {
      body.innerHTML = `<tr><td colspan="7" class="empty">No results yet.</td></tr>`;
      $("#pageInfo").textContent = "";
      $("#prevPage").disabled = $("#nextPage").disabled = true;
      return;
    }
    const params = new URLSearchParams({ page, size: state.size, status: state.status });
    body.innerHTML = `<tr><td colspan="7" class="empty">Loading…</td></tr>`;
    try {
      const res = await fetch(`/api/results/${state.job}?${params}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Could not load the results.");
      state.pageNo = data.page;
      state.pages = data.pages;
      body.innerHTML = data.items.map(rowHtml).join("") || `<tr><td colspan="7" class="empty">No rows match this filter.</td></tr>`;
      const first = (data.page - 1) * data.size + 1;
      const last = Math.min(data.page * data.size, data.total);
      $("#pageInfo").textContent = data.total
        ? `Rows ${fmt(first)}–${fmt(last)} of ${fmt(data.total)} · page ${data.page} of ${fmt(data.pages)}`
        : "No rows";
      $("#prevPage").disabled = data.page <= 1;
      $("#nextPage").disabled = data.page >= data.pages;
    } catch (err) {
      body.innerHTML = `<tr><td colspan="7" class="empty">${esc(err.message)}</td></tr>`;
      toast(err.message, true);
    }
  }

  function renderAll() {
    renderStats();
    renderPreview();
    renderResultsHeader();
    renderGaps();
  }

  // ---------- Listings and evaluation ----------
  async function loadListings() {
    if (!state.listings) {
      state.listings = await (await fetch("/api/listings")).json();
      renderStats();
    }
    const q = $("#listingSearch").value.trim().toLowerCase();
    const rows = state.listings.items.filter((r) =>
      !q || [r.title, r.company, r.category, r.required_skills, r.location].join(" ").toLowerCase().includes(q));
    $("#listingsBody").innerHTML = rows.map((r) => `<tr>
        <td class="name">${esc(r.title)}</td><td>${esc(r.company)}</td>
        <td><span class="cat blue">${esc(r.category)}</span></td><td>${esc(r.location)}</td>
        <td>${esc(r.work_mode)}</td><td>${esc(r.duration_months)}</td>
        <td class="skills">${esc(r.required_skills)}</td>
        <td><a class="link-cell" href="${safeUrl(r.source_url)}" target="_blank" rel="noopener">Open ↗</a></td>
      </tr>`).join("") || `<tr><td colspan="8" class="empty">No listings match “${esc(q)}”.</td></tr>`;
  }

  async function loadEvaluation() {
    if (!state.evaluation) state.evaluation = await (await fetch("/api/evaluation")).json();
    const m = state.evaluation;
    const pct = (v) => `${(v * 100).toFixed(1)}%`;
    $("#evalStats").innerHTML = [
      ["Accuracy", pct(m.accuracy)], ["Macro precision", pct(m.macro_precision)],
      ["Macro recall", pct(m.macro_recall)], ["Macro F1", pct(m.macro_f1)],
    ].map(([label, value]) => `<div class="stat"><div class="stat-label">${label}</div><div class="stat-value">${value}</div></div>`).join("");
    const report = m.classification_report || {};
    $("#evalBody").innerHTML = Object.keys(report)
      .filter((k) => !["accuracy", "macro avg", "weighted avg"].includes(k))
      .map((k) => `<tr><td class="name">${esc(k)}</td><td>${pct(report[k].precision)}</td>
        <td>${pct(report[k].recall)}</td><td>${pct(report[k]["f1-score"])}</td><td>${esc(report[k].support)}</td></tr>`).join("");
  }

  // ---------- Upload ----------
  async function sendFile(file, preview = false) {
    const body = new FormData();
    body.append("file", file, file.name);
    const res = await fetch(`/api/analyze${preview ? "?preview=1" : ""}`, { method: "POST", body });
    let data;
    try { data = await res.json(); } catch (_) { data = { error: "The server sent an unexpected response." }; }
    if (!res.ok) throw new Error(data.error || "Upload failed.");
    return data;
  }

  function showFileState(name, status) {
    $("#dropInner").hidden = true;
    $("#fileState").hidden = false;
    $("#fileName").textContent = name;
    $("#fileStatus").textContent = status;
  }

  function resetDropzone() {
    $("#dropInner").hidden = false;
    $("#fileState").hidden = true;
  }

  async function handleFile(file) {
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!ACCEPT.includes(ext)) {
      toast(`“${ext}” is not supported. Use CSV, TSV, Excel, JSON or XML.`, true);
      return;
    }
    if (file.size > MAX_BYTES) {
      toast("This file is larger than 150 MB.", true);
      return;
    }
    showFileState(file.name, "Analysing… large files can take up to a minute.");
    try {
      const data = await sendFile(file);
      state.job = data.job_id;
      state.fileName = data.filename;
      state.summary = data.summary;
      state.firstItems = data.results.items;
      state.pageNo = 1;
      const s = data.summary;
      showFileState(file.name, `${fmt(s.analysed)} analysed · ${fmt(s.needs_fix)} need fixing · ${fmt(s.total_rows)} rows`);
      renderAll();
      toast("Analysis complete. Opening your results.");
      showView("results");
    } catch (err) {
      resetDropzone();
      toast(err.message, true);
    }
  }

  async function loadSample() {
    try {
      const blob = await (await fetch("/api/template")).blob();
      const data = await sendFile(new File([blob], "sample_template.csv", { type: "text/csv" }), true);
      state.sampleItems = data.results.items;
      renderPreview();
    } catch (_) {
      // The preview stays empty if the sample cannot be loaded.
    }
  }


  // ---------- Individual student profile ----------
  function renderProfileResult(student) {
    const recs = (student.recommended || []).map((r) => `
      <article class="profile-rec">
        <div><span class="cat">${esc(r.category)}</span><h3>${esc(r.title)}</h3>
          <p>${esc(r.company)} · ${esc(r.location)} · ${esc(r.duration_months)} month(s)</p>
          <p class="small">Required skills: ${esc(r.missing_skills.length ? r.missing_skills.join(", ") : "All listed skills matched")}</p>
          ${safeUrl(r.source_url) !== "#" ? `<a class="link-cell" href="${safeUrl(r.source_url)}" target="_blank" rel="noopener">View listing ↗</a>` : ""}
        </div><strong class="profile-score">${Number(r.match_score).toFixed(1)}%</strong>
      </article>`).join("");
    $("#profileOutput").innerHTML = `
      <div class="profile-result-head"><div><p class="eyebrow">YOUR AI RESULT</p>
        <h2>${esc(student.student_name)}, here's your recommendation</h2></div>
        <button class="btn btn-outline" id="profilePdfBtn" type="button">↓ Download PDF report</button></div>
      <div class="profile-result-grid">
        <div class="stat"><div class="stat-label">Predicted category</div><div class="stat-value">${esc(student.predicted_category)}</div></div>
        <div class="stat"><div class="stat-label">Model confidence</div><div class="stat-value">${Number(student.confidence).toFixed(1)}%</div></div>
        <div class="stat"><div class="stat-label">Best match score</div><div class="stat-value">${Number(student.match_score).toFixed(1)}%</div></div>
      </div>
      <div class="card"><h2>Recommended internships</h2>${recs || '<p class="empty">No listings match the selected location and duration. Try changing your preferences.</p>'}</div>
      <div class="card"><h2>Skill gap analysis</h2>
        <p class="small">These are skills required by the recommended listings that are not in your profile.</p>
        <div class="gap-chips">${(student.missing_skills || []).map((x) => `<span class="gap-chip">${esc(x)}</span>`).join("") || '<span class="pill pill-teal">No skill gaps in the top recommendations</span>'}</div>
      </div>
      <p class="small">Model confidence is not a probability of being selected. Match scores are calculated using the project's rule-based matching method.</p>`;
    $("#profileOutput").hidden = false;
    $("#profilePdfBtn").addEventListener("click", () => downloadProfilePdf(student));
    $("#profileOutput").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function downloadProfilePdf(student) {
    try {
      const response = await fetch("/api/profile-report", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student })
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Could not create the PDF report.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = "InternMatch_AI_Student_Report.pdf";
      document.body.appendChild(link); link.click(); link.remove();
      URL.revokeObjectURL(url);
      toast("Your PDF report is ready.");
    } catch (error) { toast(error.message, true); }
  }

  async function submitProfile(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = $("#profileSubmit");
    const payload = Object.fromEntries(new FormData(form).entries());
    ["projects_count", "certifications_count", "preferred_duration_months"].forEach((key) => {
      payload[key] = Number(payload[key]);
    });
    payload.skills_count = payload.skills.split(/[,;|]/).map((x) => x.trim()).filter(Boolean).length;
    submit.disabled = true; submit.textContent = "Analysing profile…";
    $("#profileOutput").hidden = true;
    try {
      const response = await fetch("/api/profile-analyze", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Profile analysis failed.");
      renderProfileResult(data.student);
      toast("Your profile analysis is complete.");
    } catch (error) { toast(error.message, true); }
    finally { submit.disabled = false; submit.textContent = "Analyse My Profile →"; }
  }

  // ---------- Navigation ----------
  function showView(name) {
    $$(".view").forEach((v) => { v.hidden = v.dataset.view !== name; });
    $$(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.nav === name));
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (name === "results") { renderResultsHeader(); loadResultsPage(1); }
    if (name === "listings") loadListings();
    if (name === "eval") loadEvaluation();
    if (name === "gaps") renderGaps();
  }

  // ---------- Wiring ----------
  function init() {
    const dropzone = $("#dropzone");
    const fileInput = $("#fileInput");

    $$("[data-nav]").forEach((btn) => btn.addEventListener("click", (e) => {
      e.preventDefault();
      showView(btn.dataset.nav);
    }));

    $("#browseBtn").addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
    dropzone.addEventListener("click", () => { if ($("#fileState").hidden) fileInput.click(); });
    dropzone.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && $("#fileState").hidden) { e.preventDefault(); fileInput.click(); }
    });
    $("#clearBtn").addEventListener("click", (e) => {
      e.stopPropagation();
      state.job = null;
      state.summary = null;
      state.firstItems = [];
      state.fileName = "";
      fileInput.value = "";
      resetDropzone();
      renderAll();
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files[0]) handleFile(fileInput.files[0]);
      fileInput.value = "";
    });

    ["dragenter", "dragover"].forEach((type) => dropzone.addEventListener(type, (e) => {
      e.preventDefault();
      dropzone.classList.add("is-over");
    }));
    ["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, () => dropzone.classList.remove("is-over")));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    });
    // Stop the browser opening a file that is dropped outside the dropzone.
    window.addEventListener("dragover", (e) => e.preventDefault());
    window.addEventListener("drop", (e) => e.preventDefault());

    $("#getStarted").addEventListener("click", () => {
      showView("upload");
      dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    // Results page controls
    $("#statusFilter").addEventListener("change", (e) => { state.status = e.target.value; loadResultsPage(1); });
    $("#pageSize").addEventListener("change", (e) => { state.size = Number(e.target.value); loadResultsPage(1); });
    $("#prevPage").addEventListener("click", () => loadResultsPage(state.pageNo - 1));
    $("#nextPage").addEventListener("click", () => loadResultsPage(state.pageNo + 1));
    $("#exportBtn").addEventListener("click", () => {
      if (state.job) window.location.href = `/api/export/${state.job}`;
    });

    $("#listingSearch").addEventListener("input", loadListings);
    $("#profileForm").addEventListener("submit", submitProfile);

    // "View N listings" buttons in any results table.
    document.addEventListener("click", (e) => {
      const toggle = e.target.closest("[data-toggle]");
      if (!toggle) return;
      const detail = toggle.closest("tr").nextElementSibling;
      if (detail && detail.classList.contains("detail-row")) detail.hidden = !detail.hidden;
    });

    renderAll();
    fetch("/api/listings").then((r) => r.json()).then((data) => {
      state.listings = data;
      renderStats();
    }).catch(() => {});
    loadSample();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
