# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman 2024
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
"""Corrects a qubit frequency from the detunings Ramsey fringes oscillate at."""

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits, get_coord_name
from tergite_tuner.lib.utils.analysis_models import RamseyModel

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

model = RamseyModel()


def analyse_ramsey(
    s21: xr.DataArray, session: "SessionContext", frequency_field: str
) -> Fits:
    """``frequency``: the stored ``frequency_field`` corrected by the artificial detuning the fringes vanish at.

    Each artificial detuning's fringes are fitted for their detuning, which is signed
    by where the fitted detunings turn, and a line through them crosses zero at the
    correction.
    """
    qubit = s21.attrs["qubit"]
    artificial_detunings = s21.coords[
        get_coord_name("artificial_detunings", qubit)
    ].values
    signed_detunings = _get_signed_detunings(s21, artificial_detunings)
    slope, intercept = np.polyfit(artificial_detunings, signed_detunings, 1)
    correction = -intercept / slope
    frequency = float(session.state.read("transmons", qubit, frequency_field))
    return {
        "frequency": Fit(frequency + correction),
        "correction": Fit(correction),
        "signed_detunings": Fit(signed_detunings),
        "line": Fit(np.poly1d((slope, intercept))),
    }


def plot_ramsey(
    axis: Axes, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    detunings = s21.coords[
        get_coord_name("artificial_detunings", s21.attrs["qubit"])
    ].values
    axis.plot(detunings, fits["signed_detunings"].value, "bo", ms=5.0)
    correction = fits["correction"].value
    axis.axvline(
        correction, color="red", label=f"correction: {int(correction) / 1e3} kHz"
    )
    axis.plot(detunings, fits["line"].value(detunings), "--b", lw=1)
    axis.axvline(0, color="black", lw=1)
    axis.set_xlabel("Artificial detuning (Hz)")
    axis.set_ylabel("Fitted detuning (Hz)")
    axis.legend()
    axis.grid()


def _get_signed_detunings(
    s21: xr.DataArray, artificial_detunings: np.ndarray
) -> np.ndarray:
    """Each artificial detuning's fitted fringe frequency, negative before the fitted detunings turn."""
    qubit = s21.attrs["qubit"]
    delays = s21.coords[get_coord_name("ramsey_delays", qubit)].values
    detuning_coord = get_coord_name("artificial_detunings", qubit)
    magnitudes = np.abs(s21)
    fitted_detunings = []
    for index in range(len(artificial_detunings)):
        fringes = magnitudes.isel({detuning_coord: index}).values
        guess = model.guess(fringes, t=delays)
        result = model.fit(fringes, params=guess, t=delays)
        fitted_detunings.append(result.params["frequency"].value)
    fitted_detunings = np.array(fitted_detunings)

    directions = np.diff(artificial_detunings + 1j * fitted_detunings)
    turn = np.argmin(np.abs(np.sin(np.angle(directions)))) + 1
    return np.concatenate((-fitted_detunings[:turn], fitted_detunings[turn:]))
