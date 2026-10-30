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
from scipy import signal

from tergite_tuner.lib.base.analysis import BaseAllQubitsAnalysis, BaseQubitAnalysis
from tergite_tuner.lib.spec import Fit, Fits, get_coord_name
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.types.qoi import QOI

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


class QubitSpectroscopyMultidimAnalysis(BaseQubitAnalysis):
    """
    Analysis that fits a Lorentzian function to qubit spectroscopy data.
    The resulting fit can be analyzed to determine if a peak was found or not.
    """

    def _analyse_spectroscopy(self):
        for coord in self.dataset[self.data_var].coords:
            if "frequencies" in coord:
                self.frequency_coords = coord
                self.frequencies = self.dataset.coords[coord].values
            elif "amplitudes" in coord:
                self.amplitudes = self.dataset.coords[coord].values

        self.spec_ampl = 0
        self.qubit_ampl = 0
        self.qubit_freq = 0
        if hasattr(self, "amplitudes"):
            for i, a in enumerate(self.amplitudes):
                if isinstance(self.magnitudes, xr.Dataset):
                    data_var_name = list(self.S21.data_vars.keys())[
                        0
                    ]  # Adjust if specific variable name is known
                    s21_dataarray = self.magnitudes[data_var_name]
                else:
                    raise TypeError("Expected self.S21 to be an xarray.DataArray")
                s21_values = s21_dataarray.values

                these_magnitudes = s21_values[i]
                if not self.has_peak(these_magnitudes):
                    continue

                qubit_freq = self.frequencies[these_magnitudes.argmax()]
                qubit_ampl = these_magnitudes.max()
                if qubit_ampl > self.qubit_ampl:
                    self.qubit_ampl = qubit_ampl
                    self.qubit_freq = qubit_freq
                    self.spec_ampl = a

        else:
            if self.has_peak(self.magnitudes):
                self.qubit_freq = self.frequencies[self.magnitudes.argmax()]

    def analyse_qubit(self):
        self._analyse_spectroscopy()
        analysis_successful = True
        analysis_result = {
            "clock_freqs:f01": {
                "value": self.qubit_freq,
                "error": 0,
            },
            "spec:spec_ampl_optimal": {
                "value": self.spec_ampl,
                "error": 0,
            },
        }
        qoi = QOI(analysis_result, analysis_successful)
        return qoi

    def reject_outliers(self, x, m=3.0):
        # Filters out datapoints in x that deviate too far from the median
        d = np.abs(x - np.median(x))
        mdev = np.median(d)
        s = d / mdev if mdev else np.zeros(len(d))
        return x[s < m]

    def has_peak(
        self,
        x,
        prom_coef: float = 7,
        wid_coef: float = 2.4,
        outlier_median: float = 3.0,
    ):
        # Determines if the data contains one distinct peak or only noise
        x_filtered = self.reject_outliers(x, outlier_median)
        self.filtered_std = np.std(x_filtered)
        peaks, properties = signal.find_peaks(
            x, prominence=self.filtered_std * prom_coef, width=wid_coef
        )
        self.hasPeak = peaks.size > 0
        self.hasPeak = True
        return self.hasPeak

    def plotter(self, ax):
        self.magnitudes[self.data_var].plot(
            ax=ax, x=self.frequency_coords
        )  # Here, `self.frequency_coords` is the coordinate name
        ax.scatter(self.qubit_freq, self.spec_ampl, s=52, c="red")


class QubitSpectroscopyNodeAnalysis(BaseAllQubitsAnalysis):
    single_qubit_analysis_cls = QubitSpectroscopyMultidimAnalysis


def analyse_qubit_spectroscopy(s21: xr.DataArray, _session: "SessionContext") -> Fits:
    """The ``frequency`` and spectroscopy ``amplitude`` of the strongest peak over all amplitudes."""
    qubit = s21.attrs["qubit"]
    frequency_coord = get_coord_name("spec_frequencies", qubit)
    amplitude_coord = get_coord_name("spec_pulse_amplitudes", qubit)
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
