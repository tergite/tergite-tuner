# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2025
# (C) Chalmers Next Labs AB 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, configure_device
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.measurement import (
    TwoTonesAmplitudeMeasurement,
)


def test_amplitude_spectroscopy_accepts_long_spectroscopy_pulses(
    seeded_redis, session_context
):
    ExtendedTransmon.close_all()
    qubits = ["q13", "q14"]
    device = configure_device("spectroscopy", qubits, ["q13_q14"], session_context)
    transmons = {qubit: device.get_element(qubit) for qubit in qubits}
    for transmon in transmons.values():
        transmon.spec.spec_duration(8e-6)

    schedule = TwoTonesAmplitudeMeasurement(transmons).schedule_function(
        spec_frequencies={q: np.linspace(4.0e9, 4.1e9, 3) for q in qubits},
        spec_pulse_amplitudes={q: 0.01 for q in qubits},
    )

    assert schedule.operations
