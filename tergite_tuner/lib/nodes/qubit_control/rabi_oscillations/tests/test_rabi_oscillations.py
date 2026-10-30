# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
# (C) Copyright Chalmers Next Labs AB 2026
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

from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations import (
    analysis as rabi_analysis,
)
from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.analysis import (
    analyse_rabi,
    plot_rabi,
)
from tergite_tuner.tests.utils.datasets import get_s21


@pytest.mark.parametrize(
    "file_name",
    ["dataset_rabi_oscillations_0.hdf5", "dataset_rabi_oscillations_12_0.hdf5"],
)
def test_analyse_rabi_fits_a_pi_amplitude(node_data_dir, file_name):
    fits = analyse_rabi(get_s21(node_data_dir / file_name, "q06"), None)

    assert 0 < fits["amp180"].value < rabi_analysis.MAX_PI_AMPLITUDE


def test_a_pi_amplitude_beyond_the_drive_fails_the_qubit(node_data_dir, monkeypatch):
    monkeypatch.setattr(rabi_analysis, "MAX_PI_AMPLITUDE", 0)
    s21 = get_s21(node_data_dir / "dataset_rabi_oscillations_0.hdf5", "q06")

    assert analyse_rabi(s21, None) is None


def test_plot_rabi_draws_the_fit_over_the_data(node_data_dir):
    s21 = get_s21(node_data_dir / "dataset_rabi_oscillations_0.hdf5", "q06")
    figure, axis = plt.subplots()

    plot_rabi(axis, s21, analyse_rabi(s21, None), None)

    assert len(axis.lines) == 2
    plt.close(figure)
