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
from tergite_tuner.lib.nodes.qubit_control.motzoi_parameter.node import MOTZOI_SPECS
from tergite_tuner.utils.types.node_enum import NodeEnum


@pytest.mark.usefixtures("seeded_state")
def test_motzoi_12_drives_with_the_01_pulse_duration(session_context):
    ExtendedTransmon.close_all()
    qubits = ["q13", "q14", "q15"]
    device = configure_device("motzoi", qubits, ["q13_q14"], session_context)
    transmons = {qubit: device.get_element(qubit) for qubit in qubits}

    schedule = MOTZOI_SPECS[NodeEnum.MOTZOI_12_PARAMETER].get_schedule(
        transmons,
        mw_motzois={qubit: np.linspace(-0.3, 0.3, 3) for qubit in qubits},
        X_repetitions={qubit: np.arange(1, 8, 4) for qubit in qubits},
    )

    durations = [
        pulse["duration"]
        for operation in schedule.operations.values()
        if operation["name"] == "DRAGPulse"
        for pulse in operation["pulse_info"]
    ]
    assert durations == pytest.approx([5.6e-8] * len(durations))
