# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou  2026
# (C) Chalmers Next Labs AB 2026
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
from matplotlib import pyplot as plt

from tergite_tuner.lib.nodes.readout.ro_frequency_optimization.analysis import (
    analyse_ro_frequency,
    plot_three_state_ro_frequency,
    plot_two_state_ro_frequency,
)
from tergite_tuner.tests.utils.datasets import get_s21

DATASET = "dataset_ro_frequency_three_state_optimization.hdf5"


@pytest.mark.parametrize(
    "qubit, frequency", [("q13", 7181088888.888889), ("q15", 7128822222.222222)]
)
def test_three_states_are_furthest_apart_at_the_frequency(
    node_data_dir, qubit, frequency
):
    fits = analyse_ro_frequency(get_s21(node_data_dir / DATASET, qubit), None)

    assert fits["frequency"].value == pytest.approx(frequency)


def test_two_states_are_furthest_apart_at_the_frequency(node_data_dir):
    s21 = get_s21(node_data_dir / DATASET, "q13").sel(qubit_statesq13=[0, 1])

    fits = analyse_ro_frequency(s21, None)

    distance = np.abs(s21.sel(qubit_statesq13=1) - s21.sel(qubit_statesq13=0))
    assert fits["frequency"].value == distance.idxmax().item()


def test_plots_mark_the_frequency(node_data_dir):
    s21 = get_s21(node_data_dir / DATASET, "q13")
    two_state_s21 = s21.sel(qubit_statesq13=[0, 1])
    figure, axes = plt.subplots(4)

    plot_three_state_ro_frequency(axes[0], s21, analyse_ro_frequency(s21, None), None)
    plot_two_state_ro_frequency(
        axes[1:], two_state_s21, analyse_ro_frequency(two_state_s21, None), None
    )

    assert axes[0].collections and axes[1].collections
    plt.close(figure)
