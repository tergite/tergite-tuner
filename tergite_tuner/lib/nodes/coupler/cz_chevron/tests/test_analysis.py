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

import numpy as np
import pytest
import xarray as xr

from tergite_tuner.lib.nodes.coupler.cz_chevron.analysis import (
    CZChevronCouplerAnalysis,
    get_chevron_leads,
    get_durations_in_ns,
)
from tergite_tuner.lib.spec import is_failed
from tergite_tuner.tests.utils.datasets import get_coupler_dataset
from tergite_tuner.tests.utils.pytest import is_headless, is_work_in_progress
from tergite_tuner.tests.utils.state import loaded_state

_STATE_FILENAME = "state-export-2025-12-21.json"


@pytest.mark.skipif(is_work_in_progress(), reason="Currently work in progress")
def test_cz_chevron_analysis_good_data(session_context, node_data_dir):
    """
    Test whether single coupler analysis outputs right QOIs
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        # Load dataset
        file_path = node_data_dir / "dataset_cz_chevron_0.hdf5"
        with xr.open_dataset(file_path) as dataset:
            number_of_working_points = 3

            # Run the single coupler analysis
            analysis = CZChevronCouplerAnalysis(
                get_coupler_dataset(dataset, "q13_q14", "cz_chevron"),
                session_context,
                phase_path="via_20",
                number_of_working_points=number_of_working_points,
            )
            qoi = analysis.analyse()
            cz_working_frequencies = eval(qoi["cz_working_frequencies"].value)
            cz_working_durations_in_ns = eval(qoi["cz_working_durations_in_ns"].value)

            assert not is_failed(qoi)
            assert 715415456 in cz_working_frequencies
            assert 408 in cz_working_durations_in_ns


@pytest.mark.skip
def test_cz_chevron_analysis_bad_data(session_context, node_data_dir):
    """
    Test whether single coupler analysis outputs that the analysis fails on bad data
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        # Load dataset
        file_path = node_data_dir / "dataset_cz_chevron_0.hdf5"
        with xr.open_dataset(file_path) as dataset:

            # Run the single coupler analysis
            analysis = CZChevronCouplerAnalysis(
                get_coupler_dataset(dataset, "q14_q15", "cz_chevron"),
                session_context,
                phase_path="via_20",
            )
            qoi = analysis.analyse()

            # Make sure that the analysis returns as unsuccessful
            assert is_failed(qoi)


@pytest.mark.skipif(
    is_headless(),
    reason="Skipped in headless/CI environment: requires a display for matplotlib FacetGrid",
)
def test_plotting(session_context, node_data_dir):
    """
    Test that the plotter produces a faceted figure
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        # Load dataset
        file_path = node_data_dir / "dataset_cz_chevron_0.hdf5"
        with xr.open_dataset(file_path) as dataset:
            number_of_working_points = 3
            figures_dictionary = {}

            # Run the single coupler analysis
            analysis = CZChevronCouplerAnalysis(
                get_coupler_dataset(dataset, "q13_q14", "cz_chevron"),
                session_context,
                phase_path="via_20",
                number_of_working_points=number_of_working_points,
            )
            analysis.analyse()
            analysis.plotter(figures_dictionary)

            assert "q13_q14" in figures_dictionary

            faceted_graph_fig = figures_dictionary["q13_q14"][0]

            # the faceted graph has 7 axis: 6 for the probabilty heatmaps and one for the colorbar
            assert len(faceted_graph_fig.get_axes()) == 7


def test_durations_round_down_to_four_nanoseconds():
    durations = np.array([95.9e-9, 101.5e-9, 103.99e-9])

    assert get_durations_in_ns(durations).tolist() == [92, 100, 100]


def test_each_qubit_leads_from_its_1_to_its_end_of_the_phase_path():
    states = {"state": [0, 1, 2]}
    control = xr.DataArray([0.1, 0.2, 0.7], coords=states, dims="state")
    target = xr.DataArray([0.6, 0.3, 0.1], coords=states, dims="state")

    control_lead, target_lead = get_chevron_leads(control, target, "via_20")

    assert control_lead.item() == pytest.approx(0.7 - 0.2)
    assert target_lead.item() == pytest.approx(0.6 - 0.3)


def test_a_whole_nanosecond_duration_keeps_its_nanoseconds():
    assert get_durations_in_ns(np.array([100e-9])).tolist() == [100]
