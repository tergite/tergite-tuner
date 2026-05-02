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

from tergite_autocalibration.lib.nodes.coupler.cz_local_phases.analysis import (
    CZLocalPhasesCouplerAnalysis,
)
from tergite_autocalibration.tests.utils.decorators import loaded_redis

_test_data_dir = os.path.join(Path(__file__).parent, "data")
_redis_values = os.path.join(_test_data_dir, "redis-coupler-run-2026-02.json")


def test_cz_local_phases(redis_connection, session_context):
    with loaded_redis(redis_connection, _redis_values):
        file_path = os.path.join(_test_data_dir, "dataset_cz_local_phases.hdf5")
        dataset = xr.open_dataset(file_path)

        analysis = CZLocalPhasesCouplerAnalysis(
            "cz_calibration",
            ["cz_pulse_frequency", "cz_pulse_duration", "cz_phase"],
            session_context,
        )
        qoi = analysis.process_coupler(dataset, "q13_q14")

        control_local_phase = qoi.analysis_result["control_local_phase"]["value"]
        target_local_phase = qoi.analysis_result["target_local_phase"]["value"]

        assert qoi.analysis_successful
        assert pytest.approx(control_local_phase) == -135.2184
        assert pytest.approx(target_local_phase) == 73.0427
