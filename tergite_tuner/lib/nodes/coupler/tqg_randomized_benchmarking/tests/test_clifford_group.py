# This code is part of Tergite
#
# Copyright (C) Pontus Vikstål 2025
# Copyright (C) Chalmers Next Labs 2025


import numpy as np
import pytest

from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.utils.clifford_group import (
    SingleQubitClifford,
    TwoQubitClifford,
)

_CLASSES = [SingleQubitClifford, TwoQubitClifford]


@pytest.fixture(scope="module")
def cleared_clifford_caches():
    """Clear caches before tests"""
    SingleQubitClifford.CLIFFORD_HASH_TABLE.clear()
    TwoQubitClifford.CLIFFORD_HASH_TABLE.clear()
    TwoQubitClifford._PTM_CACHE.clear()
    TwoQubitClifford._GATE_DECOMP_CACHE.clear()
    yield [SingleQubitClifford, TwoQubitClifford]


@pytest.mark.parametrize("cls", _CLASSES)
def test_clifford_equality(cleared_clifford_caches, cls):
    c1 = cls(5)
    c2 = cls(5)
    c3 = cls(6)

    assert c1 == c2, f"{cls.__name__}s with the same index should be equal"
    assert c1 != c3, f"{cls.__name__}s with different indices should not be equal"


@pytest.mark.parametrize("cls", _CLASSES)
def test_identity_clifford(cleared_clifford_caches, cls):
    ptm = cls(0).pauli_transfer_matrix
    size = ptm.shape[0]
    eye = np.identity(size)
    assert np.array_equal(
        eye, ptm
    ), f"The identity {cls.__name__} should have an identity PTM"


@pytest.mark.parametrize("cls", _CLASSES)
def test_get_inverse(cleared_clifford_caches, cls):
    idx = 10  # arbitrary index
    c = cls(idx)
    c_inv = c.get_inverse()
    # Check that the inverse is correct up to a global-phase
    c_eye = c_inv * c  # this should be the identity
    eye = cls(0)  # This should be the identity
    assert (
        c_eye == eye
    ), f"The product of a {cls.__name__} and its inverse should be the identity"


def test_two_qubit_clifford_caching(cleared_clifford_caches):
    """Test that the PTM and gate decomposition caches are shared between instances.
    This is only used for TwoQubitClifford, as SingleQubitClifford does not have a cache.
    """
    CliffordClass = TwoQubitClifford

    idx1, idx2 = 3, 5  # arbitrary indices

    # Compute PTMs
    c1_ptm = CliffordClass(idx=idx1).pauli_transfer_matrix
    assert idx1 in CliffordClass._PTM_CACHE
    np.testing.assert_array_equal(c1_ptm, CliffordClass._PTM_CACHE[idx1])

    # Check that the instances share the same cache
    c2 = CliffordClass(idx=idx2)
    np.testing.assert_array_equal(c2._PTM_CACHE[idx1], c1_ptm)

    # Compute gate decomposition
    decomp1 = CliffordClass(idx=idx1).gate_decomposition
    assert idx1 in CliffordClass._GATE_DECOMP_CACHE
    assert decomp1 == CliffordClass._GATE_DECOMP_CACHE[idx1]

    # Check that a new instance shares the same cache
    decomp2 = CliffordClass(idx=idx2)
    assert decomp2._GATE_DECOMP_CACHE[idx1] == decomp1


@pytest.mark.parametrize("cls", _CLASSES)
def test_hash_table_generation(cleared_clifford_caches, cls):
    idx = 5  # Some arbitrary Clifford idx
    c = cls(idx)
    ptm = c.pauli_transfer_matrix

    # Trigger hash table population
    c.find_clifford_index(ptm)

    # Check if the hash table was correctly populated
    hash_value = c._hash_matrix(ptm)
    # Assert that the hash value is in the hash table
    assert hash_value in cls.CLIFFORD_HASH_TABLE
    # Assert that the index in the hash table matches the original index
    assert cls.CLIFFORD_HASH_TABLE[hash_value] == idx
