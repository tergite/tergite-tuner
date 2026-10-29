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

from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.node import (
    NRabiOscillations12Node,
    NRabiOscillationsNode,
    RabiOscillations12Node,
    RabiOscillationsNode,
)
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon


def test_dummy_01_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_01 = RabiOscillationsNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset_01 = node_01.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]
    number_of_amplitudes_01 = len(
        node_01.schedule_samplespace["mw_amplitudes"][first_qubit]
    )

    assert len(dummy_dataset_01.data_vars) == len(DEFAULT_TEST_QUBITS)
    assert dummy_dataset_01.data_vars[0].size == number_of_amplitudes_01


def test_dummy_12_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_12 = RabiOscillations12Node(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset_12 = node_12.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]
    number_of_amplitudes_12 = len(
        node_12.schedule_samplespace["mw_amplitudes"][first_qubit]
    )

    assert len(dummy_dataset_12.data_vars) == len(DEFAULT_TEST_QUBITS)
    assert dummy_dataset_12.data_vars[0].size == number_of_amplitudes_12


def test_12_pulse_duration(seeded_redis, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    qubits = ["q13", "q14", "q15"]
    node_12 = RabiOscillations12Node(qubits, ["q13_q14"], session=session_context)
    samplespace = {  # small samplespace
        "mw_amplitudes": {qubit: np.linspace(0.002, 0.800, 3) for qubit in qubits}
    }
    transmons_dict = {qubit: node_12.device.get_element(qubit) for qubit in qubits}
    measurement_class = node_12.measurement_cls(transmons_dict)
    schedule = measurement_class.schedule_function(
        **samplespace, **node_12.schedule_keywords
    )
    for pulses in schedule.operations.values():
        if pulses["name"] == "DRAGPulse":
            pulse_duration = pulses["pulse_info"][0]["duration"]

    assert pytest.approx(pulse_duration) == 7.6e-8


def test_dummy_n_rabi_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_n_rabi = NRabiOscillationsNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset_n_rabi = node_n_rabi.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]
    number_of_reps = len(node_n_rabi.schedule_samplespace["X_repetitions"][first_qubit])
    number_of_amplitudes_n_rabi = len(
        node_n_rabi.schedule_samplespace["mw_amplitudes_sweep"][first_qubit]
    )

    assert len(dummy_dataset_n_rabi.data_vars) == len(DEFAULT_TEST_QUBITS)
    assert (
        dummy_dataset_n_rabi.data_vars[0].size
        == number_of_reps * number_of_amplitudes_n_rabi
    )


def test_n_rabi_12_pulse_duration(seeded_redis, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    qubits = ["q13", "q14", "q15"]
    node_12 = NRabiOscillations12Node(qubits, ["q13_q14"], session=session_context)
    samplespace = {
        "mw_amplitudes_sweep": {qubit: np.linspace(-0.05, 0.05, 3) for qubit in qubits},
        "X_repetitions": {qubit: np.arange(1, 8, 4) for qubit in qubits},
    }
    transmons_dict = {qubit: node_12.device.get_element(qubit) for qubit in qubits}
    measurement_class = node_12.measurement_cls(transmons_dict)
    schedule = measurement_class.schedule_function(
        **samplespace, **node_12.schedule_keywords
    )
    for pulses in schedule.operations.values():
        if pulses["name"] == "DRAGPulse":
            pulse_duration = pulses["pulse_info"][0]["duration"]

    assert pytest.approx(pulse_duration) == 7.6e-8


@pytest.mark.parametrize(
    "node_cls, duration_parameter",
    [(RabiOscillationsNode, "rxy"), (RabiOscillations12Node, "r12")],
)
def test_each_qubit_is_driven_with_its_own_pulse_duration(
    seeded_redis, session_context, node_cls, duration_parameter
):
    ExtendedTransmon.close_all()
    qubits = ["q13", "q14", "q15"]
    durations = {"q13": 40e-9, "q14": 60e-9, "q15": 80e-9}
    node = node_cls(qubits, ["q13_q14"], session=session_context)
    transmons = {qubit: node.device.get_element(qubit) for qubit in qubits}
    for qubit, duration in durations.items():
        submodule = getattr(transmons[qubit], duration_parameter)
        if duration_parameter == "rxy":
            submodule.duration(duration)
        else:
            submodule.ef_duration(duration)

    schedule = node.measurement_cls(transmons).schedule_function(
        mw_amplitudes={qubit: np.linspace(0.002, 0.8, 3) for qubit in qubits},
        **node.schedule_keywords,
    )

    pulse_durations = {
        pulse["port"].split(":")[0]: pulse["duration"]
        for operation in schedule.operations.values()
        if operation["name"] == "DRAGPulse"
        for pulse in operation["pulse_info"]
    }
    assert pulse_durations == pytest.approx(durations)
