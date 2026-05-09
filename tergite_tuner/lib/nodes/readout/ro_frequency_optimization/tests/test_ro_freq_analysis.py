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
import xarray as xr

from tergite_tuner.lib.base.utils.analysis_utils import filter_ds_by_element
from tergite_tuner.lib.nodes.readout.ro_frequency_optimization.analysis import (
    ROFrequencyThreeStateNodeAnalysis,
    ROFrequencyThreeStateQubitAnalysis,
)


def test_ro_freq_3states(seeded_redis, session_context, node_data_dir):
    name = "ro_frequency_three_state_optimization"
    file_path = node_data_dir / f"dataset_{name}.hdf5"
    with xr.open_dataset(file_path) as full_dataset:
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


def test_plotting(seeded_redis, session_context, node_data_dir):
    """
    Test that the plotter produces a figure with the right number of axes
    """
    name = "ro_frequency_three_state_optimization"
    qubit_qois = ["extended_clock_freqs:readout_3state_opt"]

    analysis = ROFrequencyThreeStateNodeAnalysis(
        name, qubit_qois, session=session_context
    )
    analysis.analyze_node(node_data_dir, save_plot=True)
    number_of_qubits = len(analysis.dataset.attrs["elements"])
    assert analysis.axs.shape == (1, number_of_qubits)
