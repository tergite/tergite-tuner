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
from functools import partial
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from tergite_tuner.lib.spec import CouplerAnalysis, Fits, get_fits_from_result
from tergite_tuner.lib.utils.analysis_models import (
    SineOscillatingModel,
    fit_sine_phase,
)
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

PLOT_COLUMNS = 5

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class CZCalibrationCouplerAnalysis(CouplerAnalysis):
    def __init__(self, dataset: xr.Dataset, session: "SessionContext", **keywords: Any):
        super().__init__(dataset, session, **keywords)
        self.model = SineOscillatingModel()
        self.model.set_param_hint("phase", min=-360, max=360, vary=True)

    def analyse(self) -> Fits | None:

        for coord in self.S21.coords:
            coord = str(coord)
            if "control_ons" in coord:
                self.control_mode_coord = coord
            elif "dc_currents" in coord:
                self.dc_currents_coord = coord
                self.dc_currents = self.S21[self.dc_currents_coord].values
            elif "working_points" in coord:
                self.cz_working_points_coord = coord
                self.cz_working_points = self.S21[coord].values
                self.number_of_wp = self.S21[coord].size
                self.frequencies, self.durations = zip(*self.cz_working_points)
            elif "ramsey_phases" in coord:
                if self.target_qubit in coord:
                    self.target_phase_coord = coord
                    self.target_phases = self.S21[coord].values
            elif "loops" in coord:
                self.loops_coord = coord

        self.control_qubit_probabilities = calculate_probabilities(
            self.control_qubit_data_var, self.session.state
        )
        self.target_qubit_probabilities = calculate_probabilities(
            self.target_qubit_data_var, self.session.state
        )

        data_target_0 = self.target_qubit_probabilities.sel({"state": 0})

        self.fit_plot_phases = np.linspace(
            self.target_phases[0], self.target_phases[-1], 200
        )  # x-values for plotting

        # self.phi_0 is the global phase of each for the |0> state of the target qubit
        self.phi_0, target_plot_points_0 = xr.apply_ufunc(
            partial(
                fit_sine_phase,
                self.model,
                x=self.target_phases,
                plot_x=self.fit_plot_phases,
            ),
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
        return get_fits_from_result(analysis_result, analysis_succesful)

    def plotter(self, figures_dictionary):
        rows = max(1, int(np.ceil((self.number_of_wp + 1) / PLOT_COLUMNS)))
        figure, axes = plt.subplots(
            ncols=PLOT_COLUMNS, nrows=rows, sharex=True, sharey=True, squeeze=False
        )
        for index in range(len(self.cz_working_points)):
            self._plot_working_point(
                axes[index // PLOT_COLUMNS][index % PLOT_COLUMNS], index
            )
        figure.text(0.5, 0.04, self.target_phase_coord, ha="center")
        figure.text(
            0.04,
            0.5,
            rf"Target Qubit: {self.target_qubit}, $|0\rangle$ probailities",
            va="center",
            rotation="vertical",
        )
        summary_axis = axes[self.number_of_wp // PLOT_COLUMNS][
            self.number_of_wp % PLOT_COLUMNS
        ]
        self._plot_phase_differences(summary_axis, axes)
        figure.suptitle(
            "Target Qubit State 0 Probabilities: \n orange: control is ON - black: control is OFF"
        )
        figures_dictionary[self.coupler] = [figure]

    def _plot_working_point(self, axis: Any, index: int) -> None:
        """The target's |0> probabilities and sine fits with the control on and off, best point in red."""
        is_optimal = index == self.optimal_point_index
        point = {self.cz_working_points_coord: index}
        phi_on = self.phi_0.sel({self.control_mode_coord: True}).isel(point)
        phi_off = self.phi_0.sel({self.control_mode_coord: False}).isel(point)
        delta_phi = np.rad2deg((phi_off - phi_on).values.item())

        fit_points = self.target_plot_points_0.isel(point)
        probabilities = self.target_qubit_probabilities.isel(point)
        for is_on, colour in ((True, "orange"), (False, "black")):
            fit_points.sel({self.control_mode_coord: is_on}).plot(
                ax=axis, x=self.target_phase_coord, color=colour
            )
        for is_on, colour in ((True, "orange"), (False, "black")):
            probabilities.sel({"state": 0, self.control_mode_coord: is_on}).plot(
                ax=axis,
                x=self.target_phase_coord,
                marker="o",
                color=colour,
                ls="",
                **({} if is_on else {"label": rf"$\Delta\Phi$: {delta_phi:.1f} $^o$"}),
            )
        axis.set_title(
            f"freq: {self.frequencies[index]:.3e} duration: {self.durations[index]:.3e}",
            color="red" if is_optimal else "black",
            fontsize=10,
        )
        axis.legend(facecolor="red" if is_optimal else "white")
        axis.set_xlabel("")
        axis.set_ylabel("")

    def _plot_phase_differences(self, axis: Any, axes: np.ndarray) -> None:
        """Each working point's phase difference against its frequency, on its own scales."""
        phis_on = self.phi_0.sel({self.control_mode_coord: True})
        phis_off = self.phi_0.sel({self.control_mode_coord: False})
        for other in axes.ravel():
            axis._shared_axes["x"].remove(other)
            axis._shared_axes["y"].remove(other)
        axis.plot(self.frequencies, np.rad2deg((phis_off - phis_on).values), "bo")
