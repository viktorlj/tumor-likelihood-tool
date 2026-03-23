from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.scoring import TumorLikelihoodModel


def test_meta_and_prediction_endpoints(synthetic_data_dir) -> None:
    model = TumorLikelihoodModel.from_data_dir(synthetic_data_dir)
    app = create_app(data_dir=synthetic_data_dir, model=model)
    client = TestClient(app)

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.json()["model_version"] == "test-model"

    payload = {
        "alterations": [
            {"kind": "mutation", "gene": "BRAF", "protein": "p.K601E"},
            {"kind": "cna", "gene": "CDKN2A", "cna_state": "DeepDeletion"},
        ],
        "options": {"return_top_k": 2, "include_evidence": True},
    }
    response = client.post("/api/v1/predict", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "detailed" in body["results"]
    assert "tumor" in body["results"]
    assert body["results"]["tumor"]["rankings"][0]["class_name"] == "T2"
