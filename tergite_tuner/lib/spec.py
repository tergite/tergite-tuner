# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""A node as data: what it sweeps, measures, fits and stores."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.backend import Schedule
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

# an element's values of a swept setting
SweepFn = Callable[[str, "SessionContext"], np.ndarray]


class Fit(NamedTuple):
    value: Any
    error: float = 0


Fits = Mapping[str, Fit]


@dataclass(frozen=True)
class NodeSpec:
    """One calibration node.

    Attributes:
        name: the node.
        element: whether the node calibrates each qubit or each coupler.
        get_schedule: the schedule, given the transmons by name and each swept
            setting's values per element.
        analyse: the fits of one element's S21, which has a coordinate per swept
            setting, named by ``get_coord_name``; None if the element failed.
        qois: the Redis field each fit is stored in; fits it does not name are not stored.
        sweeps: each swept setting's values for an element, in the order the dataset
            is reshaped: the first setting varies fastest.
        get_dummy_s21: an element's S21 in dummy mode, given its sweeps' values.
        plot: draws an element's S21 and fits.
    """

    name: NodeEnum
    element: Literal["qubit", "coupler"]
    get_schedule: Callable[..., Schedule]
    analyse: Callable[[xr.DataArray], Fits | None]
    qois: Mapping[str, str]
    sweeps: Mapping[str, SweepFn]
    get_dummy_s21: Callable[[str, Mapping[str, np.ndarray], "SessionContext"], Any]
    plot: Callable[[Axes, xr.DataArray, Fits, "SessionContext"], None] | None = None
    schedule_keywords: Mapping[str, Any] = field(default_factory=dict)


def get_coord_name(quantity: str, element: str) -> str:
    return f"{quantity}{element}"
