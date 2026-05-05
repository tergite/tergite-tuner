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

from tergite_tuner.lib.nodes.qubit_control.spectroscopy.node import (
    Qubit01SpectroscopyAmplitudeNode,
    Qubit01SpectroscopyNode,
    Qubit12SpectroscopyNode,
)
from tergite_tuner.lib.nodes.schedule_node import OuterScheduleNode, ScheduleNode
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)
from tergite_tuner.utils.dto.extended_transmon_element import ExtendedTransmon


def test_measurement_01_type(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_01 = Qubit01SpectroscopyNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    assert issubclass(node_01.measurement_type_cls, ScheduleNode)


def test_measurement_12_type(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_12 = Qubit12SpectroscopyNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    assert issubclass(node_12.measurement_type_cls, ScheduleNode)


def test_measurement_bring_up_type(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_bring_up = Qubit01SpectroscopyAmplitudeNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    assert issubclass(node_bring_up.measurement_type_cls, OuterScheduleNode)


def test_dummy_01_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node = Qubit01SpectroscopyNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset = node.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]

    number_of_frequencies = len(
        node.schedule_samplespace["spec_frequencies"][first_qubit]
    )
    number_of_amplitudes = len(
        node.schedule_samplespace["spec_pulse_amplitudes"][first_qubit]
    )

    data_vars = dummy_dataset.data_vars

    assert len(data_vars) == len(DEFAULT_TEST_QUBITS)
    assert data_vars[0].size == number_of_frequencies * number_of_amplitudes


def test_dummy_12_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node = Qubit12SpectroscopyNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset = node.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]

    number_of_frequencies = len(
        node.schedule_samplespace["spec_frequencies"][first_qubit]
    )
    number_of_amplitudes = len(
        node.schedule_samplespace["spec_pulse_amplitudes"][first_qubit]
    )

    data_vars = dummy_dataset.data_vars

    assert len(data_vars) == len(DEFAULT_TEST_QUBITS)
    assert data_vars[0].size == number_of_frequencies * number_of_amplitudes
