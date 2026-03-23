"""Build compact webapp indices from enrichment result tables.

Usage:
    source .venv/bin/activate
    python webapp/scripts/build_indices.py
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

FE_EPSILON = 1e-6
FE_MAX = 1e6


@dataclass(frozen=True)
class SourcePaths:
    """Input paths used for artifact generation."""

    clinical: Path
    mut_allele_detailed: Path
    mut_gene_detailed: Path
    cna_detailed: Path
    mut_allele_tumor: Path
    mut_gene_tumor: Path
    cna_tumor: Path
    pair_mut_mut_tumor: Path
    pair_mut_amp_tumor: Path
    pair_mut_del_tumor: Path


def _infer_paths(root: Path) -> SourcePaths:
    results = root / "results"
    return SourcePaths(
        clinical=results / "selection_output" / "clinical_samples_grouped.csv",
        mut_allele_detailed=(
            results
            / "mutation_enrichment"
            / "by_cancer_type_detailed"
            / "allele_enrichment_all.csv"
        ),
        mut_gene_detailed=(
            results
            / "mutation_enrichment"
            / "by_cancer_type_detailed"
            / "gene_enrichment_all.csv"
        ),
        cna_detailed=(
            results
            / "cna_enrichment"
            / "by_cancer_type_detailed"
            / "cna_enrichment_all.csv"
        ),
        mut_allele_tumor=(
            results / "mutation_enrichment" / "by_tumor_type" / "allele_enrichment_all.csv"
        ),
        mut_gene_tumor=(
            results / "mutation_enrichment" / "by_tumor_type" / "gene_enrichment_all.csv"
        ),
        cna_tumor=(
            results / "cna_enrichment" / "by_tumor_type" / "cna_enrichment_all.csv"
        ),
        pair_mut_mut_tumor=(
            results / "genepair_enrichment" / "by_tumor_type" / "genepair_mut_mut_all.csv"
        ),
        pair_mut_amp_tumor=(
            results / "genepair_enrichment" / "by_tumor_type" / "genepair_mut_amp_all.csv"
        ),
        pair_mut_del_tumor=(
            results / "genepair_enrichment" / "by_tumor_type" / "genepair_mut_del_all.csv"
        ),
    )


def _require_files(paths: SourcePaths) -> None:
    missing = [str(path) for path in paths.__dict__.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required input files: {', '.join(missing)}")


def _fold_expr() -> pl.Expr:
    return pl.col("Fold_Enrichment").cast(pl.Float64).clip(FE_EPSILON, FE_MAX)


def _log_bf_expr() -> pl.Expr:
    return _fold_expr().log()


def _protein_key_expr() -> pl.Expr:
    return (
        pl.col("HGVSp_Short")
        .cast(pl.Utf8)
        .str.strip_chars()
        .str.to_uppercase()
        .str.replace(r"^P\.", "")
    )


def _gene_expr(column: str) -> pl.Expr:
    return pl.col(column).cast(pl.Utf8).str.strip_chars().str.to_uppercase()


def _class_expr() -> pl.Expr:
    return pl.col("Group").cast(pl.Utf8)


def _base_event_columns(
    event_id: pl.Expr,
    event_label: pl.Expr,
    evidence_type: str,
    gene: pl.Expr,
    protein_key: pl.Expr | None,
    cna_state: pl.Expr | None,
    pair_type: pl.Expr | None,
    gene1: pl.Expr | None,
    gene2: pl.Expr | None,
    affected_count: pl.Expr | None = None,
    group_total: pl.Expr | None = None,
) -> list[pl.Expr]:
    return [
        event_id.alias("event_id"),
        event_label.alias("event_label"),
        pl.lit(evidence_type).alias("evidence_type"),
        _class_expr().alias("class_name"),
        _fold_expr().alias("fold_enrichment"),
        _log_bf_expr().alias("log_bf"),
        pl.col("P_Value").cast(pl.Float64).alias("p_value"),
        pl.col("Q_Value").cast(pl.Float64).alias("q_value"),
        (affected_count if affected_count is not None else pl.lit(None, dtype=pl.Int64)).alias(
            "affected_count"
        ),
        (group_total if group_total is not None else pl.lit(None, dtype=pl.Int64)).alias(
            "group_total"
        ),
        gene.alias("gene"),
        (protein_key if protein_key is not None else pl.lit(None, dtype=pl.String)).alias(
            "protein_key"
        ),
        (cna_state if cna_state is not None else pl.lit(None, dtype=pl.String)).alias(
            "cna_state"
        ),
        (pair_type if pair_type is not None else pl.lit(None, dtype=pl.String)).alias(
            "pair_type"
        ),
        (gene1 if gene1 is not None else pl.lit(None, dtype=pl.String)).alias("gene1"),
        (gene2 if gene2 is not None else pl.lit(None, dtype=pl.String)).alias("gene2"),
    ]


def _mutation_allele_events(path: Path) -> pl.LazyFrame:
    gene = _gene_expr("Hugo_Symbol")
    protein_key = _protein_key_expr()
    event_id = pl.concat_str([pl.lit("MUT_ALLELE|"), gene, pl.lit("|"), protein_key])
    event_label = pl.concat_str([gene, pl.lit(" p."), protein_key])

    return (
        pl.scan_csv(path)
        .filter(
            pl.col("HGVSp_Short").is_not_null()
            & (pl.col("HGVSp_Short").cast(pl.Utf8).str.strip_chars().str.len_chars() > 0)
            & (pl.col("Fold_Enrichment").cast(pl.Float64) > 0)
        )
        .select(
            _base_event_columns(
                event_id=event_id,
                event_label=event_label,
                evidence_type="mutation_allele",
                gene=gene,
                protein_key=protein_key,
                cna_state=None,
                pair_type=None,
                gene1=None,
                gene2=None,
                affected_count=pl.col("Mutation_Count").cast(pl.Int64),
                group_total=pl.col("Group_Sample_Count").cast(pl.Int64),
            )
        )
    )


def _mutation_gene_events(path: Path) -> pl.LazyFrame:
    gene = _gene_expr("Gene")
    event_id = pl.concat_str([pl.lit("MUT_GENE|"), gene])
    event_label = pl.concat_str([gene, pl.lit(" mutation")])

    return (
        pl.scan_csv(path)
        .filter(pl.col("Fold_Enrichment").cast(pl.Float64) > 0)
        .select(
            _base_event_columns(
                event_id=event_id,
                event_label=event_label,
                evidence_type="mutation_gene",
                gene=gene,
                protein_key=None,
                cna_state=None,
                pair_type=None,
                gene1=None,
                gene2=None,
                affected_count=pl.col("Mutated_Samples").cast(pl.Int64),
                group_total=pl.col("Total_Samples_Group").cast(pl.Int64),
            )
        )
    )


def _cna_events(path: Path) -> pl.LazyFrame:
    gene = _gene_expr("Hugo_Symbol")
    cna_state = pl.col("CNA_Type").cast(pl.Utf8).str.strip_chars()
    cna_token = (
        pl.when(cna_state == "Amplification")
        .then(pl.lit("AMP"))
        .when(cna_state == "DeepDeletion")
        .then(pl.lit("DEL"))
        .otherwise(pl.lit(""))
    )
    event_id = pl.concat_str([pl.lit("CNA|"), gene, pl.lit("|"), cna_token])
    event_label = pl.concat_str([gene, pl.lit(" "), cna_state])

    return (
        pl.scan_csv(path)
        .filter(cna_state.is_in(["Amplification", "DeepDeletion"]))
        .filter(pl.col("Fold_Enrichment").cast(pl.Float64) > 0)
        .select(
            _base_event_columns(
                event_id=event_id,
                event_label=event_label,
                evidence_type="cna",
                gene=gene,
                protein_key=None,
                cna_state=cna_state,
                pair_type=None,
                gene1=None,
                gene2=None,
                affected_count=pl.col("CNA_Count").cast(pl.Int64),
                group_total=pl.col("Group_Sample_Count").cast(pl.Int64),
            )
        )
    )


def _pair_mut_mut_events(path: Path) -> pl.LazyFrame:
    gene1 = _gene_expr("Gene1")
    gene2 = _gene_expr("Gene2")
    g_lo = pl.min_horizontal(gene1, gene2)
    g_hi = pl.max_horizontal(gene1, gene2)

    event_id = pl.concat_str([pl.lit("PAIR|MUT_MUT|"), g_lo, pl.lit("|"), g_hi])
    event_label = pl.concat_str([g_lo, pl.lit(" + "), g_hi, pl.lit(" (mut-mut)")])

    return (
        pl.scan_csv(path)
        .filter(pl.col("Fold_Enrichment").cast(pl.Float64) > 0)
        .select(
            _base_event_columns(
                event_id=event_id,
                event_label=event_label,
                evidence_type="pair_mut_mut",
                gene=pl.lit(None, dtype=pl.String),
                protein_key=None,
                cna_state=None,
                pair_type=pl.lit("Mutation×Mutation"),
                gene1=g_lo,
                gene2=g_hi,
                affected_count=pl.col("Pair_Count_Group").cast(pl.Int64),
                group_total=pl.col("Group_Sample_Count").cast(pl.Int64),
            )
        )
    )


def _pair_mut_amp_events(path: Path) -> pl.LazyFrame:
    gene1 = _gene_expr("Gene1")
    gene2 = _gene_expr("Gene2")
    event_id = pl.concat_str([pl.lit("PAIR|MUT_AMP|"), gene1, pl.lit("|"), gene2])
    event_label = pl.concat_str([gene1, pl.lit(" mutation + "), gene2, pl.lit(" amp")])

    return (
        pl.scan_csv(path)
        .filter(pl.col("Fold_Enrichment").cast(pl.Float64) > 0)
        .select(
            _base_event_columns(
                event_id=event_id,
                event_label=event_label,
                evidence_type="pair_mut_amp",
                gene=pl.lit(None, dtype=pl.String),
                protein_key=None,
                cna_state=None,
                pair_type=pl.lit("Mutation×Amplification"),
                gene1=gene1,
                gene2=gene2,
                affected_count=pl.col("Pair_Count_Group").cast(pl.Int64),
                group_total=pl.col("Group_Sample_Count").cast(pl.Int64),
            )
        )
    )


def _pair_mut_del_events(path: Path) -> pl.LazyFrame:
    gene1 = _gene_expr("Gene1")
    gene2 = _gene_expr("Gene2")
    event_id = pl.concat_str([pl.lit("PAIR|MUT_DEL|"), gene1, pl.lit("|"), gene2])
    event_label = pl.concat_str([gene1, pl.lit(" mutation + "), gene2, pl.lit(" deep-del")])

    return (
        pl.scan_csv(path)
        .filter(pl.col("Fold_Enrichment").cast(pl.Float64) > 0)
        .select(
            _base_event_columns(
                event_id=event_id,
                event_label=event_label,
                evidence_type="pair_mut_del",
                gene=pl.lit(None, dtype=pl.String),
                protein_key=None,
                cna_state=None,
                pair_type=pl.lit("Mutation×DeepDeletion"),
                gene1=gene1,
                gene2=gene2,
                affected_count=pl.col("Pair_Count_Group").cast(pl.Int64),
                group_total=pl.col("Group_Sample_Count").cast(pl.Int64),
            )
        )
    )


def _collect_evidence(frames: list[pl.LazyFrame]) -> pl.DataFrame:
    evidence_df = pl.concat(frames, how="vertical_relaxed").collect(engine="streaming")
    return evidence_df.unique(subset=["event_id", "class_name"], keep="first")


def _build_priors(
    clinical_path: Path,
    class_column: str,
    level: str,
    exclude_blank: bool,
) -> dict[str, object]:
    clinical = pl.read_csv(clinical_path)
    class_expr = pl.col(class_column).cast(pl.Utf8).str.strip_chars()

    if exclude_blank:
        clinical = clinical.filter(class_expr.is_not_null() & (class_expr != ""))
    else:
        clinical = clinical.filter(class_expr.is_not_null())

    counts = (
        clinical.group_by(class_column)
        .agg(pl.len().alias("sample_count"))
        .sort("sample_count", descending=True)
    )

    total = int(counts["sample_count"].sum())
    classes: list[dict[str, object]] = []

    for row in counts.iter_rows(named=True):
        class_name = str(row[class_column]).strip()
        if exclude_blank and not class_name:
            continue

        sample_count = int(row["sample_count"])
        prior_probability = sample_count / total
        classes.append(
            {
                "class_name": class_name,
                "sample_count": sample_count,
                "prior_probability": prior_probability,
            }
        )

    return {
        "level": level,
        "class_column": class_column,
        "total_samples": total,
        "classes": classes,
    }


def _build_tumor_mapping(clinical_path: Path) -> dict[str, list[str]]:
    """Map each TUMOR_TYPE to its CANCER_TYPE_DETAILED subtypes, sorted by sample count."""
    clinical = pl.read_csv(clinical_path)
    clinical = clinical.filter(
        pl.col("TUMOR_TYPE").cast(pl.Utf8).str.strip_chars().is_not_null()
        & (pl.col("TUMOR_TYPE").cast(pl.Utf8).str.strip_chars() != "")
    )

    counts = (
        clinical.group_by(["TUMOR_TYPE", "CANCER_TYPE_DETAILED"])
        .agg(pl.len().alias("n"))
        .sort("n", descending=True)
    )

    mapping: dict[str, list[str]] = {}
    for row in counts.iter_rows(named=True):
        tumor = str(row["TUMOR_TYPE"]).strip()
        detailed = str(row["CANCER_TYPE_DETAILED"]).strip()
        if tumor and detailed:
            mapping.setdefault(tumor, []).append(detailed)

    return mapping


def _build_event_catalog(
    detailed_df: pl.DataFrame,
    tumor_df: pl.DataFrame,
) -> dict[str, object]:
    combined = pl.concat(
        [
            detailed_df.with_columns(pl.lit("detailed").alias("level")),
            tumor_df.with_columns(pl.lit("tumor").alias("level")),
        ],
        how="vertical_relaxed",
    )

    mutation_genes = (
        combined.filter(pl.col("evidence_type").is_in(["mutation_allele", "mutation_gene"]))
        .select(pl.col("gene"))
        .drop_nulls()
        .unique()
        .sort("gene")
        .get_column("gene")
        .to_list()
    )

    cna_genes = (
        combined.filter(pl.col("evidence_type") == "cna")
        .select(pl.col("gene"))
        .drop_nulls()
        .unique()
        .sort("gene")
        .get_column("gene")
        .to_list()
    )

    protein_keys = (
        combined.filter(pl.col("evidence_type") == "mutation_allele")
        .select(pl.col("protein_key"))
        .drop_nulls()
        .unique()
        .sort("protein_key")
        .head(500)
        .get_column("protein_key")
        .to_list()
    )

    return {
        "supported_cna_states": ["Amplification", "DeepDeletion"],
        "mutation_genes": mutation_genes,
        "cna_genes": cna_genes,
        "example_protein_keys": protein_keys,
        "event_counts": {
            "detailed": int(detailed_df.height),
            "tumor": int(tumor_df.height),
        },
    }


def build_indices(output_dir: Path, root: Path) -> dict[str, object]:
    """Build all artifact files and return summary metadata."""
    paths = _infer_paths(root)
    _require_files(paths)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] Building priors...")
    priors_detailed = _build_priors(
        clinical_path=paths.clinical,
        class_column="CANCER_TYPE_DETAILED",
        level="detailed",
        exclude_blank=False,
    )
    priors_tumor = _build_priors(
        clinical_path=paths.clinical,
        class_column="TUMOR_TYPE",
        level="tumor",
        exclude_blank=True,
    )

    print("[2/5] Building detailed evidence table...")
    detailed_df = _collect_evidence(
        [
            _mutation_allele_events(paths.mut_allele_detailed),
            _mutation_gene_events(paths.mut_gene_detailed),
            _cna_events(paths.cna_detailed),
        ]
    )

    print("[3/5] Building tumor evidence table...")
    tumor_df = _collect_evidence(
        [
            _mutation_allele_events(paths.mut_allele_tumor),
            _mutation_gene_events(paths.mut_gene_tumor),
            _cna_events(paths.cna_tumor),
            _pair_mut_mut_events(paths.pair_mut_mut_tumor),
            _pair_mut_amp_events(paths.pair_mut_amp_tumor),
            _pair_mut_del_events(paths.pair_mut_del_tumor),
        ]
    )

    print("[4/6] Building event catalog...")
    event_catalog = _build_event_catalog(detailed_df=detailed_df, tumor_df=tumor_df)

    print("[5/6] Building tumor type mapping...")
    tumor_mapping = _build_tumor_mapping(paths.clinical)

    print("[6/6] Writing artifacts...")
    (output_dir / "priors_detailed.json").write_text(
        json.dumps(priors_detailed, indent=2)
    )
    (output_dir / "priors_tumor.json").write_text(json.dumps(priors_tumor, indent=2))

    detailed_df.write_parquet(output_dir / "evidence_detailed.parquet", compression="zstd")
    tumor_df.write_parquet(output_dir / "evidence_tumor.parquet", compression="zstd")

    (output_dir / "event_catalog.json").write_text(json.dumps(event_catalog, indent=2))
    (output_dir / "tumor_mapping.json").write_text(json.dumps(tumor_mapping, indent=2))

    manifest = {
        "model_version": f"genie-webapp-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {name: str(path) for name, path in paths.__dict__.items()},
        "rows": {
            "evidence_detailed": int(detailed_df.height),
            "evidence_tumor": int(tumor_df.height),
            "priors_detailed_classes": len(priors_detailed["classes"]),
            "priors_tumor_classes": len(priors_tumor["classes"]),
        },
    }
    (output_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2))

    return manifest


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build webapp lookup indices")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("webapp/data"),
        help="Directory for generated artifacts",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Project root path",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    manifest = build_indices(output_dir=args.output_dir, root=args.root)
    print("Build complete")
    print(json.dumps(manifest["rows"], indent=2))


if __name__ == "__main__":
    main()
