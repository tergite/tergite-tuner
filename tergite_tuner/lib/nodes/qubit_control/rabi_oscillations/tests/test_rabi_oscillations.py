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
import os

import xarray as xr
from matplotlib import pyplot as plt

from conftest import node_data_dir
from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.analysis import (
    Rabi12QubitAnalysis,
    RabiQubitAnalysis,
)
from tergite_tuner.utils.types.qoi import QOI


def test_setup_rabi_oscillations_01(node_data_dir):
    file_path = node_data_dir / "dataset_rabi_oscillations_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = RabiQubitAnalysis("name", ["rxy:amp180"], session=SessionContext())

        qoi = analysis.process_qubit(dataset, "yq06")
        result_values = qoi.analysis_result
        assert isinstance(qoi, QOI)
        for quantity in result_values:
            assert isinstance(result_values[quantity]["value"], float)
        assert (
            len(result_values) == 1
        ), f"The dataset should contain one element {len(dataset)}"


def test_setup_rabi_oscillations_12(node_data_dir):
    file_path = node_data_dir / "dataset_rabi_oscillations_12_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = Rabi12QubitAnalysis(
            "name", ["r12:ef_amp180"], session=SessionContext()
        )

        qoi = analysis.process_qubit(dataset, "yq06")
        result_values = qoi.analysis_result
        assert isinstance(qoi, QOI)
        for quantity in result_values:
            assert isinstance(result_values[quantity]["value"], float)
        assert (
            len(result_values) == 1
        ), f"The dataset should contain one element {len(dataset)}"


def test_run_fitting_rabi_oscillations_01(node_data_dir):
    file_path = node_data_dir / "dataset_rabi_oscillations_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = RabiQubitAnalysis("name", ["rxy:amp180"], session=SessionContext())
        qoi = analysis.process_qubit(dataset, "yq06")
        amplitude = qoi.analysis_result["rxy:amp180"]["value"]

        assert amplitude > 0, "Amplitude has to be higher than 0"


def test_run_fitting_rabi_oscillations_12(node_data_dir):
    file_path = node_data_dir / "dataset_rabi_oscillations_12_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = Rabi12QubitAnalysis(
            "name", ["r12:ef_amp180"], session=SessionContext()
        )
        qoi = analysis.process_qubit(dataset, "yq06")
        amplitude = qoi.analysis_result["r12:ef_amp180"]["value"]

        assert amplitude > 0, f"Amplitude has to be higher than 0: {amplitude}"


def test_plotting_rabi_oscillations_01(node_data_dir):
    file_path = node_data_dir / "dataset_rabi_oscillations_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = RabiQubitAnalysis(
            "name",
            ["rxy:amp180"],
            session=SessionContext(
                data_dir=node_data_dir,
                log_dir=node_data_dir,
            ),
        )
        analysis.process_qubit(dataset, "yq06")
        figure_path = node_data_dir / "Rabi_oscillations_01_q06.png"
        figure_path.unlink(missing_ok=True)

        fig, ax = plt.subplots()
        analysis.plotter(ax)
        fig.savefig(figure_path)
        plt.close(fig)
        assert (
            figure_path.exists()
        ), f"Expected plot file to be created at {figure_path}"


def test_plotting_rabi_oscillations_12(node_data_dir):
    file_path = node_data_dir / "dataset_rabi_oscillations_12_0.hdf5"
    with xr.open_dataset(file_path) as file:
        analysis = Rabi12QubitAnalysis(
            "name", ["r12:ef_amp180"], session=SessionContext()
        )
        analysis.process_qubit(file, "yq06")
        figure_path = node_data_dir / "Rabi_oscillations_12_q06.png"
        figure_path.unlink(missing_ok=True)

        fig, ax = plt.subplots()
        analysis.plotter(ax)
        fig.savefig(figure_path)
        plt.close(fig)
        assert os.path.exists(
            figure_path
        ), f"Expected plot file to be created at {figure_path}"
