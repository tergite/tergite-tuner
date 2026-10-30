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

from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.analysis import (
    analyse_n_rabi,
    plot_n_rabi,
)
from tergite_tuner.tests.utils.datasets import get_s21


@pytest.mark.usefixtures("seeded_state")
@pytest.mark.parametrize(
    "name, amp180_field, expected",
    [
        (
            "n_rabi_oscillations",
            "rxy:amp180",
            {"q13": 0.7426703675, "q15": 0.412374722},
        ),
        (
            "n_rabi_oscillations_12",
            "r12:ef_amp180",
            {"q13": 0.7386446057, "q15": 0.179989095140},
        ),
    ],
)
def test_n_rabi_corrects_the_stored_amplitude(
    session_context, node_data_dir, name, amp180_field, expected
):
    for qubit, amp180 in expected.items():
        s21 = get_s21(node_data_dir / f"dataset_{name}.hdf5", qubit)

        fits = analyse_n_rabi(s21, session_context, amp180_field=amp180_field)

        assert fits["amp180"].value == pytest.approx(amp180)


@pytest.mark.usefixtures("seeded_state")
def test_plot_n_rabi_marks_the_correction(session_context, node_data_dir):
    s21 = get_s21(node_data_dir / "dataset_n_rabi_oscillations.hdf5", "q13")
    fits = analyse_n_rabi(s21, session_context, amp180_field="rxy:amp180")
    figure, axis = plt.subplots()

    plot_n_rabi(axis, s21, fits, session_context)

    assert axis.lines[-1].get_xdata()[0] == fits["correction"].value
    plt.close(figure)
