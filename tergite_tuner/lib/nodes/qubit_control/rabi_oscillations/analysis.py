# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Michele Faucci Giannelli 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Module containing classes that model, fit and plot data from a Rabi experiment.
"""

import numpy as np

from tergite_tuner.lib.base.analysis import BaseAllQubitsAnalysis, BaseQubitAnalysis
from tergite_tuner.lib.utils.analysis_models import RabiModel
from tergite_tuner.utils.dto.qoi import QOI


class RabiQubitAnalysis(BaseQubitAnalysis):
    """
    Analysis that fits a cosine function to Rabi oscillation data.
    """

    def _analyse_rabi(self):
        model = RabiModel()

        for coord in self.magnitudes.coords:
            if "amplitudes" in str(coord):
                self.amplitude_coord = coord
                self.amplitudes = self.magnitudes[coord].values
            else:
                raise ValueError("Invalid Coordinate")

        self.fit_plot_amplitudes = np.linspace(
            self.amplitudes[0], self.amplitudes[-1], 200
        )  # x-values for plotting

        # Gives an initial guess for the model parameters and then fits the model to the data.
        guess = model.guess(
            self.magnitudes[self.data_var].values, drive_amp=self.amplitudes
        )
        fit_result = model.fit(
            self.magnitudes[self.data_var].values,
            params=guess,
            drive_amp=self.amplitudes,
        )

        self.pi_amplitude = fit_result.params["amp180"].value
        self.uncertainty = 0  # fit_result.params["amp180"].stderr
        # self.uncertainty = fit_result.params["amp180"].stderr
        self.scaled_uncertainty = 0  # self.uncertainty / self.pi_amplitude
        # self.scaled_uncertainty = self.uncertainty / self.pi_amplitude

        self.fit_y = model.eval(fit_result.params, drive_amp=self.fit_plot_amplitudes)
        return

    def analyse_qubit(self):
        self._analyse_rabi()
        if self.scaled_uncertainty < 2e-2 and self.pi_amplitude < 0.95:
            analysis_successful = True
        else:
            analysis_successful = False

        analysis_result = {
            "rxy:amp180": {
                "value": self.pi_amplitude,
                "error": self.scaled_uncertainty,
            }
        }

        qoi = QOI(analysis_result, analysis_successful)

        return qoi

    def plotter(self, ax):
        ax.plot(
            self.fit_plot_amplitudes,
            self.fit_y,
            "r-",
            lw=3.0,
            label=f"π_ampl = {self.pi_amplitude:.2E}"
            r"$\pm$"
            f"{self.uncertainty:.2E}(V)\n"
            f"scaled uncertainty: {self.scaled_uncertainty:.2E}",
        )

        ax.plot(self.amplitudes, self.magnitudes[self.data_var].values, "bo-", ms=3.0)
        ax.set_title(f"Rabi Oscillations for {self.qubit}")
        ax.set_xlabel("Amplitude (V)")
        ax.set_ylabel("|S21| (V)")
        ax.grid()


class Rabi12QubitAnalysis(RabiQubitAnalysis):
    def analyse_qubit(self):
        self._analyse_rabi()
        if self.scaled_uncertainty < 2e-2 and self.pi_amplitude < 0.95:
            analysis_successful = True
        else:
            analysis_successful = False

        analysis_result = {
            "r12:ef_amp180": {
                "value": self.pi_amplitude,
                "error": self.scaled_uncertainty,
            }
        }

        qoi = QOI(analysis_result, analysis_successful)

        return qoi


class RabiNodeAnalysis(BaseAllQubitsAnalysis):
    single_qubit_analysis_cls = RabiQubitAnalysis


class RabiNode12Analysis(BaseAllQubitsAnalysis):
    single_qubit_analysis_cls = Rabi12QubitAnalysis


class NRabiQubitAnalysis(BaseQubitAnalysis):
    def _analyse_n_rabi(self):
        for coord in self.magnitudes.coords:
            if "amplitudes" in str(coord):
                self.mw_amplitudes_coord = coord
            elif "repetitions" in str(coord):
                self.x_repetitions_coord = coord

        sums = self.magnitudes.sum(self.x_repetitions_coord)

        self.correction = sums.idxmin()[self.data_var].item()

    def analyse_qubit(self):
        self._analyse_n_rabi()
        previous_amplitude = self.session.redis_store.read_field(
            "transmons", pk=self.qubit, field_path="rxy:amp180"
        )
        optimal_amp180 = self.correction + previous_amplitude
        analysis_successful = True

        analysis_result = {"rxy:amp180": {"value": optimal_amp180, "error": 0}}

        qoi = QOI(analysis_result, analysis_successful)

        return qoi

    def plotter(self, axis):
        datarray = self.magnitudes[self.data_var]

        datarray.plot(ax=axis, x=self.mw_amplitudes_coord, cmap="RdBu_r")
        axis.set_xlabel("mw amplitude correction")

        axis.axvline(self.correction, c="k", lw=4, linestyle="--")


class NRabi_12_QubitAnalysis(NRabiQubitAnalysis):
    def analyse_qubit(self):
        self._analyse_n_rabi()
        previous_amplitude = self.session.redis_store.read_field(
            "transmons", pk=self.qubit, field_path="r12:ef_amp180"
        )
        optimal_ef_amp180 = self.correction + previous_amplitude

        analysis_successful = True
        analysis_result = {"r12:ef_amp180": {"value": optimal_ef_amp180, "error": 0}}

        qoi = QOI(analysis_result, analysis_successful)

        return qoi


class NRabiNodeAnalysis(BaseAllQubitsAnalysis):
    single_qubit_analysis_cls = NRabiQubitAnalysis


class NRabi_12_NodeAnalysis(BaseAllQubitsAnalysis):
    single_qubit_analysis_cls = NRabi_12_QubitAnalysis
