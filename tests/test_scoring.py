from __future__ import annotations

from app.schemas import CnaInput, MutationInput
from app.scoring import TumorLikelihoodModel


def test_allele_event_prefers_allele_level(synthetic_data_dir) -> None:
    model = TumorLikelihoodModel.from_data_dir(synthetic_data_dir)
    response = model.predict(
        alterations=[MutationInput(gene="BRAF", protein="p.V600E")],
        top_k=2,
        include_evidence=True,
    )

    detailed_top = response["results"]["detailed"]["rankings"][0]
    assert detailed_top["class_name"] == "A"
    assert detailed_top["posterior"] > 0.75


def test_gene_fallback_when_allele_missing(synthetic_data_dir) -> None:
    model = TumorLikelihoodModel.from_data_dir(synthetic_data_dir)
    response = model.predict(
        alterations=[MutationInput(gene="BRAF", protein="p.K601E")],
        top_k=2,
        include_evidence=True,
    )

    assert any("used gene-level evidence" in note for note in response["notes"])
    tumor_top = response["results"]["tumor"]["rankings"][0]
    assert tumor_top["class_name"] == "T2"


def test_pair_evidence_only_for_tumor_level(synthetic_data_dir) -> None:
    model = TumorLikelihoodModel.from_data_dir(synthetic_data_dir)
    response = model.predict(
        alterations=[
            MutationInput(gene="BRAF", protein="p.K601E"),
            CnaInput(gene="CDKN2A", cna_state="DeepDeletion"),
        ],
        top_k=2,
        include_evidence=True,
    )

    tumor_terms = response["results"]["tumor"]["rankings"][0]["evidence_terms"]
    detailed_terms = response["results"]["detailed"]["rankings"][0]["evidence_terms"]

    assert any(term["evidence_type"] == "pair_mut_del" for term in tumor_terms)
    assert not any(term["evidence_type"].startswith("pair_") for term in detailed_terms)
