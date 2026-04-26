from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
from rdkit.DataStructs.cDataStructs import ExplicitBitVect

DEFAULT_FINGERPRINT_RADIUS = 2
DEFAULT_FINGERPRINT_NUM_BITS = 2048


class InvalidSmilesError(ValueError):
    pass


@dataclass(frozen=True)
class MoleculeFingerprint:
    radius: int
    num_bits: int
    bitstring: str
    on_bits: tuple[int, ...]


@dataclass(frozen=True)
class NormalizedMolecule:
    input_smiles: str
    canonical_smiles: str
    fingerprint: MoleculeFingerprint
    descriptors: dict[str, float]


def canonicalize_smiles(smiles: str) -> str:
    mol = mol_from_smiles(smiles)
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)


def mol_from_smiles(smiles: str) -> Chem.Mol:
    cleaned = smiles.strip()
    if not cleaned:
        raise InvalidSmilesError("SMILES must not be empty")

    mol = Chem.MolFromSmiles(cleaned)
    if mol is None:
        raise InvalidSmilesError(f"Invalid SMILES: {cleaned}")
    return mol


def build_morgan_fingerprint(
    smiles: str,
    *,
    radius: int = DEFAULT_FINGERPRINT_RADIUS,
    num_bits: int = DEFAULT_FINGERPRINT_NUM_BITS,
) -> MoleculeFingerprint:
    mol = mol_from_smiles(smiles)
    bit_vector = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=num_bits)
    return _fingerprint_from_bit_vector(bit_vector, radius=radius, num_bits=num_bits)


def basic_descriptors(smiles: str) -> dict[str, float]:
    mol = mol_from_smiles(smiles)
    return {
        "exact_mw": float(rdMolDescriptors.CalcExactMolWt(mol)),
        "logp": float(Descriptors.MolLogP(mol)),
        "tpsa": float(rdMolDescriptors.CalcTPSA(mol)),
        "h_bond_donors": float(rdMolDescriptors.CalcNumHBD(mol)),
        "h_bond_acceptors": float(rdMolDescriptors.CalcNumHBA(mol)),
    }


def normalize_molecule(
    smiles: str,
    *,
    radius: int = DEFAULT_FINGERPRINT_RADIUS,
    num_bits: int = DEFAULT_FINGERPRINT_NUM_BITS,
) -> NormalizedMolecule:
    cleaned = smiles.strip()
    canonical_smiles = canonicalize_smiles(cleaned)
    fingerprint = build_morgan_fingerprint(
        canonical_smiles,
        radius=radius,
        num_bits=num_bits,
    )
    descriptors = basic_descriptors(canonical_smiles)
    return NormalizedMolecule(
        input_smiles=cleaned,
        canonical_smiles=canonical_smiles,
        fingerprint=fingerprint,
        descriptors=descriptors,
    )


def tanimoto_similarity(left: MoleculeFingerprint, right: MoleculeFingerprint) -> float:
    if left.radius != right.radius or left.num_bits != right.num_bits:
        raise ValueError("Fingerprints must share radius and num_bits")

    left_vector = _bit_vector_from_bitstring(left.bitstring)
    right_vector = _bit_vector_from_bitstring(right.bitstring)
    return float(DataStructs.TanimotoSimilarity(left_vector, right_vector))


def _fingerprint_from_bit_vector(
    bit_vector: ExplicitBitVect,
    *,
    radius: int,
    num_bits: int,
) -> MoleculeFingerprint:
    on_bits = tuple(int(bit) for bit in bit_vector.GetOnBits())
    return MoleculeFingerprint(
        radius=radius,
        num_bits=num_bits,
        bitstring=bit_vector.ToBitString(),
        on_bits=on_bits,
    )


def _bit_vector_from_bitstring(bitstring: str) -> ExplicitBitVect:
    bit_vector = ExplicitBitVect(len(bitstring))
    for index, bit in enumerate(bitstring):
        if bit == "1":
            bit_vector.SetBit(index)
    return bit_vector
