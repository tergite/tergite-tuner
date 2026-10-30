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

from pathlib import Path

from tergite_tuner import NodeEnum, SessionContext, run_node

# a first calibration's starting point, for couplers with no earlier results
CZ_INITIAL_PARAMETERS = {
    "q11_q12": {
        "cz_pulse_frequency": 631910000.0,
        "cz_pulse_amplitude": 0.275,
        "cz_pulse_duration": 4.24e-07,
    },
    "q12_q13": {
        "cz_pulse_frequency": 772550000.0,
        "cz_pulse_amplitude": 0.92,
        "cz_pulse_duration": 2.84e-07,
    },
    "q13_q14": {
        "cz_pulse_frequency": 719727018.0,
        "cz_pulse_amplitude": 0.554,
        "cz_pulse_duration": 1.8e-07,
    },
    "q14_q15": {
        "cz_pulse_frequency": 427126551.0,
        "cz_pulse_amplitude": 0.39,
        "cz_pulse_duration": 2.08e-07,
    },
}
# CZ local phases negates these qubits' phases, as BCC expects them
REVERSE_PHASE_QUBITS = ("q11", "q13")


def run_cz_recalibration(coupler: str, calibration: Path | None = None) -> None:
    """Recalibrates ``coupler``'s CZ from an earlier run's results, or from the initial parameters."""
    session = SessionContext.from_env(
        "./.env",
        qubits=coupler.split("_"),
        couplers=[coupler],
        calibration=calibration,
        reverse_phase_qubits=REVERSE_PHASE_QUBITS,
    )
    if calibration is None:
        session.state.load({"couplers": {coupler: CZ_INITIAL_PARAMETERS[coupler]}})

    nodes = [NodeEnum.CZ_CALIBRATION, NodeEnum.CZ_LOCAL_PHASES, NodeEnum.CZ_RB]
    if "q12" not in coupler:
        nodes.insert(0, NodeEnum.CZ_CHEVRON)
    for node in nodes:
        run_node(node, session=session)


if __name__ == "__main__":
    run_cz_recalibration("q13_q14")
