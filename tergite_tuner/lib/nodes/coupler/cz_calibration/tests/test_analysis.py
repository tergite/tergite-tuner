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


import cf_xarray as cf
import numpy as np
import pytest
import xarray as xr

from tergite_tuner.lib.nodes.coupler.cz_calibration.analysis import (
    CZCalibrationCouplerAnalysis,
    get_distances_from_pi,
)
from tergite_tuner.lib.spec import is_failed
from tergite_tuner.storage.fs.dataset import load_dataset
from tergite_tuner.tests.utils.datasets import get_coupler_dataset
from tergite_tuner.tests.utils.state import loaded_state

_STATE_FILENAME = "state-coupler-run-2026-02.json"


def test_cz_calibration_success(session_context, node_data_dir):
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        file_path = node_data_dir / "dataset_cz_calibration.hdf5"
        with xr.open_dataset(file_path) as dataset:
            dataset = cf.decode_compress_to_multi_index(dataset, "working_points")

            analysis = CZCalibrationCouplerAnalysis(
                get_coupler_dataset(dataset, "q13_q14", "cz_calibration"),
                session_context,
            )
            qoi = analysis.analyse()

            cz_pulse_frequency = qoi["cz_pulse_frequency"].value
            cz_pulse_duration = qoi["cz_pulse_duration"].value
            cz_phase = qoi["cz_phase"].value

            assert not is_failed(qoi)
            assert pytest.approx(cz_pulse_frequency) == 713980000
            assert pytest.approx(cz_pulse_duration) == 192e-9
            assert pytest.approx(cz_phase) == 181.450086


def test_decode_multi_index(node_data_dir):
    dataset = load_dataset("cz_calibration", node_data_dir)

    assert "l1" in dataset.working_points.coords
    assert "l2" in dataset.working_points.coords
    assert "working_points" in dataset.working_points.coords
    assert dataset.working_points.size == 11


def test_plotting(session_context, node_data_dir):
    """
    Test that the plotter produces a figure with the right number of axes
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        file_path = node_data_dir / "dataset_cz_calibration.hdf5"
        with xr.open_dataset(file_path) as dataset:
            dataset = cf.decode_compress_to_multi_index(dataset, "working_points")

            analysis = CZCalibrationCouplerAnalysis(
                get_coupler_dataset(dataset, "q13_q14", "cz_calibration"),
                session_context,
            )

            figures_dictionary = {}

            analysis.analyse()
            analysis.plotter(figures_dictionary)

            assert "q13_q14" in figures_dictionary

            figure = figures_dictionary["q13_q14"][0]

            # axes are the (freq, duration) plots + figure title +
            # figure x label + figure y label + global trend plot
            assert len(figure.get_axes()) == dataset.working_points.size + 4


@pytest.mark.parametrize(
    "difference, distance", [(180, 0), (90, 90), (-170, 10), (350, 170)]
)
def test_the_distance_is_from_a_cz_phase_of_180_degrees(difference, distance):
    phi_on = xr.DataArray(np.deg2rad(difference))
    phi_off = xr.DataArray(0.0)

    assert get_distances_from_pi(phi_on, phi_off).item() == pytest.approx(distance)
