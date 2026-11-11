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


"""Coupler spectroscopy's analyses: the coupler currents where a qubit's or resonator's frequency jumps."""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, NamedTuple

import matplotlib.pyplot as plt
import numpy as np
import xarray
from matplotlib.figure import Figure

from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.analysis import (
    fit_resonator,
)
from tergite_tuner.lib.spec import Fit, Fits, get_coupler_data, get_fits_from_result
from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

# how many standard deviations a qubit spectroscopy's maximum must stand above its mean
PEAK_SIGNIFICANCE = 2.7


class CrossingSearch(NamedTuple):
    """Each qubit's ``|S21|`` over frequency and coupler current, the frequency found at each current, and the crossings, to plot.

    Attributes:
        control: the control's ``|S21|``.
        target: the target's ``|S21|``.
        currents: the coupler currents.
        control_frequencies: the control's frequency found at each current.
        target_frequencies: the target's, likewise.
        control_crossings: the currents where the control's frequency jumps.
        target_crossings: the currents where the target's frequency jumps.
        current_coord: the name of the currents' coordinate.
    """

    control: xarray.DataArray
    target: xarray.DataArray
    currents: list[float]
    control_frequencies: list[float]
    target_frequencies: list[float]
    control_crossings: list[float]
    target_crossings: list[float]
    current_coord: str


def analyse_coupler_anticrossing(
    dataset: xarray.Dataset, session: "SessionContext"
) -> Fits:
    """Finds the coupler currents where each qubit's frequency jumps, its anticrossings.

    Args:
        dataset: the coupler's variables, saved in real and imaginary parts.
        session: the session, whose device config names the coupler's qubits.

    Returns:
        The fits ``control_qubit_crossing_points`` and
        ``target_qubit_crossing_points``: each qubit's crossing currents, in A; and,
        to plot, the ``search``.
    """
    search = _search_crossings(
        dataset,
        session,
        lambda s21: xarray.ufuncs.abs(s21),
        _find_peak_frequency,
        {
            "threshold": 2000000,
            "spurious_threshold": 300000,
            "min_interval": 0.0003,
            "resonator_crossings": [],
            "resonator_crossings_interval": 0.00015,
        },
    )
    analysis_result = {
        "control_qubit_crossing_points": {
            "value": search.control_crossings,
            "error": 0,
        },
        "target_qubit_crossing_points": {"value": search.target_crossings, "error": 0},
    }
    return {**get_fits_from_result(analysis_result, True), "search": Fit(search)}


def analyse_resonator_spectroscopy_vs_current(
    dataset: xarray.Dataset, session: "SessionContext"
) -> Fits:
    """Finds the coupler currents where each qubit's resonator frequency jumps.

    Args:
        dataset: the coupler's variables, saved in real and imaginary parts.
        session: the session, whose device config names the coupler's qubits.

    Returns:
        The fits ``control_resonator_crossing_points`` and
        ``target_resonator_crossing_points``: each resonator's crossing currents,
        in A; and, to plot, the ``search``.
    """
    search = _search_crossings(
        dataset,
        session,
        lambda s21: s21,
        _fit_resonator_frequency,
        {"threshold": 30000, "spurious_threshold": 4000, "min_interval": 0.0005},
    )
    analysis_result = {
        "control_resonator_crossing_points": {
            "value": search.control_crossings,
            "error": 0,
        },
        "target_resonator_crossing_points": {
            "value": search.target_crossings,
            "error": 0,
        },
    }
    return {**get_fits_from_result(analysis_result, True), "search": Fit(search)}


def plot_coupler_anticrossing(fits: Fits) -> list[Figure]:
    """Each qubit's ``|S21|`` over current, its frequency found at each, and its anticrossings.

    Args:
        fits: the coupler's fits.

    Returns:
        The coupler's one figure.
    """
    search = fits["search"].value
    figure, axes = plt.subplots(2, 1)
    for axis, magnitudes, frequencies, crossings in (
        (axes[0], search.control, search.control_frequencies, search.control_crossings),
        (axes[1], search.target, search.target_frequencies, search.target_crossings),
    ):
        magnitudes.plot(ax=axis, x=search.current_coord)
        axis.scatter(search.currents, frequencies, s=52, c="red")
        for crossing in crossings:
            axis.axvline(crossing, color="grey", linestyle="dashed", linewidth=2)
    return [figure]


