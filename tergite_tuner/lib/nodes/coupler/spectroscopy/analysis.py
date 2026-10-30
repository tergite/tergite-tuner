# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Michele Faucci Giannelli 2024, 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


from collections.abc import Sequence
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import xarray

from tergite_tuner.lib.nodes.qubit_control.spectroscopy.analysis import (
    QubitSpectroscopyMaxThresholdQubitAnalysis,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.analysis import (
    fit_resonator,
)
from tergite_tuner.lib.spec import CouplerAnalysis, Fits, get_fits_from_result

if TYPE_CHECKING:
    pass


class CouplerAnticrossingAnalysis(CouplerAnalysis):
    """
    This class analyzes the qubit spectroscopy data as a function of the current for a coupler.
    """

    def detect_peaks(self, qubit_specs_dataarray: xarray.DataArray):
        detected_frequencies = []
        detected_currents = []
        for current in self.dc_currents:
            ds = qubit_specs_dataarray.sel({self.current_coord: current})
            freq_analysis = QubitSpectroscopyMaxThresholdQubitAnalysis(ds)
            qubit_frequency = freq_analysis.process_qubit()
            detected_frequencies.append(qubit_frequency)
            detected_currents.append(current)
        return detected_frequencies, detected_currents

    def analyse(self) -> Fits | None:
        for coord in self.dataset[self.data_var].coords:
            if "frequencies" in coord:
                self.frequencies = coord
            elif "currents" in coord:
                self.current_coord = coord
                self.dc_currents = self.dataset[self.current_coord].values

        threshold = 2000000
        spurious_threshold = 300000
        min_interval = 0.0003
        resonator_crossings_interval = 0.00015

        control_qubit_magnitudes = xarray.ufuncs.abs(self.control_qubit_data_var)
        target_qubit_magnitudes = xarray.ufuncs.abs(self.target_qubit_data_var)
        (
            self.control_qubit_detected_frequencies,
            self.control_qubit_detected_currents,
        ) = self.detect_peaks(control_qubit_magnitudes)
        self.target_qubit_detected_frequencies, self.target_qubit_detected_currents = (
            self.detect_peaks(target_qubit_magnitudes)
        )
        self.resonator_crossing_points = []
        self.control_crossing_currents = find_crossing_currents(
            self.control_qubit_detected_currents,
            self.control_qubit_detected_frequencies,
            threshold,
            spurious_threshold,
            min_interval,
            self.resonator_crossing_points,
            resonator_crossings_interval,
        )
        self.target_crossing_currents = find_crossing_currents(
            self.target_qubit_detected_currents,
            self.target_qubit_detected_frequencies,
            threshold,
            spurious_threshold,
            min_interval,
            self.resonator_crossing_points,
            resonator_crossings_interval,
        )

        analysis_succesful = True
        analysis_result = {
            "control_qubit_crossing_points": {
                "value": self.control_crossing_currents,
                "error": 0,
            },
            "target_qubit_crossing_points": {
                "value": self.target_crossing_currents,
                "error": 0,
            },
        }

        return get_fits_from_result(analysis_result, analysis_succesful)

    def plotter(self, figures_dictionary: dict[str, list]):
        """
        Create the anticrossing figures and populate the figures dictionary.
        Args:
             figures_dictionary: A reference to the figures dictionary that the base
             analysis plots the key is the coupler labe and the value is a list
             containing the anticrossing figure for that coupler
        """
        figures_list = []
        fig, (ax1, ax2) = plt.subplots(2, 1)
        control_qubit_magnitudes = xarray.ufuncs.abs(self.control_qubit_data_var)
        target_qubit_magnitudes = xarray.ufuncs.abs(self.target_qubit_data_var)
        control_qubit_magnitudes.plot(ax=ax1, x=self.current_coord)
        target_qubit_magnitudes.plot(ax=ax2, x=self.current_coord)

        ax1.scatter(
            self.control_qubit_detected_currents,
            self.control_qubit_detected_frequencies,
            s=52,
            c="red",
        )
        for cross_current in self.control_crossing_currents:
            ax1.axvline(
                cross_current,
                color="grey",
                linestyle="dashed",
                linewidth=2,
            )
        ax2.scatter(
            self.target_qubit_detected_currents,
            self.target_qubit_detected_frequencies,
            s=52,
            c="red",
        )
        for cross_current in self.target_crossing_currents:
            ax2.axvline(
                cross_current,
                color="grey",
                linestyle="dashed",
                linewidth=2,
            )
        figures_list.append(fig)
        figures_dictionary[self.coupler] = figures_list
        return


class ResonatorSpectroscopyVsCurrentCouplerAnalysis(CouplerAnalysis):
    """
    This class analyzes the resonator spectroscopy data as a function of the current for a coupler.
    """

    def detect_peaks(self, res_specs_dataarray: xarray.DataArray):
        detected_frequencies = []
        detected_currents = []
        for current in self.dc_currents:
            darray = res_specs_dataarray.sel({self.current_coord: current})
            frequencies = darray.coords[darray.dims[0]].values
            resonator_frequency = fit_resonator(frequencies, darray.values).frequency
            detected_frequencies.append(resonator_frequency)
            detected_currents.append(current)
        return detected_frequencies, detected_currents

    def analyse(self) -> Fits | None:
        """
        This function analyzes the coupler data to find crossing currents for both qubits.
        """
        for coord in self.dataset[self.data_var].coords:
            if "frequencies" in coord:
                self.frequencies = coord
            elif "currents" in coord:
                self.current_coord = coord
                self.dc_currents = self.dataset[self.current_coord].values

        threshold = 30000
        spurious_threshold = 4000
        min_interval = 0.0005  # Adjust based on data range

        self.control_qubit_detected_frequencies, self.target_qubit_detected_currents = (
            self.detect_peaks(self.control_qubit_data_var)
        )
        self.target_qubit_detected_frequencies, self.control_qubit_detected_currents = (
            self.detect_peaks(self.target_qubit_data_var)
        )
        self.control_crossing_currents = find_crossing_currents(
            self.control_qubit_detected_currents,
            self.control_qubit_detected_frequencies,
            threshold,
            spurious_threshold,
            min_interval,
        )
        self.target_crossing_currents = find_crossing_currents(
            self.target_qubit_detected_currents,
            self.target_qubit_detected_frequencies,
            threshold,
            spurious_threshold,
            min_interval,
        )

        analysis_succesful = True
        analysis_result = {
            "control_resonator_crossing_points": {
                "value": self.control_crossing_currents,
                "error": 0,
            },
            "target_resonator_crossing_points": {
                "value": self.target_crossing_currents,
                "error": 0,
            },
        }
        return get_fits_from_result(analysis_result, analysis_succesful)

    def plotter(self, figures_dictionary):
        """
        Create the anticrossing figures and populate the figures dictionary.
        Args:
             figures_dictionary: A reference to the figures dictionary that the base
             analysis plots the key is the coupler labe and the value is a list
             containing the anticrossing figure for that coupler
        """
        figures_list = []
        fig, (ax1, ax2) = plt.subplots(1, 2)
        control_qubit_magnitudes = xarray.ufuncs.abs(self.control_qubit_data_var)
        target_qubit_magnitudes = xarray.ufuncs.abs(self.target_qubit_data_var)
        control_qubit_magnitudes.plot(ax=ax1)
        target_qubit_magnitudes.plot(ax=ax2)
        ax1.scatter(
            self.control_qubit_detected_frequencies,
            self.control_qubit_detected_currents,
            s=52,
            c="red",
        )
        for cross_current in self.control_crossing_currents:
            ax1.axhline(
                cross_current,
                color="grey",
                linestyle="dashed",
                linewidth=2,
            )
        ax2.scatter(
            self.target_qubit_detected_frequencies,
            self.target_qubit_detected_currents,
            s=52,
            c="red",
        )
        for cross_current in self.target_crossing_currents:
            ax2.axhline(
                cross_current,
                color="grey",
                linestyle="dashed",
                linewidth=2,
            )
        figures_list.append(fig)
        figures_dictionary[self.coupler] = figures_list
        return


def find_crossing_currents(
    currents: Sequence[float],
    frequencies: Sequence[float],
    threshold: float = 2e6,
    spurious_threshold: float = 3e5,
    min_interval: float = 0.0003,
    resonator_crossings: Sequence[float] = (),
    resonator_crossings_interval: float = 0.00015,
) -> list[float]:
    """The mean current of each group of frequency jumps over ``threshold``, but those near a resonator crossing.

    A zero frequency is a dropout; a group closes once it spans ``min_interval``, or at the last point.
    """
    frequencies = np.asarray(frequencies, dtype=float)
    is_detected = ~np.isnan(frequencies)
    currents = np.asarray(currents)[is_detected]
    frequencies = _fill_dropouts(frequencies[is_detected], spurious_threshold)
    last = len(frequencies) - 1
    group = []
    crossings = []
    for i in range(last):
        if frequencies[i] == 0:
            continue
        j = i + 1
        while j <= last and frequencies[j] == 0:
            j += 1
        if j > last:
            break
        if abs(frequencies[i] - frequencies[j]) > threshold:
            group.extend(currents[i : j + 1])
        if group and (currents[i] - group[0] > min_interval or j == last):
            mid_current = np.mean(group)
            if all(
                abs(mid_current - crossing) > resonator_crossings_interval
                for crossing in resonator_crossings
            ):
                crossings.append(mid_current)
            group = []
    return crossings


def _fill_dropouts(
    frequencies: np.ndarray, spurious_threshold: float
) -> np.ndarray:
    """Fills a single dropout between close neighbours, and drops a point isolated between dropouts."""
    frequencies = frequencies.copy()
    for i in range(1, len(frequencies) - 1):
        previous, current, following = frequencies[i - 1 : i + 2]
        if current == 0 and abs(previous - following) < spurious_threshold:
            frequencies[i] = (previous + following) / 2
        if previous == 0 and following == 0:
            frequencies[i] = 0
    return frequencies
