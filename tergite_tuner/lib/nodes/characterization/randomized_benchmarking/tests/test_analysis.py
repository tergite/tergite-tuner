# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2026
# (C) Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import pytest
import xarray as xr
from matplotlib import pyplot as plt

from tergite_tuner.lib.nodes.characterization.randomized_benchmarking.analysis import (
    RandomizedBenchmarkingQubitAnalysis,
)
from tergite_tuner.lib.run import get_element_s21s
from tergite_tuner.lib.spec import plot_class_analysis
from tergite_tuner.tests.utils.state import loaded_state

_STATE_FILENAME = "state-2026-03-10-21-33-32.json"


def _get_fits(node_data_dir, session_context) -> dict:
    with xr.open_dataset(
        node_data_dir / "dataset_randomized_benchmarking.hdf5"
    ) as data:
        s21s = get_element_s21s(data.load())
    return {
        qubit: RandomizedBenchmarkingQubitAnalysis(
            s21s[qubit], session_context
        ).analyse()
        for qubit in ("q11", "q15")
    }


def test_randomized_benchmarking_analysis(session_context, node_data_dir):
    with loaded_state(session_context, node_data_dir / _STATE_FILENAME):
        fits = _get_fits(node_data_dir, session_context)

    assert fits["q11"]["fidelity"].value == pytest.approx(0.99951747)
    assert fits["q11"]["leakage"].value == pytest.approx(0.00207032)
    assert fits["q15"]["fidelity"].value == pytest.approx(0.99788337)
    assert fits["q15"]["leakage"].value == pytest.approx(0.0064318)


def test_plotting(session_context, node_data_dir):
    with loaded_state(session_context, node_data_dir / _STATE_FILENAME):
        fits = _get_fits(node_data_dir, session_context)["q11"]
    figure, axis = plt.subplots()

    plot_class_analysis(axis, None, fits, session_context)

    assert axis.get_xlabel() == "number of cliffords"
    plt.close(figure)
