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

import pytest
import xarray as xr

from tergite_tuner.lib.nodes.qubit_control.ramsey_fringes.analysis import (
    analyse_ramsey,
)
from tergite_tuner.lib.nodes.qubit_control.ramsey_fringes.node import (
    DUMMY_DETUNING,
    RAMSEY_SPECS,
)
from tergite_tuner.lib.run import get_dataset, get_dummy_dataset, get_sweeps
from tergite_tuner.utils.types.node_enum import NodeEnum


def test_the_correction_is_the_detuning_the_fringes_vanish_at(session_context):
    spec = RAMSEY_SPECS[NodeEnum.RAMSEY_CORRECTION]
    session = session_context.model_copy(update={"user_samplespace": {}})
    sweeps = get_sweeps(spec, session)
    dataset = get_dataset(
        get_dummy_dataset(spec, sweeps, session), sweeps, session.qubits
    )
    qubit = session.qubits[0]
    s21: xr.DataArray = dataset[f"y{qubit}"]
    s21.attrs["qubit"] = qubit
    session.state.load({"transmons": {qubit: {"clock_freqs:f01": 4.5e9}}})

    fits = analyse_ramsey(s21, session, frequency_field="clock_freqs:f01")

    assert fits["correction"].value == pytest.approx(DUMMY_DETUNING, rel=0.05)
    assert fits["frequency"].value - fits["correction"].value == 4.5e9
