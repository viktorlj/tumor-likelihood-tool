from __future__ import annotations

import pytest

from app.parser import (
    normalize_cna_state,
    normalize_gene,
    normalize_protein,
    protein_to_key,
)


def test_normalize_gene() -> None:
    assert normalize_gene(" braf ") == "BRAF"


def test_normalize_protein_variants() -> None:
    assert normalize_protein("p.v600e") == "p.V600E"
    assert normalize_protein("V600E") == "p.V600E"
    assert protein_to_key("p.v600e") == "V600E"


def test_normalize_protein_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_protein("BRAF")


def test_normalize_cna_aliases() -> None:
    assert normalize_cna_state("amp") == "Amplification"
    assert normalize_cna_state("deep_deletion") == "DeepDeletion"
