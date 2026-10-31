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
from typing import TYPE_CHECKING

import matplotlib.patches as mpatches
import numpy as np
import xarray as xr
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import ConfusionMatrixDisplay

from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.utils import (
    align_on_y_axis,
)
from tergite_tuner.lib.spec import ElementAnalysis, Fit, Fits
from tergite_tuner.lib.utils.analysis_models import ThreeClassBoundary, TwoClassBoundary
from tergite_tuner.lib.utils.classification_functions import classify_shots

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class OptimalROAmplitudeQubitAnalysis(ElementAnalysis):
    """Classifies a qubit's readout shots at each amplitude; ``analyse`` gives the best amplitude's."""

    def populate_coords(self):
        """Finds the amplitude, state and loop coordinates, and stacks the loops and states into shots.

        Raises:
            ValueError: if the dataset has any other coordinate.
        """
        for coord in self.S21.coords:
            if "amplitudes" in str(coord):
                self.amplitude_coord = coord
                self.amplitudes = self.S21.coords[coord]
            elif "state" in str(coord):
                self.state_coord = coord
                self.unique_qubit_states = self.S21[coord].values
            elif "loops" in str(coord):
                self.loop_coord = coord
            else:
                raise ValueError("Coordinate not found in dataset")

        self.S21_stacked = self.S21.stack(shots=[self.loop_coord, self.state_coord])
        self.qubit_states = self.S21_stacked[self.state_coord].values

    def IQ(self, index: int) -> np.ndarray:
        """Extracts I/Q components from the dataset at a given index.

        Args:
            index: the readout amplitude's index.

        Returns:
            The amplitude's shots, a row of I and Q each.
        """

        IQ_complex = self.S21_stacked[self.data_var].isel({self.amplitude_coord: index})
        I = IQ_complex.real.values
        Q = IQ_complex.imag.values
        return np.array([I, Q]).T

    def classify_amplitudes(self) -> None:
        """Classifies each amplitude's shots; the best amplitude has the highest assignment fidelity."""
        self.lda = LinearDiscriminantAnalysis(solver="svd", store_covariance=True)
        self.fidelities = []
        self.cms = []
        for index in range(len(self.amplitudes)):
            _, cm_norm, assignment = classify_shots(
                self.IQ(index), self.qubit_states, self.lda
            )
            self.fidelities.append(assignment)
            self.cms.append(cm_norm)
        self.optimal_index = np.argmax(self.fidelities)
        self.optimal_amplitude = self.amplitudes.values[self.optimal_index]

    def plot_iq_scatter(
        self, ax, iq_points: np.ndarray, marker: str, color: str, label: str = ""
    ):
        """Draws shots in the IQ plane.

        Args:
            ax: the axis to draw on.
            iq_points: the shots, a row of I and Q each.
            marker: the shots' marker.
            color: the shots' colour.
            label: the shots' legend entry; none if empty.
        """
        self.mark_size = 40
        styles = {"marker": marker, "s": self.mark_size, "color": color}
        ax.scatter(iq_points[:, 0], iq_points[:, 1], **styles, label=label)

    def primary_plotter(self, ax):
        """Draws the assignment fidelity per readout amplitude, the best one starred.

        Args:
            ax: the axis to draw on.
        """
        ax.set_xlabel("RO amplitude")
        ax.set_ylabel("assignment fidelity")
        ax.plot(self.amplitudes, self.fidelities)
        ax.plot(self.optimal_amplitude, self.fidelities[self.optimal_index], "*", ms=14)
        ax.grid()

    def plot(self, primary_axis, secondary_axes):
        """Draws the fidelities and the best amplitude's shots, with the qubit in the legend.

        Args:
            primary_axis: the axis for the fidelity per amplitude.
            secondary_axes: the two axes for the best amplitude's shots.
        """
        self.plotter(
            primary_axis, secondary_axes
        )  # Assuming node_analysis object is available

        # Customize plot as needed
        handles, labels = primary_axis.get_legend_handles_labels()
        patch = mpatches.Patch(color="red", label=f"{self.qubit}")
        handles.append(patch)
        primary_axis.legend(handles=handles, fontsize="small")


