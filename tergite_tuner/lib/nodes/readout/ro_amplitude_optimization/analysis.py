# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Stefan Hill 2024
# (C) Copyright Michele Faucci Giannelli 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Readout amplitude optimization's analyses: the amplitude that best tells the states apart."""

from typing import TYPE_CHECKING, NamedTuple

import matplotlib.patches as mpatches
import numpy as np
import xarray as xr
from matplotlib.axes import Axes
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import ConfusionMatrixDisplay

from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.utils import (
    align_on_y_axis,
)
from tergite_tuner.lib.spec import Fit, Fits
from tergite_tuner.lib.utils.analysis_models import ThreeClassBoundary, TwoClassBoundary
from tergite_tuner.lib.utils.classification_functions import classify_shots

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

MARKER_SIZE = 40
# each state's shots read as it, and read as another: the colours, then the label
SHOT_STYLES = (
    ("blue", "dodgerblue", "send 0 and read 0"),
    ("red", "orange", "send 1 and read 1"),
    ("green", "lime", "send 2 and read 2"),
)


class AmplitudeSweep(NamedTuple):
    """Each readout amplitude's assignment fidelity, and the best amplitude's.

    Attributes:
        amplitudes: the readout amplitudes.
        fidelities: each amplitude's assignment fidelity.
        optimal_index: the index of the amplitude with the highest fidelity.
        confusion_matrix: the best amplitude's normalised confusion matrix.
    """

    amplitudes: np.ndarray
    fidelities: list[float]
    optimal_index: int
    confusion_matrix: np.ndarray


class TwoStateReadout(NamedTuple):
    """The two-state readout at the best amplitude, to plot.

    Attributes:
        sweep: the fidelity per amplitude.
        shots: each state's shots read as it, and read as the other.
        rotated_shots: the same shots, rotated so the boundary is upright.
        centers: the two states' centres.
        slope: the boundary's slope.
        y_intercept: the boundary's Q at I = 0.
        boundary_i: the I values to draw the boundary over.
        limits: the I limits and the Q limits of the shots' axis.
        rotation_degrees: the acquisition rotation.
        threshold: the acquisition threshold, on the rotated I axis.
    """

    sweep: AmplitudeSweep
    shots: list[tuple[np.ndarray, np.ndarray]]
    rotated_shots: list[tuple[np.ndarray, np.ndarray]]
    centers: np.ndarray
    slope: float
    y_intercept: np.ndarray
    boundary_i: np.ndarray
    limits: tuple[tuple[float, float], tuple[float, float]]
    rotation_degrees: float
    threshold: float


class ThreeStateReadout(NamedTuple):
    """The three-state readout at the best amplitude, to plot.

    Attributes:
        sweep: the fidelity per amplitude.
        shots: each state's shots read as it, and read as another.
        boundary: the boundaries between the states.
    """

    sweep: AmplitudeSweep
    shots: list[tuple[np.ndarray, np.ndarray]]
    boundary: ThreeClassBoundary


def analyse_two_state_ro_amplitude(
    s21: xr.DataArray, _session: "SessionContext"
) -> Fits:
    """Classifies 0 and 1 at each amplitude, and rotates the best one's shots onto the I axis.

    Args:
        s21: the qubit's shots over prepared state, readout amplitude and loop.
        _session: unused; part of the ``analyse`` signature.

    Returns:
        The best ``measure_2state_opt:pulse_amp``, the ``acq_rotation`` in degrees
        and ``acq_threshold`` that put 0 at negative and 1 at positive I, the
        discriminant's ``lda_coef_0``, ``lda_coef_1`` and ``lda_intercept``, and,
        to plot, the ``readout``.
    """
    sweep, iq, states = _classify_amplitudes(s21)
    lda = _get_lda()
    classified = lda.fit(iq, states).predict(iq)
    boundary = TwoClassBoundary(lda)
    aligned, rotation_rad, threshold = align_on_y_axis(
        iq, classified, boundary.theta_rad, boundary.threshold
    )
    readout = TwoStateReadout(
        sweep=sweep,
        shots=[_split_by_outcome(iq, states, classified, state) for state in (0, 1)],
        rotated_shots=[
            _split_by_outcome(aligned, states, classified, state) for state in (0, 1)
        ],
        centers=boundary.centers,
        slope=boundary.lamda,
        y_intercept=boundary.y_intercept,
        boundary_i=np.linspace(iq[:, 0].min(), iq[:, 0].max(), 100),
        limits=get_iq_limits(iq, boundary.centers),
        rotation_degrees=np.rad2deg(rotation_rad),
        threshold=threshold,
    )
    return {
        "measure_2state_opt:pulse_amp": Fit(sweep.amplitudes[sweep.optimal_index]),
        "measure_2state_opt:acq_rotation": Fit(readout.rotation_degrees),
        "measure_2state_opt:acq_threshold": Fit(threshold),
        "lda_coef_0": Fit(str(float(lda.coef_[0][0]))),
        "lda_coef_1": Fit(str(float(lda.coef_[0][1]))),
        "lda_intercept": Fit(str(float(lda.intercept_[0]))),
        "readout": Fit(readout),
    }