def plot_resonator_spectroscopy_vs_current(fits: Fits) -> list[Figure]:
    """Each resonator's ``|S21|`` over frequency and current, its frequency fitted at each current, and its crossings.

    Args:
        fits: the coupler's fits.

    Returns:
        The coupler's one figure.
    """
    search = fits["search"].value
    figure, axes = plt.subplots(1, 2)
    xarray.ufuncs.abs(search.control).plot(ax=axes[0])
    xarray.ufuncs.abs(search.target).plot(ax=axes[1])
    for axis, frequencies, crossings in (
        (axes[0], search.control_frequencies, search.control_crossings),
        (axes[1], search.target_frequencies, search.target_crossings),
    ):
        axis.scatter(frequencies, search.currents, s=52, c="red")
        for crossing in crossings:
            axis.axhline(crossing, color="grey", linestyle="dashed", linewidth=2)
    return [figure]


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

    Args:
        currents: the coupler currents, in A.
        frequencies: the frequency detected at each current, in Hz; NaN where none was.
        threshold: the smallest jump, in Hz, that counts as a crossing.
        spurious_threshold: how close, in Hz, the neighbours of a single dropout must be
            for it to be filled in.
        min_interval: the span of currents, in A, a group closes at.
        resonator_crossings: currents, in A, of known resonator crossings to ignore.
        resonator_crossings_interval: how close, in A, a crossing must be to a
            resonator crossing to be ignored.

    Returns:
        The crossing currents, in A.
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


def _fill_dropouts(frequencies: np.ndarray, spurious_threshold: float) -> np.ndarray:
    """Fills a single dropout between close neighbours, and drops a point isolated between dropouts."""
    frequencies = frequencies.copy()
    for i in range(1, len(frequencies) - 1):
        previous, current, following = frequencies[i - 1 : i + 2]
        if current == 0 and abs(previous - following) < spurious_threshold:
            frequencies[i] = (previous + following) / 2
        if previous == 0 and following == 0:
            frequencies[i] = 0
    return frequencies


def _search_crossings(
    dataset: xarray.Dataset,
    session: "SessionContext",
    get_signal: Callable[[xarray.DataArray], xarray.DataArray],
    find_frequency: Callable[[xarray.DataArray], float],
    thresholds: dict,
) -> CrossingSearch:
    """Each qubit's frequency at each coupler current, found in ``get_signal`` of its S21, and the currents where it jumps."""
    data = get_coupler_data(dataset, session)
    first = data.s21[list(data.s21.data_vars)[0]]
    current_coord = next(str(coord) for coord in first.coords if "currents" in coord)
    currents = list(data.s21[current_coord].values)
    control, target = get_signal(data.control), get_signal(data.target)
    control_frequencies = [
        find_frequency(control.sel({current_coord: current})) for current in currents
    ]
    target_frequencies = [
        find_frequency(target.sel({current_coord: current})) for current in currents
    ]
    return CrossingSearch(
        control=control,
        target=target,
        currents=currents,
        control_frequencies=control_frequencies,
        target_frequencies=target_frequencies,
        control_crossings=find_crossing_currents(
            currents, control_frequencies, **thresholds
        ),
        target_crossings=find_crossing_currents(
            currents, target_frequencies, **thresholds
        ),
        current_coord=current_coord,
    )


def _find_peak_frequency(magnitudes: xarray.DataArray) -> float:
    """The frequency of a qubit spectroscopy's maximum, or NaN if it does not stand ``PEAK_SIGNIFICANCE`` standard deviations above the mean."""
    # TODO: scipy's find_peaks, by prominence, would do this
    maximum = magnitudes.max()
    mean = magnitudes.mean().item()
    std = magnitudes.std().item()
    if abs((maximum - mean) / std) < PEAK_SIGNIFICANCE:
        logger.warning(
            "This spectroscopy doeas not have a proper maximum, it is ok if this is in a transition region in the coupler spectroscopy"
        )
        return np.nan
    return magnitudes.idxmax().item()


def _fit_resonator_frequency(s21: xarray.DataArray) -> float:
    """The resonator's frequency fitted to its S21 over frequency."""
    frequencies = s21.coords[s21.dims[0]].values
    return fit_resonator(frequencies, s21.values).frequency
