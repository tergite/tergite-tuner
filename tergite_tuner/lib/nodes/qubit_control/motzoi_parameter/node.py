# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2026
# (C) Copyright Liangyu Chen 2024
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
"""DRAG motzoi calibration, from 0 and from 1."""

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.qubit_control.motzoi_parameter.analysis import (
    analyse_motzoi,
    plot_motzoi,
)
from tergite_tuner.lib.nodes.qubit_control.motzoi_parameter.measurement import (
    MotzoiParameterMeasurement,
)
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.lib.utils.analysis_models import RabiModel
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

MOTZOI_FIELDS = ("rxy:motzoi", "r12:ef_motzoi")
MOTZOIS = (np.linspace(-0.4, 0.1, 40), np.linspace(-0.2, 0.4, 41))
REPETITIONS = (np.arange(1, 19, 6), np.arange(1, 13, 4))
DUMMY_MOTZOI = -0.1

rabi = RabiModel()


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    mw_motzois: dict[str, np.ndarray],
    X_repetitions: dict[str, np.ndarray],
    state: int,
) -> Schedule:
    return MotzoiParameterMeasurement(transmons).schedule_function(
        mw_motzois, X_repetitions, qubit_state=state
    )


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    """Oscillations whose minimum is at ``DUMMY_MOTZOI`` for every number of repetitions."""
    columns = []
    for repetitions in sweeps["X_repetitions"]:
        frequency = repetitions / 2
        params = rabi.make_params(
            amplitude=0.2,
            frequency=frequency,
            offset=0.2,
            phase=np.pi - 2 * np.pi * frequency * DUMMY_MOTZOI,
        )
        columns.append(rabi.eval(params=params, drive_amp=sweeps["mw_motzois"]))
    return np.stack(columns, axis=1)


MOTZOI_SPECS = {
    name: NodeSpec(
        name=name,
        element="qubit",
        get_schedule=partial(get_schedule, state=state),
        analyse=analyse_motzoi,
        qois={"motzoi": MOTZOI_FIELDS[state]},
        sweeps={
            "mw_motzois": get_fixed_sweep(MOTZOIS[state]),
            "X_repetitions": get_fixed_sweep(REPETITIONS[state]),
        },
        get_dummy_s21=get_dummy_s21,
        plot=plot_motzoi,
    )
    for state, name in enumerate(
        (NodeEnum.MOTZOI_PARAMETER, NodeEnum.MOTZOI_12_PARAMETER)
    )
}
