# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Joel Sandås 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Qubit (two-tone) spectroscopy's analysis: the qubit's frequency at the amplitude that shows it best."""

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits, get_coord_name

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def analyse_qubit_spectroscopy(
    s21: xr.DataArray, _session: "SessionContext", amplitude_coord: str | None = None
) -> Fits:
    """The ``frequency`` and spectroscopy ``amplitude`` of the strongest peak over all amplitudes.

    The amplitudes are the qubit's own sweep, unless ``amplitude_coord`` names an outer one.

    Args:
        s21: the qubit's S21, a point per frequency and amplitude.
        _session: unused; part of the ``analyse`` signature.
        amplitude_coord: the coordinate of the amplitudes, if not the qubit's own sweep.

    Returns:
        ``frequency``, the qubit's frequency, and ``amplitude``, the spectroscopy
        amplitude that shows it best.
    """
    qubit = s21.attrs["qubit"]
    frequency_coord = get_coord_name("spec_frequencies", qubit)
    amplitude_coord = amplitude_coord or get_coord_name("spec_pulse_amplitudes", qubit)
    magnitudes = np.abs(s21).transpose(amplitude_coord, frequency_coord)
    strongest = int(magnitudes.max(frequency_coord).argmax())
    peak = int(magnitudes.isel({amplitude_coord: strongest}).argmax())
    return {
        "frequency": Fit(s21.coords[frequency_coord].values[peak]),
        "amplitude": Fit(s21.coords[amplitude_coord].values[strongest]),
    }


def plot_qubit_spectroscopy(
    axis: Axes, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """Draws ``|S21|`` against frequency and amplitude, and marks the peak found.

    Args:
        axis: the axis to draw on.
        s21: the qubit's S21.
        fits: the qubit's fits.
        _session: unused; part of the ``plot`` signature.
    """
    np.abs(s21).plot(ax=axis, x=get_coord_name("spec_frequencies", s21.attrs["qubit"]))
    if fits:
        axis.scatter(fits["frequency"].value, fits["amplitude"].value, s=52, c="red")
