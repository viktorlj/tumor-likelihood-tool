const mutationRows = document.getElementById("mutation-rows");
const cnaRows = document.getElementById("cna-rows");
const mutationTemplate = document.getElementById("mutation-row-template");
const cnaTemplate = document.getElementById("cna-row-template");
const form = document.getElementById("predict-form");
const errorBox = document.getElementById("error-box");
const notesBox = document.getElementById("notes");
const resultTumor = document.getElementById("results-tumor");
const resultsPanel = document.getElementById("results-panel");

// Cached from last prediction
let lastData = null;

function addMutationRow(defaults = { gene: "", protein: "" }) {
  const row = mutationTemplate.content.firstElementChild.cloneNode(true);
  row.querySelector(".mutation-gene").value = defaults.gene;
  row.querySelector(".mutation-protein").value = defaults.protein;
  row.querySelector(".remove-row").addEventListener("click", () => row.remove());
  mutationRows.appendChild(row);
}

function addCnaRow(defaults = { gene: "", cnaState: "Amplification" }) {
  const row = cnaTemplate.content.firstElementChild.cloneNode(true);
  row.querySelector(".cna-gene").value = defaults.gene;
  row.querySelector(".cna-state").value = defaults.cnaState;
  row.querySelector(".remove-row").addEventListener("click", () => row.remove());
  cnaRows.appendChild(row);
}

function parseResponseError(payload) {
  if (!payload) return "Unknown error";
  if (typeof payload.detail === "string") return payload.detail;
  return JSON.stringify(payload, null, 2);
}

function formatFreq(affected, total) {
  if (!total || total === 0) return "";
  const pct = (affected / total) * 100;
  const pctStr = pct >= 1 ? pct.toFixed(1) : pct < 0.1 ? pct.toFixed(2) : pct.toFixed(1);
  return `${affected.toLocaleString()} / ${total.toLocaleString()} (${pctStr}%)`;
}

function renderFreqBar(term) {
  const fe = Number(term.fold_enrichment);
  const hasFreq = term.affected_count != null && term.group_total != null && term.group_total > 0;
  const cappedWidth = Math.min(fe / 10, 1) * 100;
  const depleted = fe < 1.0;
  const feLabel = fe >= 100 ? fe.toFixed(0) + "x" : fe >= 10 ? fe.toFixed(1) + "x" : fe.toFixed(2) + "x";
  const freqStr = hasFreq ? formatFreq(term.affected_count, term.group_total) : "";

  return `
    <div class="freq-bar-container">
      <div class="freq-bar-label mp-soft">
        <span>${term.event_label}</span>
        <span>${feLabel} enriched${freqStr ? " \u00b7 " + freqStr : ""}</span>
      </div>
      <div class="mp-bar-track">
        <div class="mp-bar-fill${depleted ? " depleted" : ""}" style="width: ${cappedWidth}%"></div>
      </div>
    </div>
  `;
}

function renderDetailPanel(tumorType) {
  if (!lastData) return "";

  const mapping = lastData.tumor_to_detailed || {};
  const detailedTypes = mapping[tumorType] || [];
  if (detailedTypes.length === 0) return "";

  const detailedRankings = lastData.results?.detailed?.rankings || [];

  // Build lookup of detailed results by class name
  const detailedByName = {};
  detailedRankings.forEach((r) => { detailedByName[r.class_name] = r; });

  // Filter to subtypes within this tumor group that have evidence
  const matchedSubtypes = detailedTypes
    .map((name) => detailedByName[name])
    .filter((r) => r && r.evidence_terms && r.evidence_terms.length > 0);

  if (matchedSubtypes.length === 0) {
    return `
      <div class="detail-panel">
        <div class="mp-section-title">Detailed subtypes</div>
        <div class="detail-no-evidence mp-soft">No subtype-level evidence for these aberrations.</div>
      </div>
    `;
  }

  // Sort by posterior descending
  matchedSubtypes.sort((a, b) => b.posterior - a.posterior);

  const subtypeHtml = matchedSubtypes.map((r) => {
    const postPct = (r.posterior * 100).toFixed(2);
    const priorPct = (r.prior_probability * 100).toFixed(2);

    const bars = (r.evidence_terms || [])
      .filter((t) => t.fold_enrichment != null)
      .slice(0, 4)
      .map((t) => renderFreqBar(t))
      .join("");

    return `
      <div class="detail-subtype">
        <div class="detail-subtype-header mp-flex mp-between">
          <span class="detail-subtype-name">${r.class_name}</span>
          <span class="detail-subtype-posterior">${postPct}%</span>
        </div>
        <div class="detail-subtype-meta mp-soft">${priorPct}% prior</div>
        ${bars}
      </div>
    `;
  }).join("");

  return `
    <div class="detail-panel">
      <div class="mp-section-title">Detailed subtypes within ${tumorType.replace(/_/g, " ")}</div>
      ${subtypeHtml}
    </div>
  `;
}

