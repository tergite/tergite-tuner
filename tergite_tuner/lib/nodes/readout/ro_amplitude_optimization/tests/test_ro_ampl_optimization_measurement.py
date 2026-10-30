# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2025
# (C) Chalmers Next Labs AB 2025, 2026
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
from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.node import (
    RO_AMPLITUDE_SPECS,
)
from tergite_tuner.utils.types.node_enum import NodeEnum


def test_each_qubit_gets_its_own_12_pulse_duration(seeded_redis, session_context):
    ExtendedTransmon.close_all()
    qubits = ["q13", "q14", "q15"]
    durations = {"q13": 40e-9, "q14": 60e-9, "q15": 80e-9}
    device = configure_device("ro", qubits, ["q13_q14"], session_context)
    transmons = {qubit: device.get_element(qubit) for qubit in qubits}
    for qubit, duration in durations.items():
        transmons[qubit].r12.ef_duration(duration)
    spec = RO_AMPLITUDE_SPECS[NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION]

    schedule = spec.get_schedule(
        transmons,
        qubit_states={qubit: np.array([0, 1, 2], dtype=np.int16) for qubit in qubits},
        ro_amplitudes={qubit: np.linspace(0.1, 0.3, 3) for qubit in qubits},
        loop_repetitions=spec.loops,
    )

    pulse_durations = {
        pulse["port"].split(":")[0]: pulse["duration"]
        for operation in schedule.operations.values()
        if operation["name"] == "LoopOperation"
        for shot in operation["control_flow_info"]["body"].operations.values()
        if shot["name"] == "DRAGPulse"
        for pulse in shot["pulse_info"]
    }
    assert pulse_durations == pytest.approx(durations)
