# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2025
# (C) Chalmers Next Labs AB 2025
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

from tergite_tuner.backend import ExtendedTransmon, configure_device
from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.node import (
    N_RABI_SPECS,
    RABI_SPECS,
)
from tergite_tuner.utils.types.node_enum import NodeEnum

QUBITS = ["q13", "q14", "q15"]


def test_dummy_n_rabi_is_least_at_its_correction(session_context):
    spec = N_RABI_SPECS[NodeEnum.N_RABI_OSCILLATIONS]
    sweeps = {
        "mw_amplitudes_sweep": np.linspace(-0.045, 0.045, 91),
        "X_repetitions": [1, 7],
    }

    s21 = spec.get_dummy_s21("q00", sweeps, session_context)

    corrections = sweeps["mw_amplitudes_sweep"][np.argmin(s21, axis=0)]
    assert corrections == pytest.approx([-0.01, -0.01], abs=1e-3)


@pytest.mark.usefixtures("seeded_state")
@pytest.mark.parametrize("state", [0, 1])
def test_each_qubit_is_driven_with_its_own_pulse_duration(session_context, state):
    ExtendedTransmon.close_all()
    durations = {"q13": 40e-9, "q14": 60e-9, "q15": 80e-9}
    device = configure_device("rabi", QUBITS, ["q13_q14"], session_context)
    transmons = {qubit: device.get_element(qubit) for qubit in QUBITS}
    for qubit, duration in durations.items():
        if state == 0:
            transmons[qubit].rxy.duration(duration)
        else:
            transmons[qubit].r12.ef_duration(duration)
    spec = list(RABI_SPECS.values())[state]

    schedule = spec.get_schedule(
        transmons, mw_amplitudes={qubit: np.linspace(0.002, 0.8, 3) for qubit in QUBITS}
    )

    pulse_durations = {
        pulse["port"].split(":")[0]: pulse["duration"]
        for operation in schedule.operations.values()
        if operation["name"] == "DRAGPulse"
        for pulse in operation["pulse_info"]
    }
    assert pulse_durations == pytest.approx(durations)
