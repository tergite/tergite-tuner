# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Michele Faucci Giannelli 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import numpy as np
from quantify_core.analysis import fitting_models as fm

from tergite_autocalibration.lib.base.analysis import (
    BaseAllQubitsAnalysis,
    BaseQubitAnalysis,
)
from tergite_autocalibration.utils.dto.qoi import QOI

model = fm.ResonatorModel()


class OptimalRO01FrequencyQubitAnalysis(BaseQubitAnalysis):
    """
    Analysis that fits the data of resonator spectroscopy experiments
    and extractst the optimal RO frequency.
    """

    def analyse_qubit(self):
        for coord in self.S21.coords:
            if "frequencies" in str(coord):
                self.frequencies = self.S21[coord].values
                self.frequency_coord = coord
            elif "qubit_states" in str(coord):
                self.qubit_states = self.S21[coord].values
                self.qubit_state_coord = coord

        self.s21_0 = self.S21[self.data_var].sel({self.qubit_state_coord: 0})
        self.s21_1 = self.S21[self.data_var].sel({self.qubit_state_coord: 1})
        self.magnitudes_0 = np.abs(self.s21_0)
        self.magnitudes_1 = np.abs(self.s21_1)
        self.phase_0 = np.angle(self.s21_0)
        self.phase_1 = np.angle(self.s21_1)

        distances = self.s21_1 - self.s21_0

        self.optimal_frequency = np.abs(distances).idxmax().item()
        self.index_of_max_distance = np.abs(distances).argmax()

        analysis_successful = True
        analysis_result = {
            "extended_clock_freqs:readout_2state_opt": {
                "value": self.optimal_frequency,
                "error": 0,
            }
        }

        qoi = QOI(analysis_result, analysis_successful)

        return qoi


class ROFrequencyThreeStateQubitAnalysis(OptimalRO01FrequencyQubitAnalysis):
    def analyse_qubit(self):
        super().analyse_qubit()
        self.s21_2 = self.S21[self.data_var].sel({self.qubit_state_coord: 2})
        self.magnitudes_2 = np.abs(self.s21_2)

        distances_01 = np.abs(self.s21_0 - self.s21_1)
        distances_12 = np.abs(self.s21_1 - self.s21_2)
        distances_20 = np.abs(self.s21_2 - self.s21_0)
        self.total_distance = (distances_01 + 2 * distances_12 + 1 * distances_20) / 4
        self.optimal_frequency = self.total_distance.idxmax().item()
        self.optimal_distance = self.total_distance.max().item()

        analysis_successful = True
        analysis_result = {
            "extended_clock_freqs:readout_3state_opt": {
                "value": self.optimal_frequency,
                "error": 0,
            }
        }

        qoi = QOI(analysis_result, analysis_successful)

        return qoi

    def plotter(self, ax):
        ax.set_xlabel("RO frequency")
        ax.set_ylabel("IQ distance")
        ax.plot(self.frequencies, self.magnitudes_0, label="0")
        ax.plot(self.frequencies, self.magnitudes_1, label="1")
        ax.plot(self.frequencies, self.magnitudes_2, label="2")
        ax.plot(self.frequencies, self.total_distance, "--", label="distance")

        styles = dict(marker="*", c="red", s=64)
        ax.scatter(self.optimal_frequency, self.optimal_distance, **styles)
        ax.grid()


class OptimalRO01FrequencyNodeAnalysis(BaseAllQubitsAnalysis):
    single_qubit_analysis_cls = OptimalRO01FrequencyQubitAnalysis


class ROFrequencyThreeStateNodeAnalysis(BaseAllQubitsAnalysis):
    single_qubit_analysis_cls = ROFrequencyThreeStateQubitAnalysis
