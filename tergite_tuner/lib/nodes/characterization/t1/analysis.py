# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Michele Faucci Giannelli 2024, 2025

# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Module containing a class that fits and plots data from a T1 experiment.
"""

import numpy as np
from quantify_core.analysis.fitting_models import ExpDecayModel

from tergite_tuner.lib.base.analysis import (
    BaseAllQubitsAnalysis,
    BaseQubitAnalysis,
)
from tergite_tuner.utils.dto.qoi import QOI


class T1QubitAnalysis(BaseQubitAnalysis):
    """
    Class for T1 analysis of a single qubit, which fits the data from a T1 experiment
    and plots the results.
    """

    def __init__(self, name, redis_fields, session=None, **kwargs):
        super().__init__(name, redis_fields, session, **kwargs)
        self.t1_times = []
        self.offset_times = []
        self.amplitude_times = []
        self.repetitions_coord = None
        self.delays_coord = None
        self.delays = None
        self.fit_delays = None
        self.average_t1 = None
        self.average_offset = None
        self.average_amplitude = None
        self.error = None
        self.average_t1_y = None
        self.average_t1_upper = None
        self.average_t1_lower = None

    def analyse_qubit(self):
        """
        Perform the analysis of the T1 data for a single qubit.
        Returns:
            QOI: A QOI object containing the analysis results.
        """

        for coord in self.dataset[self.data_var].coords:
            if "T1_repetition" in coord:
                self.repetitions_coord = coord
            elif "delays" in coord:
                self.delays_coord = coord

        self.delays = (
            self.dataset[self.delays_coord].values * 1e6
        )  # Convert delays to microseconds

        model = ExpDecayModel()

        self.fit_delays = np.linspace(
            self.delays[0], self.delays[-1], 400
        )  # x-values for plotting

        fit_result = None

        for indx in range(len(self.dataset.coords[self.repetitions_coord])):
            magnitudes = self.magnitudes[self.data_var].isel(
                {self.repetitions_coord: indx}
            )
            magnitudes_flat = (
                magnitudes.values.flatten() * 1e6
            )  # Convert to microseconds

            # Gives an initial guess for the model parameters and then fits the model to the data.
            guess = model.guess(data=magnitudes_flat, delay=self.delays)
            fit_result = model.fit(magnitudes_flat, params=guess, t=self.delays)
            self.t1_times.append(fit_result.params["tau"].value)
            self.offset_times.append(fit_result.params["offset"].value)
            self.amplitude_times.append(fit_result.params["amplitude"].value)

        self.average_t1 = np.mean(self.t1_times)
        self.average_offset = np.mean(self.offset_times)
        self.average_amplitude = np.mean(self.amplitude_times)
        self.error = np.std(self.t1_times)

        # Prepare base params object for evaluating mean fit
        average_params = fit_result.params.copy()
        average_params["tau"].value = self.average_t1
        average_params["offset"].value = self.average_offset
        average_params["amplitude"].value = self.average_amplitude

        # Evaluate mean T1 fit
        self.average_t1_y = model.eval(params=average_params, t=self.fit_delays)

        # Evaluate upper and lower bands
        params_upper = average_params.copy()
        params_upper["tau"].value = self.average_t1 + self.error
        self.average_t1_upper = model.eval(params=params_upper, t=self.fit_delays)

        params_lower = average_params.copy()
        params_lower["tau"].value = self.average_t1 - self.error
        self.average_t1_lower = model.eval(params=params_lower, t=self.fit_delays)

        analysis_successful = True

        analysis_result = {
            "t1_time": {
                "value": self.average_t1,
                "error": self.error,
            }
        }

        qoi = QOI(analysis_result, analysis_successful)

        return qoi


class T1NodeAnalysis(BaseAllQubitsAnalysis):
    """
    Class for T1 analysis node, which uses T1QubitAnalysis for each qubit
    """

    single_qubit_analysis_cls = T1QubitAnalysis
