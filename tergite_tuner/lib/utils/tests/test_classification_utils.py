# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Chalmers Next Labs AB 2026
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
import xarray
from numpy import exp, pi

from tergite_tuner.lib.utils.classification_functions import (
    assign_state,
    generate_iq_shots,
    get_state_angles,
)
from tergite_tuner.state import DeviceState


def test_assign_state():
    qubit = "q06"
    discriminator = {"centroid_I": 1, "centroid_Q": 0, "omega_01": 330}
    discriminator |= {"omega_12": 180, "omega_20": 90}
    state = DeviceState({"transmons": {qubit: discriminator}})

    iq_points = np.array(
        [
            2,
            2 * exp(-1j * pi / 4),
            2 * exp(1j * pi / 4),
            2 * exp(1j * 3 * pi / 4),
            2 * exp(-1j * 3 * pi / 4),
        ]
    )
    iq_points_array = xarray.DataArray(iq_points).assign_attrs(qubit=qubit)
    assert xarray.DataArray([0, 1, 0, 2, 1]).equals(
        assign_state(iq_points_array, state)
    )


def test_each_state_lies_halfway_between_its_boundaries():
    angles = get_state_angles(omega_01=45, omega_12=120, omega_20=300)
    assert angles == pytest.approx({0: 352.5, 1: 82.5, 2: 210})


def test_generated_shots_are_read_as_the_states_they_were_drawn_for():
    qubit = "q06"
    discriminator = {"centroid_I": 1, "centroid_Q": 0, "omega_01": 330}
    discriminator |= {"omega_12": 180, "omega_20": 90}
    state = DeviceState({"transmons": {qubit: discriminator}})
    # each point certain of one state: 2, 0, then 1
    probabilities = np.zeros((3, 3))
    probabilities[[2, 0, 1], [0, 1, 2]] = 1

    shots = generate_iq_shots(probabilities, qubit, 2, state)

    states = assign_state(xarray.DataArray(shots).assign_attrs(qubit=qubit), state)
    assert states.values.tolist() == [2, 0, 1, 2, 0, 1]
