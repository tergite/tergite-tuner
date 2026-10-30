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

import pytest
from matplotlib import pyplot as plt

from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.analysis import (
    analyse_three_state_ro_amplitude,
    plot_ro_amplitude,
)
from tergite_tuner.tests.utils.datasets import get_s21

DATASET = "dataset_ro_amplitude_three_state_optimization.hdf5"
EXPECTED = {
    "q13": {
        "measure_3state_opt:pulse_amp": 0.04369655,
        "centroid_I": -0.0166358284,
        "centroid_Q": 0.01054417388,
        "omega_01": 48.533332544,
        "omega_12": 289.04966963,
        "omega_20": 158.9517810,
    },
    "q15": {
        "measure_3state_opt:pulse_amp": 0.0403862069,
        "centroid_I": 0.01131925,
        "centroid_Q": 0.01364486,
        "omega_01": 274.3834996,
        "omega_12": 156.0215330,
        "omega_20": 10.16925296,
    },
}


@pytest.mark.parametrize("qubit", EXPECTED)
def test_three_state_boundaries_at_the_best_amplitude(node_data_dir, qubit):
    fits = analyse_three_state_ro_amplitude(
        get_s21(node_data_dir / DATASET, qubit), None
    )

    assert {field: fits[field].value for field in EXPECTED[qubit]} == pytest.approx(
        EXPECTED[qubit]
    )


def test_plot_draws_fidelity_shots_and_confusion_matrix(node_data_dir):
    s21 = get_s21(node_data_dir / DATASET, "q13")
    figure, axes = plt.subplots(3)

    plot_ro_amplitude(axes, s21, analyse_three_state_ro_amplitude(s21, None), None)

    assert axes[0].lines and axes[1].collections and axes[2].images
    plt.close(figure)
