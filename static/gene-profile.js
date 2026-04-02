/* gene-profile.js — Gene profile browsing logic */

(function () {
  "use strict";

  const geneInput = document.getElementById("gene-input");
  const searchBtn = document.getElementById("search-btn");
  const levelSelect = document.getElementById("level-select");
  const sortSelect = document.getElementById("sort-select");
  const subthresholdToggle = document.getElementById("show-subthreshold");
  const resultsSection = document.getElementById("results-section");
  const summaryEl = document.getElementById("profile-summary");

  let activeTab = "mutation_allele";
  const DEFAULT_SORT = "frequency";
  let currentGene = "";

  function init() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("gene")) {
      geneInput.value = params.get("gene").toUpperCase();
    }
    if (params.get("level")) {
      levelSelect.value = params.get("level");
    }
    sortSelect.value = params.get("sort") || DEFAULT_SORT;
    if (params.get("subthreshold") === "true") {
      subthresholdToggle.checked = true;
    }

    searchBtn.addEventListener("click", onSearch);
    geneInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onSearch();
      }
    });
    levelSelect.addEventListener("change", () => {
      if (currentGene) loadAllTabs();
      updateURL();
    });
    sortSelect.addEventListener("change", () => {
      if (currentGene) loadAllTabs();
      updateURL();
    });
    subthresholdToggle.addEventListener("change", () => {
      if (currentGene) loadAllTabs();
      updateURL();
    });

    document.querySelectorAll(".tab-button").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    if (geneInput.value) {
      onSearch();
    }
  }

  function onSearch() {
    const gene = geneInput.value.trim().toUpperCase();
    if (!gene) return;
    currentGene = gene;
    geneInput.value = gene;
    updateURL();
    loadAllTabs();
  }

  function updateURL() {
    const params = new URLSearchParams();
    if (currentGene) params.set("gene", currentGene);
    if (levelSelect.value !== "tumor") params.set("level", levelSelect.value);
    if (sortSelect.value !== DEFAULT_SORT) params.set("sort", sortSelect.value);
    if (subthresholdToggle.checked) params.set("subthreshold", "true");
    const qs = params.toString();
    history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }

  function switchTab(tabName) {
    activeTab = tabName;
    document.querySelectorAll(".tab-button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tabName);
    });
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `tab-${tabName}`);
    });
  }

  async function loadAllTabs() {
    resultsSection.style.display = "";
    summaryEl.innerHTML = `Showing results for <strong>${esc(currentGene)}</strong>`;
    await Promise.all([
      loadTab("mutation_gene"),
      loadTab("mutation_allele"),
      loadTab("cna"),
    ]);
  }

  async function loadTab(evidenceType) {
    if (!currentGene) return;

    const panel = document.getElementById(`tab-${evidenceType}`);
    panel.innerHTML = '<div class="empty-state"><p>Loading...</p></div>';

    const params = new URLSearchParams({
      evidence_type: evidenceType,
      sort_by: sortSelect.value,
      limit: "100",
      include_subthreshold: subthresholdToggle.checked.toString(),
      level: levelSelect.value,
    });

    try {
      const resp = await fetch(`/api/v1/gene-profile/${encodeURIComponent(currentGene)}?${params}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        panel.innerHTML = `<div class="empty-state"><p>${resp.status === 404 ? "Gene not found in database." : "Error: " + (err.detail || resp.statusText)}</p></div>`;
        return;
      }
      const data = await resp.json();
      renderTable(data, panel, evidenceType);
    } catch (e) {
      panel.innerHTML = `<div class="empty-state"><p>Network error: ${e.message}</p></div>`;
    }
  }

  function renderTable(data, container, evidenceType) {
    if (!data.items.length) {
      const msg = data.total_significant === 0
        ? "No significant enrichments found for this evidence type."
        : "No results match the current filters.";
      container.innerHTML = `<div class="empty-state"><p>${msg}</p></div>`;
      return;
    }

    const isAllele = evidenceType === "mutation_allele";
    const isCna = evidenceType === "cna";
    const maxFE = Math.max(...data.items.map((d) => d.fold_enrichment));

    let html = '<table class="profile-table"><thead><tr>';
    html += "<th>#</th>";
    html += "<th>Tumor Type</th>";
    if (isAllele) {
      html += "<th>Variant</th>";
    } else if (isCna) {
      html += "<th>Type</th>";
    }
    html += '<th class="col-numeric">Frequency</th>';
    html += '<th class="col-fe">Fold Enrichment</th>';
    html += '<th class="col-numeric">q-value</th>';
    html += "</tr></thead><tbody>";

    data.items.forEach((item, i) => {
      const rowClass = item.is_significant ? "" : ' class="subthreshold"';
      html += `<tr${rowClass}>`;
      html += `<td class="col-numeric">${i + 1}</td>`;
      html += `<td class="col-gene">${esc(item.class_name)}</td>`;

      if (isAllele) {
        html += `<td>${esc(item.event_label || "")}</td>`;
      } else if (isCna) {
        html += `<td>${esc(item.cna_state || "")}</td>`;
      }

      html += `<td class="col-numeric">${item.affected_count}/${item.group_total} (${item.frequency_pct.toFixed(1)}%)</td>`;

      const barPct = Math.min((item.fold_enrichment / maxFE) * 100, 100);
      const barClass = item.fold_enrichment < 1 ? "inline-bar-fill depleted" : "inline-bar-fill";
      html += `<td><div class="inline-bar">`;
      html += `<span class="inline-bar-value">${fmtFE(item.fold_enrichment)}</span>`;
      html += `<div class="inline-bar-track"><div class="${barClass}" style="width:${barPct.toFixed(1)}%"></div></div>`;
      html += `</div></td>`;

      html += `<td class="col-numeric">${fmtQ(item.q_value)}</td>`;
      html += "</tr>";
    });

    html += "</tbody></table>";
    container.innerHTML = html;
  }

  function fmtFE(val) {
    if (val >= 100) return val.toFixed(0);
    if (val >= 10) return val.toFixed(1);
    return val.toFixed(2);
  }

  function fmtQ(val) {
    if (val === 0) return "< 1e-300";
    if (val < 0.001) return val.toExponential(1);
    return val.toFixed(4);
  }

  function esc(s) {
    const el = document.createElement("span");
    el.textContent = s;
    return el.innerHTML;
  }

  document.addEventListener("DOMContentLoaded", init);
})();
