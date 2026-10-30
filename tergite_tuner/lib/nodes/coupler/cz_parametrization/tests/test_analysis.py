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
import shutil

import numpy as np
import pytest
import xarray as xr

from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.lib.nodes.coupler.cz_parametrization.analysis import (
    CZParametrizationCouplerAnalysis,
    get_path_scores,
    get_smoothed_scores,
)
from tergite_tuner.lib.run import get_coupler_datasets
from tergite_tuner.lib.spec import is_failed, save_coupler_figures
from tergite_tuner.storage.fs.dataset import load_dataset
from tergite_tuner.tests.utils.datasets import get_coupler_dataset
from tergite_tuner.tests.utils.state import loaded_state
from tergite_tuner.utils.types.node_enum import NodeEnum

_STATE_FILENAME = "state-export-2025-12-16.json"


def test_cz_parametrization_analysis_good_data(session_context, node_data_dir):
    """
    Test whether single coupler analysis outputs right QOIs
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        # Load dataset
        file_path = node_data_dir / "dataset_cz_parametrization_0.hdf5"
        with xr.open_dataset(file_path) as dataset:
            coupler = "q14_q15"

            # Run the single coupler analysis
            analysis = CZParametrizationCouplerAnalysis(
                get_coupler_dataset(dataset, coupler, "cz_parametrization"),
                session_context,
                phase_path="via_20",
            )
            qoi = analysis.analyse()

            # Compare the output values
            assert math.isclose(qoi["cz_pulse_frequency"].value, 415004736.84210527)
            assert math.isclose(qoi["cz_pulse_amplitude"].value, 0.28448275862068967)
            assert math.isclose(qoi["parking_current"].value, 0.0006400000000000002)


def test_cz_parametrization_analysis_bad_data(session_context, node_data_dir):
    """
    Test whether single coupler analysis outputs that the analysis fails on bad data
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        # Load dataset
        file_path = node_data_dir / "dataset_cz_parametrization_1.hdf5"
        with xr.open_dataset(file_path) as dataset:
            coupler = "q14_q15"

            # Run the single coupler analysis
            analysis = CZParametrizationCouplerAnalysis(
                get_coupler_dataset(dataset, coupler, "cz_parametrization"),
                session_context,
                phase_path="via_20",
            )
            qoi = analysis.analyse()

            # Make sure that the analysis returns as unsuccessful
            assert is_failed(qoi)


def test_plotting(session_context, tmp_path, node_data_dir):
    """
    Test whether plotting produces right plots
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        # Copy dataset to the temporary data path
        shutil.copy(
            node_data_dir / "dataset_cz_parametrization_0.hdf5",
            tmp_path / "dataset_cz_parametrization.hdf5",
        )

        coupler = "q14_q15"
        # Run the node analysis
        dataset = get_coupler_datasets(
            load_dataset("cz_parametrization", tmp_path), "cz_parametrization"
        )[coupler]
        fits = DEFAULT_NODE_SPECS[NodeEnum.CZ_PARAMETRIZATION].analyse(
            dataset, session_context, phase_path="via_20"
        )
        save_coupler_figures(dataset, fits, tmp_path, session_context)

        # Check whether output images exist
        for i in range(5):
            image_path = tmp_path / f"cz_parametrization_{coupler}_{i}_preview.png"
            try:
                assert image_path.exists()
            finally:
                image_path.unlink(missing_ok=True)


def _get_probabilities(p0: float, p1: float, p2: float) -> xr.DataArray:
    return xr.DataArray([p0, p1, p2], coords={"state": [0, 1, 2]}, dims="state")


@pytest.mark.parametrize(
    "phase_path, expected",
    [
        ("via_20", (0.7 - 0.2 - 0.1) + (0.6 - 0.3 - 0.1)),
        ("via_02", (0.1 - 0.2 - 0.7) + (0.1 - 0.3 - 0.6)),
    ],
)
def test_a_point_scores_how_far_it_moves_along_the_phase_path(phase_path, expected):
    control = _get_probabilities(0.1, 0.2, 0.7)
    target = _get_probabilities(0.6, 0.3, 0.1)

    assert get_path_scores(control, target, phase_path).item() == pytest.approx(
        expected
    )


def test_smoothing_weights_a_point_by_its_neighbours():
    scores = xr.DataArray(np.ones((3, 3)))

    smoothed = get_smoothed_scores(scores)

    # the centre has all its neighbours; the edges count the -1s beyond the grid
    assert smoothed.values[1, 1] == pytest.approx(1.0)
    assert smoothed.values[0, 0] < smoothed.values[1, 1]
