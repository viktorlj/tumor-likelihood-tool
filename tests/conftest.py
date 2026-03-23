from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest


@pytest.fixture()
def synthetic_data_dir(tmp_path: Path) -> Path:
    priors_detailed = {
        "level": "detailed",
        "class_column": "CANCER_TYPE_DETAILED",
        "total_samples": 100,
        "classes": [
            {"class_name": "A", "sample_count": 70, "prior_probability": 0.7},
            {"class_name": "B", "sample_count": 30, "prior_probability": 0.3},
        ],
    }
    priors_tumor = {
        "level": "tumor",
        "class_column": "TUMOR_TYPE",
        "total_samples": 100,
        "classes": [
            {"class_name": "T1", "sample_count": 60, "prior_probability": 0.6},
            {"class_name": "T2", "sample_count": 40, "prior_probability": 0.4},
        ],
    }

    detailed_rows = [
        {
            "event_id": "MUT_ALLELE|BRAF|V600E",
            "event_label": "BRAF p.V600E",
            "evidence_type": "mutation_allele",
            "class_name": "A",
            "fold_enrichment": 7.389,
            "log_bf": 2.0,
            "p_value": 0.001,
            "q_value": 0.01,
            "affected_count": 45,
            "group_total": 70,
            "gene": "BRAF",
            "protein_key": "V600E",
            "cna_state": None,
            "pair_type": None,
            "gene1": None,
            "gene2": None,
        },
        {
            "event_id": "MUT_GENE|BRAF",
            "event_label": "BRAF mutation",
            "evidence_type": "mutation_gene",
            "class_name": "B",
            "fold_enrichment": 2.718,
            "log_bf": 1.0,
            "p_value": 0.01,
            "q_value": 0.05,
            "affected_count": 10,
            "group_total": 30,
            "gene": "BRAF",
            "protein_key": None,
            "cna_state": None,
            "pair_type": None,
            "gene1": None,
            "gene2": None,
        },
        {
            "event_id": "CNA|CDKN2A|DEL",
            "event_label": "CDKN2A DeepDeletion",
            "evidence_type": "cna",
            "class_name": "B",
            "fold_enrichment": 4.481,
            "log_bf": 1.5,
            "p_value": 0.01,
            "q_value": 0.05,
            "affected_count": 8,
            "group_total": 30,
            "gene": "CDKN2A",
            "protein_key": None,
            "cna_state": "DeepDeletion",
            "pair_type": None,
            "gene1": None,
            "gene2": None,
        },
    ]

    tumor_rows = [
        {
            "event_id": "MUT_ALLELE|BRAF|V600E",
            "event_label": "BRAF p.V600E",
            "evidence_type": "mutation_allele",
            "class_name": "T1",
            "fold_enrichment": 4.481,
            "log_bf": 1.5,
            "p_value": 0.001,
            "q_value": 0.01,
            "affected_count": 30,
            "group_total": 60,
            "gene": "BRAF",
            "protein_key": "V600E",
            "cna_state": None,
            "pair_type": None,
            "gene1": None,
            "gene2": None,
        },
        {
            "event_id": "MUT_GENE|BRAF",
            "event_label": "BRAF mutation",
            "evidence_type": "mutation_gene",
            "class_name": "T2",
            "fold_enrichment": 148.413,
            "log_bf": 5.0,
            "p_value": 0.01,
            "q_value": 0.05,
            "affected_count": 35,
            "group_total": 40,
            "gene": "BRAF",
            "protein_key": None,
            "cna_state": None,
            "pair_type": None,
            "gene1": None,
            "gene2": None,
        },
        {
            "event_id": "CNA|CDKN2A|DEL",
            "event_label": "CDKN2A DeepDeletion",
            "evidence_type": "cna",
            "class_name": "T2",
            "fold_enrichment": 2.226,
            "log_bf": 0.8,
            "p_value": 0.01,
            "q_value": 0.05,
            "affected_count": 12,
            "group_total": 40,
            "gene": "CDKN2A",
            "protein_key": None,
            "cna_state": "DeepDeletion",
            "pair_type": None,
            "gene1": None,
            "gene2": None,
        },
        {
            "event_id": "PAIR|MUT_DEL|BRAF|CDKN2A",
            "event_label": "BRAF mutation + CDKN2A deep-del",
            "evidence_type": "pair_mut_del",
            "class_name": "T2",
            "fold_enrichment": 7.389,
            "log_bf": 2.0,
            "p_value": 0.001,
            "q_value": 0.01,
            "affected_count": 5,
            "group_total": 40,
            "gene": None,
            "protein_key": None,
            "cna_state": None,
            "pair_type": "Mutation×DeepDeletion",
            "gene1": "BRAF",
            "gene2": "CDKN2A",
        },
    ]

    tumor_mapping = {
        "T1": ["A"],
        "T2": ["B"],
    }

    (tmp_path / "priors_detailed.json").write_text(json.dumps(priors_detailed))
    (tmp_path / "priors_tumor.json").write_text(json.dumps(priors_tumor))
    (tmp_path / "tumor_mapping.json").write_text(json.dumps(tumor_mapping))
    (tmp_path / "build_manifest.json").write_text(
        json.dumps({"model_version": "test-model"})
    )

    pl.DataFrame(detailed_rows).write_parquet(tmp_path / "evidence_detailed.parquet")
    pl.DataFrame(tumor_rows).write_parquet(tmp_path / "evidence_tumor.parquet")

    return tmp_path