def analyse_three_state_ro_amplitude(
    s21: xr.DataArray, _session: "SessionContext"
) -> Fits:
    """The best amplitude's three-state boundaries: their centroid and the angle of each pair's boundary.

    Args:
        s21: the qubit's shots over prepared state, readout amplitude and loop.
        _session: unused; part of the ``analyse`` signature.

    Returns:
        The best ``measure_3state_opt:pulse_amp``, the boundaries' ``centroid_I``
        and ``centroid_Q``, ``omega_01``, ``omega_12`` and ``omega_20``,
        ``inv_cm_opt``, always 0, and, to plot, the ``readout``.
    """
    sweep, iq, states = _classify_amplitudes(s21)
    lda = _get_lda()
    classified = lda.fit(iq, states).predict(iq)
    boundary = ThreeClassBoundary(lda)
    readout = ThreeStateReadout(
        sweep=sweep,
        shots=[_split_by_outcome(iq, states, classified, state) for state in (0, 1, 2)],
        boundary=boundary,
    )
    return {
        "measure_3state_opt:pulse_amp": Fit(sweep.amplitudes[sweep.optimal_index]),
        "centroid_I": Fit(boundary.centroid[0]),
        "centroid_Q": Fit(boundary.centroid[1]),
        "omega_01": Fit(boundary.omega_01),
        "omega_12": Fit(boundary.omega_12),
        "omega_20": Fit(boundary.omega_20),
        "inv_cm_opt": Fit(0),
        "readout": Fit(readout),
    }


