# This code is part of Tergite
#
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Eleftherios Moschandreou 2025, 2026
# (C) Chalmers Next Labs AB 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import math
import os
import shutil
from pathlib import Path

import xarray as xr

from tergite_autocalibration.lib.nodes.coupler.cz_parametrization.analysis import (
    CZParametrizationCouplerAnalysis,
    CZParametrizationNodeAnalysis,
)
from tergite_autocalibration.tests.utils.decorators import loaded_redis

_test_data_dir = os.path.join(Path(__file__).parent, "data")
_redis_values = os.path.join(_test_data_dir, "redis-export-2025-12-16.json")


def test_cz_parametrization_analysis_good_data(redis_connection, session_context):
    """
    Test whether single coupler analysis outputs right QOIs
    """
    with loaded_redis(redis_connection, _redis_values):
        # Load dataset
        file_path = os.path.join(
            _test_data_dir, "data_0", "dataset_cz_parametrization.hdf5"
        )
        dataset = xr.open_dataset(file_path)
        coupler = "q14_q15"

        # Run the single coupler analysis
        analysis = CZParametrizationCouplerAnalysis(
            "cz_parametrization",
            ["cz_pulse_frequency", "cz_pulse_amplitude", "parking_current"],
            session_context,
            phase_path="via_20",
        )
        qoi = analysis.process_coupler(dataset, coupler)

        # Compare the output values
        assert math.isclose(
            qoi.analysis_result["cz_pulse_frequency"]["value"], 415004736.84210527
        )
        assert math.isclose(
            qoi.analysis_result["cz_pulse_amplitude"]["value"], 0.28448275862068967
        )
        assert math.isclose(
            qoi.analysis_result["parking_current"]["value"], 0.0006400000000000002
        )


def test_cz_parametrization_analysis_bad_data(redis_connection, session_context):
    """
    Test whether single coupler analysis outputs that the analysis fails on bad data
    """
    with loaded_redis(redis_connection, _redis_values):
        # Load dataset
        file_path = os.path.join(
            _test_data_dir, "data_1", "dataset_cz_parametrization.hdf5"
        )
        dataset = xr.open_dataset(file_path)
        coupler = "q14_q15"

        # Run the single coupler analysis
        analysis = CZParametrizationCouplerAnalysis(
            "cz_parametrization",
            ["cz_pulse_frequency", "cz_pulse_amplitude", "parking_current"],
            session_context,
            phase_path="via_20",
        )
        qoi = analysis.process_coupler(dataset, coupler)

        # Make sure that the analysis returns as unsuccessful
        assert qoi.analysis_successful is False
