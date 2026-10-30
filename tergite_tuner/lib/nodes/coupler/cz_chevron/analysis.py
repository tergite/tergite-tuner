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


from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from tergite_tuner.lib.nodes.coupler.cz_parametrization.analysis import (
    CZParametrizationAnalysis,
)
from tergite_tuner.lib.spec import Fits, get_fits_from_result
from tergite_tuner.lib.utils.analysis_models import SineOscillatingModel

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


CURVE_POINTS = 200


class CZChevronCouplerAnalysis(CZParametrizationAnalysis):

    def __init__(self, dataset: xr.Dataset, session: "SessionContext", **keywords: Any):
        super().__init__(dataset, session, **keywords)
        self.model = SineOscillatingModel()
        self.model.set_param_hint("optimal_duration", expr="1/frequency", vary=False)

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

    def analyse(self) -> Fits | None:
        """The (frequency, duration) points where the chevron returns to |11>, as CZ working points."""
        self.calculate_probabilities()
        self.fit_plot_durations = np.linspace(
            self.durations[0], self.durations[-1], CURVE_POINTS
        )
        self.control_diffs, self.target_diffs = get_chevron_leads(
            self.probabilities.sel({"qubit": self.control_qubit}),
            self.probabilities.sel({"qubit": self.target_qubit}),
            self.phase_path,
        )
        self.combined_data = self.control_diffs + self.target_diffs

        # a sine fitted to each frequency's column of durations
        cz_durations, _ = xr.apply_ufunc(
            self.apply_sinusoidal_slices_fit,
            self.combined_data,
            input_core_dims=[[self.durations_coord]],
            output_core_dims=[["cz_pulse_durations"], ["plot_points"]],
            vectorize=True,
        )
        # the rejected fits' columns go
        cz_durations = cz_durations.dropna(dim=self.frequencies_coord)
        self.cz_working_durations_in_ns = get_durations_in_ns(
            cz_durations.values.flatten()
        )
        self.cz_working_frequencies = cz_durations.cz_pulse_frequencies.values
        # every working point is selected
        self.selected_frequencies = self.cz_working_frequencies
        self.selected_durations_in_ns = self.cz_working_durations_in_ns

        analysis_result = {
            "cz_working_frequencies": {
                "value": str(self.selected_frequencies.astype(int).tolist()),
                "error": 0,
            },
            "cz_working_durations_in_ns": {
                "value": str(self.selected_durations_in_ns.tolist()),
                "error": 0,
            },
        }
        return get_fits_from_result(analysis_result, True)

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


def get_chevron_leads(
    control: xr.DataArray, target: xr.DataArray, phase_path: str
) -> tuple[xr.DataArray, xr.DataArray]:
    """Each qubit's population at its end of the phase path, less its |1>: |2> for the control and |0> for the target via 20, the reverse via 02."""
    ends = {"via_20": (2, 0), "via_02": (0, 2)}
    if phase_path not in ends:
        raise ValueError(f"Invalid phase path:{phase_path}")
    control_end, target_end = ends[phase_path]
    return (
        control.sel({"state": control_end}) - control.sel({"state": 1}),
        target.sel({"state": target_end}) - target.sel({"state": 1}),
    )


def get_durations_in_ns(durations: np.ndarray) -> np.ndarray:
    """Durations in seconds, rounded down to whole nanoseconds and then to multiples of 4 ns."""
    return ((durations // 1e-9).astype(int) // 4) * 4
