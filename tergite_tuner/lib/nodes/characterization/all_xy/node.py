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
"""AllXY: each pair of pulses' |1> population against the ideal gates'."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.characterization.all_xy.analysis import (
    IDEAL_POPULATIONS,
    analyse_all_xy,
    plot_all_xy,
)
from tergite_tuner.lib.nodes.characterization.all_xy.measurement import AllXYMeasurement
from tergite_tuner.lib.spec import NodeSpec, get_fixed_sweep
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


DUMMY_ERROR = 0.01


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon], XY_index: dict[str, np.ndarray]
) -> Schedule:
    """The AllXY schedule: each pulse pair, then the calibration points, on every qubit.

    Args:
        transmons: the qubits to measure, by name.
        XY_index: each qubit's pulse pair indices.

    Returns:
        The schedule.
    """
    return AllXYMeasurement(transmons).schedule_function(XY_index)


def get_dummy_s21(
    _qubit: str, _sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    """The ideal populations off by ``DUMMY_ERROR``, then the |0> and |1> calibration points.

    Args:
        _qubit: unused; part of the ``get_dummy_s21`` signature.
        _sweeps: unused; part of the ``get_dummy_s21`` signature.
        _session: unused; part of the ``get_dummy_s21`` signature.

    Returns:
        The qubit's S21, a point per pulse pair, then the two calibration points.
    """
    populations = IDEAL_POPULATIONS + DUMMY_ERROR
    return np.concatenate([populations, [0.0, 1.0]]).astype(complex)


ALL_XY_SPECS = {
    NodeEnum.ALL_XY: NodeSpec(
        name=NodeEnum.ALL_XY,
        element="qubit",
        get_schedule=get_schedule,
        analyse=analyse_all_xy,
        qois={"error": "all_xy_error"},
        sweeps={"XY_index": get_fixed_sweep(np.arange(23))},
        get_dummy_s21=get_dummy_s21,
        plot=plot_all_xy,
    )
}
