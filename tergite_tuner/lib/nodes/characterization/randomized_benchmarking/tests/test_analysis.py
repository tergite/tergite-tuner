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

from tergite_tuner.lib.base.utils.analysis_utils import filter_ds_by_element
from tergite_tuner.lib.nodes.characterization.randomized_benchmarking.analysis import (
    RandomizedBenchmarkingNodeAnalysis,
    RandomizedBenchmarkingQubitAnalysis,
)
from tergite_tuner.tests.utils.decorators import loaded_redis

_REDIS_DATA_FILENAME = "redis-2026-03-10-21-33-32.json"


def test_randomized_benchmarking_analysis(
    redis_connection, session_context, node_data_dir
):
    redis_data_file = node_data_dir / _REDIS_DATA_FILENAME
    with loaded_redis(redis_connection, redis_data_file):
        file_path = node_data_dir / "dataset_randomized_benchmarking.hdf5"
        with xr.open_dataset(file_path) as dataset:

            qubit_qois = ["fidelity", "fidelity_error", "leakage", "leakage_error"]
            analysis = RandomizedBenchmarkingQubitAnalysis(
                "randomized_benchmarking", qubit_qois, session_context
            )
            ds_11 = filter_ds_by_element(dataset, "q11")
            ds_15 = filter_ds_by_element(dataset, "q15")
            qoi_11 = analysis.process_qubit(ds_11, "q11")
            qoi_15 = analysis.process_qubit(ds_15, "q15")

            standard_fidelity_11 = qoi_11.analysis_result["fidelity"]["value"]
            standard_leakage_11 = qoi_11.analysis_result["leakage"]["value"]
            standard_fidelity_15 = qoi_15.analysis_result["fidelity"]["value"]
            standard_leakage_15 = qoi_15.analysis_result["leakage"]["value"]

            assert qoi_11.analysis_successful
            assert qoi_15.analysis_successful
            assert pytest.approx(standard_fidelity_11) == 0.99951747
            assert pytest.approx(standard_leakage_11) == 0.00207032
            assert pytest.approx(standard_fidelity_15) == 0.99788337
            assert pytest.approx(standard_leakage_15) == 0.0064318


def test_plotting(redis_connection, session_context, node_data_dir):
    """
    Test that the plotter produces a figure with the right number of axes
    """
    redis_data_file = node_data_dir / _REDIS_DATA_FILENAME
    with loaded_redis(redis_connection, redis_data_file):
        qubit_qois = ["fidelity", "fidelity_error", "leakage", "leakage_error"]
        name = "randomized_benchmarking"
        analysis = RandomizedBenchmarkingNodeAnalysis(
            name,
            redis_fields=qubit_qois,
            session_context=session_context,
        )
        analysis.analyze_node(node_data_dir, save_plot=True)
        figure = analysis.fig

        # TODO: this will change when the top band is removed
        assert len(figure.get_axes()) == 8
