# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
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

from conftest import node_data_dir
from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.analysis import (
    ResonatorSpectroscopyQubitAnalysis,
)
from tergite_tuner.utils.dto.qoi import QOI


def test_resonator_spectroscopy_setup(node_data_dir):
    file_path = node_data_dir / "dataset_resonator_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = ResonatorSpectroscopyQubitAnalysis(
            "name",
            ["clock_freqs:readout", "Ql", "resonator_minimum"],
            session=SessionContext(data_dir=node_data_dir, log_dir=node_data_dir),
        )
        qoi = analysis.process_qubit(dataset, "yq06")
        result_values = qoi.analysis_result

        assert isinstance(qoi, QOI)
        for quantity in result_values:
            assert isinstance(result_values[quantity]["value"], float)
        assert (
            len(result_values) == 3
        ), f"The dataset should contain three elements {len(dataset)}"


def test_run_fitting(node_data_dir):
    file_path = node_data_dir / "dataset_resonator_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = ResonatorSpectroscopyQubitAnalysis(
            "name",
            ["clock_freqs:readout", "Ql", "resonator_minimum"],
            session=SessionContext(data_dir=node_data_dir, log_dir=node_data_dir),
        )
        qoi = analysis.process_qubit(dataset, "yq06")
        minimum_freq = qoi.analysis_result["clock_freqs:readout"]["value"]
        fit_Ql = qoi.analysis_result["Ql"]["value"]
        min_freq_data = qoi.analysis_result["resonator_minimum"]["value"]

        assert (
            6e9 < minimum_freq < 8e9
        ), f"Minimum frequency should be between 6 GHz and 8 GHz, got {minimum_freq}"
        assert fit_Ql > 0, f"Fit Ql should be a positive value, got {fit_Ql}"
        assert min_freq_data == pytest.approx(
            minimum_freq, rel=1e3
        ), f"The both frequencies should be close to each other {minimum_freq} {min_freq_data}"


def test_plotting(node_data_dir):
    file_path = node_data_dir / "dataset_resonator_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = ResonatorSpectroscopyQubitAnalysis(
            "name",
            ["clock_freqs:readout", "Ql", "resonator_minimum"],
            session=SessionContext(data_dir=node_data_dir, log_dir=node_data_dir),
        )
        analysis.process_qubit(dataset, "yq06")
        figure_path = node_data_dir / "Resonator_spectroscopy_q06.png"
        figure_path.unlink(missing_ok=True)

        fig, ax = plt.subplots()
        analysis.plotter(ax)
        fig.savefig(figure_path)
        plt.close(fig)

        assert figure_path.exists()
