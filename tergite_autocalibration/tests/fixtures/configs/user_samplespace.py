# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Chalmers Next Labs AB 2024, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Example helper showing how to build a custom user samplespace.

The function below takes a fully loaded ``Configuration`` object so that
samplespaces can be derived from device parameters (VNA frequencies, qubit
ids, ...) without relying on any global state.

user_samplespace schema:
user_samplespace = {
    node1_name : {
            "settable_of_node1_1": { 'q1': np.ndarray, 'q2': np.ndarray },
            "settable_of_node1_2": { 'q1': np.ndarray, 'q2': np.ndarray },
            ...
        },
    node2_name : {
            "settable_of_node2_1": { 'q1': np.ndarray, 'q2': np.ndarray },
            "settable_of_node2_2": { 'q1': np.ndarray, 'q2': np.ndarray },
            ...
        }
}
"""

from tergite_autocalibration.config.load import Configuration
from tergite_autocalibration.lib.utils.samplespace import resonator_samples


def make_user_samplespace(config: Configuration) -> dict:
    """Return an example user samplespace derived from ``config``."""
    qubits = config.device.qubits
    return {
        "resonator_spectroscopy": {
            "ro_frequencies": {
                qubit: resonator_samples(qubit, config) for qubit in qubits
            }
        },
    }
