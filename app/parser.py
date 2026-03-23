"""Parsing and normalization for mutation and CNA user inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import CnaInput, MutationInput

PROTEIN_PATTERN = re.compile(r"^(?:P\.)?([A-Z\*])([0-9]+)([A-Z\*])$")

CNA_ALIASES = {
    "AMPLIFICATION": "Amplification",
    "AMP": "Amplification",
    "GAIN": "Amplification",
    "DEEPDELETION": "DeepDeletion",
    "DEEP_DELETION": "DeepDeletion",
    "DELETION": "DeepDeletion",
    "DEL": "DeepDeletion",
    "LOSS": "DeepDeletion",
}


@dataclass(frozen=True)
class NormalizedAlteration:
    """Canonical representation used by scoring logic."""

    kind: str
    gene: str
    protein: str | None = None
    protein_key: str | None = None
    cna_state: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize as JSON-safe dict."""
        return {
            "kind": self.kind,
            "gene": self.gene,
            "protein": self.protein,
            "cna_state": self.cna_state,
        }


def normalize_gene(gene: str) -> str:
    """Normalize gene symbol casing and whitespace."""
    normalized = gene.strip().upper()
    if not normalized:
        raise ValueError("Gene symbol is required")
    return normalized


def normalize_protein(protein: str) -> str:
    """Normalize protein notation to canonical HGVS short form (e.g., p.V600E)."""
    token = protein.strip().upper().replace(" ", "")
    if not token:
        raise ValueError("Protein notation is empty")

    match = PROTEIN_PATTERN.match(token)
    if not match:
        raise ValueError(
            "Invalid protein notation. Expected HGVS short format like p.V600E"
        )

    ref, position, alt = match.groups()
    return f"p.{ref}{position}{alt}"


def protein_to_key(protein: str) -> str:
    """Convert canonical protein notation (p.X123Y) to key token (X123Y)."""
    normalized = normalize_protein(protein)
    return normalized[2:]


def normalize_cna_state(cna_state: str) -> str:
    """Normalize user-provided CNA state to model canonical values."""
    token = cna_state.strip().upper().replace(" ", "")
    if not token:
        raise ValueError("CNA state is required")
    canonical = CNA_ALIASES.get(token)
    if canonical is None:
        raise ValueError(
            "Unsupported CNA state. Use Amplification or DeepDeletion"
        )
    return canonical


def normalize_mutation_input(item: MutationInput) -> NormalizedAlteration:
    """Normalize a mutation alteration payload."""
    gene = normalize_gene(item.gene)
    if item.protein is None or not item.protein.strip():
        return NormalizedAlteration(kind="mutation", gene=gene)

    protein = normalize_protein(item.protein)
    return NormalizedAlteration(
        kind="mutation",
        gene=gene,
        protein=protein,
        protein_key=protein_to_key(protein),
    )


def normalize_cna_input(item: CnaInput) -> NormalizedAlteration:
    """Normalize a CNA alteration payload."""
    return NormalizedAlteration(
        kind="cna",
        gene=normalize_gene(item.gene),
        cna_state=normalize_cna_state(item.cna_state),
    )
