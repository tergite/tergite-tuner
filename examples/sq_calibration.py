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

from tergite_tuner import NodeEnum, SessionContext, run_node

QUBITS = [f"q{i}" for i in range(11, 16)]
# these run one qubit at a time
SERIAL_NODES = frozenset({NodeEnum.RAMSEY_CORRECTION_12, NodeEnum.T2, NodeEnum.T2_ECHO})


def run_nodes(session: SessionContext, nodes: list[NodeEnum]) -> None:
    """Runs each node in ``session``, which carries each node's results to the next."""
    qubits = list(session.qubits)
    for node in nodes:
        if node in SERIAL_NODES:
            for qubit in qubits:
                run_node(node, session=session, qubits=[qubit])
            session.update(qubits=qubits)
        else:
            run_node(node, session=session)


def run_full_recalibration(session: SessionContext) -> None:
    """Every single-qubit node, from the device config's values."""
    run_nodes(
        session,
        [
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
        ],
    )


def run_two_state_recalibration(session: SessionContext) -> None:
    run_nodes(
        session,
        [
            NodeEnum.RABI_OSCILLATIONS,
            NodeEnum.RAMSEY_CORRECTION,
            NodeEnum.MOTZOI_PARAMETER,
            NodeEnum.N_RABI_OSCILLATIONS,
            NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
            NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
        ],
    )


def run_coherence_time_calibration(session: SessionContext) -> None:
    run_nodes(session, [NodeEnum.T1, NodeEnum.T2, NodeEnum.T2_ECHO])


def run_three_state_recalibration(session: SessionContext) -> None:
    run_nodes(
        session,
        [
            NodeEnum.RABI_OSCILLATIONS_12,
            NodeEnum.RAMSEY_CORRECTION_12,
            NodeEnum.MOTZOI_12_PARAMETER,
            NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
            NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
            NodeEnum.RANDOMIZED_BENCHMARKING,
        ],
    )


def run_fast_recalibration(session: SessionContext) -> None:
    run_nodes(
        session,
        [
            NodeEnum.RABI_OSCILLATIONS,
            NodeEnum.RAMSEY_CORRECTION,
            NodeEnum.RAMSEY_CORRECTION_12,
            NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
            NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
            NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
            NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
            NodeEnum.RANDOMIZED_BENCHMARKING,
        ],
    )


if __name__ == "__main__":
    # pass an earlier run's results.json as calibration= to start from them
    run_fast_recalibration(
        SessionContext.from_env("./.env", qubits=QUBITS, couplers=[])
    )
