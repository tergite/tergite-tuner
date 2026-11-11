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
from matplotlib import pyplot as plt

from tergite_tuner.lib.nodes.coupler.cz_local_phases.analysis import (
    analyse_cz_local_phases,
    get_gate_phase,
    plot_cz_local_phases,
)
from tergite_tuner.lib.spec import is_failed
from tergite_tuner.tests.utils.datasets import get_coupler_dataset
from tergite_tuner.tests.utils.state import loaded_state

_STATE_FILENAME = "state-coupler-run-2026-02.json"


@pytest.fixture
def fits(session_context, node_data_dir):
    with loaded_state(session_context, node_data_dir / _STATE_FILENAME):
        file_path = node_data_dir / "dataset_cz_local_phases.hdf5"
        with xr.open_dataset(file_path) as dataset:
            return analyse_cz_local_phases(
                get_coupler_dataset(dataset, "q13_q14", "cz_calibration"),
                session_context,
            )


def test_cz_local_phases(fits):
    assert not is_failed(fits)


def test_plot_draws_both_qubits_swapped_and_not(fits):
    (figure,) = plot_cz_local_phases(fits)

    assert len(figure.get_axes()) == 4
    plt.close(figure)


def test_the_gate_phase_is_the_phase_with_the_gate_less_without():
    phis = xr.DataArray(
        [np.pi / 2, np.pi / 6], coords={"gate": [True, False]}, dims="gate"
    )

    assert get_gate_phase(phis, "gate") == pytest.approx(60.0)
