"""Bayesian-style tumor likelihood scoring engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .data_loader import EventContribution, LevelArtifacts, ModelArtifacts, load_model_artifacts
from .parser import (
    NormalizedAlteration,
    normalize_cna_input,
    normalize_mutation_input,
)
from .schemas import CnaInput, MutationInput

CNA_STATE_TOKEN = {
    "Amplification": "AMP",
    "DeepDeletion": "DEL",
}

DEFAULT_WEIGHTS = {
    "mutation_allele": 1.2,
    "mutation_gene": 0.1,
    "cna": 0.5,
    "pair": 0.0,
}

# Calibration tiers from holdout validation (N=22,965 samples, GENIE v18)
# Maps (min_posterior, max_posterior) -> (tier_name, observed_ppv, description)
CONFIDENCE_TIERS = [
    (0.90, 1.01, "Very High", 0.863, "Historically correct 86% of the time at this confidence level"),
    (0.60, 0.90, "High", 0.636, "Historically correct 64% of the time at this confidence level"),
    (0.30, 0.60, "Moderate", 0.362, "Consider additional clinical and morphological evidence"),
    (0.00, 0.30, "Low", 0.152, "Insufficient molecular evidence for confident classification"),
]


@dataclass(frozen=True)
class SelectedEvent:
    """Selected evidence event for one query."""

    event_id: str
    event_label: str
    evidence_type: str
    weight: float


def _softmax(log_scores: list[float]) -> list[float]:
    max_score = max(log_scores)
    exp_scores = [math.exp(score - max_score) for score in log_scores]
    total = sum(exp_scores)
    return [score / total for score in exp_scores]


def _allele_event_id(gene: str, protein_key: str) -> str:
    return f"MUT_ALLELE|{gene}|{protein_key}"


def _gene_event_id(gene: str) -> str:
    return f"MUT_GENE|{gene}"


def _cna_event_id(gene: str, cna_state: str) -> str:
    token = CNA_STATE_TOKEN[cna_state]
    return f"CNA|{gene}|{token}"


def _pair_mut_mut_event_id(gene1: str, gene2: str) -> str:
    g1, g2 = sorted((gene1, gene2))
    return f"PAIR|MUT_MUT|{g1}|{g2}"


def _pair_mut_amp_event_id(mut_gene: str, amp_gene: str) -> str:
    return f"PAIR|MUT_AMP|{mut_gene}|{amp_gene}"


def _pair_mut_del_event_id(mut_gene: str, del_gene: str) -> str:
    return f"PAIR|MUT_DEL|{mut_gene}|{del_gene}"


def _normalize_inputs(alterations: Iterable[MutationInput | CnaInput]) -> list[NormalizedAlteration]:
    normalized: list[NormalizedAlteration] = []
    for alteration in alterations:
        if isinstance(alteration, MutationInput):
            normalized.append(normalize_mutation_input(alteration))
        elif isinstance(alteration, CnaInput):
            normalized.append(normalize_cna_input(alteration))
        else:
            raise ValueError(f"Unsupported alteration type: {type(alteration).__name__}")
    return normalized


def _append_if_present(
    level: LevelArtifacts,
    event_id: str,
    weight: float,
    selected_events: list[SelectedEvent],
    selected_ids: set[str],
) -> bool:
    if event_id in selected_ids:
        return True

    event = level.events.get(event_id)
    if event is None:
        return False

    selected_events.append(
        SelectedEvent(
            event_id=event_id,
            event_label=event.event_label,
            evidence_type=event.evidence_type,
            weight=weight,
        )
    )
    selected_ids.add(event_id)
    return True


def _format_event_term(
    event: EventContribution,
    selected: SelectedEvent,
    raw_log_bf: float,
    weighted_log_bf: float,
    fold_enrichment: float | None = None,
    affected_count: int | None = None,
    group_total: int | None = None,
) -> dict[str, str | float | int | None]:
    return {
        "event_id": selected.event_id,
        "event_label": selected.event_label,
        "evidence_type": selected.evidence_type,
        "weight": selected.weight,
        "raw_log_bf": raw_log_bf,
        "weighted_log_bf": weighted_log_bf,
        "fold_enrichment": fold_enrichment,
        "affected_count": affected_count,
        "group_total": group_total,
        "metadata": {
            "gene": event.metadata.get("gene"),
            "protein_key": event.metadata.get("protein_key"),
            "cna_state": event.metadata.get("cna_state"),
            "pair_type": event.metadata.get("pair_type"),
            "gene1": event.metadata.get("gene1"),
            "gene2": event.metadata.get("gene2"),
        },
    }


class TumorLikelihoodModel:
    """Runtime inference model for tumor-type likelihood ranking."""

    def __init__(self, artifacts: ModelArtifacts) -> None:
        self.artifacts = artifacts

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "TumorLikelihoodModel":
        """Load model artifacts from data directory."""
        return cls(load_model_artifacts(data_dir))

    def model_version(self) -> str:
        """Return manifest model version string."""
        return self.artifacts.model_version

    def metadata(self) -> dict[str, object]:
        """Return metadata for API consumers."""
        priors_meta: dict[str, dict[str, int]] = {}
        for level_name, level in self.artifacts.levels.items():
            priors_meta[level_name] = {
                "n_classes": len(level.classes),
                "n_samples": sum(level.sample_counts),
                "n_events": len(level.events),
            }

        return {
            "model_version": self.artifacts.model_version,
            "priors": priors_meta,
            "settings": {
                "weight_mutation_allele": DEFAULT_WEIGHTS["mutation_allele"],
                "weight_mutation_gene": DEFAULT_WEIGHTS["mutation_gene"],
                "weight_cna": DEFAULT_WEIGHTS["cna"],
                "weight_pair": DEFAULT_WEIGHTS["pair"],
                "pair_evidence_tumor_only": True,
                "uses_empirical_prior": True,
            },
            "supported_cna_states": ["Amplification", "DeepDeletion"],
        }

    def _select_primary_events(
        self,
        level: LevelArtifacts,
        normalized: list[NormalizedAlteration],
    ) -> tuple[list[SelectedEvent], list[str]]:
        selected_events: list[SelectedEvent] = []
        selected_ids: set[str] = set()
        notes: list[str] = []

        for item in normalized:
            if item.kind == "mutation":
                if item.protein_key:
                    allele_id = _allele_event_id(item.gene, item.protein_key)
                    used_allele = _append_if_present(
                        level,
                        allele_id,
                        DEFAULT_WEIGHTS["mutation_allele"],
                        selected_events,
                        selected_ids,
                    )
                    if used_allele:
                        continue

                    gene_id = _gene_event_id(item.gene)
                    used_gene = _append_if_present(
                        level,
                        gene_id,
                        DEFAULT_WEIGHTS["mutation_gene"],
                        selected_events,
                        selected_ids,
                    )
                    if used_gene:
                        notes.append(
                            f"No allele-level record for {item.gene} {item.protein}; used gene-level evidence."
                        )
                    else:
                        notes.append(
                            f"No enrichment record found for {item.gene} {item.protein}."
                        )
                else:
                    gene_id = _gene_event_id(item.gene)
                    used_gene = _append_if_present(
                        level,
                        gene_id,
                        DEFAULT_WEIGHTS["mutation_gene"],
                        selected_events,
                        selected_ids,
                    )
                    if not used_gene:
                        notes.append(f"No enrichment record found for gene {item.gene}.")

            elif item.kind == "cna":
                if item.cna_state is None:
                    notes.append(f"Ignoring malformed CNA entry for {item.gene}.")
                    continue

                cna_id = _cna_event_id(item.gene, item.cna_state)
                used_cna = _append_if_present(
                    level,
                    cna_id,
                    DEFAULT_WEIGHTS["cna"],
                    selected_events,
                    selected_ids,
                )
                if not used_cna:
                    notes.append(
                        f"No enrichment record found for CNA {item.gene} {item.cna_state}."
                    )

        return selected_events, notes

    def _select_pair_events(
        self,
        level: LevelArtifacts,
        normalized: list[NormalizedAlteration],
        selected_events: list[SelectedEvent],
    ) -> list[str]:
        if level.level != "tumor":
            return []

        selected_ids = {event.event_id for event in selected_events}
        notes: list[str] = []

        mutation_genes = sorted({item.gene for item in normalized if item.kind == "mutation"})
        amp_genes = sorted(
            {
                item.gene
                for item in normalized
                if item.kind == "cna" and item.cna_state == "Amplification"
            }
        )
        del_genes = sorted(
            {
                item.gene
                for item in normalized
                if item.kind == "cna" and item.cna_state == "DeepDeletion"
            }
        )

        for i, gene1 in enumerate(mutation_genes):
            for gene2 in mutation_genes[i + 1 :]:
                event_id = _pair_mut_mut_event_id(gene1, gene2)
                _append_if_present(
                    level,
                    event_id,
                    DEFAULT_WEIGHTS["pair"],
                    selected_events,
                    selected_ids,
                )

        for mut_gene in mutation_genes:
            for amp_gene in amp_genes:
                event_id = _pair_mut_amp_event_id(mut_gene, amp_gene)
                _append_if_present(
                    level,
                    event_id,
                    DEFAULT_WEIGHTS["pair"],
                    selected_events,
                    selected_ids,
                )

            for del_gene in del_genes:
                event_id = _pair_mut_del_event_id(mut_gene, del_gene)
                _append_if_present(
                    level,
                    event_id,
                    DEFAULT_WEIGHTS["pair"],
                    selected_events,
                    selected_ids,
                )

        if mutation_genes and (amp_genes or del_genes):
            notes.append("Tumor-level pair evidence was included for mutation/CNA combinations.")
        elif len(mutation_genes) >= 2:
            notes.append("Tumor-level mutation-pair evidence was included.")

        return notes

    def _score_level(
        self,
        level: LevelArtifacts,
        selected_events: list[SelectedEvent],
        include_evidence: bool,
        top_k: int,
    ) -> dict[str, object]:
        scores = list(level.prior_log_probabilities)
        evidence_by_class: list[list[dict[str, object]]] = [
            [] for _ in range(len(level.classes))
        ]

        for selected in selected_events:
            event = level.events.get(selected.event_id)
            if event is None:
                continue

            for class_idx, raw_log_bf, fold_enr, aff_count, grp_total in zip(
                event.class_indices,
                event.class_log_bfs,
                event.class_fold_enrichments,
                event.class_affected_counts,
                event.class_group_totals,
            ):
                weighted = selected.weight * raw_log_bf
                scores[class_idx] += weighted

                if include_evidence:
                    evidence_by_class[class_idx].append(
                        _format_event_term(
                            event, selected, raw_log_bf, weighted, fold_enr, aff_count, grp_total
                        )
                    )

        posteriors = _softmax(scores)

        # Only rank classes that have at least one evidence contribution.
        # Classes with no evidence are just prior noise and should be excluded.
        has_evidence = {idx for idx in range(len(level.classes)) if evidence_by_class[idx]}
        ranked_indices = sorted(
            has_evidence,
            key=lambda idx: posteriors[idx],
            reverse=True,
        )

        rankings: list[dict[str, object]] = []
        for idx in ranked_indices[:top_k]:
            evidence_terms = evidence_by_class[idx]
            evidence_terms.sort(
                key=lambda term: abs(float(term["weighted_log_bf"])),
                reverse=True,
            )

            rankings.append(
                {
                    "class_name": level.classes[idx],
                    "posterior": posteriors[idx],
                    "log_score": scores[idx],
                    "prior_probability": level.prior_probabilities[idx],
                    "prior_log_probability": level.prior_log_probabilities[idx],
                    "evidence_terms": evidence_terms,
                }
            )

        return {
            "level": level.level,
            "top_k": top_k,
            "rankings": rankings,
        }

    def predict(
        self,
        alterations: list[MutationInput | CnaInput],
        top_k: int,
        include_evidence: bool,
    ) -> dict[str, object]:
        """Score two taxonomy levels and return ranked posterior outputs."""
        normalized = _normalize_inputs(alterations)
        notes: list[str] = []

        detailed_level = self.artifacts.levels["detailed"]
        tumor_level = self.artifacts.levels["tumor"]

        detailed_events, detailed_notes = self._select_primary_events(
            detailed_level,
            normalized,
        )
        notes.extend(detailed_notes)

        tumor_events, tumor_notes = self._select_primary_events(
            tumor_level,
            normalized,
        )
        notes.extend(tumor_notes)
        notes.extend(self._select_pair_events(tumor_level, normalized, tumor_events))

        if not detailed_events and not tumor_events:
            notes.append("No matching evidence events were found; outputs reflect priors only.")

        # Return all detailed classes with evidence (needed for tumor drill-down).
        detailed_result = self._score_level(
            detailed_level,
            selected_events=detailed_events,
            include_evidence=include_evidence,
            top_k=len(detailed_level.classes),
        )
        tumor_result = self._score_level(
            tumor_level,
            selected_events=tumor_events,
            include_evidence=include_evidence,
            top_k=top_k,
        )

        # Compute confidence assessment from the top tumor-level posterior
        top_posterior = 0.0
        if tumor_result["rankings"]:
            top_posterior = tumor_result["rankings"][0]["posterior"]

        confidence = {"tier": "Low", "top_posterior": top_posterior,
                      "historical_ppv": 0.152, "description": CONFIDENCE_TIERS[-1][4]}
        for lo, hi, tier, ppv, desc in CONFIDENCE_TIERS:
            if lo <= top_posterior < hi:
                confidence = {"tier": tier, "top_posterior": top_posterior,
                              "historical_ppv": ppv, "description": desc}
                break

        return {
            "input_normalized": [item.to_dict() for item in normalized],
            "results": {
                "detailed": detailed_result,
                "tumor": tumor_result,
            },
            "confidence": confidence,
            "tumor_to_detailed": self.artifacts.tumor_to_detailed,
            "notes": notes,
        }
