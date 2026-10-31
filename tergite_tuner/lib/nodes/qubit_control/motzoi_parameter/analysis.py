# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2025
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
"""Finds the motzoi whose DRAG pulses leave the least phase error after many repetitions."""

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits, get_coord_name

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def analyse_motzoi(s21: xr.DataArray, _session: "SessionContext") -> Fits:
    """``motzoi``: the one with the least ``|S21|`` summed over all repetitions.

    Args:
        s21: the qubit's S21, a point per motzoi and number of repetitions.
        _session: unused; part of the ``analyse`` signature.

    Returns:
        ``motzoi``, the DRAG motzoi to store.
    """
    sums = np.abs(s21).sum(get_coord_name("X_repetitions", s21.attrs["qubit"]))
    return {"motzoi": Fit(sums.idxmin().item())}


def plot_motzoi(
    axis: Axes, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """Draws ``|S21|`` against motzoi and repetitions, and marks the chosen motzoi.

    Args:
        axis: the axis to draw on.
        s21: the qubit's S21.
        fits: the qubit's fits.
        _session: unused; part of the ``plot`` signature.
    """
    x = get_coord_name("mw_motzois", s21.attrs["qubit"])
    np.abs(s21).plot(ax=axis, x=x, cmap="RdBu_r")
    if "motzoi" in fits:
        motzoi = fits["motzoi"].value
        axis.axvline(
            motzoi, c="k", lw=4, linestyle="--", label=f"Optimal Motzoi: {motzoi:.3f}"
        )
        axis.legend()
