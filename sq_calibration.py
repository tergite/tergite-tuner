from tergite_tuner import run_node, NodeEnum

qubits = [f"q{i}" for i in range(11, 16)]

def run_recalibration_with_empty_redis(qubits:list):
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
        NodeEnum.RANDOMIZED_BENCHMARKING
    ]

    for node in nodes:
        run_node(env_file="./.env", qubits=qubits, couplers=[], node=node)

def run_two_state_recalibration(qubits:list):
    nodes = [
        NodeEnum.RABI_OSCILLATIONS,
        NodeEnum.RAMSEY_CORRECTION,
        NodeEnum.MOTZOI_PARAMETER,
        NodeEnum.N_RABI_OSCILLATIONS,
        NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION
    ]

    for node in nodes:
        run_node(env_file="./.env", qubits=qubits, couplers=[], node=node)

def run_coherence_time_calibration(qubits:list):
    run_node(env_file="./.env", qubits=qubits, couplers=[], node=NodeEnum.T1)
    for qubit in qubits:
        run_node(env_file="./.env", qubits=[qubit], couplers=[], node=NodeEnum.T2)
        run_node(env_file="./.env", qubits=[qubit], couplers=[], node=NodeEnum.T2_ECHO)

def run_three_state_recalibration(qubits:list):
    nodes = [
        NodeEnum.RABI_OSCILLATIONS_12,
        NodeEnum.RAMSEY_CORRECTION_12,
        NodeEnum.MOTZOI_12_PARAMETER,
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
        NodeEnum.RANDOMIZED_BENCHMARKING
    ]

    for node in nodes:
        run_node(env_file="./.env", qubits=qubits, couplers=[], node=node)

if __name__ == "__main__":
    run_three_state_recalibration(qubits)