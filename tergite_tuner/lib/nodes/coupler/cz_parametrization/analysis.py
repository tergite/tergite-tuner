# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman, 2024
# (C) Chalmers Next Labs 2025
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
from scipy.ndimage import convolve

from tergite_tuner.lib.spec import CouplerAnalysis, Fits, get_fits_from_result
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


# the weight of each nearest neighbour's score in a point's
NEIGHBOUR_WEIGHTS = np.array(
    [[0.02, 0.05, 0.01], [0.05, 1.0, 0.05], [0.02, 0.02, 0.02]]
)


class CZParametrizationAnalysis(CouplerAnalysis):
    """Base of the CZ analyses that read both qubits' state populations over the CZ pulse's settings."""

    def __init__(self, dataset: xr.Dataset, session: "SessionContext", **keywords: Any):
        super().__init__(dataset, session, **keywords)

    def calculate_probabilities(self):
        """Finds the swept settings in the dataset, and classifies both qubits' shots into ``probabilities``."""
        dataset = self.S21
        for coord in dataset.coords:
            coord = str(coord)
            if "loops" in coord:
                self.loops_coord = coord
            elif "frequencies" in coord:
                self.frequencies_coord = coord
                self.frequencies = dataset[self.frequencies_coord].values
            elif "amplitudes" in coord:
                self.amplitudes_coord = coord
                self.amplitudes = dataset[self.amplitudes_coord].values
            elif "durations" in coord:
                self.durations_coord = coord
                self.durations = dataset[self.durations_coord].values
            elif "dc_currents" in coord:
                self.dc_currents_coord = coord
                self.dc_currents = dataset[self.dc_currents_coord].values

        control_qubit_probabilities = calculate_probabilities(
            self.control_qubit_data_var, self.session.state
        )
        target_qubit_probabilities = calculate_probabilities(
            self.target_qubit_data_var, self.session.state
        )

        self.probabilities = xr.concat(
            [control_qubit_probabilities, target_qubit_probabilities],
            dim="qubit",
        )
        self.probabilities = self.probabilities.rename(self.coupler)


