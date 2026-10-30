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
"""How far AllXY's pulse pairs leave the qubit from the populations ideal gates give."""

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.nodes.characterization.all_xy.measurement import all_XY_angles
from tergite_tuner.lib.spec import Fit, Fits

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

# the |1> population ideal gates give each pulse pair, in the measurement's order
IDEAL_POPULATIONS = np.array([0.0] * 5 + [0.5] * 12 + [1.0] * 4)
GATE_NAMES = {
    (0, 0): "I",
    (90, 0): "X90",
    (180, 0): "X",
    (90, 90): "Y90",
    (180, 90): "Y",
}


def analyse_all_xy(s21: xr.DataArray, _session: "SessionContext") -> Fits:
    """Each pair's |1> population, from the |0> and |1> calibration points last, and their mean deviation from the ideal."""
    values = s21.values
    calibration_0, calibration_1 = values[-2], values[-1]
    populations = np.real(
        (values[:-2] - calibration_0) / (calibration_1 - calibration_0)
    )
    deviations = np.abs(populations - IDEAL_POPULATIONS)
    return {
        "error": Fit(float(deviations.mean()), float(deviations.std())),
        "populations": Fit(populations),
    }


def plot_all_xy(
    axis: Axes, _s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    pairs = np.arange(len(IDEAL_POPULATIONS))
    axis.plot(pairs, IDEAL_POPULATIONS, "k--", lw=1, label="ideal")
    axis.plot(pairs, fits["populations"].value, "bo", ms=5.0)
    axis.set_xticks(pairs)
    axis.set_xticklabels(get_pair_labels(), rotation=90)
    axis.set_ylabel("|1> population")
    axis.set_title(f"error = {fits['error'].value:.3f}")
    axis.legend()
    axis.grid()


def get_pair_labels() -> list[str]:
    """Each pulse pair's gates, as ``XY90``."""
    return [
        "".join(GATE_NAMES[(pulse["theta"], pulse["phi"])] for pulse in pulses)
        for pulses in all_XY_angles.values()
    ]
