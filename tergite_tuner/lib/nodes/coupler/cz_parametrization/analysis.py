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

from typing import TYPE_CHECKING, NamedTuple

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.figure import Figure
from scipy.ndimage import convolve

from tergite_tuner.lib.spec import (
    CouplerData,
    Fit,
    Fits,
    get_coupler_data,
    get_fits_from_result,
)
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


# the weight of each nearest neighbour's score in a point's
NEIGHBOUR_WEIGHTS = np.array(
    [[0.02, 0.05, 0.01], [0.05, 1.0, 0.05], [0.02, 0.02, 0.02]]
)


class ParametrizationScores(NamedTuple):
    """Both qubits' populations and the best point at each parking current, to plot.

    Attributes:
        coupler: the coupler.
        probabilities: both qubits' state populations over frequency, amplitude and
            parking current.
        optimal_values: each parking current's best point's score.
        optimal: the best point's frequency, amplitude, parking current and index.
        is_successful: whether any point scores above 1.
        coords: the names of the ``frequencies``, ``amplitudes`` and ``dc_currents``
            coordinates.
    """

    coupler: str
    probabilities: xr.DataArray
    optimal_values: xr.Dataset
    optimal: list
    is_successful: bool
    coords: dict[str, str]


def get_cz_probabilities(
    data: CouplerData, session: "SessionContext"
) -> tuple[xr.DataArray, dict[str, str]]:
    """Both qubits' state populations, and the names of the CZ pulse's swept settings.

    Args:
        data: the coupler's data.
        session: the session, whose device state holds the discriminators.

    Returns:
        The populations, over a ``qubit`` dimension and named after the coupler,
        and the names of the ``loops``, ``frequencies``, ``amplitudes``,
        ``durations`` and ``dc_currents`` coordinates the dataset has.
    """
    coords = {}
    for coord in data.s21.coords:
        coord = str(coord)
        for setting in ("loops", "frequencies", "amplitudes", "durations"):
            if setting in coord:
                coords[setting] = coord
                break
        else:
            if "dc_currents" in coord:
                coords["dc_currents"] = coord
    probabilities = xr.concat(
        [
            calculate_probabilities(data.control, session.state),
            calculate_probabilities(data.target, session.state),
        ],
        dim="qubit",
    )
    return probabilities.rename(data.coupler), coords


def analyse_cz_parametrization(
    dataset: xr.Dataset, session: "SessionContext", phase_path: str
) -> Fits:
    """Scores every frequency and amplitude at each parking current, and keeps the best.

    Args:
        dataset: the coupler's variables, saved in real and imaginary parts.
        session: the session, whose device state holds the discriminators.
        phase_path: ``via_20`` or ``via_02``.

    Returns:
        The fits ``cz_pulse_frequency``, ``cz_pulse_amplitude`` and
        ``parking_current``, marked ``failed`` if no point scores above 1, and, to
        plot, the ``scores``.
    """
    data = get_coupler_data(dataset, session)
    probabilities, coords = get_cz_probabilities(data, session)
    optimal_values = xr.DataArray(name=data.coupler)
    for current_index in range(probabilities.sizes[coords["dc_currents"]]):
        optimal_values = xr.merge(
            [
                optimal_values,
                _get_optimal_point(
                    probabilities, data, coords, phase_path, current_index
                ),
            ],
            join="outer",
            compat="no_conflicts",
        )
    optimal = optimal_values.idxmax()[data.coupler].values.tolist()
    is_successful = any(optimal_values[data.coupler] > 1)
    analysis_result = {
        "cz_pulse_frequency": {"value": optimal[0], "error": 0},
        "cz_pulse_amplitude": {"value": optimal[1], "error": 0},
        "parking_current": {"value": optimal[2], "error": 0},
    }
    scores = ParametrizationScores(
        data.coupler, probabilities, optimal_values, optimal, is_successful, coords
    )
    return {
        **get_fits_from_result(analysis_result, is_successful),
        "scores": Fit(scores),
    }


def plot_cz_parametrization(fits: Fits) -> list[Figure]:
    """Both qubits' populations over frequency and amplitude, a figure per parking current, with each one's best point.

    Args:
        fits: the coupler's fits.

    Returns:
        The coupler's figures, one per parking current.
    """
    scores = fits["scores"].value
    coords = scores.coords
    optimal_frequency, optimal_amplitude, _, optimal_current_index = scores.optimal
    figures = []
    dc_currents = scores.probabilities[coords["dc_currents"]].values
    for current_index, current in enumerate(dc_currents):
        marker = "*" if current_index == optimal_current_index else "8"
        scores.probabilities.isel({coords["dc_currents"]: current_index}).plot(
            x=coords["frequencies"], cmap="RdBu_r", row="qubit", col="state"
        )
        point = scores.optimal_values.sel({"index": current_index})
        score = point[scores.coupler].item()
        figure = plt.gcf()
        if scores.is_successful:
            figure.suptitle(f"{score = :.3f}   {current = :.6f}", x=0.55, color="red")
            for axis in figure.axes:
                axis.scatter(
                    point[coords["frequencies"]],
                    point[coords["amplitudes"]],
                    s=100,
                    color="yellow",
                    marker=marker,
                )
            if current_index == optimal_current_index:
                figure.suptitle(
                    f"{current = :.6f}"
                    f"  score = {score:.3f}"
                    f"  freq = {optimal_frequency:.5e}"
                    f"  ampl = {optimal_amplitude:.5f}",
                    x=0.5,
                    size=14,
                    color="red",
                )
        else:
            figure.suptitle(
                f"No good points found, {score = :.3f}   {current = :.6f}",
                x=0.55,
                color="red",
            )
        figures.append(figure)
    return figures


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


def _get_optimal_point(
    probabilities: xr.DataArray,
    data: CouplerData,
    coords: dict[str, str],
    phase_path: str,
    current_index: int,
) -> xr.DataArray:
    """The best-scoring frequency and amplitude at one parking current, as a point of the stack."""
    at_current = probabilities.isel({coords["dc_currents"]: current_index})
    scores = get_smoothed_scores(
        get_path_scores(
            at_current.sel({"qubit": data.control_qubit}),
            at_current.sel({"qubit": data.target_qubit}),
            phase_path,
        )
    )
    point = (
        scores.where(scores == scores.max(), drop=True)
        .expand_dims(coords["dc_currents"])
        .expand_dims({"index": [current_index]})
    )
    return point.stack(
        multi=[
            coords["frequencies"],
            coords["amplitudes"],
            coords["dc_currents"],
            "index",
        ]
    )
