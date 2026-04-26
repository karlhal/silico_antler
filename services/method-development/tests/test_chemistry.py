from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.chemistry import (
    DEFAULT_FINGERPRINT_NUM_BITS,
    InvalidSmilesError,
    basic_descriptors,
    build_morgan_fingerprint,
    canonicalize_smiles,
    normalize_molecule,
    tanimoto_similarity,
)


def test_canonicalize_smiles_normalizes_equivalent_inputs() -> None:
    assert canonicalize_smiles("C(C)O") == canonicalize_smiles("CCO")


def test_canonicalize_smiles_rejects_invalid_smiles() -> None:
    with pytest.raises(InvalidSmilesError, match="Invalid SMILES"):
        canonicalize_smiles("not-a-smiles")


def test_canonicalize_smiles_rejects_empty_input() -> None:
    with pytest.raises(InvalidSmilesError, match="must not be empty"):
        canonicalize_smiles("   ")


def test_build_morgan_fingerprint_is_deterministic() -> None:
    left = build_morgan_fingerprint("CCO")
    right = build_morgan_fingerprint("C(C)O")

    assert left.radius == 2
    assert left.num_bits == DEFAULT_FINGERPRINT_NUM_BITS
    assert left.bitstring == right.bitstring
    assert left.on_bits == right.on_bits
    assert len(left.bitstring) == DEFAULT_FINGERPRINT_NUM_BITS


def test_basic_descriptors_return_expected_keys() -> None:
    descriptors = basic_descriptors("CCO")

    assert set(descriptors) == {
        "exact_mw",
        "logp",
        "tpsa",
        "h_bond_donors",
        "h_bond_acceptors",
    }
    assert descriptors["exact_mw"] > 0.0
    assert descriptors["tpsa"] >= 0.0


def test_normalize_molecule_returns_canonical_smiles_fingerprint_and_descriptors() -> (
    None
):
    normalized = normalize_molecule(" C(C)O ")

    assert normalized.input_smiles == "C(C)O"
    assert normalized.canonical_smiles == canonicalize_smiles("CCO")
    assert normalized.fingerprint.num_bits == DEFAULT_FINGERPRINT_NUM_BITS
    assert normalized.descriptors["exact_mw"] > 0.0


def test_tanimoto_similarity_is_one_for_equivalent_molecules() -> None:
    left = build_morgan_fingerprint("CCO")
    right = build_morgan_fingerprint("C(C)O")

    assert tanimoto_similarity(left, right) == pytest.approx(1.0)


def test_tanimoto_similarity_rejects_mismatched_fingerprint_shapes() -> None:
    left = build_morgan_fingerprint("CCO", num_bits=1024)
    right = build_morgan_fingerprint("CCO", num_bits=2048)

    with pytest.raises(ValueError, match="share radius and num_bits"):
        tanimoto_similarity(left, right)
