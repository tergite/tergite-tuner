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

import numpy as np
import pytest

from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    DUMMY_SHIFTS,
    RESONATOR_SPECTROSCOPY_SPECS,
)
from tergite_tuner.lib.run import get_dummy_dataset, get_sweeps


@pytest.mark.parametrize("state", [0, 1, 2])
def test_dummy_resonator_dips_below_its_vna_frequency_by_the_states_shift(
    state, session_context
):
    spec = list(RESONATOR_SPECTROSCOPY_SPECS.values())[state]
    session = session_context.model_copy(update={"user_samplespace": {}})
    sweeps = get_sweeps(spec, session)

    dataset = get_dummy_dataset(spec, sweeps, session)

    qubit = session.qubits[0]
    frequencies = sweeps["ro_frequencies"][qubit]
    dip = frequencies[np.argmin(np.abs(dataset[0].values))]
    vna_frequency = session.device_config.resonators[qubit]["VNA_frequency"]
    assert len(dataset.data_vars) == len(session.qubits)
    assert dataset[0].size == len(frequencies)
    assert dip == pytest.approx(vna_frequency - DUMMY_SHIFTS[state], abs=0.3e6)
