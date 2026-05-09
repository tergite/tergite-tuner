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

import xarray as xr

from conftest import node_data_dir
from tergite_tuner.lib.nodes.coupler.cz_local_phases.analysis import (
    CZLocalPhasesCouplerAnalysis,
)
from tergite_tuner.tests.utils.decorators import loaded_redis

_REDIS_DATA_FILENAME = "redis-coupler-run-2026-02.json"


def test_cz_local_phases(redis_connection, session_context, node_data_dir):
    redis_data_file = node_data_dir / _REDIS_DATA_FILENAME
    with loaded_redis(redis_connection, redis_data_file):
        file_path = node_data_dir / "dataset_cz_local_phases.hdf5"
        with xr.open_dataset(file_path) as dataset:
            analysis = CZLocalPhasesCouplerAnalysis(
                "cz_calibration",
                ["cz_pulse_frequency", "cz_pulse_duration", "cz_phase"],
                session_context,
            )
            qoi = analysis.process_coupler(dataset, "q13_q14")

            cz_dynamic_control = qoi.analysis_result["cz_dynamic_control"]["value"]
            cz_dynamic_target = qoi.analysis_result["cz_dynamic_target"]["value"]

            assert qoi.analysis_successful
            # assert pytest.approx(control_local_phase) == -135.2184
            # assert pytest.approx(target_local_phase) == 73.0427


def test_plotting(redis_connection, session_context, node_data_dir):
    """
    Test that the plotter produces a figure with the right number of axes
    """
    redis_data_file = node_data_dir / _REDIS_DATA_FILENAME
    with loaded_redis(redis_connection, redis_data_file):
        file_path = node_data_dir / "dataset_cz_local_phases.hdf5"
        with xr.open_dataset(file_path) as dataset:

            analysis = CZLocalPhasesCouplerAnalysis(
                "cz_calibration",
                ["cz_pulse_frequency", "cz_pulse_duration", "cz_phase"],
                session_context,
            )

            figures_dictionary = {}

            analysis.process_coupler(dataset, "q13_q14")
            analysis.plotter(figures_dictionary)

            assert "q13_q14" in figures_dictionary

            figure = figures_dictionary["q13_q14"][0]

            assert len(figure.get_axes()) == 4
