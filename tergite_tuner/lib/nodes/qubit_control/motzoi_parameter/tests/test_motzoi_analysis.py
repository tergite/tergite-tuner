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

from tergite_tuner.lib.nodes.qubit_control.motzoi_parameter.analysis import (
    analyse_motzoi,
    plot_motzoi,
)
from tergite_tuner.tests.utils.datasets import get_s21


@pytest.mark.parametrize(
    "name, expected",
    [
        ("motzoi_parameter", {"q13": 0.023076923077, "q15": -0.0923076923077}),
        ("motzoi_12_parameter", {"q13": 0.12, "q15": -0.036}),
    ],
)
def test_motzoi_is_least_summed_over_repetitions(node_data_dir, name, expected):
    for qubit, motzoi in expected.items():
        s21 = get_s21(node_data_dir / f"dataset_{name}.hdf5", qubit)

        assert analyse_motzoi(s21, None)["motzoi"].value == pytest.approx(motzoi)


def test_plot_motzoi_marks_the_optimum(node_data_dir):
    s21 = get_s21(node_data_dir / "dataset_motzoi_parameter.hdf5", "q13")
    fits = analyse_motzoi(s21, None)
    figure, axis = plt.subplots()

    plot_motzoi(axis, s21, fits, None)

    assert axis.lines[-1].get_xdata()[0] == fits["motzoi"].value
    plt.close(figure)
