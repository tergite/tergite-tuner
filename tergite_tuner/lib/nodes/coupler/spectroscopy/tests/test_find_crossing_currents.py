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
import numpy as np
import pytest

from tergite_tuner.lib.nodes.coupler.spectroscopy.analysis import (
    find_crossing_currents,
)

CURRENTS = np.arange(10) * 1e-4


def test_a_jump_across_a_dropout_is_one_crossing():
    frequencies = [4e9] * 4 + [0, 0] + [4.1e9] * 4
    crossings = find_crossing_currents(CURRENTS, frequencies)
    assert crossings == pytest.approx([np.mean(CURRENTS[3:7])])


def test_a_single_dropout_between_close_neighbours_is_filled():
    frequencies = [4e9] * 4 + [0] + [4e9] * 5
    assert find_crossing_currents(CURRENTS, frequencies) == []


def test_undetected_frequencies_are_dropped():
    frequencies = [4e9] * 4 + [np.nan] + [4.1e9] * 5
    crossings = find_crossing_currents(CURRENTS, frequencies)
    assert crossings == pytest.approx([np.mean(CURRENTS[[3, 5]])])


def test_a_crossing_near_a_resonator_crossing_is_dropped():
    frequencies = [4e9] * 4 + [0, 0] + [4.1e9] * 4
    crossings = find_crossing_currents(
        CURRENTS, frequencies, resonator_crossings=[4.5e-4]
    )
    assert crossings == []
