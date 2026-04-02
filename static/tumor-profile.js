/* tumor-profile.js — Tumor-type profile browsing logic */

(function () {
  "use strict";

  const tumorSelect = document.getElementById("tumor-select");
  const sortSelect = document.getElementById("sort-select");
  const subthresholdToggle = document.getElementById("show-subthreshold");
  const resultsSection = document.getElementById("results-section");
  const summaryEl = document.getElementById("profile-summary");

  let activeTab = "mutation_gene";
  const DEFAULT_SORT = "frequency";
  const cache = {};

  function init() {
    // Restore from URL params
    const params = new URLSearchParams(window.location.search);
    if (params.get("type")) {
      tumorSelect.value = params.get("type");
    }
    sortSelect.value = params.get("sort") || DEFAULT_SORT;
    if (params.get("subthreshold") === "true") {
      subthresholdToggle.checked = true;
    }

    tumorSelect.addEventListener("change", onSelectionChange);
    sortSelect.addEventListener("change", onSelectionChange);
    subthresholdToggle.addEventListener("change", onSelectionChange);

    document.querySelectorAll(".tab-button").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    if (tumorSelect.value) {
      loadAllTabs();
    }
  }

  function onSelectionChange() {
    cache.mutation_allele = null;
    cache.mutation_gene = null;
    cache.cna = null;
    updateURL();
    if (tumorSelect.value) {
      loadAllTabs();
    } else {
      resultsSection.style.display = "none";
    }
  }

  function updateURL() {
    const params = new URLSearchParams();
    if (tumorSelect.value) params.set("type", tumorSelect.value);
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
    await Promise.all([
      loadTab("mutation_allele"),
      loadTab("mutation_gene"),
      loadTab("cna"),
    ]);
  }

  async function loadTab(evidenceType) {
    const tumorType = tumorSelect.value;
    if (!tumorType) return;

    const panel = document.getElementById(`tab-${evidenceType}`);
    panel.innerHTML = '<div class="empty-state"><p>Loading...</p></div>';

    const params = new URLSearchParams({
      evidence_type: evidenceType,
      sort_by: sortSelect.value,
      limit: "100",
      include_subthreshold: subthresholdToggle.checked.toString(),
    });

    try {
      const resp = await fetch(`/api/v1/tumor-profile/${encodeURIComponent(tumorType)}?${params}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        panel.innerHTML = `<div class="empty-state"><p>Error: ${err.detail || resp.statusText}</p></div>`;
        return;
      }
      const data = await resp.json();
      cache[evidenceType] = data;

      if (evidenceType === "mutation_allele") {
        summaryEl.innerHTML = `Showing results for <strong>${data.tumor_type}</strong> ` +
          `(${data.sample_count.toLocaleString()} samples, prior ${(data.prior_probability * 100).toFixed(1)}%)`;
      }

      renderTable(data, panel, evidenceType);
    } catch (e) {
      panel.innerHTML = `<div class="empty-state"><p>Network error: ${e.message}</p></div>`;
    }
  }

  function renderTable(data, container, evidenceType) {
    if (!data.items.length) {
      container.innerHTML = '<div class="empty-state"><p>No significant enrichments found.</p></div>';
      return;
    }

    const isCna = evidenceType === "cna";
    const isAllele = evidenceType === "mutation_allele";
    const maxFE = Math.max(...data.items.map((d) => d.fold_enrichment));

    let html = '<table class="profile-table"><thead><tr>';
    html += "<th>#</th>";
    if (isAllele) {
      html += "<th>Mutation</th><th>Gene</th>";
    } else if (isCna) {
      html += "<th>Gene</th><th>Type</th>";
    } else {
      html += "<th>Gene</th>";
    }
    html += '<th class="col-numeric">Frequency</th>';
    html += '<th class="col-fe">Fold Enrichment</th>';
    html += '<th class="col-numeric">q-value</th>';
    html += "</tr></thead><tbody>";

    data.items.forEach((item, i) => {
      const rowClass = item.is_significant ? "" : ' class="subthreshold"';
      html += `<tr${rowClass}>`;
      html += `<td class="col-numeric">${i + 1}</td>`;

      if (isAllele) {
        html += `<td class="col-gene">${esc(item.event_label)}</td>`;
        html += `<td>${esc(item.gene || "")}</td>`;
      } else if (isCna) {
        html += `<td class="col-gene">${esc(item.gene || "")}</td>`;
        html += `<td>${esc(item.cna_state || "")}</td>`;
      } else {
        html += `<td class="col-gene">${esc(item.event_label)}</td>`;
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
