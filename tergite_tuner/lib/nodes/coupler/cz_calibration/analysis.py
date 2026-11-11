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
from typing import TYPE_CHECKING, Any, NamedTuple

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.figure import Figure

from tergite_tuner.lib.spec import Fit, Fits, get_coupler_data, get_fits_from_result
from tergite_tuner.lib.utils.analysis_models import (
    SineOscillatingModel,
    fit_sine_phase,
)
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

PLOT_COLUMNS = 5
CURVE_POINTS = 200

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class PhaseCalibration(NamedTuple):
    """The target's |0> probabilities and fitted phases at each working point, to plot.

    Attributes:
        target_qubit: the coupler's target qubit.
        probabilities: the target's |0> probability per working point, Ramsey phase
            and control mode.
        phis: the target's fitted phase, in radians, per working point and control mode.
        fits: the fitted sines over the Ramsey phases.
        frequencies: each working point's CZ frequency.
        durations: each working point's CZ duration.
        optimal_index: the index of the chosen working point.
        coords: the names of the ``control``, ``working_points`` and
            ``target_phases`` coordinates.
    """

    target_qubit: str
    probabilities: xr.DataArray
    phis: xr.DataArray
    fits: xr.DataArray
    frequencies: tuple[float, ...]
    durations: tuple[float, ...]
    optimal_index: int
    coords: dict[str, str]


def analyse_cz_calibration(dataset: xr.Dataset, session: "SessionContext") -> Fits:
    """Picks the working point whose CZ shifts the target's phase closest to 180 degrees.

    Args:
        dataset: the coupler's variables, saved in real and imaginary parts.
        session: the session, whose device state holds the discriminators.

    Returns:
        The fits ``cz_pulse_frequency`` and ``cz_pulse_duration`` of that working
        point, ``cz_phase``, the phase it adds, in degrees, and, to plot, the
        ``calibration``.
    """
    data = get_coupler_data(dataset, session)
    coords = _find_coords(data.s21, data.target_qubit)
    frequencies, durations = zip(*data.s21[coords["working_points"]].values)
    probabilities = calculate_probabilities(data.target, session.state).sel(
        {"state": 0}
    )
    # the phase of the target's |0> at each working point, with and without the control
    phis, sine_fits = _fit_phases(
        probabilities,
        data.s21[coords["target_phases"]].values,
        coords["target_phases"],
    )
    distances = get_distances_from_pi(
        phis.sel({coords["control"]: True}), phis.sel({coords["control"]: False})
    )
    optimal_index = distances.argmin().item()
    analysis_result = {
        "cz_pulse_frequency": {"value": frequencies[optimal_index], "error": 0},
        "cz_pulse_duration": {"value": durations[optimal_index], "error": 0},
        "cz_phase": {"value": distances.min().item() + 180, "error": 0},
    }
    calibration = PhaseCalibration(
        target_qubit=data.target_qubit,
        probabilities=probabilities,
        phis=phis,
        fits=sine_fits,
        frequencies=frequencies,
        durations=durations,
        optimal_index=optimal_index,
        coords=coords,
    )
    return {
        **get_fits_from_result(analysis_result, True),
        "calibration": Fit(calibration),
    }


