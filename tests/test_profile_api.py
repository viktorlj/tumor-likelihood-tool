"""Tests for tumor-type and gene profile API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create test client using real data artifacts."""
    data_dir = Path(__file__).resolve().parents[1] / "data"
    if not (data_dir / "evidence_tumor.parquet").exists():
        pytest.skip("Data artifacts not found; run build first")
    app = create_app(data_dir=data_dir)
    return TestClient(app)


class TestTumorProfileAPI:
    def test_valid_tumor_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_allele&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tumor_type"] == "LUNG"
        assert data["sample_count"] > 0
        assert data["evidence_type"] == "mutation_allele"
        assert len(data["items"]) <= 5
        assert data["total_significant"] > 0

    def test_items_have_required_fields(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_allele&limit=1")
        item = resp.json()["items"][0]
        assert "event_label" in item
        assert "gene" in item
        assert "fold_enrichment" in item
        assert "q_value" in item
        assert "affected_count" in item
        assert "group_total" in item
        assert "frequency_pct" in item
        assert "is_significant" in item

    def test_sort_by_frequency(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_allele&sort_by=frequency&limit=10")
        data = resp.json()
        assert data["sort_by"] == "frequency"
        freqs = [item["frequency_pct"] for item in data["items"]]
        assert freqs == sorted(freqs, reverse=True)

    def test_sort_by_qvalue(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_allele&sort_by=q_value&limit=10")
        data = resp.json()
        qvals = [item["q_value"] for item in data["items"]]
        assert qvals == sorted(qvals)

    def test_cna_evidence_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=cna&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_type"] == "cna"
        for item in data["items"]:
            assert item["cna_state"] in ("Amplification", "DeepDeletion")

    def test_gene_mutation_evidence_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_gene&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_type"] == "mutation_gene"

    def test_invalid_tumor_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/NONEXISTENT")
        assert resp.status_code == 404

    def test_invalid_evidence_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=invalid")
        assert resp.status_code == 422

    def test_invalid_sort_by(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?sort_by=invalid")
        assert resp.status_code == 422

    def test_subthreshold_toggle(self, client: TestClient) -> None:
        resp_sig = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_gene&limit=500")
        resp_all = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_gene&limit=500&include_subthreshold=true")
        # Including sub-threshold should return at least as many results
        assert len(resp_all.json()["items"]) >= len(resp_sig.json()["items"])

    def test_significance_filter(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tumor-profile/LUNG?evidence_type=mutation_allele&limit=50")
        for item in resp.json()["items"]:
            assert item["is_significant"] is True
            assert item["q_value"] < 0.05
            assert item["fold_enrichment"] > 1.0


class TestGeneProfileAPI:
    def test_valid_gene(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gene-profile/BRAF?evidence_type=mutation_gene&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gene"] == "BRAF"
        assert data["evidence_type"] == "mutation_gene"
        assert len(data["items"]) <= 5
        assert data["total_significant"] > 0

    def test_items_have_required_fields(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gene-profile/BRAF?evidence_type=mutation_gene&limit=1")
        item = resp.json()["items"][0]
        assert "class_name" in item
        assert "sample_count" in item
        assert "fold_enrichment" in item
        assert "q_value" in item
        assert "affected_count" in item
        assert "group_total" in item
        assert "frequency_pct" in item
        assert "is_significant" in item

    def test_case_insensitive_gene(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gene-profile/braf?evidence_type=mutation_gene")
        assert resp.status_code == 200
        assert resp.json()["gene"] == "BRAF"

    def test_allele_evidence_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gene-profile/BRAF?evidence_type=mutation_allele&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_type"] == "mutation_allele"

    def test_cna_evidence_type(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gene-profile/CDKN2A?evidence_type=cna&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_type"] == "cna"

    def test_nonexistent_gene(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gene-profile/ZZZZNOTREAL")
        assert resp.status_code == 404

    def test_sort_by_fold_enrichment(self, client: TestClient) -> None:
        resp = client.get("/api/v1/gene-profile/TP53?evidence_type=mutation_gene&sort_by=fold_enrichment&limit=50")
        data = resp.json()
        fes = [item["fold_enrichment"] for item in data["items"]]
        assert fes == sorted(fes, reverse=True)

    def test_braf_thyroid_melanoma(self, client: TestClient) -> None:
        """BRAF should be highly enriched in thyroid and melanoma."""
        resp = client.get("/api/v1/gene-profile/BRAF?evidence_type=mutation_gene&sort_by=fold_enrichment")
        data = resp.json()
        top_types = [item["class_name"] for item in data["items"][:3]]
        assert "THYROID" in top_types
        assert "SKIN_AND_MELANOMA" in top_types


class TestPageRoutes:
    def test_tumor_profile_page(self, client: TestClient) -> None:
        resp = client.get("/tumor-profile")
        assert resp.status_code == 200
        assert "Tumor-Type Profile" in resp.text
        assert "mp-nav" in resp.text

    def test_gene_profile_page(self, client: TestClient) -> None:
        resp = client.get("/gene-profile")
        assert resp.status_code == 200
        assert "Gene Profile" in resp.text
        assert "mp-nav" in resp.text

    def test_index_has_navbar(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "mp-nav" in resp.text

    def test_tutorial_has_navbar(self, client: TestClient) -> None:
        resp = client.get("/tutorial")
        assert resp.status_code == 200
        assert "mp-nav" in resp.text
