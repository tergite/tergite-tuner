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
"""Fits Rabi oscillations, and finds the amplitude correction a train of pi pulses settles."""

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits, get_coord_name
from tergite_tuner.lib.utils.analysis_models import RabiModel

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

# a pi amplitude at or above this is beyond what the drive can give
MAX_PI_AMPLITUDE = 0.95

model = RabiModel()


def analyse_rabi(s21: xr.DataArray, _session: "SessionContext") -> Fits | None:
    """The pi pulse's ``amp180`` from a cosine fitted to ``|S21|`` against drive amplitude."""
    amplitudes = s21.coords[get_coord_name("mw_amplitudes", s21.attrs["qubit"])].values
    magnitudes = np.abs(s21.values)
    guess = model.guess(magnitudes, drive_amp=amplitudes)
    result = model.fit(magnitudes, params=guess, drive_amp=amplitudes)
    pi_amplitude = result.params["amp180"].value
    if pi_amplitude >= MAX_PI_AMPLITUDE:
        return None
    return {"amp180": Fit(pi_amplitude), "model": Fit(result)}


def plot_rabi(
    axis: Axes, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    amplitudes = s21.coords[get_coord_name("mw_amplitudes", s21.attrs["qubit"])].values
    if "model" in fits:
        fit_amplitudes = np.linspace(amplitudes[0], amplitudes[-1], 200)
        axis.plot(
            fit_amplitudes,
            fits["model"].value.eval(drive_amp=fit_amplitudes),
            "r-",
            lw=3.0,
            label=f"π_ampl = {fits['amp180'].value:.2E} (V)",
        )
        axis.legend()
    axis.plot(amplitudes, np.abs(s21.values), "bo-", ms=3.0)
    axis.set_xlabel("Amplitude (V)")
    axis.set_ylabel("|S21| (V)")
    axis.grid()


def analyse_n_rabi(
    s21: xr.DataArray, session: "SessionContext", amp180_field: str
) -> Fits:
    """``amp180``: the stored ``amp180_field`` plus the correction with the least ``|S21|`` over all repetitions."""
    qubit = s21.attrs["qubit"]
    sums = np.abs(s21).sum(get_coord_name("X_repetitions", qubit))
    correction = sums.idxmin().item()
    previous_amplitude = session.redis_store.read_field(
        "transmons", pk=qubit, field_path=amp180_field
    )
    return {
        "amp180": Fit(correction + previous_amplitude),
        "correction": Fit(correction),
    }


def plot_n_rabi(
    axis: Axes, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    x = get_coord_name("mw_amplitudes_sweep", s21.attrs["qubit"])
    np.abs(s21).plot(ax=axis, x=x, cmap="RdBu_r")
    axis.set_xlabel("mw amplitude correction")
    if "correction" in fits:
        axis.axvline(fits["correction"].value, c="k", lw=4, linestyle="--")
