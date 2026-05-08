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

import os
from pathlib import Path

import pytest
import xarray as xr

from tergite_tuner.lib.base.utils.analysis_utils import filter_ds_by_element
from tergite_tuner.lib.nodes.readout.ro_frequency_optimization.analysis import (
    ROFrequencyThreeStateNodeAnalysis,
    ROFrequencyThreeStateQubitAnalysis,
)
from tergite_tuner.tests.utils.decorators import loaded_redis

_test_data_dir = os.path.join(
    Path(__file__).parent.parent.parent.parent, "data", "single_qubits_run"
)
_redis_values = os.path.join(_test_data_dir, "redis-single-qubits-run.json")


def test_ro_freq_3states(redis_connection, session_context):
    with loaded_redis(redis_connection, _redis_values):
        name = "ro_frequency_three_state_optimization"
        file_path = os.path.join(_test_data_dir, name, f"dataset_{name}.hdf5")
        full_dataset = xr.open_dataset(file_path)
        qubit_qois = ["extended_clock_freqs:readout_3state_opt"]

        ds_13 = filter_ds_by_element(full_dataset, "q13")
        ds_15 = filter_ds_by_element(full_dataset, "q15")

        analysis = ROFrequencyThreeStateQubitAnalysis(
            name, qubit_qois, session=session_context
        )
        analysis.S21 = ds_13.isel(ReIm=0) + 1j * ds_13.isel(ReIm=1)
        analysis.data_var = "yq13"
        qoi = analysis.analyse_qubit()

        ro_frequency = qoi.analysis_result["extended_clock_freqs:readout_3state_opt"][
            "value"
        ]

        assert qoi.analysis_successful
        assert pytest.approx(ro_frequency) == 7181088888.888889

        analysis.S21 = ds_15.isel(ReIm=0) + 1j * ds_15.isel(ReIm=1)
        analysis.data_var = "yq15"
        qoi = analysis.analyse_qubit()

        ro_frequency = qoi.analysis_result["extended_clock_freqs:readout_3state_opt"][
            "value"
        ]

        assert qoi.analysis_successful
        assert pytest.approx(ro_frequency) == 7128822222.222222


def test_plotting(redis_connection, session_context):
    """
    Test that the plotter produces a figure with the right number of axes
    """
    with loaded_redis(redis_connection, _redis_values):
        name = "ro_frequency_three_state_optimization"
        file_path = Path(_test_data_dir, name)
        qubit_qois = ["extended_clock_freqs:readout_3state_opt"]

        try:
            analysis = ROFrequencyThreeStateNodeAnalysis(
                name, qubit_qois, session=session_context
            )
            analysis.analyze_node(file_path, save_plot=True)
            number_of_qubits = len(analysis.dataset.attrs["elements"])
            assert analysis.axs.shape == (1, number_of_qubits)
        finally:
            (file_path / f"{name}.png").unlink(missing_ok=True)
            (file_path / f"{name}_preview.png").unlink(missing_ok=True)