class OptimalROTwoStateAmplitudeQubitAnalysis(OptimalROAmplitudeQubitAnalysis):
    """Finds the readout amplitude that best tells 0 from 1, and its thresholded acquisition."""

    def analyse(self) -> Fits:
        """Classifies 0 and 1 at each amplitude, and rotates the best one's shots onto the I axis.

        Returns:
            The best ``measure_2state_opt:pulse_amp``, the ``acq_rotation`` in degrees
            and ``acq_threshold`` that put 0 at negative and 1 at positive I, the
            discriminant's ``lda_coef_0``, ``lda_coef_1`` and ``lda_intercept``, and the
            ``analysis`` for the plot.
        """
        self.populate_coords()
        self.classify_amplitudes()

        states = self.qubit_states
        optimal_IQ = self.IQ(self.optimal_index)
        classified_states = self.lda.fit(optimal_IQ, states).predict(optimal_IQ)

        boundary = TwoClassBoundary(self.lda)
        self.theta_rad = boundary.theta_rad
        self.y_intercept = boundary.y_intercept
        self.absolute_threshold = boundary.threshold
        self.centers = boundary.centers
        self.lamda = boundary.lamda

        aligned_IQ, rotation_angle_rad, self.threshold = align_on_y_axis(
            optimal_IQ, classified_states, self.theta_rad, self.absolute_threshold
        )
        self.rotation_angle_degrees = np.rad2deg(rotation_angle_rad)

        self.IQ0_tp, self.IQ0_fp = _split_by_outcome(
            optimal_IQ, states, classified_states, 0
        )
        self.IQ1_tp, self.IQ1_fp = _split_by_outcome(
            optimal_IQ, states, classified_states, 1
        )
        self.rotated_IQ0_tp, self.rotated_IQ0_fp = _split_by_outcome(
            aligned_IQ, states, classified_states, 0
        )
        self.rotated_IQ1_tp, self.rotated_IQ1_fp = _split_by_outcome(
            aligned_IQ, states, classified_states, 1
        )

        self.x_space = np.linspace(optimal_IQ[:, 0].min(), optimal_IQ[:, 0].max(), 100)
        self.x_limits, self.y_limits = get_iq_limits(optimal_IQ, self.centers)

        return {
            "measure_2state_opt:pulse_amp": Fit(self.optimal_amplitude),
            "measure_2state_opt:acq_rotation": Fit(self.rotation_angle_degrees),
            "measure_2state_opt:acq_threshold": Fit(self.threshold),
            "lda_coef_0": Fit(str(float(self.lda.coef_[0][0]))),
            "lda_coef_1": Fit(str(float(self.lda.coef_[0][1]))),
            "lda_intercept": Fit(str(float(self.lda.intercept_[0]))),
            "analysis": Fit(self),
        }

    def plotter(self, ax, secondary_axes):
        """Draws the fidelities, then the best amplitude's shots as measured and as rotated.

        Args:
            ax: the axis for the fidelity per amplitude.
            secondary_axes: the axes for the measured shots, with the boundary, and
                the rotated shots, with the threshold.
        """
        self.primary_plotter(ax)
        iq_axis = secondary_axes[0]

        optimal_iq_axis = secondary_axes[0]
        optimal_iq_axis.set_xlim(*self.x_limits)
        optimal_iq_axis.set_ylim(*self.y_limits)
        self.plot_iq_scatter(
            iq_axis, self.IQ0_tp, ".", "blue", label="send 0 and read 0"
        )
        self.plot_iq_scatter(iq_axis, self.IQ0_fp, "x", "dodgerblue")
        self.plot_iq_scatter(
            iq_axis, self.IQ1_tp, ".", "red", label="send 1 and read 1"
        )
        self.plot_iq_scatter(iq_axis, self.IQ1_fp, "x", "orange")
        iq_axis.scatter(
            self.centers[:, 0],
            self.centers[:, 1],
            s=2 * self.mark_size,
            color="brown",
            zorder=10,
        )
        iq_axis.scatter(
            0,
            self.y_intercept,
            s=2 * self.mark_size,
            marker="P",
            color="black",
            zorder=11,
        )

        iq_axis.plot(
            self.x_space,
            self.lamda * self.x_space + self.y_intercept,
            lw=2,
            label=f"angle: {self.rotation_angle_degrees:0.1f}" r"$\degree$",
        )
        optimal_iq_axis.legend()
        optimal_iq_axis.axhline(0, color="black")
        optimal_iq_axis.axvline(0, color="black")
        rotated_iq_axis = secondary_axes[1]
        self.plot_iq_scatter(
            rotated_iq_axis, self.rotated_IQ0_tp, ".", "blue", label="send 0 and read 0"
        )
        self.plot_iq_scatter(rotated_iq_axis, self.rotated_IQ0_fp, "x", "dodgerblue")
        self.plot_iq_scatter(
            rotated_iq_axis, self.rotated_IQ1_tp, ".", "red", label="send 1 and read 1"
        )
        self.plot_iq_scatter(rotated_iq_axis, self.rotated_IQ1_fp, "x", "orange")
        rotated_iq_axis.axvline(
            self.threshold,
            color="purple",
            lw=3,
            label=f"threshold: {self.threshold:0.4f}",
        )

        rotated_iq_axis.legend()
        rotated_iq_axis.axhline(0, color="black")
        rotated_iq_axis.axvline(0, color="black")


