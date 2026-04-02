"""Pydantic schemas for the web application API."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class MutationInput(BaseModel):
    """Mutation alteration provided by the user."""

    kind: Literal["mutation"] = "mutation"
    gene: str = Field(..., min_length=1, description="HGNC gene symbol")
    protein: str | None = Field(
        default=None,
        description="Protein-level HGVS short notation, e.g. p.V600E",
    )


class CnaInput(BaseModel):
    """Copy number alteration provided by the user."""

    kind: Literal["cna"] = "cna"
    gene: str = Field(..., min_length=1, description="HGNC gene symbol")
    cna_state: str = Field(..., min_length=1, description="Amplification or DeepDeletion")


AlterationInput = Annotated[MutationInput | CnaInput, Field(discriminator="kind")]


class PredictOptions(BaseModel):
    """Tuning options for prediction response formatting."""

    return_top_k: int = Field(default=10, ge=1, le=100)
    include_evidence: bool = Field(default=True)


class PredictRequest(BaseModel):
    """Prediction request payload."""

    alterations: list[AlterationInput] = Field(..., min_length=1, max_length=100)
    options: PredictOptions = Field(default_factory=PredictOptions)


class EvidenceTerm(BaseModel):
    """Evidence term contribution to a class score."""

    event_id: str
    event_label: str
    evidence_type: str
    weight: float
    raw_log_bf: float
    weighted_log_bf: float
    fold_enrichment: float | None = None
    affected_count: int | None = None
    group_total: int | None = None
    metadata: dict[str, str | float | None]


class ClassPrediction(BaseModel):
    """Single class output in ranked response."""

    class_name: str
    posterior: float
    log_score: float
    prior_probability: float
    prior_log_probability: float
    evidence_terms: list[EvidenceTerm]


class PredictionLevelResult(BaseModel):
    """Results for one taxonomy level."""

    level: str
    top_k: int
    rankings: list[ClassPrediction]


class ConfidenceAssessment(BaseModel):
    """Calibrated confidence assessment for the top prediction."""

    tier: str  # "Very High", "High", "Moderate", "Low"
    top_posterior: float
    historical_ppv: float
    description: str


class PredictResponse(BaseModel):
    """Prediction response payload."""

    input_normalized: list[dict[str, str | None]]
    results: dict[str, PredictionLevelResult]
    confidence: ConfidenceAssessment
    tumor_to_detailed: dict[str, list[str]]
    notes: list[str]


class MetaResponse(BaseModel):
    """Metadata response payload."""

    model_version: str
    priors: dict[str, dict[str, int]]
    settings: dict[str, float | int | bool]
    supported_cna_states: list[str]


# --- Profile browsing views ---


class ProfileItem(BaseModel):
    """Single enrichment event in a tumor-type profile."""

    event_label: str
    gene: str | None = None
    protein_key: str | None = None
    cna_state: str | None = None
    fold_enrichment: float
    q_value: float
    affected_count: int
    group_total: int
    frequency_pct: float
    log_bf: float
    is_significant: bool


class TumorProfileResponse(BaseModel):
    """Response for tumor-type profile browsing."""

    tumor_type: str
    sample_count: int
    prior_probability: float
    evidence_type: str
    sort_by: str
    total_significant: int
    items: list[ProfileItem]


class GeneProfileItem(BaseModel):
    """Single tumor-type row in a gene profile."""

    class_name: str
    sample_count: int
    event_label: str | None = None
    protein_key: str | None = None
    cna_state: str | None = None
    fold_enrichment: float
    q_value: float
    affected_count: int
    group_total: int
    frequency_pct: float
    log_bf: float
    is_significant: bool


class GeneProfileResponse(BaseModel):
    """Response for gene profile browsing."""

    gene: str
    evidence_type: str
    sort_by: str
    total_significant: int
    items: list[GeneProfileItem]
