# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman, 2024
# (C) Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from tergite_tuner.lib.base.analysis import BaseAllCouplersAnalysis
from tergite_tuner.lib.nodes.coupler.cz_parametrization.analysis import (
    CZParametrizationAnalysis,
)
from tergite_tuner.lib.utils.analysis_models import QuadraticModel, SineOscillatingModel
from tergite_tuner.utils.types.qoi import QOI


class CZChevronCouplerAnalysis(CZParametrizationAnalysis):

    def __init__(self, name, redis_fields, session, **kwargs):
        super().__init__(name, redis_fields, session, **kwargs)
        self.model = SineOscillatingModel()
        self.model.set_param_hint("optimal_duration", expr="1/frequency", vary=False)
        self.chevron_model = QuadraticModel()
        self.number_of_working_points: int = kwargs["number_of_working_points"]

    def apply_sinusoidal_slices_fit(self, data):
        # durations is the independent variable in the cosine definition
        guess = self.model.guess(data, x=self.durations)
        try:
            fit = self.model.fit(
                data,
                params=guess,
                x=self.durations,
            )
            duration = fit.values["optimal_duration"]
            amplitude = fit.values["amplitude"]

            fit_data = self.model.eval(fit.params, x=self.fit_plot_durations)

            # discard if the oscillations are not strong enough
            if amplitude < 0.30:
                duration = np.nan
            return np.array([duration]), np.array([fit_data])
        except:
            return np.array([np.nan]), np.array([np.nan])

    def analyze_coupler(self) -> QOI:
        """Analyze the chevron pattern measured while sweeping the flux duration and frequency.

        Analyze the chevron pattern measured while sweeping the flux pulse duration (y-axis)
        and flux pulse frequency (x-axis).
        The method assigns value to the attributes
         - self.cz_working_durations_in_ns
         - self.cz_working_frequencies
        which correspond to all the (frequency, duration) points where a return to the |11> is observed
        The working pairs may be unnesasrily mainy, sothe method assigns value also to the attributes
         - self.selected_cz_durations_in_ns
         - self.selected_cz_frequencies
        which are a subset of the wotking points with array size according to self.number_of_working_points
        """
        self.calculate_probabilities()

        self.fit_plot_durations = np.linspace(
            self.durations[0], self.durations[-1], 200
        )  # x-values for plotting

        probabilities = self.probabilities
        control_state_2 = probabilities.sel({"qubit": self.control_qubit, "state": 2})
        control_state_1 = probabilities.sel({"qubit": self.control_qubit, "state": 1})
        control_state_0 = probabilities.sel({"qubit": self.control_qubit, "state": 0})
        target_state_0 = probabilities.sel({"qubit": self.target_qubit, "state": 0})
        target_state_1 = probabilities.sel({"qubit": self.target_qubit, "state": 1})
        target_state_2 = probabilities.sel({"qubit": self.target_qubit, "state": 2})

        if self.phase_path == "via_02":
            self.control_diffs = control_state_0 - control_state_1  # - control_state_0
            self.target_diffs = target_state_2 - target_state_1  # - target_state_2
        elif self.phase_path == "via_20":
            self.control_diffs = control_state_2 - control_state_1  # - control_state_2
            self.target_diffs = target_state_0 - target_state_1  # - control_state_0
        else:
            raise ValueError(f"Invalid phase path:{self.phase_path}")

        self.combined_data = self.control_diffs + self.target_diffs

        # apply a sinusoidal fit to each verical slice (column of specific frequency)
        cz_durations, self.fit_plot_probs = xr.apply_ufunc(
            self.apply_sinusoidal_slices_fit,
            self.combined_data,
            input_core_dims=[[self.durations_coord]],
            output_core_dims=[["cz_pulse_durations"], ["plot_points"]],
            vectorize=True,
        )

        # cleanup entries with nan values from rejected fits:
        cz_durations = cz_durations.dropna(dim=self.frequencies_coord)
        cz_duration_values = cz_durations.values.flatten()

        integer_gate_durations_in_ns = (cz_duration_values // 1e-9).astype(int)
        # ensure durations are in multiples of 4ns:
        cz_working_durations_in_ns = (integer_gate_durations_in_ns // 4) * 4
        cz_working_frequencies = cz_durations.cz_pulse_frequencies.values

        selected_cz_frequencies = cz_working_frequencies
        selected_cz_durations_in_ns = cz_working_durations_in_ns

        self.cz_working_frequencies = cz_working_frequencies
        self.cz_working_durations_in_ns = cz_working_durations_in_ns

        self.selected_frequencies = selected_cz_frequencies
        self.selected_durations_in_ns = selected_cz_durations_in_ns

        selected_cz_durations_in_ns = selected_cz_durations_in_ns.tolist()
        selected_cz_frequencies = selected_cz_frequencies.astype(int).tolist()

        selected_frequencies_str = str(selected_cz_frequencies)
        selected_cz_durations_in_ns_str = str(selected_cz_durations_in_ns)
        analysis_succesful = True
        analysis_result = {
            "cz_working_frequencies": {
                "value": selected_frequencies_str,
                "error": 0,
            },
            "cz_working_durations_in_ns": {
                "value": selected_cz_durations_in_ns_str,
                "error": 0,
            },
        }
        qoi = QOI(analysis_result, analysis_succesful)
        return qoi

    @property
    def processed_dataset(self):
        return self.probabilities

    def plotter(self, figures_dictionary):

        current_probabilities = self.probabilities
        current_probabilities.plot(
            x=self.frequencies_coord, cmap="RdBu_r", row="qubit", col="state"
        )

        fig = plt.gcf()
        # if there are no working points return only the faceting plot
        if self.cz_working_durations_in_ns.size == 0:
            figures_dictionary[self.coupler] = [fig]
            return

        # plot the working points on every one of the six faceting axes
        for ax in fig.axes:
            ax.plot(
                self.cz_working_frequencies,
                self.cz_working_durations_in_ns * 1e-9,
                marker="8",
                ls="",
                color="yellow",
            )
            ax.plot(
                self.selected_frequencies,
                self.selected_durations_in_ns * 1e-9,
                marker="*",
                markersize=12,
                ls="",
                color="yellow",
            )

        figures_dictionary[self.coupler] = [fig]


class CZChevronAnalysis(BaseAllCouplersAnalysis):
    single_coupler_analysis_obj = CZChevronCouplerAnalysis