class CZParametrizationCouplerAnalysis(CZParametrizationAnalysis):
    """Finds the CZ pulse's frequency and amplitude, and the coupler's parking current, that best exchange population along the phase path."""

    def analyse(self) -> Fits | None:
        """Scores every frequency and amplitude at each parking current, and keeps the best.

        Returns:
            The fits ``cz_pulse_frequency``, ``cz_pulse_amplitude`` and
            ``parking_current``, marked ``failed`` if no point scores above 1.
        """
        self.calculate_probabilities()
        self.optimal_values = xr.DataArray(name=self.coupler)
        for current_index in range(len(self.dc_currents)):
            self.optimal_values = xr.merge(
                [self.optimal_values, self._get_optimal_point(current_index)],
                join="outer",
                compat="no_conflicts",
            )
        optimal = self.optimal_values.idxmax()[self.coupler].values.tolist()
        self.optimal_frequency = optimal[0]
        self.optimal_amplitude = optimal[1]
        self.optimal_dc_current = optimal[2]
        self.optimal_current_index = optimal[3]

        self.analysis_succesful = any(self.optimal_values[self.coupler] > 1)
        analysis_result = {
            "cz_pulse_frequency": {"value": self.optimal_frequency, "error": 0},
            "cz_pulse_amplitude": {"value": self.optimal_amplitude, "error": 0},
            "parking_current": {"value": self.optimal_dc_current, "error": 0},
        }
        return get_fits_from_result(analysis_result, self.analysis_succesful)

    def _get_optimal_point(self, current_index: int) -> xr.DataArray:
        """The best-scoring frequency and amplitude at one parking current, as a point of the stack."""
        probabilities = self.probabilities.isel({self.dc_currents_coord: current_index})
        scores = get_smoothed_scores(
            get_path_scores(
                probabilities.sel({"qubit": self.control_qubit}),
                probabilities.sel({"qubit": self.target_qubit}),
                self.phase_path,
            )
        )
        point = (
            scores.where(scores == scores.max(), drop=True)
            .expand_dims(self.dc_currents_coord)
            .expand_dims({"index": [current_index]})
        )
        return point.stack(
            multi=[
                self.frequencies_coord,
                self.amplitudes_coord,
                self.dc_currents_coord,
                "index",
            ]
        )

    def plotter(self, figures_dictionary: dict[str, list]):
        """Draws both qubits' populations over frequency and amplitude, a figure per parking current, with each one's best point.

        Args:
            figures_dictionary: takes the coupler's figures, under the coupler's name.
        """
        figures_list = []
        for current_index, current in enumerate(self.dc_currents):

            marker = "8"
            if current_index == self.optimal_current_index:
                marker = "*"
            current_probabilities = self.probabilities.isel(
                {self.dc_currents_coord: current_index}
            )

            current_probabilities.plot(
                x=self.frequencies_coord,
                cmap="RdBu_r",
                row="qubit",
                col="state",
            )

            population_exchange_points = self.optimal_values.sel(
                {"index": current_index}
            )
            frequency = population_exchange_points[self.frequencies_coord]
            amplitude = population_exchange_points[self.amplitudes_coord]
            score = population_exchange_points[self.coupler].item()
            fig = plt.gcf()

            if self.analysis_succesful:
                title = f"{score = :.3f}   {current = :.6f}"
                fig.suptitle(title, x=0.55, color="red")
                for ax in fig.axes:
                    ax.scatter(
                        frequency,
                        amplitude,
                        s=100,
                        color="yellow",
                        marker=marker,
                    )
                if current_index == self.optimal_current_index:
                    fig.suptitle(
                        f"{current = :.6f}"
                        f"  score = {score:.3f}"
                        f"  freq = {self.optimal_frequency:.5e}"
                        f"  ampl = {self.optimal_amplitude:.5f}",
                        x=0.5,
                        size=14,
                        color="red",
                    )
            else:
                title = f"No good points found, {score = :.3f}   {current = :.6f}"
                fig.suptitle(title, x=0.55, color="red")
            figures_list.append(fig)

        figures_dictionary[self.coupler] = figures_list


def get_path_scores(
    control: xr.DataArray, target: xr.DataArray, phase_path: str
) -> xr.DataArray:
    """How far each point moves the population along the phase path: |2> for the control and |0> for the target via 20, the reverse via 02.

    Args:
        control: the control's state populations.
        target: the target's state populations.
        phase_path: ``via_20`` or ``via_02``.

    Returns:
        Each point's score; higher is better.

    Raises:
        ValueError: if the phase path is neither.
    """
    if phase_path == "via_20":
        control_end, target_end = 2, 0
    elif phase_path == "via_02":
        control_end, target_end = 0, 2
    else:
        raise ValueError("Invalid phase path")
    return _get_state_lead(control, control_end) + _get_state_lead(target, target_end)


def get_smoothed_scores(scores: xr.DataArray) -> xr.DataArray:
    """The scores weighted with their nearest neighbours', points off the grid counting -1.

    Args:
        scores: each point's score, over frequency and amplitude.

    Returns:
        The smoothed scores, on the same grid.
    """
    smoothed = scores.copy(deep=True)
    smoothed.values = convolve(
        smoothed.values,
        NEIGHBOUR_WEIGHTS / np.sum(NEIGHBOUR_WEIGHTS),
        mode="constant",
        cval=-1,
    )
    return smoothed


def _get_state_lead(probabilities: xr.DataArray, state: int) -> xr.DataArray:
    """The probability of ``state`` less those of |1> and of the third state, in that order."""
    other = 2 - state
    return (
        probabilities.sel({"state": state})
        - probabilities.sel({"state": 1})
        - probabilities.sel({"state": other})
    )