def plot_cz_calibration(fits: Fits) -> list[Figure]:
    """The target's fitted phases at each working point, and their differences.

    Args:
        fits: the coupler's fits.

    Returns:
        The coupler's one figure.
    """
    calibration = fits["calibration"].value
    points = len(calibration.frequencies)
    rows = max(1, int(np.ceil((points + 1) / PLOT_COLUMNS)))
    figure, axes = plt.subplots(
        ncols=PLOT_COLUMNS, nrows=rows, sharex=True, sharey=True, squeeze=False
    )
    for index in range(points):
        _plot_working_point(
            axes[index // PLOT_COLUMNS][index % PLOT_COLUMNS], calibration, index
        )
    figure.text(0.5, 0.04, calibration.coords["target_phases"], ha="center")
    figure.text(
        0.04,
        0.5,
        rf"Target Qubit: {calibration.target_qubit}, $|0\rangle$ probailities",
        va="center",
        rotation="vertical",
    )
    summary_axis = axes[points // PLOT_COLUMNS][points % PLOT_COLUMNS]
    _plot_phase_differences(summary_axis, axes, calibration)
    figure.suptitle(
        "Target Qubit State 0 Probabilities: \n orange: control is ON - black: control is OFF"
    )
    return [figure]


def get_distances_from_pi(phi_on: xr.DataArray, phi_off: xr.DataArray) -> xr.DataArray:
    """How far, in degrees, the phase the control adds is from 180°, a CZ's.

    Args:
        phi_on: the target's phase, in radians, with the control in |1>.
        phi_off: the target's phase, in radians, with the control in |0>.

    Returns:
        The distance from 180°, in degrees, per working point.
    """
    return abs((np.rad2deg(phi_on - phi_off) + 360) % 360 - 180)


def _find_coords(s21: xr.Dataset, target_qubit: str) -> dict[str, str]:
    """The names of the control mode, working points and target's Ramsey phases coordinates."""
    coords = {}
    for coord in s21.coords:
        coord = str(coord)
        if "control_ons" in coord:
            coords["control"] = coord
        elif "working_points" in coord:
            coords["working_points"] = coord
        elif "ramsey_phases" in coord and target_qubit in coord:
            coords["target_phases"] = coord
    return coords


def _fit_phases(
    probabilities: xr.DataArray, target_phases: np.ndarray, phases_coord: str
) -> tuple[xr.DataArray, xr.DataArray]:
    """The phase of a sine fitted to each |0> curve, and the fits over ``phases_coord``."""
    plot_phases = np.linspace(target_phases[0], target_phases[-1], CURVE_POINTS)
    model = SineOscillatingModel()
    model.set_param_hint("phase", min=-360, max=360, vary=True)
    phis, plot_points = xr.apply_ufunc(
        partial(fit_sine_phase, model, x=target_phases, plot_x=plot_phases),
        probabilities,
        input_core_dims=[[phases_coord]],
        output_core_dims=[["phases"], ["plot_points"]],
        vectorize=True,
    )
    plot_points = plot_points.assign_coords({"plot_points": plot_phases})
    return phis, plot_points.rename({"plot_points": phases_coord})


def _plot_working_point(axis: Any, calibration: PhaseCalibration, index: int) -> None:
    """The target's |0> probabilities and sine fits with the control on and off, best point in red."""
    control, phases = calibration.coords["control"], calibration.coords["target_phases"]
    is_optimal = index == calibration.optimal_index
    point = {calibration.coords["working_points"]: index}
    phi_on = calibration.phis.sel({control: True}).isel(point)
    phi_off = calibration.phis.sel({control: False}).isel(point)
    delta_phi = np.rad2deg((phi_off - phi_on).values.item())

    fit_points = calibration.fits.isel(point)
    probabilities = calibration.probabilities.isel(point)
    for is_on, colour in ((True, "orange"), (False, "black")):
        fit_points.sel({control: is_on}).plot(ax=axis, x=phases, color=colour)
    for is_on, colour in ((True, "orange"), (False, "black")):
        probabilities.sel({control: is_on}).plot(
            ax=axis,
            x=phases,
            marker="o",
            color=colour,
            ls="",
            **({} if is_on else {"label": rf"$\Delta\Phi$: {delta_phi:.1f} $^o$"}),
        )
    axis.set_title(
        f"freq: {calibration.frequencies[index]:.3e} "
        f"duration: {calibration.durations[index]:.3e}",
        color="red" if is_optimal else "black",
        fontsize=10,
    )
    axis.legend(facecolor="red" if is_optimal else "white")
    axis.set_xlabel("")
    axis.set_ylabel("")


def _plot_phase_differences(
    axis: Any, axes: np.ndarray, calibration: PhaseCalibration
) -> None:
    """Each working point's phase difference against its frequency, on its own scales."""
    control = calibration.coords["control"]
    phis_on = calibration.phis.sel({control: True})
    phis_off = calibration.phis.sel({control: False})
    for other in axes.ravel():
        axis._shared_axes["x"].remove(other)
        axis._shared_axes["y"].remove(other)
    axis.plot(calibration.frequencies, np.rad2deg((phis_off - phis_on).values), "bo")
