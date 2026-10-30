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

from tergite_tuner.lib.nodes.qubit_control.spectroscopy.analysis import (
    analyse_qubit_spectroscopy,
    plot_qubit_spectroscopy,
)
from tergite_tuner.tests.utils.datasets import get_s21


@pytest.mark.parametrize(
    "file_name",
    ["dataset_qubit_01_spectroscopy_0.hdf5", "dataset_qubit_12_spectroscopy_0.hdf5"],
)
def test_analysis_finds_the_strongest_peak(node_data_dir, file_name):
    fits = analyse_qubit_spectroscopy(get_s21(node_data_dir / file_name, "q06"), None)

    assert 3e9 < fits["frequency"].value < 6e9
    assert fits["amplitude"].value > 0


def test_plot_marks_the_peak(node_data_dir):
    s21 = get_s21(node_data_dir / "dataset_qubit_01_spectroscopy_0.hdf5", "q06")
    figure, axis = plt.subplots()

    plot_qubit_spectroscopy(axis, s21, analyse_qubit_spectroscopy(s21, None), None)

    assert axis.collections
    plt.close(figure)
