# This code is part of Tergite
#
# (C) Eleftherios Moschandreou 2024, 2025, 2026
# (C) Copyright Chalmers Next Labs 2024, 2025, 2026
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
import xarray as xr
from sklearn.metrics import confusion_matrix

if TYPE_CHECKING:
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

    from tergite_tuner.state import DeviceState

DISCRIMINATOR_FIELDS = ("centroid_I", "centroid_Q", "omega_01", "omega_12", "omega_20")
# a dummy shot's distance from the centroid, in mV
DUMMY_RADIUS = 2
DUMMY_RADIUS_SPREAD = 0.1


def assign_state(iq_values: xr.DataArray, state: "DeviceState") -> xr.DataArray:
    """Classifies each shot as 0, 1 or 2 with the qubit's three-state discriminator.

    Args:
        iq_values: one qubit's IQ shots, with the qubit in its ``qubit`` attribute.
        state: the device state holding the qubit's discriminator.

    Returns:
        Each shot's state, shaped as ``iq_values``.
    """
    centroid_i, centroid_q, omega_01, omega_12, omega_20 = _get_discriminator(
        iq_values.attrs["qubit"], state
    )
    state_boundaries = {"01": omega_01, "12": omega_12, "20": omega_20}
    sorted_state_boundaries_dict = {
        k: v for k, v in sorted(state_boundaries.items(), key=lambda item: item[1])
    }
    sorted_state_boundaries = list(sorted_state_boundaries_dict.keys())
    iq_values = iq_values - (centroid_i + 1j * centroid_q)
    iq_values = xr.apply_ufunc(lambda x: (np.angle(x, deg=True) + 360) % 360, iq_values)

    def state_filter(angles_array) -> xr.DataArray:
        boundary_1 = sorted_state_boundaries[0]  # eg '01'
        boundary_2 = sorted_state_boundaries[1]  # eg '12'
        boundary_3 = sorted_state_boundaries[2]  # eg '20'
        angle_1 = state_boundaries[boundary_1]
        angle_2 = state_boundaries[boundary_2]
        angle_3 = state_boundaries[boundary_3]
        # find the common state between the boundaries. eg: '01' & '12' -> 1
        state_between_1_and_2 = int(list(set(boundary_1) & set(boundary_2))[0])
        state_between_2_and_3 = int(list(set(boundary_2) & set(boundary_3))[0])
        state_between_3_and_1 = int(list(set(boundary_3) & set(boundary_1))[0])
        condition_1 = (
            (angles_array > angle_1) & (angles_array < angle_2)
        ) * state_between_1_and_2
        condition_2 = (
            (angles_array > angle_2) & (angles_array < angle_3)
        ) * state_between_2_and_3
        condition_3 = (
            (angles_array < angle_1) | (angles_array > angle_3)
        ) * state_between_3_and_1
        return condition_1 + condition_2 + condition_3

    assigned_states = xr.apply_ufunc(state_filter, iq_values)
    return assigned_states


def calculate_probabilities(iq_data_var: xr.DataArray, state: "DeviceState"):
    """The fraction of a qubit's shots in 0, 1 and 2 at each point, over the ``loops`` dimension.

    Args:
        iq_data_var: one qubit's IQ shots, with a ``loops`` coordinate.
        state: the device state holding the qubit's discriminator.

    Returns:
        The probabilities, with a ``state`` dimension added and ``loops`` removed.

    Raises:
        ValueError: if ``iq_data_var`` has no ``loops`` coordinate.
    """
    if "loops" not in iq_data_var.coords:
        raise ValueError("Dataarray does not contain loop coordinate")
    states_array = assign_state(iq_data_var, state)
    qubit = iq_data_var.attrs["qubit"]
    loops_coord = iq_data_var.loops.name
    number_of_loops = iq_data_var.loops.size

    zeros = xr.where(states_array == 0, x=1, y=0)  # keep only |0> states
    ones = xr.where(states_array == 1, x=1, y=0)  # keep only |1> states
    twos = xr.where(states_array == 2, x=1, y=0)  # keep only |2> states

    ones = ones.reduce(func=np.sum, dim=loops_coord)
    twos = twos.reduce(func=np.sum, dim=loops_coord)
    zeros = zeros.reduce(func=np.sum, dim=loops_coord)

    probabilities_state_0 = zeros / number_of_loops
    probabilities_state_0 = probabilities_state_0.assign_coords(state=0)
    probabilities_state_0 = probabilities_state_0.assign_coords(qubit=qubit)
    probabilities_state_1 = ones / number_of_loops
    probabilities_state_1 = probabilities_state_1.assign_coords(state=1)
    probabilities_state_1 = probabilities_state_1.assign_coords(qubit=qubit)
    probabilities_state_2 = twos / number_of_loops
    probabilities_state_2 = probabilities_state_2.assign_coords(state=2)
    probabilities_state_2 = probabilities_state_2.assign_coords(qubit=qubit)

    state_probabilities = xr.concat(
        [probabilities_state_0, probabilities_state_1, probabilities_state_2],
        dim="state",
    )
    return state_probabilities


