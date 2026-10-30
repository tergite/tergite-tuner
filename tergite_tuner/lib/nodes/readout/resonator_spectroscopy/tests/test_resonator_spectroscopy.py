# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
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
from matplotlib import pyplot as plt

from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy import (
    analysis as resonator_analysis,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.analysis import (
    ResonatorSpectroscopyQubitAnalysis,
    analyse_resonator,
    plot_resonator,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    RESONATOR_SPECTROSCOPY_SPECS,
)
from tergite_tuner.lib.run import get_redis_record
from tergite_tuner.tests.utils.datasets import get_s21
from tergite_tuner.utils.types.node_enum import NodeEnum


def _get_s21(node_data_dir, qubit: str = "q06") -> xr.DataArray:
    return get_s21(node_data_dir / "dataset_resonator_spectroscopy_0.hdf5", qubit)


def test_analyse_resonator_fits_the_dip(node_data_dir):
    fits = analyse_resonator(_get_s21(node_data_dir), None)

    assert 6e9 < fits["frequency"].value < 8e9
    assert fits["Ql"].value > 0
    assert fits["minimum"].value == pytest.approx(fits["frequency"].value, rel=1e-4)


def test_a_fit_that_raises_fails_the_element(node_data_dir, monkeypatch):
    def _raise(*args, **kwargs):
        raise ValueError("fit diverged")

    monkeypatch.setattr(resonator_analysis.model, "fit", _raise)

    assert analyse_resonator(_get_s21(node_data_dir), None) is None


def test_each_state_stores_its_own_fields(node_data_dir):
    fits = analyse_resonator(_get_s21(node_data_dir), None)
    records = {
        node: get_redis_record(spec.qois, fits)
        for node, spec in RESONATOR_SPECTROSCOPY_SPECS.items()
    }

    assert records[NodeEnum.RESONATOR_SPECTROSCOPY]["Ql"] == fits["Ql"].value
    assert records[NodeEnum.RESONATOR_SPECTROSCOPY_1]["Ql_1"] == fits["Ql"].value
    assert set(records[NodeEnum.RESONATOR_SPECTROSCOPY_2]) == {
        "extended_clock_freqs:readout_2",
        "extended_clock_freqs:readout_2_error",
    }


def test_plot_resonator_draws_the_fit(node_data_dir):
    s21 = _get_s21(node_data_dir)
    figure, axis = plt.subplots()

    plot_resonator(axis, s21, analyse_resonator(s21, None), session=None, state=0)

    assert axis.lines
    plt.close(figure)


def test_punchout_reuses_the_fit_through_the_qubit_analysis(node_data_dir):
    file_path = node_data_dir / "dataset_resonator_spectroscopy_0.hdf5"
    with xr.open_dataset(file_path) as dataset:
        analysis = ResonatorSpectroscopyQubitAnalysis(
            "name", [], session=SessionContext(data_dir=node_data_dir)
        )
        qoi = analysis.process_qubit(dataset, "yq06")

    expected = analyse_resonator(_get_s21(node_data_dir), None)["frequency"].value
    assert qoi.analysis_result["clock_freqs:readout"]["value"] == expected
    assert np.isfinite(expected)
