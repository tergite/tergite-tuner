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

"""
Module containing classes that model, fit and plot data
from a qubit (two tone) spectroscopy experiment.
"""

from typing import TYPE_CHECKING

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits, get_coord_name
from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

# TODO: this is flagged for removal


class QubitSpectroscopyMaxThresholdQubitAnalysis:
    """
    Analysis that finds the maximum value in qubit spectroscopy data.
    """

    SIGNIFICANCE_THRESHOLD = 2.7

    # TODO: this is not necessary. Repace with scipy,find_peaks prominence

    def __init__(self, qubit_specs_dataarray):
        self.qubit_specs_dataarray = qubit_specs_dataarray

    def process_qubit(self):
        for coord in self.qubit_specs_dataarray:
            if "frequencies" in coord:
                self.frequencies_coord = coord
                self.frequencies = self.qubit_specs_dataarray[
                    self.frequencies_coord
                ].values

        self.max_value = self.qubit_specs_dataarray.max()

        mean_value = self.qubit_specs_dataarray.mean().item()
        std_value = self.qubit_specs_dataarray.std().item()

        self.max_significance = abs((self.max_value - mean_value) / std_value)

        if self.max_significance < self.SIGNIFICANCE_THRESHOLD:
            logger.warning(
                "This spectroscopy doeas not have a proper maximum, it is ok if this is in a transition region in the coupler spectroscopy"
            )
            self.freq = np.nan
        else:
            self.freq = self.qubit_specs_dataarray.idxmax().item()
        self.uncertainty = None

        return self.freq


def analyse_qubit_spectroscopy(
    s21: xr.DataArray, _session: "SessionContext", amplitude_coord: str | None = None
) -> Fits:
    """The ``frequency`` and spectroscopy ``amplitude`` of the strongest peak over all amplitudes.

    The amplitudes are the qubit's own sweep, unless ``amplitude_coord`` names an outer one.
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
    np.abs(s21).plot(ax=axis, x=get_coord_name("spec_frequencies", s21.attrs["qubit"]))
    if fits:
        axis.scatter(fits["frequency"].value, fits["amplitude"].value, s=52, c="red")
