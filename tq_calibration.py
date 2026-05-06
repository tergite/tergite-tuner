from tergite_tuner import run_node, NodeEnum
from tergite_tuner.config.session import SessionContext

couplers = ["q11_q12", "q12_q13", "q13_q14" , "q14_q15"]

cz_initial_parameters = {
    "q11_q12": {
        "cz_pulse_frequency": "631910000.0",
        "cz_pulse_amplitude": "0.275",
        "cz_pulse_duration": "4.24e-07"
    },
    "q12_q13": {
        "cz_pulse_frequency": "772550000.0",
        "cz_pulse_amplitude": "0.92",
        "cz_pulse_duration": "2.84e-07"
    },
    "q13_q14": {
        "cz_pulse_frequency": "719727018",
        "cz_pulse_amplitude": "0.554",
        "cz_pulse_duration": "1.8e-07"
    },
    "q14_q15": {
        "cz_pulse_frequency": "427126551.0",
        "cz_pulse_amplitude": "0.39",
        "cz_pulse_duration": "2.08e-07"
    }
}

def load_initial_cz_parameters_to_empty_redis(env_file="./.env"):
    session = SessionContext.from_env(env_file)
    redis_connection = session.redis
    for coupler in cz_initial_parameters:
        for key in cz_initial_parameters[coupler]:
            redis_connection.hset(
                f"couplers:{coupler}", key, cz_initial_parameters[coupler][key])
            
def flip_phase(coupler):
    qubits = coupler.split("_")
    session = SessionContext.from_env("./.env")
    redis_connection = session.redis
    for qubit in qubits:
        if int(qubit[1:]) % 2 == 0:
            # Even qubits are data/control qubits
            qubit_type = "control"
        else:
            # Odd qubits are ancilla/target qubits
            qubit_type = "target"
        redis_key = 'cz_dynamic_' + qubit_type
        if qubit in ["q11", "q13"]:
            phase = float(redis_connection.hget(f"couplers:{coupler}", redis_key))
            phase = -phase
            redis_connection.hset(f"couplers:{coupler}", redis_key, phase)

def run_cz_recalibration(coupler:str):
    qubits = coupler.split("_")
    nodes = [
        NodeEnum.CZ_CALIBRATION,
        NodeEnum.CZ_LOCAL_PHASES,
        NodeEnum.CZ_RB,
    ]
    if "q12" not in coupler:
        nodes.insert(0, NodeEnum.CZ_CHEVRON)

    for node in nodes:
        run_node(env_file="./.env", qubits=qubits, couplers=[coupler], node=node)

if __name__ == "__main__":
    # run_cz_recalibration("q13_q14")
    # flip_phase("q11_q12")
    flip_phase("q12_q13")