class ROThreeStateAmplitudeQubitAnalysis(OptimalROAmplitudeQubitAnalysis):
    """Finds the readout amplitude that best tells 0, 1 and 2 apart, and the boundaries between them."""

    def analyse(self) -> Fits:
        """The best amplitude's three-state boundaries: their centroid and the angle of each pair's boundary.

        Returns:
            The best ``measure_3state_opt:pulse_amp``, the boundaries' ``centroid_I``
            and ``centroid_Q``, ``omega_01``, ``omega_12`` and ``omega_20``,
            ``inv_cm_opt``, always 0, and the ``analysis`` for the plot.
        """
        self.populate_coords()
        self.classify_amplitudes()

        states = self.qubit_states
        optimal_IQ = self.IQ(self.optimal_index)
        classified_states = self.lda.fit(optimal_IQ, states).predict(optimal_IQ)

        self.boundary = ThreeClassBoundary(self.lda)
        self.centroid_I = self.boundary.centroid[0]
        self.centroid_Q = self.boundary.centroid[1]
        self.omega_01 = self.boundary.omega_01
        self.omega_12 = self.boundary.omega_12
        self.omega_20 = self.boundary.omega_20

        self.IQ0_tp, self.IQ0_fp = _split_by_outcome(
            optimal_IQ, states, classified_states, 0
        )
        self.IQ1_tp, self.IQ1_fp = _split_by_outcome(
            optimal_IQ, states, classified_states, 1
        )
        self.IQ2_tp, self.IQ2_fp = _split_by_outcome(
            optimal_IQ, states, classified_states, 2
        )

        return {
            "measure_3state_opt:pulse_amp": Fit(self.optimal_amplitude),
            "centroid_I": Fit(self.centroid_I),
            "centroid_Q": Fit(self.centroid_Q),
            "omega_01": Fit(self.omega_01),
            "omega_12": Fit(self.omega_12),
            "omega_20": Fit(self.omega_20),
            "inv_cm_opt": Fit(0),
            "analysis": Fit(self),
        }

    def plot_classified_IQ_points(self, iq_axis, amplitude_index: int):
        """Draws the best amplitude's shots, coloured by the state they were prepared in.

        Args:
            iq_axis: the axis to draw on.
            amplitude_index: unused; the best amplitude's shots are drawn.
        """

        angle = 0
        rotation_angle_rad = np.deg2rad(angle)
        rotation_matrix = np.array(
            [
                [np.cos(rotation_angle_rad), -np.sin(rotation_angle_rad)],
                [np.sin(rotation_angle_rad), np.cos(rotation_angle_rad)],
            ]
        )
        iq0_tp = self.IQ0_tp @ rotation_matrix.T
        iq1_tp = self.IQ1_tp @ rotation_matrix.T
        iq2_tp = self.IQ2_tp @ rotation_matrix.T

        self.plot_iq_scatter(iq_axis, iq0_tp, ".", "blue", label="send 0 and read 0")
        self.plot_iq_scatter(iq_axis, self.IQ0_fp, "x", "dodgerblue")
        self.plot_iq_scatter(iq_axis, iq1_tp, ".", "red", label="send 1 and read 1")
        self.plot_iq_scatter(iq_axis, self.IQ1_fp, "x", "orange")
        self.plot_iq_scatter(iq_axis, iq2_tp, ".", "green", label="send 2 and read 2")
        self.plot_iq_scatter(iq_axis, self.IQ2_fp, "x", "lime")

    def plotter(self, ax, secondary_axes):
        """Draws the fidelities, the best amplitude's shots with the boundaries, and its confusion matrix.

        Args:
            ax: the axis for the fidelity per amplitude.
            secondary_axes: the axes for the shots and the confusion matrix.
        """
        self.primary_plotter(ax)

        iq_axis = secondary_axes[0]
        self.plot_classified_IQ_points(iq_axis, self.optimal_index)
        iq_axis.plot(
            self.boundary.boundary_line(0, 1)[0],
            self.boundary.boundary_line(0, 1)[1],
            color="blueviolet",
            lw=4,
        )
        iq_axis.plot(
            self.boundary.boundary_line(1, 2)[0],
            self.boundary.boundary_line(1, 2)[1],
            color="firebrick",
            lw=4,
        )
        iq_axis.plot(
            self.boundary.boundary_line(2, 0)[0],
            self.boundary.boundary_line(2, 0)[1],
            color="cyan",
            lw=4,
        )
        iq_axis.scatter(
            self.centroid_I, self.centroid_Q, marker="*", s=480, color="black", zorder=2
        )

        cm_axis = secondary_axes[1]
        optimal_confusion_matrix = self.cms[self.optimal_index]
        disp = ConfusionMatrixDisplay(confusion_matrix=optimal_confusion_matrix)
        disp.plot(ax=cm_axis)


