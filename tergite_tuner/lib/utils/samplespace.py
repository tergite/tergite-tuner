# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Stefan Hill 2024
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def resonator_samples(qubit: str, session: "SessionContext") -> np.ndarray:
    res_spec_samples = 91
    sweep_range = 4.0e6
    vna_frequency = session.device_config.resonators[qubit]["VNA_frequency"]
    min_freq = vna_frequency - sweep_range / 2
    max_freq = vna_frequency + sweep_range / 2
    return np.linspace(min_freq, max_freq, res_spec_samples)


def qubit_samples(
    qubit: str, session: "SessionContext", transition: str = "01"
) -> np.ndarray:
    """
    Raises:
        ValueError: If `transition` is not one of "01", or "12
    """
    qub_spec_samples = 71
    sweep_range = 6e6
    if transition == "01":
        vna_frequency = session.device_config.qubits[qubit]["VNA_f01_frequency"]
    elif transition == "12":
        vna_frequency = session.device_config.qubits[qubit]["VNA_f12_frequency"]
    else:
        raise ValueError(f"Unknown transition type '{transition}'")
    # FIXME: This is not safe, because vna_frequency might be undefined
    min_freq = vna_frequency - sweep_range / 2
    max_freq = vna_frequency + sweep_range / 2
    return np.linspace(min_freq, max_freq, qub_spec_samples)
