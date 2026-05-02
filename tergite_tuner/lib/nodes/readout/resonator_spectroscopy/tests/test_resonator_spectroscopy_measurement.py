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

from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    ResonatorSpectroscopy1Node,
    ResonatorSpectroscopy2Node,
    ResonatorSpectroscopyNode,
)
from tergite_tuner.lib.nodes.schedule_node import ScheduleNode
from tergite_tuner.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)
from tergite_tuner.utils.dto.extended_transmon_element import ExtendedTransmon


def test_measurement_0_type(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_0 = ResonatorSpectroscopyNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    assert issubclass(node_0.measurement_type_cls, ScheduleNode)


def test_measurement_1_type(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_1 = ResonatorSpectroscopy1Node(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    assert issubclass(node_1.measurement_type_cls, ScheduleNode)


def test_measurement_2_type(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_2 = ResonatorSpectroscopy2Node(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    assert issubclass(node_2.measurement_type_cls, ScheduleNode)


def test_dummy_0_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node = ResonatorSpectroscopyNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset_0 = node.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]
    number_of_frequencies = len(
        node.schedule_samplespace["ro_frequencies"][first_qubit]
    )
    assert len(dummy_dataset_0.data_vars) == len(DEFAULT_TEST_QUBITS)
    assert dummy_dataset_0.data_vars[0].size == number_of_frequencies


def test_dummy_1_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node = ResonatorSpectroscopy1Node(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset_1 = node.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]
    number_of_frequencies = len(
        node.schedule_samplespace["ro_frequencies"][first_qubit]
    )
    assert len(dummy_dataset_1.data_vars) == len(DEFAULT_TEST_QUBITS)
    assert dummy_dataset_1.data_vars[0].size == number_of_frequencies


def test_dummy_2_generation(session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node = ResonatorSpectroscopy2Node(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset_2 = node.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]
    number_of_frequencies = len(
        node.schedule_samplespace["ro_frequencies"][first_qubit]
    )
    assert len(dummy_dataset_2.data_vars) == len(DEFAULT_TEST_QUBITS)
    assert dummy_dataset_2.data_vars[0].size == number_of_frequencies
