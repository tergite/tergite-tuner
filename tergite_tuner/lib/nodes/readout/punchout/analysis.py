# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Finds the largest readout amplitude before the resonator punches out."""

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib import patches
from matplotlib import pyplot as plt
from matplotlib.axes import Axes

from tergite_tuner.lib.base.utils.figure_utils import create_figure_with_top_band
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.analysis import (
    fit_resonator,
    plot_resonator,
)
from tergite_tuner.lib.spec import Fit, Fits, get_coord_name

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

# a resonator frequency moving further than this from the last amplitude's has punched out
SHIFT_THRESHOLD = 0.1e6
SPECTROSCOPY_COLUMNS = 4


def analyse_punchout(s21: xr.DataArray, _session: "SessionContext") -> Fits | None:
    """``amplitude``: the largest before the fitted resonator frequency shifts.

    Amplitudes whose resonator fit raised are skipped. The qubit fails if none fitted.
    """
    qubit = s21.attrs["qubit"]
    amplitudes = s21.coords[get_coord_name("ro_amplitudes", qubit)].values
    frequencies = s21.coords[get_coord_name("ro_frequencies", qubit)].values
    resonator_fits = [
        fit_resonator(
            frequencies,
            s21.isel({get_coord_name("ro_amplitudes", qubit): index}).values,
        )
        for index in range(len(amplitudes))
    ]
    detected_frequencies = np.array(
        [np.nan if fit is None else fit.frequency for fit in resonator_fits]
    )

    best_amplitude, last_frequency = None, None
    for amplitude, frequency in zip(amplitudes, detected_frequencies, strict=True):
        if np.isnan(frequency):
            continue
        if (
            last_frequency is not None
            and abs(frequency - last_frequency) > SHIFT_THRESHOLD
        ):
            break
        best_amplitude, last_frequency = amplitude, frequency
    if best_amplitude is None:
        return None
    return {
        "amplitude": Fit(best_amplitude, np.nan),
        "frequency": Fit(last_frequency),
        "detected_frequencies": Fit(detected_frequencies),
        "resonator_fits": Fit(resonator_fits),
    }


def plot_punchout(
    axis: Axes, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """``|S21|``, normalised per amplitude, with the fitted frequencies and the chosen amplitude."""
    qubit = s21.attrs["qubit"]
    amplitude_coord = get_coord_name("ro_amplitudes", qubit)
    magnitudes = np.abs(s21)
    normalised = magnitudes / magnitudes.max(get_coord_name("ro_frequencies", qubit))
    mesh = normalised.plot(ax=axis, x=amplitude_coord)
    if fits:
        axis.scatter(
            s21.coords[amplitude_coord].values,
            fits["detected_frequencies"].value,
            c="b",
            label="Fitted resonator freq.",
            marker="o",
        )
        axis.scatter(
            fits["amplitude"].value,
            fits["frequency"].value,
            c="r",
            label=f"Amplitude = {fits['amplitude'].value:.3f}",
            marker="X",
            s=200,
            edgecolors="k",
            linewidth=1.5,
            zorder=10,
        )
        axis.legend()
    axis.set_ylabel("Resonator frequency [Hz]")
    axis.set_xlabel("Readout pulse amplitude [V?]")
    mesh.colorbar.set_label("Normalized |S21|", rotation=270, labelpad=15)


def save_punchout_spectroscopies(
    s21: xr.DataArray, fits: Fits, data_path: Path, session: "SessionContext"
) -> None:
    """Each amplitude's resonator fit, the chosen one framed in red."""
    if not fits:
        return
    qubit = s21.attrs["qubit"]
    amplitude_coord = get_coord_name("ro_amplitudes", qubit)
    amplitudes = s21.coords[amplitude_coord].values
    resonator_fits = fits["resonator_fits"].value
    nrows = int(np.ceil(len(amplitudes) / SPECTROSCOPY_COLUMNS))
    figure, axes = create_figure_with_top_band(nrows, SPECTROSCOPY_COLUMNS)
    for index, resonator_fit in enumerate(resonator_fits):
        axis = axes[index // SPECTROSCOPY_COLUMNS, index % SPECTROSCOPY_COLUMNS]
        resonator_fits_of_amplitude = (
            {}
            if resonator_fit is None
            else {
                "model": Fit(resonator_fit.result),
                "frequency": Fit(resonator_fit.frequency),
            }
        )
        plot_resonator(
            axis,
            s21.isel({amplitude_coord: index}),
            resonator_fits_of_amplitude,
            session,
            state=0,
        )
        if amplitudes[index] == fits["amplitude"].value:
            axis.add_patch(
                patches.Rectangle(
                    (0, 0),
                    1,
                    1,
                    transform=axis.transAxes,
                    linewidth=3,
                    edgecolor="red",
                    facecolor="none",
                    zorder=20,
                )
            )
    figure.savefig(
        data_path / f"punchout_{qubit}_spectroscopies.png", bbox_inches="tight", dpi=300
    )
    plt.close(figure)
