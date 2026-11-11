# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Chalmers Next Labs 2024, 2025, 2026
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
from cycler import cycler
from matplotlib.figure import Figure

from tergite_tuner.lib.spec import (
    CouplerData,
    Fit,
    Fits,
    get_coupler_data,
    get_fits_from_result,
)
from tergite_tuner.lib.utils.analysis_models import (
    SineOscillatingModel,
    fit_sine_phase,
)
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

CURVE_POINTS = 400

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class LocalPhases(NamedTuple):
    """Both qubits' |1> probabilities, and the sine fits the gate's phases come from, to plot.

    Attributes:
        control: the control's |1> probability over its phases, swapped and not, with
            the gate on and off.
        target: the target's, likewise.
        control_fits: the fits to the control's swapped probabilities.
        target_fits: the fits to the target's unswapped probabilities.
        phase_01: the phase, in degrees, the gate adds to the target.
        phase_10: the phase, in degrees, the gate adds to the control.
    """

    control: xr.DataArray
    target: xr.DataArray
    control_fits: xr.DataArray
    target_fits: xr.DataArray
    phase_01: float
    phase_10: float


def analyse_cz_local_phases(dataset: xr.Dataset, session: "SessionContext") -> Fits:
    """Fits each qubit's |1> probability over the Ramsey phases, with the CZ on and off.

    Args:
        dataset: the coupler's variables, saved in real and imaginary parts.
        session: the session, whose device state holds the discriminators.

    Returns:
        The fits ``cz_dynamic_control`` and ``cz_dynamic_target``: the phase, in
        degrees, the CZ adds to each qubit, negated for ``reverse_phase_qubits``;
        and, to plot, the ``phases``.

    Raises:
        ValueError: if the dataset has a coordinate other than the loops, the
            phases, the swap and the gate mode.
    """
    data = get_coupler_data(dataset, session)
    coords = _find_coords(data)
    phases = _fit_gate_phases(
        calculate_probabilities(data.control, session.state),
        calculate_probabilities(data.target, session.state),
        coords,
        data.s21[coords["target_phases"]].values,
    )
    # FIXME: Work around to be removed in the next version
    reverse_phase_qubits = session.reverse_phase_qubits
    cz_dynamic_target = phases.phase_01
    if data.target_qubit in reverse_phase_qubits:
        cz_dynamic_target = -cz_dynamic_target
    cz_dynamic_control = phases.phase_10
    if data.control_qubit in reverse_phase_qubits:
        cz_dynamic_control = -cz_dynamic_control
    analysis_result = {
        "cz_dynamic_control": {"value": cz_dynamic_control, "error": 0},
        "cz_dynamic_target": {"value": cz_dynamic_target, "error": 0},
    }
    return {**get_fits_from_result(analysis_result, True), "phases": Fit(phases)}


def plot_cz_local_phases(fits: Fits) -> list[Figure]:
    """Each qubit's |1> probabilities, swapped and not, with the fits the phases come from.

    Args:
        fits: the coupler's fits.

    Returns:
        The coupler's one figure.
    """
    phases = fits["phases"].value
    figure, axes = plt.subplots(ncols=2, nrows=2, sharey=True, sharex=True)
    _plot_panel(axes[0][0], phases.control, False)
    _plot_panel(
        axes[0][1],
        phases.target,
        False,
        phases.target_fits,
        rf"$\varphi_{{01}} = {phases.phase_01:.1f} ^o$",
    )
    _plot_panel(
        axes[1][0],
        phases.control,
        True,
        phases.control_fits,
        rf"$\varphi_{{10}} = {phases.phase_10:.1f} ^o$",
    )
    _plot_panel(axes[1][1], phases.target, True)
    return [figure]


def get_gate_phase(phis: xr.DataArray, gate_mode_coord: str) -> float:
    """The phase, in degrees, the gate adds: the fitted phase with it less the phase without.

    Args:
        phis: the fitted phases, in radians, with the gate on and off.
        gate_mode_coord: the coordinate saying whether the gate is on.

    Returns:
        The gate's phase, in degrees.
    """
    on = phis.sel({gate_mode_coord: True})
    off = phis.sel({gate_mode_coord: False})
    return np.rad2deg((on - off).item())


