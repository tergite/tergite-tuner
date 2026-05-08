# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from tergite_tuner import NodeEnum, run_node

qubits5 = [f"q{i}" for i in range(11, 16)]


def run_nodes(nodes: list[str], qubits: list[str], is_parallels: list[bool]):
    assert len(nodes) == len(is_parallels)
    for node, is_parallel in zip(nodes, is_parallels):
        if is_parallel:
            run_node(env_file="./.env", qubits=qubits, couplers=[], node=node)
        else:
            for qubit in qubits:
                run_node(env_file="./.env", qubits=[qubit], couplers=[], node=node)


def _is_parallel(node: str):
    if "correction_12" in node or "T2" in node:
        return False
    else:
        return True


def run_recalibration_with_empty_redis(qubits: list):
    nodes = [
        NodeEnum.RESONATOR_SPECTROSCOPY,
        NodeEnum.QUBIT_01_SPECTROSCOPY,
        NodeEnum.RABI_OSCILLATIONS,
        NodeEnum.RAMSEY_CORRECTION,
        NodeEnum.MOTZOI_PARAMETER,
        NodeEnum.N_RABI_OSCILLATIONS,
        NodeEnum.RESONATOR_SPECTROSCOPY_1,
        NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
        NodeEnum.QUBIT_12_SPECTROSCOPY,
        NodeEnum.RABI_OSCILLATIONS_12,
        NodeEnum.RAMSEY_CORRECTION_12,
        NodeEnum.MOTZOI_12_PARAMETER,
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
        NodeEnum.RANDOMIZED_BENCHMARKING,
    ]

    run_nodes(nodes, qubits, is_parallels=[_is_parallel(node) for node in nodes])


def run_two_state_recalibration(qubits: list):
    nodes = [
        NodeEnum.RABI_OSCILLATIONS,
        NodeEnum.RAMSEY_CORRECTION,
        NodeEnum.MOTZOI_PARAMETER,
        NodeEnum.N_RABI_OSCILLATIONS,
        NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
    ]

    run_nodes(nodes, qubits, is_parallels=[_is_parallel(node) for node in nodes])


def run_coherence_time_calibration(qubits: list):
    nodes = [NodeEnum.T1, NodeEnum.T2, NodeEnum.T2_ECHO]
    run_nodes(nodes, qubits, is_parallels=[_is_parallel(node) for node in nodes])


def run_three_state_recalibration(qubits: list):
    nodes = [
        NodeEnum.RABI_OSCILLATIONS_12,
        NodeEnum.RAMSEY_CORRECTION_12,
        NodeEnum.MOTZOI_12_PARAMETER,
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
        NodeEnum.RANDOMIZED_BENCHMARKING,
    ]

    run_nodes(nodes, qubits, is_parallels=[_is_parallel(node) for node in nodes])


def run_fast_recalibration(qubits: list):
    nodes = [
        NodeEnum.RABI_OSCILLATIONS,
        NodeEnum.RAMSEY_CORRECTION,
        NodeEnum.RAMSEY_CORRECTION_12,
        NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
    ]

    run_nodes(nodes, qubits, is_parallels=[_is_parallel(node) for node in nodes])


if __name__ == "__main__":
    run_fast_recalibration(qubits5)