def generate_iq_shots(
    probabilities: np.ndarray, qubit: str, loops: int, state: "DeviceState"
) -> np.ndarray:
    """``loops`` shots per point that the qubit's discriminator reads with ``probabilities``, for dummy datasets.

    The inverse of ``calculate_probabilities``; each point's probabilities are like [0.2, 0.3, 0.5].

    Args:
        probabilities: each point's probabilities of 0, 1 and 2.
        qubit: the qubit whose discriminator reads the shots.
        loops: the shots per point.
        state: the device state holding the qubit's discriminator.

    Returns:
        The IQ shots, loop by loop, each loop a shot per point.
    """
    centroid_i, centroid_q, *omegas = _get_discriminator(qubit, state)
    state_angles = get_state_angles(*omegas)
    number_of_points = probabilities.size // 3
    probabilities = probabilities.T.reshape(number_of_points, 3)
    angles = [
        state_angles[np.random.choice([0, 1, 2], p=point_probabilities)]
        for _ in range(loops)
        for point_probabilities in probabilities
    ]
    rng = np.random.default_rng()
    magnitudes = np.tile(
        rng.normal(DUMMY_RADIUS, DUMMY_RADIUS_SPREAD, size=number_of_points), loops
    )
    return magnitudes * np.exp(1j * np.deg2rad(angles)) + centroid_i + 1j * centroid_q


def get_state_angles(
    omega_01: float, omega_12: float, omega_20: float
) -> dict[int, float]:
    """Each state's angle, in degrees, halfway between the two boundaries around it.

    Args:
        omega_01: the angle of the boundary between 0 and 1, in degrees.
        omega_12: the angle of the boundary between 1 and 2, in degrees.
        omega_20: the angle of the boundary between 2 and 0, in degrees.

    Returns:
        Each state's angle from the discriminator's centroid.
    """
    boundaries = sorted(
        {"01": omega_01, "12": omega_12, "20": omega_20}.items(),
        key=lambda item: item[1],
    )
    angles = {}
    for index, (pair, angle) in enumerate(boundaries):
        next_pair, next_angle = boundaries[(index + 1) % 3]
        between = int((set(pair) & set(next_pair)).pop())
        # the last state's boundaries wrap around through 360
        angles[between] = (angle + next_angle) / 2 + (180 if index == 2 else 0)
    return angles


def classify_shots(
    iq: np.ndarray, states: np.ndarray, lda: "LinearDiscriminantAnalysis"
) -> tuple[np.ndarray, np.ndarray, float]:
    """Each shot's state as ``lda`` fitted to them classifies it, the normalised confusion matrix, and the assignment fidelity, its mean diagonal.

    Args:
        iq: the shots, as rows of I and Q.
        states: the state each shot was prepared in.
        lda: the discriminant to fit to the shots.

    Returns:
        The shots' classified states, the confusion matrix and the assignment fidelity.
    """
    classified = lda.fit(iq, states).predict(iq)
    matrix = confusion_matrix(states, classified, normalize="true")
    return classified, matrix, np.trace(matrix) / len(np.unique(states))


def _get_discriminator(qubit: str, state: "DeviceState") -> tuple[float, ...]:
    """The qubit's three-state discriminator: its centroid's I and Q, and its boundaries' angles."""
    return tuple(
        float(state.read("transmons", qubit, field)) for field in DISCRIMINATOR_FIELDS
    )
