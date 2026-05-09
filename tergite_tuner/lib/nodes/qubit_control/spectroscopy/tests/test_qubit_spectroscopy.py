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

import numpy as np
import xarray as xr
from matplotlib import pyplot as plt

from conftest import node_data_dir
from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.analysis import (
    QubitSpectroscopy12MultidimAnalysis,
    QubitSpectroscopyMultidimAnalysis,
)
from tergite_tuner.utils.types.qoi import QOI


def test_setup_qubit_01_spectroscopy(node_data_dir):
    """Can set up qubit 01 spectroscopy"""
    file_path = node_data_dir / "dataset_qubit_01_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = QubitSpectroscopyMultidimAnalysis(
            "name",
            ["clock_freqs:f01", "spec:spec_ampl_optimal"],
            session=SessionContext(),
        )

        qoi = analysis.process_qubit(dataset, "yq06")
        result_values = qoi.analysis_result
        assert isinstance(qoi, QOI)

        for quantity in result_values:
            assert isinstance(result_values[quantity]["value"], np.float64)
        assert (
            len(result_values) == 2
        ), f"The dataset should contain one element {len(dataset)}"


def test_setup_qubit_12_spectroscopy(node_data_dir):
    file_path = node_data_dir / "dataset_qubit_12_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as file:
        analysis = QubitSpectroscopy12MultidimAnalysis(
            "name",
            ["clock_freqs:f12", "spec:spec_ampl_12_optimal"],
            session=SessionContext(),
        )
        qoi = analysis.process_qubit(file, "yq06")
        result_values = qoi.analysis_result
        assert isinstance(qoi, QOI)

        for quantity in result_values:
            assert isinstance(result_values[quantity]["value"], np.float64)
        assert (
            len(result_values) == 2
        ), f"The dataset should contain one element {len(file)}"


def test_run_fitting_qubit_01_spectroscopy(node_data_dir):
    file_path = node_data_dir / "dataset_qubit_01_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as file:
        analysis = QubitSpectroscopyMultidimAnalysis(
            "name",
            ["clock_freqs:f01", "spec:spec_ampl_optimal"],
            session=SessionContext(),
        )
        qoi = analysis.process_qubit(file, "yq06")
        frequency = qoi.analysis_result["clock_freqs:f01"]["value"]
        amplitude = qoi.analysis_result["spec:spec_ampl_optimal"]["value"]

        assert (
            3e9 < frequency < 6e9
        ), f"Frequency should be between 4 GHz and 6 GHz, got {frequency}"
        assert amplitude > 0, "Amplitude has to be higher than 0"


def test_run_fitting_qubit_12_spectroscopy(node_data_dir):
    file_path = node_data_dir / "dataset_qubit_12_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as file:
        analysis = QubitSpectroscopy12MultidimAnalysis(
            "name",
            ["clock_freqs:f12", "spec:spec_ampl_12_optimal"],
            session=SessionContext(),
        )
        qoi = analysis.process_qubit(file, "yq06")
        frequency = qoi.analysis_result["clock_freqs:f12"]["value"]
        amplitude = qoi.analysis_result["spec:spec_ampl_12_optimal"]["value"]

        assert (
            3e9 < frequency < 6e9
        ), f"Frequency should be between 4 GHz and 6 GHz, got {frequency}"
        assert amplitude > 0, "Amplitude has to be higher than 0"


def test_plotting_01(node_data_dir):
    file_path = node_data_dir / "dataset_qubit_01_spectroscopy_0.hdf5"

    with xr.open_dataset(file_path) as dataset:
        analysis = QubitSpectroscopyMultidimAnalysis(
            "name",
            ["clock_freqs:f01", "spec:spec_ampl_optimal"],
            session=SessionContext(
                data_dir=node_data_dir,
                log_dir=node_data_dir,
            ),
        )
        analysis.process_qubit(dataset, "yq06")
        figure_path = node_data_dir / "Qubit_spectroscopy_01_q06.png"
        figure_path.unlink(missing_ok=True)

        fig, ax = plt.subplots()
        analysis.plotter(ax)
        fig.savefig(figure_path)
        plt.close(fig)
        assert (
            figure_path.exists()
        ), f"Expected plot file to be created at {figure_path}"


def test_plotting_12(node_data_dir):
    file_path = node_data_dir / "dataset_qubit_12_spectroscopy_0.hdf5"

    with xr.open_dataset(file_path) as dataset:
        analysis = QubitSpectroscopy12MultidimAnalysis(
            "name",
            ["clock_freqs:f12", "spec:spec_ampl_12_optimal"],
            session=SessionContext(
                data_dir=node_data_dir,
                log_dir=node_data_dir,
            ),
        )
        analysis.process_qubit(dataset, "yq06")
        figure_path = node_data_dir / "Qubit_spectroscopy_12_q06.png"
        figure_path.unlink(missing_ok=True)

        fig, ax = plt.subplots()
        analysis.plotter(ax)
        fig.savefig(figure_path)
        plt.close(fig)
        assert (
            figure_path.exists()
        ), f"Expected plot file to be created at {figure_path}"
