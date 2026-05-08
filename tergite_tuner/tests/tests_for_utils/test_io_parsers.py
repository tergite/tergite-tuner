# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests for :mod:`tergite_tuner.utils.io.parsers`.

These cover the small parser that turns user-typed qubit strings (e.g.
``"q01-q03,q07"``) into a sorted, deduplicated list. The function is
the input layer for several CLI helpers, so exercising the documented
shapes — single tokens, ranges, mixed lists, reversed ranges and
duplicates — is what keeps it correct.
"""

import pytest

from tergite_tuner.utils.io.parsers import parse_input_qubits


def test_parse_input_qubits_single_token():
    """A single qubit name parses to a one-element list."""
    assert parse_input_qubits("q01") == ["q01"]


def test_parse_input_qubits_simple_list():
    """Comma-separated tokens are returned in sorted order."""
    assert parse_input_qubits("q01,q02,q03,q04") == ["q01", "q02", "q03", "q04"]


def test_parse_input_qubits_simple_range():
    """A ``qXX-qYY`` range expands inclusively."""
    assert parse_input_qubits("q01-q03") == ["q01", "q02", "q03"]


def test_parse_input_qubits_mixed_lists_and_ranges():
    """The parser handles a mix of single tokens and ranges, with surrounding spaces."""
    assert parse_input_qubits("q01-q05, q08, q10, q12-q15") == [
        "q01",
        "q02",
        "q03",
        "q04",
        "q05",
        "q08",
        "q10",
        "q12",
        "q13",
        "q14",
        "q15",
    ]


def test_parse_input_qubits_reversed_range():
    """A reversed range (``q05-q01``) is normalised before expansion."""
    assert parse_input_qubits("q05-q01") == ["q01", "q02", "q03", "q04", "q05"]


def test_parse_input_qubits_deduplicates():
    """Repeated tokens are deduplicated."""
    assert parse_input_qubits("q01,q02,q01,q02") == ["q01", "q02"]


def test_parse_input_qubits_strips_whitespace():
    """Leading/trailing whitespace and stray spaces are tolerated."""
    assert parse_input_qubits("   q01,   q02   ") == ["q01", "q02"]


def test_parse_input_qubits_returns_sorted():
    """Output is sorted by the prefix and then numerically."""
    assert parse_input_qubits("q10,q02,q01") == ["q01", "q02", "q10"]


def test_parse_input_qubits_overlapping_ranges_dedupe():
    """Overlapping ranges produce the union, not duplicates."""
    assert parse_input_qubits("q01-q03,q02-q04") == ["q01", "q02", "q03", "q04"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("q01", ["q01"]),
        ("q01,q02", ["q01", "q02"]),
        ("q01-q02", ["q01", "q02"]),
    ],
)
def test_parse_input_qubits_parametrized(raw, expected):
    """Spot-check the simplest cases via parametrize."""
    assert parse_input_qubits(raw) == expected
