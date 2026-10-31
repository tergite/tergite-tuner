# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Readout amplitude optimization for two and three states, and three-state discrimination."""

from collections.abc import Callable, Mapping
from functools import partial
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.analysis import (
    analyse_three_state_ro_amplitude,
    analyse_two_state_ro_amplitude,
    plot_ro_amplitude,
)
from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.measurement import (
    ROAmplitudeOptimizationMeasurement,
)
from tergite_tuner.lib.spec import Fits, NodeSpec, SweepFn, get_fixed_sweep
from tergite_tuner.lib.utils.functions import isosceles_triangle
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

LOOPS = 1000
TWO_STATE_FIELDS = (
    "measure_2state_opt:pulse_amp",
    "measure_2state_opt:acq_rotation",
    "measure_2state_opt:acq_threshold",
    "lda_coef_0",
    "lda_coef_1",
    "lda_intercept",
)
THREE_STATE_FIELDS = (
    "measure_3state_opt:pulse_amp",
    "centroid_I",
    "centroid_Q",
    "omega_01",
    "omega_12",
    "omega_20",
    "inv_cm_opt",
)
# the dummy shots' spread around their state's centre
DUMMY_SPREAD = 0.7


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    qubit_states: dict[str, np.ndarray],
    ro_amplitudes: dict[str, np.ndarray],
    loop_repetitions: int,
    state: int,
) -> Schedule:
    """The schedule that prepares each state and reads it out at each amplitude, ``loop_repetitions`` times.

    Args:
        transmons: the qubits' transmons by name.
        qubit_states: each qubit's states to prepare.
        ro_amplitudes: each qubit's readout amplitudes.
        loop_repetitions: how many shots to take of each point.
        state: the highest state prepared: 1 for two states, 2 for three.

    Returns:
        The schedule.
    """
    return ROAmplitudeOptimizationMeasurement(transmons).schedule_function(
        ro_amplitudes, qubit_states, loop_repetitions, qubit_state=state
    )


def get_amplitudes(
    qubit: str, session: "SessionContext", low: float, high: float, points: int
) -> np.ndarray:
    """``points`` amplitudes from ``low`` to ``high`` times the qubit's punchout amplitude.

    Args:
        qubit: the qubit.
        session: the session whose device state holds the punchout amplitude.
        low: the lowest amplitude, as a fraction of the punchout amplitude.
        high: the highest amplitude, as a fraction of the punchout amplitude.
        points: how many amplitudes.

    Returns:
        The amplitudes.
    """
    punchout = float(session.state.read("transmons", qubit, "measure:pulse_amp"))
    return np.linspace(punchout * low, punchout * high, points)


def get_optimal_amplitude(qubit: str, session: "SessionContext") -> np.ndarray:
    """The three-state readout amplitude already stored, as the only point of the sweep.

    Args:
        qubit: the qubit.
        session: the session whose device state holds the amplitude.

    Returns:
        The one amplitude.
    """
    amplitude = session.state.read("transmons", qubit, "measure_3state_opt:pulse_amp")
    return np.array([float(amplitude)])


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    """Shots around each state's corner of a triangle that grows with the amplitude's index.

    Args:
        _qubit: unused; part of the ``get_dummy_s21`` signature.
        sweeps: the prepared states and readout amplitudes.
        _session: unused; part of the ``get_dummy_s21`` signature.

    Returns:
        S21 with an axis per state, amplitude and loop.
    """
    rng = np.random.default_rng(0)
    states, amplitudes = len(sweeps["qubit_states"]), len(sweeps["ro_amplitudes"])
    shots = np.empty((states, amplitudes, LOOPS), dtype=complex)
    for amplitude in range(amplitudes):
        size = amplitude + 0.05
        centres = isosceles_triangle(base_length=3 * size, height=5 * size)
        for state in range(states):
            iq = rng.normal(loc=centres[state], scale=DUMMY_SPREAD, size=(LOOPS, 2))
            shots[state, amplitude] = iq[:, 0] + 1j * iq[:, 1]
    return shots


def _get_spec(
    name: NodeEnum,
    states: int,
    amplitudes: SweepFn,
    analyse: Callable[..., Fits],
    fields: tuple[str, ...],
) -> NodeSpec:
    return NodeSpec(
        name=name,
        element="qubit",
        get_schedule=partial(get_schedule, state=states - 1),
        analyse=analyse,
        qois={field: field for field in fields},
        sweeps={
            "qubit_states": get_fixed_sweep(np.arange(states, dtype=np.int16)),
            "ro_amplitudes": amplitudes,
        },
        get_dummy_s21=get_dummy_s21,
        plot=plot_ro_amplitude,
        loops=LOOPS,
        plot_rows=3,
    )


RO_AMPLITUDE_SPECS = {
    spec.name: spec
    for spec in (
        _get_spec(
            NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
            2,
            partial(get_amplitudes, low=1 / 4, high=1.2, points=45),
            analyse_two_state_ro_amplitude,
            TWO_STATE_FIELDS,
        ),
        _get_spec(
            NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
            3,
            partial(get_amplitudes, low=1 / 2.5, high=1.4, points=30),
            analyse_three_state_ro_amplitude,
            THREE_STATE_FIELDS,
        ),
        _get_spec(
            NodeEnum.THREE_STATE_DISCRIMINATION,
            3,
            get_optimal_amplitude,
            analyse_three_state_ro_amplitude,
            THREE_STATE_FIELDS,
        ),
    )
}
