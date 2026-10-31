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
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from cycler import cycler

from tergite_tuner.lib.spec import CouplerAnalysis, Fits, get_fits_from_result
from tergite_tuner.lib.utils.analysis_models import (
    SineOscillatingModel,
    fit_sine_phase,
)
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

CURVE_POINTS = 400

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class CZLocalPhasesCouplerAnalysis(CouplerAnalysis):
    """Finds the dynamic phase a coupler's CZ adds to each of its qubits, from Ramseys with the gate on and off."""

    def __init__(self, dataset: xr.Dataset, session: "SessionContext", **keywords: Any):
        super().__init__(dataset, session, **keywords)
        self.model = SineOscillatingModel()

    def analyse(self) -> Fits | None:
        """Fits each qubit's |1> probability over the Ramsey phases, with the CZ on and off.

        Returns:
            The fits ``cz_dynamic_control`` and ``cz_dynamic_target``: the phase, in
            degrees, the CZ adds to each qubit, negated for ``reverse_phase_qubits``.
        """
        self._find_coords()
        self.control_qubit_probabilities = calculate_probabilities(
            self.control_qubit_data_var, self.session.state
        )
        self.target_qubit_probabilities = calculate_probabilities(
            self.target_qubit_data_var, self.session.state
        )
        self.fit_plot_phases = np.linspace(
            self.target_phases[0], self.target_phases[-1], CURVE_POINTS
        )
        # the target's |1> unswapped, and the control's |1> swapped
        target_phis, self.target_plot_points = self._fit_phases(
            self.target_qubit_probabilities, False, self.target_phases_coord
        )
        control_phis, self.control_swaped_plot_points = self._fit_phases(
            self.control_qubit_probabilities, True, self.control_phases_coord
        )
        self.phase_01 = get_gate_phase(target_phis, self.gate_mode_coord)
        self.phase_10 = get_gate_phase(control_phis, self.gate_mode_coord)

        # FIXME: Work around to be removed in the next version
        reverse_phase_qubits = self.session.reverse_phase_qubits
        self.cz_dynamic_target = self.phase_01
        if self.target_qubit_data_var.qubit in reverse_phase_qubits:
            self.cz_dynamic_target = -self.cz_dynamic_target
        self.cz_dynamic_control = self.phase_10
        if self.control_qubit_data_var.qubit in reverse_phase_qubits:
            self.cz_dynamic_control = -self.cz_dynamic_control

        analysis_result = {
            "cz_dynamic_control": {"value": self.cz_dynamic_control, "error": 0},
            "cz_dynamic_target": {"value": self.cz_dynamic_target, "error": 0},
        }
        return get_fits_from_result(analysis_result, True)

    def _find_coords(self) -> None:
        for coord in self.S21.coords:
            coord = str(coord)
            if "loops" in coord:
                self.loops_coord = coord
            elif "phases" in coord:
                if self.S21[coord].attrs["qubit"] == self.control_qubit:
                    self.control_phases_coord = coord
                elif self.S21[coord].attrs["qubit"] == self.target_qubit:
                    self.target_phases_coord = coord
                    self.target_phases = self.S21[coord].values
            elif "swap" in coord:
                self.swap_coord = coord
            elif "gate" in coord:
                self.gate_mode_coord = coord
            else:
                raise ValueError

    def _fit_phases(
        self, probabilities: xr.DataArray, is_swapped: bool, phases_coord: str
    ) -> tuple[xr.DataArray, xr.DataArray]:
        """The phase of a sine fitted to each |1> curve, and the fits over ``phases_coord``."""
        phis, plot_points = xr.apply_ufunc(
            # over the target's phases, as both qubits sweep the same ones
            partial(
                fit_sine_phase,
                self.model,
                x=self.target_phases,
                plot_x=self.fit_plot_phases,
            ),
            probabilities.sel({"state": 1, self.swap_coord: is_swapped}),
            input_core_dims=[[phases_coord]],
            output_core_dims=[["phases"], ["plot_points"]],
            vectorize=True,
        )
        plot_points = plot_points.assign_coords({"plot_points": self.fit_plot_phases})
        return phis, plot_points.rename({"plot_points": phases_coord})

    def plotter(self, figures_dictionary):
        """Draws each qubit's |1> probabilities, swapped and not, with the fits the phases come from.

        Args:
            figures_dictionary: takes the coupler's figure, under the coupler's name.
        """
        figure, axes = plt.subplots(ncols=2, nrows=2, sharey=True, sharex=True)
        target_probabilities = self.target_qubit_probabilities.sel({"state": 1})
        control_probabilities = self.control_qubit_probabilities.sel({"state": 1})
        self._plot_panel(axes[0][0], control_probabilities, False)
        self._plot_panel(
            axes[0][1],
            target_probabilities,
            False,
            self.target_plot_points,
            rf"$\varphi_{{01}} = {self.phase_01:.1f} ^o$",
        )
        self._plot_panel(
            axes[1][0],
            control_probabilities,
            True,
            self.control_swaped_plot_points,
            rf"$\varphi_{{10}} = {self.phase_10:.1f} ^o$",
        )
        self._plot_panel(axes[1][1], target_probabilities, True)
        figures_dictionary[self.coupler] = [figure]

    def _plot_panel(
        self,
        axis: Any,
        probabilities: xr.DataArray,
        is_swapped: bool,
        fits: xr.DataArray | None = None,
        phase_label: str = "",
    ) -> None:
        """One qubit's |1> probabilities with the gate on and off, and their sine fits if given."""
        axis.set_prop_cycle(cycler("color", ["orange", "black"]))
        probabilities.sel({self.swap_coord: is_swapped}).plot(
            ax=axis, hue=self.gate_mode_coord, marker="o", ls=""
        )
        axis.set_title(f"swap: {is_swapped}")
        if fits is None:
            return
        fits.plot(ax=axis, hue=self.gate_mode_coord)
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
