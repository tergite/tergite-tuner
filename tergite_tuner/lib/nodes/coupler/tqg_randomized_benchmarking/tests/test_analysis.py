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

from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.analysis import (
    CZRBCouplerAnalysis,
)
from tergite_tuner.lib.spec import is_failed
from tergite_tuner.lib.utils.analysis_models import ExpDecayModel
from tergite_tuner.tests.utils.datasets import get_coupler_dataset
from tergite_tuner.tests.utils.state import loaded_state

_STATE_FILENAME = "state-2026-03-05-10-55-35.json"


def test_cz_rb(session_context, node_data_dir):
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        file_path = node_data_dir / "dataset_cz_rb.hdf5"
        with xr.open_dataset(file_path) as dataset:
            analysis = CZRBCouplerAnalysis(
                get_coupler_dataset(dataset, "q12_q13", "cz_rb"),
                session_context,
            )
            qoi = analysis.analyse()

            cz_fidelity = qoi["cz_fidelity"].value

            assert not is_failed(qoi)
            assert pytest.approx(cz_fidelity) == 0.95848


def test_plotting(session_context, node_data_dir):
    """
    Test that the plotter produces a figure with the right number of axes
    """
    state_file = node_data_dir / _STATE_FILENAME
    with loaded_state(session_context, state_file):
        file_path = node_data_dir / "dataset_cz_rb.hdf5"
        with xr.open_dataset(file_path) as dataset:
            analysis = CZRBCouplerAnalysis(
                get_coupler_dataset(dataset, "q12_q13", "cz_rb"),
                session_context,
            )

            figures_dictionary = {}

            analysis.analyse()
            analysis.plotter(figures_dictionary)

            assert "q12_q13" in figures_dictionary

            figure = figures_dictionary["q12_q13"][0]

            # one axis for the standard exponentials and one for the leakage RB exponentials
            assert len(figure.get_axes()) == 2


def test_a_decay_fitted_to_zero_fails_the_fits(
    session_context, node_data_dir, monkeypatch
):
    fit = ExpDecayModel.fit

    def fit_to_zero(self, *args, **kwargs):
        result = fit(self, *args, **kwargs)
        result.params["p"].value = 0.0
        return result

    monkeypatch.setattr(ExpDecayModel, "fit", fit_to_zero)
    with (
        loaded_state(session_context, node_data_dir / _STATE_FILENAME),
        xr.open_dataset(node_data_dir / "dataset_cz_rb.hdf5") as dataset,
    ):
        analysis = CZRBCouplerAnalysis(
            get_coupler_dataset(dataset, "q12_q13", "cz_rb"), session_context
        )
        fits = analysis.analyse()

    assert is_failed(fits)
