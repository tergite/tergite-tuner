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


import numpy as np
import pytest
import xarray as xr

from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.analysis import (
    CZRBCouplerAnalysis,
    DecayFits,
    get_cz_fidelities,
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


def _get_decays(p: float, lambda_L: float, AM: float, lambda_r: float) -> DecayFits:
    curve = np.zeros(3)
    return DecayFits(p, lambda_L, AM, lambda_r, curve, curve, curve)


def test_an_ideal_cz_has_unit_fidelities():
    decays = _get_decays(p=0.9, lambda_L=0.99, AM=0.5, lambda_r=0.9)

    assert get_cz_fidelities(decays, decays) == pytest.approx((1.0, 1.0))


def test_the_cz_fidelity_follows_the_decay_ratio():
    standard = _get_decays(p=0.9, lambda_L=1.0, AM=0.5, lambda_r=0.8)
    interleaved = _get_decays(p=0.45, lambda_L=1.0, AM=0.5, lambda_r=0.4)

    # no leakage: 1 - L1 is 1 in both modes, so Nakamura's is 3/4 * lambda_r ratio + 1/4
    assert get_cz_fidelities(standard, interleaved) == pytest.approx((0.625, 0.625))


def test_without_interleaving_there_is_no_cz_fidelity():
    decays = _get_decays(p=0.9, lambda_L=0.99, AM=0.5, lambda_r=0.9)

    assert np.isnan(get_cz_fidelities(decays, None)).all()
