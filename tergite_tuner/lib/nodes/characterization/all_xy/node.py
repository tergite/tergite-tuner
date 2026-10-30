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
"""AllXY, which has no analysis yet (REFACTOR.md step 9.7)."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.characterization.all_xy.measurement import AllXYMeasurement
from tergite_tuner.lib.spec import Fits, NodeSpec, get_fixed_sweep
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon], XY_index: dict[str, np.ndarray]
) -> Schedule:
    return AllXYMeasurement(transmons).schedule_function(XY_index)


def analyse_all_xy(_s21: xr.DataArray, _session: "SessionContext") -> Fits:
    raise NotImplementedError("AllXY has no analysis yet (REFACTOR.md step 9.7)")


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return np.zeros(len(sweeps["XY_index"]), dtype=complex)


ALL_XY_SPECS = {
    NodeEnum.ALL_XY: NodeSpec(
        name=NodeEnum.ALL_XY,
        element="qubit",
        get_schedule=get_schedule,
        analyse=analyse_all_xy,
        qois={},
        sweeps={"XY_index": get_fixed_sweep(np.arange(23))},
        get_dummy_s21=get_dummy_s21,
    )
}
