# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Abdullah Al Amin 2026
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Rabi and NRabi, from 0 to 1 and from 1 to 2: each transition's pi amplitude."""

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.analysis import (
    analyse_n_rabi,
    analyse_rabi,
    plot_n_rabi,
    plot_rabi,
)
from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.measurement import (
    NRabiOscillationsMeasurement,
    RabiOscillationsMeasurement,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.lib.utils.analysis_models import RabiModel
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

AMP180_FIELDS = ("rxy:amp180", "r12:ef_amp180")
# the largest drive amplitude Rabi sweeps to, per transition
RABI_MAX_AMPLITUDES = (0.90, 0.80)
RABI_POINTS = 61
# NRabi's amplitude corrections, as (half width, points), and pi pulse counts
N_RABI_CORRECTIONS = ((0.045, 30), (0.05, 31))
N_RABI_REPETITIONS = (np.arange(1, 23, 6), np.arange(1, 13, 4))
# the dummy NRabi's amplitude correction
DUMMY_CORRECTION = -0.01

rabi = RabiModel()


def get_rabi_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    mw_amplitudes: dict[str, np.ndarray],
    state: int,
) -> Schedule:
    return RabiOscillationsMeasurement(transmons).schedule_function(
        mw_amplitudes, qubit_state=state
    )


def get_n_rabi_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    mw_amplitudes_sweep: dict[str, np.ndarray],
    X_repetitions: dict[str, np.ndarray],
    state: int,
) -> Schedule:
    return NRabiOscillationsMeasurement(transmons).schedule_function(
        mw_amplitudes_sweep, X_repetitions, qubit_state=state
    )


def get_dummy_rabi(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    params = rabi.make_params(amplitude=0.2, frequency=1, offset=0.2)
    return rabi.eval(params=params, drive_amp=sweeps["mw_amplitudes"])


def get_dummy_n_rabi(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    """Oscillations whose minimum is at ``DUMMY_CORRECTION`` for every number of pi pulses."""
    columns = []
    for repetitions in sweeps["X_repetitions"]:
        frequency = 2 * repetitions
        params = rabi.make_params(
            amplitude=0.2,
            frequency=frequency,
            offset=0.2,
            phase=np.pi - 2 * np.pi * frequency * DUMMY_CORRECTION,
        )
        columns.append(
            rabi.eval(params=params, drive_amp=sweeps["mw_amplitudes_sweep"])
        )
    return np.stack(columns, axis=1)


RABI_SPECS = {
    name: NodeSpec(
        name=name,
        element="qubit",
        get_schedule=partial(get_rabi_schedule, state=state),
        analyse=analyse_rabi,
        qois={"amp180": AMP180_FIELDS[state]},
        sweeps={
            "mw_amplitudes": get_fixed_sweep(
                np.linspace(0.002, RABI_MAX_AMPLITUDES[state], RABI_POINTS)
            )
        },
        get_dummy_s21=get_dummy_rabi,
        plot=plot_rabi,
    )
    for state, name in enumerate(
        (NodeEnum.RABI_OSCILLATIONS, NodeEnum.RABI_OSCILLATIONS_12)
    )
}

N_RABI_SPECS = {
    name: NodeSpec(
        name=name,
        element="qubit",
        get_schedule=partial(get_n_rabi_schedule, state=state),
        analyse=partial(analyse_n_rabi, amp180_field=AMP180_FIELDS[state]),
        qois={"amp180": AMP180_FIELDS[state]},
        sweeps={
            "mw_amplitudes_sweep": get_fixed_sweep(np.linspace(-width, width, points)),
            "X_repetitions": get_fixed_sweep(N_RABI_REPETITIONS[state]),
        },
        get_dummy_s21=get_dummy_n_rabi,
        plot=plot_n_rabi,
    )
    for state, (name, (width, points)) in enumerate(
        zip(
            (NodeEnum.N_RABI_OSCILLATIONS, NodeEnum.N_RABI_12_OSCILLATIONS),
            N_RABI_CORRECTIONS,
            strict=True,
        )
    )
}
