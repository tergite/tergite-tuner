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

from tergite_tuner.lib.nodes.characterization.t1.node import DUMMY_T1, T1_SPECS
from tergite_tuner.lib.nodes.characterization.t2.node import DUMMY_T2_US, T2_SPECS
from tergite_tuner.lib.run import get_sweeps
from tergite_tuner.utils.types.node_enum import NodeEnum


@pytest.mark.parametrize(
    "spec, repetitions_coord, expected_us",
    [
        (T1_SPECS[NodeEnum.T1], "T1_repetitions", DUMMY_T1 * 1e6),
        (T2_SPECS[NodeEnum.T2], "repeat", DUMMY_T2_US),
        (T2_SPECS[NodeEnum.T2_ECHO], "repeat", 4 * DUMMY_T2_US),
    ],
)
def test_the_decay_time_is_the_dummy_qubits(
    session_context, spec, repetitions_coord, expected_us
):
    session = session_context.model_copy(update={"user_samplespace": {}})
    delays = get_sweeps(spec, session)["delays"]["q00"]
    decay = spec.get_dummy_s21("q00", {"delays": delays}, session)
    s21 = xr.DataArray(
        np.tile(decay, (3, 1)),
        dims=(repetitions_coord, "delaysq00"),
        coords={"delaysq00": delays},
        attrs={"qubit": "q00"},
    )

    fits = spec.analyse(s21, session)

    assert fits["time"].value == pytest.approx(expected_us, rel=0.05)
    assert fits["time"].error == pytest.approx(0, abs=1e-6)


def test_t2_fails_its_fits_on_data_without_an_oscillation(session_context):
    # a flat spectrum guesses a frequency of 0, which the model's swap and cz expressions divide by
    session = session_context.model_copy(update={"user_samplespace": {}})
    spec = T2_SPECS[NodeEnum.T2]
    delays = get_sweeps(spec, session)["delays"]["q00"]
    s21 = xr.DataArray(
        np.zeros((len(delays), 3), dtype=complex),
        dims=("delaysq00", "repeat"),
        coords={"delaysq00": delays},
        attrs={"qubit": "q00"},
    )

    assert spec.analyse(s21, session) is None
