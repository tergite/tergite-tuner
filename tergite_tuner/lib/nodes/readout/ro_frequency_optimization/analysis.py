# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
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
"""Finds the readout frequency at which the resonator's response tells the qubit's states apart best."""

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits, get_coord_name

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def analyse_ro_frequency(s21: xr.DataArray, _session: "SessionContext") -> Fits:
    """``frequency``: where the states' S21 lie furthest apart.

    With three states, the distance weighs the 1-2 pair twice, as it is the closest.

    Args:
        s21: the qubit's S21 over readout frequency and prepared state.
        _session: unused; part of the ``analyse`` signature.

    Returns:
        ``frequency``, and the ``distance`` at each frequency for the plot.
    """
    s21s = _get_state_s21s(s21)
    if len(s21s) == 2:
        distance = np.abs(s21s[1] - s21s[0])
    else:
        distance = (
            np.abs(s21s[0] - s21s[1])
            + 2 * np.abs(s21s[1] - s21s[2])
            + np.abs(s21s[2] - s21s[0])
        ) / 4
    return {"frequency": Fit(distance.idxmax().item()), "distance": Fit(distance)}


def plot_two_state_ro_frequency(
    axes: np.ndarray, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """The two states' traces on the IQ plane, then their magnitudes and phases, with the optimum.

    Args:
        axes: the column of three axes to draw on.
        s21: the qubit's S21 over readout frequency and prepared state.
        fits: the qubit's fits; without them the optimum is not marked.
        _session: unused; part of the ``plot`` signature.
    """
    s21_0, s21_1 = _get_state_s21s(s21)
    frequencies = s21_0.coords[s21_0.dims[0]].values
    iq_axis, magnitude_axis, phase_axis = axes
    iq_axis.set_xlabel("I quadrature (V)")
    iq_axis.set_ylabel("Q quadrature (V)")
    if fits:
        optimum = int(fits["distance"].value.argmax())
        iq_axis.scatter(
            [s21_0[optimum].real, s21_1[optimum].real],
            [s21_0[optimum].imag, s21_1[optimum].imag],
            marker="*",
            c="black",
            s=100,
            label=f"opt_ro: {int(fits['frequency'].value)}\n",
            zorder=5,
        )
    iq_axis.plot(s21_0.real, s21_0.imag, "bo-", lw=2, ms=4)
    iq_axis.plot(s21_1.real, s21_1.imag, "ro-", lw=2, ms=4)
    iq_axis.legend()
    iq_axis.grid()
    for axis, quantity in ((magnitude_axis, np.abs), (phase_axis, np.angle)):
        axis.plot(frequencies, quantity(s21_0), "o-", ms=2, color="blue")
        axis.plot(frequencies, quantity(s21_1), "o-", ms=2, color="red")
        if fits:
            axis.axvline(fits["frequency"].value, color="black")


def plot_three_state_ro_frequency(
    axis: Axes, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """The three states' magnitudes and their weighted distance, with the optimum.

    Args:
        axis: the axis to draw on.
        s21: the qubit's S21 over readout frequency and prepared state.
        fits: the qubit's fits; without them only the magnitudes are drawn.
        _session: unused; part of the ``plot`` signature.
    """
    s21s = _get_state_s21s(s21)
    frequencies = s21s[0].coords[s21s[0].dims[0]].values
    axis.set_xlabel("RO frequency")
    axis.set_ylabel("IQ distance")
    for state, state_s21 in enumerate(s21s):
        axis.plot(frequencies, np.abs(state_s21), label=str(state))
    if fits:
        axis.plot(frequencies, fits["distance"].value, "--", label="distance")
        axis.scatter(
            fits["frequency"].value,
            fits["distance"].value.max().item(),
            marker="*",
            c="red",
            s=64,
        )
    axis.grid()


def _get_state_s21s(s21: xr.DataArray) -> list[xr.DataArray]:
    state_coord = get_coord_name("qubit_states", s21.attrs["qubit"])
    return [s21.sel({state_coord: state}) for state in s21.coords[state_coord].values]