def _find_coords(data: CouplerData) -> dict[str, str]:
    """The names of the loops, each qubit's phases, the swap and the gate mode coordinates."""
    coords = {}
    for coord in data.s21.coords:
        coord = str(coord)
        if "loops" in coord:
            coords["loops"] = coord
        elif "phases" in coord:
            if data.s21[coord].attrs["qubit"] == data.control_qubit:
                coords["control_phases"] = coord
            elif data.s21[coord].attrs["qubit"] == data.target_qubit:
                coords["target_phases"] = coord
        elif "swap" in coord:
            coords["swap"] = coord
        elif "gate" in coord:
            coords["gate"] = coord
        else:
            raise ValueError(f"Unexpected coordinate: {coord}")
    return coords


def _fit_gate_phases(
    control: xr.DataArray,
    target: xr.DataArray,
    coords: dict[str, str],
    target_phases: np.ndarray,
) -> LocalPhases:
    """The phase the gate adds to each qubit, from sines fitted to the target's |1> unswapped and the control's swapped."""
    plot_phases = np.linspace(target_phases[0], target_phases[-1], CURVE_POINTS)
    model = SineOscillatingModel()
    target_phis, target_fits = _fit_phases(
        model,
        target,
        False,
        coords["target_phases"],
        coords,
        target_phases,
        plot_phases,
    )
    control_phis, control_fits = _fit_phases(
        model,
        control,
        True,
        coords["control_phases"],
        coords,
        target_phases,
        plot_phases,
    )
    return LocalPhases(
        control.sel({"state": 1}),
        target.sel({"state": 1}),
        control_fits,
        target_fits,
        get_gate_phase(target_phis, coords["gate"]),
        get_gate_phase(control_phis, coords["gate"]),
    )


def _fit_phases(
    model: SineOscillatingModel,
    probabilities: xr.DataArray,
    is_swapped: bool,
    phases_coord: str,
    coords: dict[str, str],
    target_phases: np.ndarray,
    plot_phases: np.ndarray,
) -> tuple[xr.DataArray, xr.DataArray]:
    """The phase of a sine fitted to each |1> curve, and the fits over ``phases_coord``."""
    phis, plot_points = xr.apply_ufunc(
        # over the target's phases, as both qubits sweep the same ones
        partial(fit_sine_phase, model, x=target_phases, plot_x=plot_phases),
        probabilities.sel({"state": 1, coords["swap"]: is_swapped}),
        input_core_dims=[[phases_coord]],
        output_core_dims=[["phases"], ["plot_points"]],
        vectorize=True,
    )
    plot_points = plot_points.assign_coords({"plot_points": plot_phases})
    return phis, plot_points.rename({"plot_points": phases_coord})


def _plot_panel(
    axis: Any,
    probabilities: xr.DataArray,
    is_swapped: bool,
    fits: xr.DataArray | None = None,
    phase_label: str = "",
) -> None:
    """One qubit's |1> probabilities with the gate on and off, and their sine fits if given."""
    swap_coord = _find_coord(probabilities, "swap")
    gate_coord = _find_coord(probabilities, "gate")
    axis.set_prop_cycle(cycler("color", ["orange", "black"]))
    probabilities.sel({swap_coord: is_swapped}).plot(
        ax=axis, hue=gate_coord, marker="o", ls=""
    )
    axis.set_title(f"swap: {is_swapped}")
    if fits is None:
        return
    fits.plot(ax=axis, hue=gate_coord)
    axis.text(
        0,
        0,
        phase_label,
        bbox={"facecolor": "white", "alpha": 0.5, "linewidth": 0},
        size=16,
        color="red",
        backgroundcolor="white",
    )
    axis.get_legend().remove()


def _find_coord(array: xr.DataArray, part: str) -> str:
    return next(str(coord) for coord in array.coords if part in str(coord))