def plot_two_state_ro_amplitude(
    axes: np.ndarray, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """The fidelity per amplitude, then the best amplitude's shots as measured, with the boundary, and as rotated, with the threshold.

    Args:
        axes: the column of three axes to draw on.
        s21: the qubit's shots, which name the qubit.
        fits: the qubit's fits; nothing is drawn if empty.
        _session: unused; part of the ``plot`` signature.
    """
    if not fits:
        return
    readout = fits["readout"].value
    _plot_sweep(axes[0], readout.sweep)
    iq_axis, rotated_axis = axes[1], axes[2]
    iq_axis.set_xlim(*readout.limits[0])
    iq_axis.set_ylim(*readout.limits[1])
    _plot_shots(iq_axis, readout.shots)
    iq_axis.scatter(
        readout.centers[:, 0],
        readout.centers[:, 1],
        s=2 * MARKER_SIZE,
        color="brown",
        zorder=10,
    )
    iq_axis.scatter(
        0, readout.y_intercept, s=2 * MARKER_SIZE, marker="P", color="black", zorder=11
    )
    iq_axis.plot(
        readout.boundary_i,
        readout.slope * readout.boundary_i + readout.y_intercept,
        lw=2,
        label=f"angle: {readout.rotation_degrees:0.1f}" r"$\degree$",
    )
    _draw_axes_lines(iq_axis)
    _plot_shots(rotated_axis, readout.rotated_shots)
    rotated_axis.axvline(
        readout.threshold,
        color="purple",
        lw=3,
        label=f"threshold: {readout.threshold:0.4f}",
    )
    _draw_axes_lines(rotated_axis)
    _add_qubit_legend(axes[0], s21.attrs["qubit"])


def plot_three_state_ro_amplitude(
    axes: np.ndarray, s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """The fidelity per amplitude, then the best amplitude's shots with the boundaries, and its confusion matrix.

    Args:
        axes: the column of three axes to draw on.
        s21: the qubit's shots, which name the qubit.
        fits: the qubit's fits; nothing is drawn if empty.
        _session: unused; part of the ``plot`` signature.
    """
    if not fits:
        return
    readout = fits["readout"].value
    _plot_sweep(axes[0], readout.sweep)
    iq_axis = axes[1]
    _plot_shots(iq_axis, readout.shots)
    for pair, colour in (
        ((0, 1), "blueviolet"),
        ((1, 2), "firebrick"),
        ((2, 0), "cyan"),
    ):
        iq_axis.plot(*readout.boundary.boundary_line(*pair), color=colour, lw=4)
    iq_axis.scatter(
        *readout.boundary.centroid, marker="*", s=480, color="black", zorder=2
    )
    ConfusionMatrixDisplay(confusion_matrix=readout.sweep.confusion_matrix).plot(
        ax=axes[2]
    )
    _add_qubit_legend(axes[0], s21.attrs["qubit"])


def get_iq_limits(
    iq: np.ndarray, centers: np.ndarray
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Square I and Q limits that hold the shots and the origin, padded by half the centres' distance.

    Args:
        iq: the shots, a row of I and Q each.
        centers: the states' centres, a row of I and Q each.

    Returns:
        The I limits and the Q limits, each as (low, high).
    """
    lower = np.minimum(iq.min(axis=0), 0)
    span = (np.maximum(iq.max(axis=0), 0) - lower).max()
    padding = np.linalg.norm(centers[0] - centers[1]) / 2
    return tuple((low - padding, low + span + padding) for low in lower)


def _split_by_outcome(
    iq: np.ndarray, states: np.ndarray, classified_states: np.ndarray, state: int
) -> tuple[np.ndarray, np.ndarray]:
    """The shots prepared in ``state`` that were read as it, and those that were not."""
    is_sent = states == state
    is_read = classified_states[is_sent] == state
    return iq[is_sent][is_read], iq[is_sent][~is_read]


def _classify_amplitudes(
    s21: xr.DataArray,
) -> tuple[AmplitudeSweep, np.ndarray, np.ndarray]:
    """Classifies each amplitude's shots; the best amplitude has the highest assignment fidelity.

    Returns:
        The sweep, the best amplitude's shots as rows of I and Q, and the state each
        shot was prepared in.

    Raises:
        ValueError: if the dataset has a coordinate other than the amplitudes, the
            states and the loops.
    """
    unknown = [
        coord
        for coord in s21.coords
        if not any(part in str(coord) for part in ("amplitudes", "state", "loops"))
    ]
    if unknown:
        raise ValueError(f"Coordinates not found in dataset: {unknown}")
    amplitude_coord = _find_coord(s21, "amplitudes")
    shots = s21.stack(shots=[_find_coord(s21, "loops"), _find_coord(s21, "state")])
    states = shots[_find_coord(s21, "state")].values
    amplitudes = s21[amplitude_coord].values
    lda = _get_lda()
    fidelities, matrices = [], []
    for index in range(len(amplitudes)):
        _, matrix, fidelity = classify_shots(
            _get_iq(shots, amplitude_coord, index), states, lda
        )
        fidelities.append(fidelity)
        matrices.append(matrix)
    optimal_index = np.argmax(fidelities)
    sweep = AmplitudeSweep(
        amplitudes, fidelities, optimal_index, matrices[optimal_index]
    )
    return sweep, _get_iq(shots, amplitude_coord, optimal_index), states


def _get_iq(shots: xr.DataArray, amplitude_coord: str, index: int) -> np.ndarray:
    """One amplitude's shots, as rows of I and Q."""
    complex_shots = shots.isel({amplitude_coord: index})
    return np.array([complex_shots.real.values, complex_shots.imag.values]).T


def _get_lda() -> LinearDiscriminantAnalysis:
    return LinearDiscriminantAnalysis(solver="svd", store_covariance=True)


def _find_coord(array: xr.DataArray, part: str) -> str:
    """The array's coordinate whose name holds ``part``."""
    return next(str(coord) for coord in array.coords if part in str(coord))


def _plot_sweep(axis: Axes, sweep: AmplitudeSweep) -> None:
    """The assignment fidelity per readout amplitude, the best one starred."""
    axis.set_xlabel("RO amplitude")
    axis.set_ylabel("assignment fidelity")
    axis.plot(sweep.amplitudes, sweep.fidelities)
    axis.plot(
        sweep.amplitudes[sweep.optimal_index],
        sweep.fidelities[sweep.optimal_index],
        "*",
        ms=14,
    )
    axis.grid()


def _plot_shots(axis: Axes, shots: list[tuple[np.ndarray, np.ndarray]]) -> None:
    """Each state's shots, those read as it as dots and labelled, the others as crosses."""
    styles = SHOT_STYLES[: len(shots)]
    for (read, misread), (colour, misread_colour, label) in zip(
        shots, styles, strict=True
    ):
        axis.scatter(
            read[:, 0], read[:, 1], marker=".", s=MARKER_SIZE, color=colour, label=label
        )
        axis.scatter(
            misread[:, 0],
            misread[:, 1],
            marker="x",
            s=MARKER_SIZE,
            color=misread_colour,
            label="",
        )


def _draw_axes_lines(axis: Axes) -> None:
    """The legend, then the I and Q axes through the origin."""
    axis.legend()
    axis.axhline(0, color="black")
    axis.axvline(0, color="black")


def _add_qubit_legend(axis: Axes, qubit: str) -> None:
    """A small legend on ``axis`` naming the qubit."""
    handles, _ = axis.get_legend_handles_labels()
    handles.append(mpatches.Patch(color="red", label=qubit))
    axis.legend(handles=handles, fontsize="small")
