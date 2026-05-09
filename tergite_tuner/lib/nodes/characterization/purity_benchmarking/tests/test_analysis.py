# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
# (C) Copyright Michele Faucci Giannelli 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from pathlib import Path

import numpy as np
import xarray as xr
from lmfit.model import ModelResult
from matplotlib.figure import Figure

from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.nodes.characterization.purity_benchmarking.analysis import (
    PurityBenchmarkingQubitAnalysis,
)

_HDF_FILENAME = "dataset_purity_benchmarking_0.hdf5"


def test_initialization(node_data_dir):
    file_path = node_data_dir / _HDF_FILENAME
    with xr.open_dataset(file_path) as dataset:
        analysis = PurityBenchmarkingQubitAnalysis(
            "name", ["purity_fidelity"], session=SessionContext()
        )
        analysis.process_qubit(dataset, "yq06")
        # Check that the analysis object has the expected attributes
        assert hasattr(analysis, "purity_results_dict")
        assert hasattr(analysis, "normalized_data_dict")

        assert analysis.number_of_repetitions == dataset.sizes.get("seed", 1)


def test_run_fitting(node_data_dir):
    file_path = node_data_dir / _HDF_FILENAME
    with xr.open_dataset(file_path) as dataset:
        analysis = PurityBenchmarkingQubitAnalysis(
            "name", ["purity_fidelity"], session=SessionContext()
        )
        analysis.process_qubit(dataset, "yq06")
        # Verify the average purity result is within the expected range

        assert 0.7 < np.average(list(analysis.purity_results_dict.values())) < 0.8

        # Trim the dataset to only 5 Cliffords before running the fitting so it will fit the model
        analysis.number_of_cliffords = analysis.number_of_cliffords[:5]
        for key in analysis.purity_results_dict.keys():
            analysis.purity_results_dict[key] = analysis.purity_results_dict[key][:5]
        qoi = analysis.analyse_qubit()

        fidelity = qoi.analysis_result["purity_fidelity"]["value"]

        # Verify that the fitting results are valid
        assert isinstance(fidelity, float)
        assert fidelity > 0.99
        assert 0 <= fidelity <= 1.002
        assert isinstance(analysis.fit_results, ModelResult)


def test_plotter(node_data_dir):
    file_path = node_data_dir / _HDF_FILENAME
    with xr.open_dataset(file_path) as dataset:
        analysis = PurityBenchmarkingQubitAnalysis(
            "name", ["purity_fidelity"], session=SessionContext()
        )
        analysis.process_qubit(dataset, "yq14")

        # Trim the dataset to only 5 Cliffords before plotting, same reason as above
        analysis.number_of_cliffords = analysis.number_of_cliffords[:5]
        for key in analysis.purity_results_dict.keys():
            analysis.purity_results_dict[key] = analysis.purity_results_dict[key][:5]

        analysis.analyse_qubit()
        fig = Figure()
        ax = fig.subplots()
        analysis.plotter(ax)

        # Check that three lines were plotted (data and fit)
        assert len(ax.lines) == 3
