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
import pytest

from tergite_tuner.backend import ExtendedTransmon, configure_device
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.measurement import (
    TwoTonesAmplitudeMeasurement,
    TwoTonesMultidimMeasurement,
)
from tergite_tuner.tests.utils.fixtures import DEFAULT_TEST_QUBITS


@pytest.mark.usefixtures("seeded_state")
def test_amplitude_spectroscopy_accepts_long_spectroscopy_pulses(session_context):
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


@pytest.mark.usefixtures("seeded_state")
@pytest.mark.parametrize(
    "duration, expected", [(4e-6, "SoftSquarePulse"), (6e-6, "long_square_pulse")]
)
def test_spectroscopy_plays_long_square_pulses_beyond_the_waveform_memory(
    session_context, duration, expected
):
    """Four soft square waveforms of 6 us, 24000 samples, would not fit in 16384"""
    ExtendedTransmon.close_all()
    qubit = DEFAULT_TEST_QUBITS[0]
    device = configure_device("spectroscopy", [qubit], [], session_context)
    transmon = device.get_element(qubit)
    transmon.spec.spec_duration(duration)

    schedule = TwoTonesMultidimMeasurement({qubit: transmon}).schedule_function(
        spec_frequencies={qubit: np.linspace(4.0e9, 4.1e9, 3)},
        spec_pulse_amplitudes={qubit: np.linspace(1e-3, 8e-3, 5)},
    )

    names = {operation.name for operation in schedule.operations.values()}
    assert expected in names
