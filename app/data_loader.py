"""Load and structure model artifacts produced by the webapp build script."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class EventContribution:
    """Sparse event contribution values for class scores."""

    event_id: str
    event_label: str
    evidence_type: str
    metadata: dict[str, str | None]
    class_indices: tuple[int, ...]
    class_log_bfs: tuple[float, ...]
    class_fold_enrichments: tuple[float, ...]
    class_affected_counts: tuple[int, ...]
    class_group_totals: tuple[int, ...]


@dataclass(frozen=True)
class LevelArtifacts:
    """All scoring artifacts for one classification level."""

    level: str
    classes: list[str]
    prior_probabilities: list[float]
    prior_log_probabilities: list[float]
    sample_counts: list[int]
    events: dict[str, EventContribution]

    @property
    def class_to_index(self) -> dict[str, int]:
        """Map class names to their array index."""
        return {name: idx for idx, name in enumerate(self.classes)}


@dataclass(frozen=True)
class ModelArtifacts:
    """In-memory model object shared by API handlers."""

    model_version: str
    levels: dict[str, LevelArtifacts]
    tumor_to_detailed: dict[str, list[str]]


def _load_prior_file(path: Path) -> LevelArtifacts:
    payload = json.loads(path.read_text())
    classes: list[str] = []
    priors: list[float] = []
    prior_logs: list[float] = []
    sample_counts: list[int] = []

    for item in payload["classes"]:
        class_name = str(item["class_name"])
        prior = float(item["prior_probability"])
        sample_count = int(item["sample_count"])

        classes.append(class_name)
        priors.append(prior)
        prior_logs.append(math.log(prior))
        sample_counts.append(sample_count)

    return LevelArtifacts(
        level=payload["level"],
        classes=classes,
        prior_probabilities=priors,
        prior_log_probabilities=prior_logs,
        sample_counts=sample_counts,
        events={},
    )


def _load_event_file(path: Path, level_artifacts: LevelArtifacts) -> dict[str, EventContribution]:
    df = pl.read_parquet(path)
    class_to_index = level_artifacts.class_to_index

    bucket: dict[str, dict[str, object]] = {}
    for row in df.iter_rows(named=True):
        class_name = str(row["class_name"])
        class_idx = class_to_index.get(class_name)
        if class_idx is None:
            continue

        event_id = str(row["event_id"])
        entry = bucket.get(event_id)
        if entry is None:
            entry = {
                "event_id": event_id,
                "event_label": str(row["event_label"]),
                "evidence_type": str(row["evidence_type"]),
                "metadata": {
                    "gene": row.get("gene"),
                    "protein_key": row.get("protein_key"),
                    "cna_state": row.get("cna_state"),
                    "pair_type": row.get("pair_type"),
                    "gene1": row.get("gene1"),
                    "gene2": row.get("gene2"),
                },
                "indices": [],
                "log_bfs": [],
                "fold_enrichments": [],
                "affected_counts": [],
                "group_totals": [],
            }
            bucket[event_id] = entry

        entry["indices"].append(class_idx)
        entry["log_bfs"].append(float(row["log_bf"]))
        entry["fold_enrichments"].append(float(row.get("fold_enrichment", 0.0)))
        raw_ac = row.get("affected_count")
        raw_gt = row.get("group_total")
        entry["affected_counts"].append(int(raw_ac) if raw_ac is not None else 0)
        entry["group_totals"].append(int(raw_gt) if raw_gt is not None else 0)

    events: dict[str, EventContribution] = {}
    for event_id, entry in bucket.items():
        events[event_id] = EventContribution(
            event_id=event_id,
            event_label=entry["event_label"],
            evidence_type=entry["evidence_type"],
            metadata=entry["metadata"],
            class_indices=tuple(entry["indices"]),
            class_log_bfs=tuple(entry["log_bfs"]),
            class_fold_enrichments=tuple(entry["fold_enrichments"]),
            class_affected_counts=tuple(entry["affected_counts"]),
            class_group_totals=tuple(entry["group_totals"]),
        )

    return events


def load_model_artifacts(data_dir: Path) -> ModelArtifacts:
    """Load model priors/evidence from the build output directory."""
    manifest_path = data_dir / "build_manifest.json"
    prior_detailed_path = data_dir / "priors_detailed.json"
    prior_tumor_path = data_dir / "priors_tumor.json"
    evidence_detailed_path = data_dir / "evidence_detailed.parquet"
    evidence_tumor_path = data_dir / "evidence_tumor.parquet"
    tumor_mapping_path = data_dir / "tumor_mapping.json"

    required = [
        manifest_path,
        prior_detailed_path,
        prior_tumor_path,
        evidence_detailed_path,
        evidence_tumor_path,
        tumor_mapping_path,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing webapp model artifacts. Run `python webapp/scripts/build_indices.py` first. "
            f"Missing: {', '.join(missing)}"
        )

    manifest = json.loads(manifest_path.read_text())
    tumor_to_detailed: dict[str, list[str]] = json.loads(tumor_mapping_path.read_text())

    detailed_level = _load_prior_file(prior_detailed_path)
    tumor_level = _load_prior_file(prior_tumor_path)

    detailed_events = _load_event_file(evidence_detailed_path, detailed_level)
    tumor_events = _load_event_file(evidence_tumor_path, tumor_level)

    detailed_level = LevelArtifacts(
        level=detailed_level.level,
        classes=detailed_level.classes,
        prior_probabilities=detailed_level.prior_probabilities,
        prior_log_probabilities=detailed_level.prior_log_probabilities,
        sample_counts=detailed_level.sample_counts,
        events=detailed_events,
    )
    tumor_level = LevelArtifacts(
        level=tumor_level.level,
        classes=tumor_level.classes,
        prior_probabilities=tumor_level.prior_probabilities,
        prior_log_probabilities=tumor_level.prior_log_probabilities,
        sample_counts=tumor_level.sample_counts,
        events=tumor_events,
    )

    return ModelArtifacts(
        model_version=str(manifest.get("model_version", "unknown")),
        levels={
            "detailed": detailed_level,
            "tumor": tumor_level,
        },
        tumor_to_detailed=tumor_to_detailed,
    )