def analyse_two_state_ro_amplitude(
    s21: xr.DataArray, session: "SessionContext"
) -> Fits:
    """The two-state readout's best amplitude, rotation and threshold.

    Args:
        s21: the qubit's shots over prepared state, readout amplitude and loop.
        session: the session the analysis reads.

    Returns:
        The fits of ``OptimalROTwoStateAmplitudeQubitAnalysis.analyse``.
    """
    return OptimalROTwoStateAmplitudeQubitAnalysis(s21, session).analyse()


def analyse_three_state_ro_amplitude(
    s21: xr.DataArray, session: "SessionContext"
) -> Fits:
    """The three-state readout's best amplitude and boundaries.

    Args:
        s21: the qubit's shots over prepared state, readout amplitude and loop.
        session: the session the analysis reads.

    Returns:
        The fits of ``ROThreeStateAmplitudeQubitAnalysis.analyse``.
    """
    return ROThreeStateAmplitudeQubitAnalysis(s21, session).analyse()


def plot_ro_amplitude(
    axes: np.ndarray, _s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """The fidelity per amplitude, then the best amplitude's shots, on three axes.

    Args:
        axes: the column of three axes to draw on.
        _s21: unused; part of the ``plot`` signature.
        fits: the qubit's fits, whose ``analysis`` draws itself; nothing is drawn if empty.
        _session: unused; part of the ``plot`` signature.
    """
    if fits:
        fits["analysis"].value.plot(axes[0], list(axes[1:]))


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
