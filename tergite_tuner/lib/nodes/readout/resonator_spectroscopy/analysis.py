# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023
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
"""Fits a resonator's dip in a frequency sweep of its S21."""

from typing import TYPE_CHECKING, NamedTuple

import lmfit
import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits
from tergite_tuner.lib.utils import fitting_models as fm
from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

model = fm.ResonatorModel()

# the Redis field of the readout frequency with the qubit in each state
READOUT_FIELDS = (
    "clock_freqs:readout",
    "extended_clock_freqs:readout_1",
    "extended_clock_freqs:readout_2",
)
STATE_COLOURS = ("blue", "green", "red")


class ResonatorFit(NamedTuple):
    result: lmfit.model.ModelResult
    frequency: float
    Ql: float
    minimum: float


def fit_resonator(frequencies: np.ndarray, s21: np.ndarray) -> ResonatorFit | None:
    """The resonator model fitted to ``s21``, or None if the fit raised.

    ``frequency`` is the fitted dip's minimum, and ``minimum`` the swept frequency
    with the smallest ``|s21|``.
    """
    guess = model.guess(s21, f=frequencies)
    try:
        result = model.fit(s21, params=guess, f=frequencies)
    except Exception as e:
        logger.info(f"Could not fit the resonator data: {e}")
        return None
    if not result.success:
        logger.info("Fit was unsuccessful.")
        logger.info(f"Reason:{result.message}")

    fr = result.params["fr"].value
    Ql = result.params["Ql"].value
    Qe = result.params["Qe"].value
    theta = result.params["theta"].value
    # the analytical minimum; an interpolation of the fit might be better
    frequency = (
        fr
        / (4 * Qe * Ql * np.sin(theta))
        * (
            4 * Qe * Ql * np.sin(theta)
            - 2 * Qe * np.cos(theta)
            + Ql
            + np.sqrt(4 * Qe**2 - 4 * Qe * Ql * np.cos(theta) + Ql**2)
        )
    )
    minimum = frequencies[np.argmin(np.abs(s21))]
    return ResonatorFit(result, frequency, Ql, minimum)


def analyse_resonator(s21: xr.DataArray, _session: "SessionContext") -> Fits | None:
    """The resonator's ``frequency``, ``Ql`` and data ``minimum``, and the lmfit ``model``."""
    fit = fit_resonator(s21.coords[s21.dims[0]].values, s21.values)
    if fit is None:
        return None
    return {
        "frequency": Fit(fit.frequency),
        "Ql": Fit(fit.Ql),
        "minimum": Fit(fit.minimum),
        "model": Fit(fit.result),
    }


def plot_resonator(
    axis: Axes, s21: xr.DataArray, fits: Fits, session: "SessionContext", state: int
) -> None:
    """The fit and its frequency, with the readout frequencies of the states below ``state``."""
    if "model" not in fits or not fits["model"].value.success:
        axis.plot(s21.coords[s21.dims[0]].values, np.abs(s21.values))
    else:
        fits["model"].value.plot_fit(axis, numpoints=400, xlabel=None, title=None)
        frequency = fits["frequency"].value
        label = f"f = {frequency:.6E}" if state == 0 else f"frequency |{state}>"
        axis.axvline(frequency, c=STATE_COLOURS[state], ls="solid", label=label)
        for lower_state in reversed(range(state)):
            lower_frequency = session.redis.hget(
                f"transmons:{s21.attrs['qubit']}", READOUT_FIELDS[lower_state]
            )
            if lower_frequency is None:
                continue
            axis.axvline(
                float(lower_frequency),
                c=STATE_COLOURS[lower_state],
                ls="dashed",
                label=f"frequency |{lower_state}>",
            )
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel("|S21| (V)")
    axis.legend()
    axis.grid()
