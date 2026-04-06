"""Polars query functions for tumor-type and gene profile browsing views.

Uses lazy parquet scans so evidence DataFrames are never held in memory.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

VALID_EVIDENCE_TYPES = {"mutation_allele", "mutation_gene", "cna"}
VALID_SORT_OPTIONS = {"fold_enrichment", "frequency", "q_value"}

SIG_Q_THRESHOLD = 0.05
SIG_FE_THRESHOLD = 1.0
MIN_GROUP_TOTAL = 100


def query_tumor_profile(
    parquet_path: Path,
    tumor_type: str,
    evidence_type: str = "mutation_allele",
    sort_by: str = "fold_enrichment",
    limit: int = 50,
    include_subthreshold: bool = False,
) -> tuple[list[dict], int]:
    """Return top enrichment events for a specific tumor type.

    Returns (items, total_significant) where items is a list of dicts
    and total_significant is the count of significant events before limiting.
    """
    base_filter = (
        (pl.col("class_name") == tumor_type)
        & (pl.col("evidence_type") == evidence_type)
    )
    if evidence_type in ("mutation_allele", "mutation_gene"):
        base_filter = base_filter & (pl.col("group_total") >= MIN_GROUP_TOTAL)

    result = pl.scan_parquet(parquet_path).filter(base_filter).collect()

    result = result.with_columns(
        (pl.col("affected_count") / pl.col("group_total") * 100)
        .round(2)
        .alias("frequency_pct"),
        (
            (pl.col("q_value") < SIG_Q_THRESHOLD)
            & (pl.col("fold_enrichment") > SIG_FE_THRESHOLD)
        ).alias("is_significant"),
    )

    total_significant = result.filter(pl.col("is_significant")).height

    if not include_subthreshold:
        result = result.filter(pl.col("is_significant"))

    if sort_by == "frequency":
        result = result.sort("frequency_pct", descending=True)
    elif sort_by == "q_value":
        result = result.sort("q_value", descending=False)
    else:
        result = result.sort("fold_enrichment", descending=True)

    result = result.head(limit)

    columns = [
        "event_label", "gene", "protein_key", "cna_state",
        "fold_enrichment", "q_value", "affected_count", "group_total",
        "frequency_pct", "log_bf", "is_significant",
    ]
    return result.select(columns).to_dicts(), total_significant


def query_gene_profile(
    parquet_path: Path,
    gene: str,
    evidence_type: str = "mutation_gene",
    sort_by: str = "fold_enrichment",
    limit: int = 50,
    include_subthreshold: bool = False,
) -> tuple[list[dict], int]:
    """Return enrichment data for a specific gene across all tumor types.

    Returns (items, total_results) where items is a list of dicts
    and total_results is the count of significant results before limiting.
    """
    base_filter = (
        (pl.col("gene") == gene)
        & (pl.col("evidence_type") == evidence_type)
    )
    if evidence_type in ("mutation_allele", "mutation_gene"):
        base_filter = base_filter & (pl.col("group_total") >= MIN_GROUP_TOTAL)

    result = pl.scan_parquet(parquet_path).filter(base_filter).collect()

    result = result.with_columns(
        (pl.col("affected_count") / pl.col("group_total") * 100)
        .round(2)
        .alias("frequency_pct"),
        (
            (pl.col("q_value") < SIG_Q_THRESHOLD)
            & (pl.col("fold_enrichment") > SIG_FE_THRESHOLD)
        ).alias("is_significant"),
    )

    total_significant = result.filter(pl.col("is_significant")).height

    if not include_subthreshold:
        result = result.filter(pl.col("is_significant"))

    if sort_by == "frequency":
        result = result.sort("frequency_pct", descending=True)
    elif sort_by == "q_value":
        result = result.sort("q_value", descending=False)
    else:
        result = result.sort("fold_enrichment", descending=True)

    result = result.head(limit)

    columns = [
        "class_name", "event_label", "protein_key", "cna_state",
        "fold_enrichment", "q_value", "affected_count", "group_total",
        "frequency_pct", "log_bf", "is_significant",
    ]
    return result.select(columns).to_dicts(), total_significant


def get_gene_list(parquet_path: Path) -> list[str]:
    """Return sorted list of unique gene symbols in the evidence data."""
    return sorted(
        pl.scan_parquet(parquet_path)
        .filter(
            pl.col("evidence_type").is_in(["mutation_allele", "mutation_gene", "cna"])
        )
        .select("gene")
        .drop_nulls()
        .unique()
        .collect()
        .to_series()
        .to_list()
    )