function renderConfidence(confidence) {
  const banner = document.getElementById("confidence-banner");
  if (!confidence) {
    banner.classList.add("mp-hidden");
    return;
  }

  const tierMap = {
    "Very High": "mp-alert-success",
    "High": "mp-alert-info",
    "Moderate": "mp-alert-warning",
    "Low": "mp-alert-error",
  };

  const ppvPct = (confidence.historical_ppv * 100).toFixed(0);
  const postPct = (confidence.top_posterior * 100).toFixed(1);
  const alertClass = tierMap[confidence.tier] || "mp-alert-warning";

  banner.className = `mp-alert ${alertClass}`;
  banner.innerHTML = `
    <div class="confidence-tier">${confidence.tier} Confidence</div>
    <div class="confidence-detail mp-mono">
      Top posterior: ${postPct}% &mdash;
      Validated accuracy at this level: ${ppvPct}%
    </div>
    <div class="confidence-desc">${confidence.description}</div>
  `;
  banner.classList.remove("mp-hidden");
}

function renderRankings(target, rankings) {
  target.innerHTML = "";
  if (!rankings || rankings.length === 0) {
    target.innerHTML = "<p>No ranked classes available.</p>";
    return;
  }

  rankings.forEach((item) => {
    const posteriorPct = (Number(item.posterior) * 100).toFixed(2);
    const priorPct = (Number(item.prior_probability) * 100).toFixed(2);

    const terms = item.evidence_terms || [];
    const freqBarsHtml = terms
      .filter((t) => t.fold_enrichment != null)
      .slice(0, 6)
      .map((t) => renderFreqBar(t))
      .join("");

    const card = document.createElement("article");
    card.className = "mp-card result-card";
    card.innerHTML = `
      <div class="result-header mp-flex mp-between">
        <span class="class-name">${item.class_name}</span>
        <span class="posterior">${posteriorPct}%</span>
      </div>
      <div class="score-meta mp-soft">Prior ${priorPct}% | log score ${Number(item.log_score).toFixed(3)}</div>
      ${
        freqBarsHtml
          ? `<div class="mp-section-title" style="margin-top:10px">Aberration frequency in this type</div>${freqBarsHtml}`
          : ""
      }
      <div class="expand-hint mp-soft">Click to see detailed subtypes</div>
    `;

    card.addEventListener("click", () => {
      const isExpanded = card.classList.contains("active");
      // Collapse all
      target.querySelectorAll(".mp-card").forEach((c) => {
        c.classList.remove("active");
        const dp = c.querySelector(".detail-panel");
        if (dp) dp.remove();
        const hint = c.querySelector(".expand-hint");
        if (hint) hint.textContent = "Click to see detailed subtypes";
      });

      if (!isExpanded) {
        card.classList.add("active");
        const hint = card.querySelector(".expand-hint");
        if (hint) hint.textContent = "Click to collapse";
        const detailHtml = renderDetailPanel(item.class_name);
        if (detailHtml) {
          card.insertAdjacentHTML("beforeend", detailHtml);
        }
      }
    });

    target.appendChild(card);
  });
}

function collectPayload() {
  const alterations = [];

  mutationRows.querySelectorAll(".mutation-row").forEach((row) => {
    const gene = row.querySelector(".mutation-gene").value.trim();
    const protein = row.querySelector(".mutation-protein").value.trim();
    if (!gene) return;
    const mutation = { kind: "mutation", gene };
    if (protein) mutation.protein = protein;
    alterations.push(mutation);
  });

  cnaRows.querySelectorAll(".cna-row").forEach((row) => {
    const gene = row.querySelector(".cna-gene").value.trim();
    const cnaState = row.querySelector(".cna-state").value;
    if (!gene) return;
    alterations.push({ kind: "cna", gene, cna_state: cnaState });
  });

  if (alterations.length === 0) {
    throw new Error("Add at least one mutation or CNA before running prediction.");
  }

  const returnTopK = Number(document.getElementById("top-k").value || 10);
  return {
    alterations,
    options: { return_top_k: returnTopK, include_evidence: true },
  };
}

async function runPrediction(event) {
  event.preventDefault();
  errorBox.classList.add("mp-hidden");
  errorBox.textContent = "";

  let payload;
  try {
    payload = collectPayload();
  } catch (error) {
    errorBox.textContent = String(error.message || error);
    errorBox.classList.remove("mp-hidden");
    return;
  }

  const submitButton = document.getElementById("predict-button");
  submitButton.disabled = true;
  submitButton.textContent = "Predicting...";

  try {
    const response = await fetch("/api/v1/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => null);
      throw new Error(parseResponseError(errorPayload));
    }

    lastData = await response.json();
    notesBox.innerHTML = (lastData.notes || []).map((n) => `<div>\u2022 ${n}</div>`).join("");

    renderConfidence(lastData.confidence);
    renderRankings(resultTumor, lastData.results?.tumor?.rankings || []);

    resultsPanel.classList.remove("mp-hidden");
    resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    errorBox.textContent = String(error.message || error);
    errorBox.classList.remove("mp-hidden");
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Predict";
  }
}

function bootstrap() {
  document.getElementById("add-mutation").addEventListener("click", () => addMutationRow());
  document.getElementById("add-cna").addEventListener("click", () => addCnaRow());
  form.addEventListener("submit", runPrediction);
  addMutationRow({ gene: "BRAF", protein: "p.V600E" });
  addCnaRow({ gene: "CDKN2A", cnaState: "DeepDeletion" });
}

bootstrap();
