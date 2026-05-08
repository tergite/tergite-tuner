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

from tergite_tuner import run_node, NodeEnum
from tergite_tuner.config.session import SessionContext

couplers4 = ["q11_q12", "q12_q13", "q13_q14" , "q14_q15"]

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
    """
    Load initial cz parameters into an empty redis.
    This should only be run for the first-time calibration.    
    """
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

def run_cz_recalibration(coupler:str, export_to_bcc:bool=True):
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

    if export_to_bcc: flip_phase(coupler)

if __name__ == "__main__":
    run_cz_recalibration("q13_q14")