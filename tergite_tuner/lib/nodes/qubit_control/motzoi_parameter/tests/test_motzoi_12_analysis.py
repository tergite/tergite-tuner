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

import numpy as np
import pytest
import xarray as xr

from tergite_tuner.lib.base.utils.analysis_utils import filter_ds_by_element
from tergite_tuner.lib.nodes.qubit_control.motzoi_parameter.analysis import (
    Motzoi12NodeAnalysis,
    Motzoi12QubitAnalysis,
)
from tergite_tuner.tests.utils.decorators import loaded_redis

_TEST_DATA_DIR = (
    Path(__file__).parent.parent.parent.parent / "data" / "single_qubits_run"
)
_REDIS_DATA_FILE = _TEST_DATA_DIR / "redis-single-qubits-run.json"
_NODE_TEST_DIR = _TEST_DATA_DIR / "motzoi_12_parameter"
_HDF_FILE = _NODE_TEST_DIR / "dataset_motzoi_12_parameter.hdf5"


def test_motzoi_parameter(redis_connection, session_context):
    with loaded_redis(redis_connection, _REDIS_DATA_FILE):
        name = "motzoi_12_parameter"
        full_dataset = xr.open_dataset(_HDF_FILE)
        qubit_qois = ["r12:ef_motzoi"]

        ds_13 = filter_ds_by_element(full_dataset, "q13")
        ds_15 = filter_ds_by_element(full_dataset, "q15")

        analysis = Motzoi12QubitAnalysis(name, qubit_qois, session=session_context)
        s21 = ds_13.isel(ReIm=0) + 1j * ds_13.isel(ReIm=1)
        analysis.magnitudes = np.abs(s21)
        analysis.data_var = "yq13"
        qoi = analysis.analyse_qubit()

        motzoi_12 = qoi.analysis_result["r12:ef_motzoi"]["value"]

        assert qoi.analysis_successful
        assert pytest.approx(motzoi_12) == 0.12

        s21 = ds_15.isel(ReIm=0) + 1j * ds_15.isel(ReIm=1)
        analysis.magnitudes = np.abs(s21)
        analysis.data_var = "yq15"
        qoi = analysis.analyse_qubit()

        motzoi_12 = qoi.analysis_result["r12:ef_motzoi"]["value"]

        assert qoi.analysis_successful
        assert pytest.approx(motzoi_12) == -0.036


def test_plotting(redis_connection, session_context):
    """
    Test that the plotter produces a figure with the right number of axes
    """
    with loaded_redis(redis_connection, _REDIS_DATA_FILE):
        name = "motzoi_12_parameter"
        qubit_qois = ["r12:ef_motzoi"]

        try:
            analysis = Motzoi12NodeAnalysis(name, qubit_qois, session=session_context)
            analysis.analyze_node(_NODE_TEST_DIR, save_plot=True)
            number_of_qubits = len(analysis.dataset.attrs["elements"])
            assert analysis.axs.shape == (1, number_of_qubits)
        finally:
            (_NODE_TEST_DIR / f"{name}.png").unlink(missing_ok=True)
            (_NODE_TEST_DIR / f"{name}_preview.png").unlink(missing_ok=True)
