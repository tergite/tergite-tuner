# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Chalmers Next Labs AB 2024, 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import numpy as np
import xarray as xr

from tergite_tuner.lib.base.analysis import BaseAllCouplersAnalysis, BaseCouplerAnalysis
from tergite_tuner.lib.utils.analysis_models import SineOscillatingModel
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities
from tergite_tuner.utils.dto.qoi import QOI


class CZCalibrationCouplerAnalysis(BaseCouplerAnalysis):
    def __init__(self, name, redis_fields, session=None, **kwargs):
        super().__init__(name, redis_fields, session, **kwargs)
        self.model = SineOscillatingModel()
        self.model.set_param_hint("phase", min=-360, max=360, vary=True)

    def apply_sine_fit(self, data):
        guess = self.model.guess(data, x=self.target_phases)
        fit = self.model.fit(
            data,
            params=guess,
            x=self.target_phases,
        )
        phase = fit.values["phase"]
        fit_data = self.model.eval(fit.params, x=self.fit_plot_phases)
        return np.array([phase]), np.array([fit_data])

    def analyze_coupler(self):

        for coord in self.S21.coords:
            coord = str(coord)
            if "control_ons" in coord:
                self.control_mode_coord = coord
            elif "dc_currents" in coord:
                self.dc_currents_coord = coord
                self.dc_currents = self.S21[self.dc_currents_coord].values
            elif "cz_frequencies" in coord:
                self.cz_frequencies_coord = coord
                self.cz_frequencies = self.S21[coord].values
                self.number_of_frequencies = self.S21[coord].size
            elif "working_points" in coord:
                self.cz_working_points_coord = coord
                self.cz_working_points = self.S21[coord].values
                self.number_of_wp = self.S21[coord].size
                self.frequencies, self.durations = zip(*self.cz_working_points)
            elif "ramsey_phases" in coord:
                if self.control_qubit in coord:
                    self.control_phase_coord = coord
                elif self.target_qubit in coord:
                    self.target_phase_coord = coord
                    self.target_phases = self.S21[coord].values
            elif "loops" in coord:
                self.loops_coord = coord
                self.number_of_loops = self.S21[self.loops_coord].size

        self.control_qubit_probabilities = calculate_probabilities(
            self.control_qubit_data_var, self.session.redis
        )
        self.target_qubit_probabilities = calculate_probabilities(
            self.target_qubit_data_var, self.session.redis
        )

        data_target_0 = self.target_qubit_probabilities.sel({"state": 0})

        self.fit_plot_phases = np.linspace(
            self.target_phases[0], self.target_phases[-1], 200
        )  # x-values for plotting

        # self.phi_0 is the global phase of each for the |0> state of the target qubit
        self.phi_0, target_plot_points_0 = xr.apply_ufunc(
            self.apply_sine_fit,
            data_target_0,
            input_core_dims=[[self.target_phase_coord]],
            output_core_dims=[["phases"], ["plot_points"]],
            vectorize=True,
        )

        self.target_plot_points_0 = target_plot_points_0.assign_coords(
            {"plot_points": self.fit_plot_phases}
        )
        self.target_plot_points_0 = self.target_plot_points_0.rename(
            {"plot_points": self.target_phase_coord}
        )

        phi_with_control_on = self.phi_0.sel({self.control_mode_coord: True})
        phi_with_control_off = self.phi_0.sel({self.control_mode_coord: False})

        # we subtract 180 because we want the distance of each phase from 180
        delta_phis = abs(
            (np.rad2deg(phi_with_control_on - phi_with_control_off) + 360) % 360 - 180
        )
        self.optimal_point_index = delta_phis.argmin().item()
        optimal_frequency = self.frequencies[self.optimal_point_index]
        optimal_duration = self.durations[self.optimal_point_index]
        optimal_phase = delta_phis.min().item() + 180

        analysis_succesful = True
        analysis_result = {
            "cz_pulse_frequency": {
                "value": optimal_frequency,
                "error": 0,
            },
            "cz_pulse_duration": {
                "value": optimal_duration,
                "error": 0,
            },
            "cz_phase": {
                "value": optimal_phase,
                "error": 0,
            },
        }
        qoi = QOI(analysis_result, analysis_succesful)
        return qoi

    @property
    def processed_dataset(self):
        return self.target_qubit_probabilities


class CZCalibrationNodeAnalysis(BaseAllCouplersAnalysis):
    single_coupler_analysis_obj = CZCalibrationCouplerAnalysis

    def __init__(self, name, redis_fields, config=None, **kwargs):
        super().__init__(name, redis_fields, config)
