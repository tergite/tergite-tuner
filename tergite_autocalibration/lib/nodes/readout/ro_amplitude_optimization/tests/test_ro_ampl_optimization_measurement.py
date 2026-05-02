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


import os
from pathlib import Path

import numpy as np
import pytest

from tergite_autocalibration.lib.nodes.readout.ro_amplitude_optimization.node import (
    ROAmplitudeThreeStateOptimizationNode,
)
from tergite_autocalibration.tests.utils.decorators import loaded_redis
from tergite_autocalibration.tests.utils.fixtures import (
    DEFAULT_TEST_COUPLERS,
    DEFAULT_TEST_QUBITS,
)
from tergite_autocalibration.utils.dto.extended_transmon_element import ExtendedTransmon

_test_data_dir = os.path.join(
    Path(__file__).parent.parent.parent.parent, "data", "single_qubits_run"
)
_redis_values = os.path.join(_test_data_dir, "redis-single-qubits-run.json")


def test_dummy_generation(redis_connection, session_context):
    for qubit in DEFAULT_TEST_QUBITS:
        redis_connection.hset(f"transmons:{qubit}", "measure:pulse_amp", "0.05")
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    node_3 = ROAmplitudeThreeStateOptimizationNode(
        DEFAULT_TEST_QUBITS, DEFAULT_TEST_COUPLERS, session=session_context
    )
    dummy_dataset = node_3.generate_dummy_dataset()
    first_qubit = DEFAULT_TEST_QUBITS[0]
    number_of_ampls = len(node_3.schedule_samplespace["ro_amplitudes"][first_qubit])
    number_of_states = len(node_3.schedule_samplespace["qubit_states"][first_qubit])

    assert len(dummy_dataset.data_vars) == len(DEFAULT_TEST_QUBITS)
    assert (
        dummy_dataset.data_vars[0].size
        == number_of_ampls * number_of_states * node_3.loops
    )


def test_12_pulse_duration(redis_connection, session_context):
    ExtendedTransmon.close_all()  # ensure no other transmon objects are instantiated
    qubits = ["q13", "q14", "q15"]
    with loaded_redis(redis_connection, _redis_values):
        node_12 = ROAmplitudeThreeStateOptimizationNode(
            qubits, ["q13_q14"], session=session_context
        )
        # samplespace = {
        #     "mw_amplitudes": {qubit: np.linspace(0.002, 0.800, 3) for qubit in qubits}
        # }
        samplespace = {  # small samplespace
            "qubit_states": {
                qubit: np.array([0, 1, 2], dtype=np.int16) for qubit in qubits
            },
            "ro_amplitudes": {qubit: np.linspace(0.1, 0.3, 3) for qubit in qubits},
        }
        transmons_dict = {qubit: node_12.device.get_element(qubit) for qubit in qubits}
        measurement_class = node_12.measurement_cls(transmons_dict)
        schedule = measurement_class.schedule_function(
            **samplespace, **node_12.schedule_keywords
        )
        for pulses in schedule.operations.values():
            if pulses["name"] == "LoopOperation":
                shot_schedule = pulses["control_flow_info"]["body"]
                for shot in shot_schedule.operations.values():
                    if shot["name"] == "DRAGPulse":
                        pulse_duration = shot["pulse_info"][0]["duration"]
                        break

    assert pytest.approx(pulse_duration) == 7.6e-8
