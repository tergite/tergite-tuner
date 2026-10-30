# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
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

from tergite_tuner.lib.nodes.characterization.all_xy.analysis import (
    IDEAL_POPULATIONS,
    analyse_all_xy,
    get_pair_labels,
)
from tergite_tuner.lib.nodes.characterization.all_xy.node import DUMMY_ERROR
from tergite_tuner.tests.utils.runs import run_dummy_node
from tergite_tuner.utils.types.node_enum import NodeEnum


def test_ideal_gates_have_no_error(session_context):
    # the calibration points span any rotation and scale of the IQ plane
    s21 = xr.DataArray(
        (2 + 1j) + (0.5 - 3j) * np.concatenate([IDEAL_POPULATIONS, [0.0, 1.0]])
    )

    fits = analyse_all_xy(s21, session_context)

    assert fits["error"].value == pytest.approx(0, abs=1e-12)
    assert fits["populations"].value == pytest.approx(IDEAL_POPULATIONS)


def test_pairs_are_labelled_by_their_gates():
    labels = get_pair_labels()

    assert labels[:5] == ["II", "XX", "YY", "XY", "YX"]
    assert labels[-4:] == ["XI", "YI", "X90X90", "Y90Y90"]


@pytest.mark.slow
def test_a_dummy_run_recovers_the_dummy_error(session_context, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    session = run_dummy_node(NodeEnum.ALL_XY, session_context, tmp_path)

    for qubit in session.qubits:
        error = session.state.read("transmons", qubit, "all_xy_error")
        assert error == pytest.approx(DUMMY_ERROR)
