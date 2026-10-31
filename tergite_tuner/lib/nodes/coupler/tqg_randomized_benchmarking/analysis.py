# This code is part of Tergite
#
# (C) Copyright Amr Osman 2024
# (C) Copyright Eleftherios Moschandreou 2025, 2026
# (C) Copyright Chalmers Next Labs 2025, 2026
# (C) Copyright Pontus Vikstål 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import TYPE_CHECKING, Any, NamedTuple

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from tergite_tuner.lib.spec import CouplerAnalysis, Fits, get_fits_from_result
from tergite_tuner.lib.utils.analysis_models import ExpDecayModel
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

COMPUTATIONAL_SPACE_DIMENSION = 4
CURVE_POINTS = 200


class DecayFits(NamedTuple):
    """One mode's three decays (Nakamura's eqs. K14, K15): the decay parameters, and each fitted curve."""

    p: float
    lambda_L: float
    AM: float
    lambda_r: float
    curve_00: np.ndarray
    curve_chi_1: np.ndarray
    curve_ideal: np.ndarray


class CZRBCouplerAnalysis(CouplerAnalysis):
    """Finds a coupler's CZ fidelity from two-qubit randomized benchmarking, standard and interleaved."""

    def __init__(self, dataset: xr.Dataset, session: "SessionContext", **keywords: Any):
        super().__init__(dataset, session, **keywords)
        self.single_model = ExpDecayModel(inverted=False)

    def state_probabilities(self, c_qubit_state: int, t_qubit_state: int):
        """The probability of a two-qubit state, as the product of each qubit's.

        Args:
            c_qubit_state: the control's state.
            t_qubit_state: the target's state.

        Returns:
            The state's probability over the Clifford counts, seeds and modes.
        """
        c_state_probs = self.control_qubit_probabilities.sel({"state": c_qubit_state})
        t_state_probs = self.target_qubit_probabilities.sel({"state": t_qubit_state})
        return c_state_probs * t_state_probs

    def analyse(self) -> Fits | None:
        """Fits the decays of |00> and of the computational subspace over the number of Cliffords.

        Returns:
            The fit ``cz_fidelity``, marked ``failed`` if it, or Nakamura's fidelity,
            is not finite, as without interleaved sequences.
        """
        self._find_coords()
        self.control_qubit_probabilities = calculate_probabilities(
            self.control_qubit_data_var, self.session.state
        )
        self.target_qubit_probabilities = calculate_probabilities(
            self.target_qubit_data_var, self.session.state
        )
        self.P00 = self.state_probabilities(0, 0)
        self.P01 = self.state_probabilities(0, 1)
        self.P10 = self.state_probabilities(1, 0)
        self.P11 = self.state_probabilities(1, 1)

        mean_00 = self.P00.mean(self.seed_coord)
        # the probability of staying in the computational subspace
        mean_chi_1 = sum(
            probabilities.mean(self.seed_coord)
            for probabilities in (self.P00, self.P01, self.P10, self.P11)
        )
        self.fit_n_cliffords = np.linspace(
            self.number_cliffords[0], self.number_cliffords[-1], CURVE_POINTS
        )
        self.standard = self._fit_decays(mean_00, mean_chi_1, is_interleaved=False)
        self.interleaved = None
        if True in self.interleave_modes:
            self.interleaved = self._fit_decays(
                mean_00, mean_chi_1, is_interleaved=True
            )

        self.cz_fidelity, self.average_fidelity_nakamura = get_cz_fidelities(
            self.standard, self.interleaved
        )
        analysis_succesful = bool(
            np.isfinite([self.cz_fidelity, self.average_fidelity_nakamura]).all()
        )
        analysis_result = {"cz_fidelity": {"value": self.cz_fidelity, "error": 0}}
        return get_fits_from_result(analysis_result, analysis_succesful)

    def _find_coords(self) -> None:
        for coord in self.S21.coords:
            coord = str(coord)
            if "cliffords" in coord:
                self.number_cliffords_coord = coord
                self.number_cliffords = self.S21[coord].values
            elif "seed" in coord:
                self.seed_coord = coord
            elif "loops" in coord:
                self.loops_coord = coord
            elif "interleave" in coord:
                self.interleave_modes_coord = coord
                self.interleave_modes = self.S21[coord].values
            else:
                raise ValueError

    def _fit_decays(
        self, mean_00: xr.DataArray, mean_chi_1: xr.DataArray, is_interleaved: bool
    ) -> DecayFits:
        """The decays of |00>, of the computational subspace and of the reduced ideal probability, in one mode."""
        mode = {self.interleave_modes_coord: is_interleaved}
        mean_00 = mean_00.sel(mode)
        mean_chi_1 = mean_chi_1.sel(mode)
        reduced_ideal = mean_00 - mean_chi_1 / COMPUTATIONAL_SPACE_DIMENSION
        results = [
            self._fit_decay(data) for data in (mean_00, mean_chi_1, reduced_ideal)
        ]
        fit_00, fit_chi_1, fit_ideal = results
        return DecayFits(
            p=fit_00.params["p"].value,
            lambda_L=fit_chi_1.params["p"].value,
            AM=fit_chi_1.params["A"].value,
            lambda_r=fit_ideal.params["p"].value,
            curve_00=self._get_curve(fit_00),
            curve_chi_1=self._get_curve(fit_chi_1),
            curve_ideal=self._get_curve(fit_ideal),
        )

    def _fit_decay(self, data: xr.DataArray) -> Any:
        guess = self.single_model.guess(data=data.values, m=self.number_cliffords)
        return self.single_model.fit(data.values, params=guess, m=self.number_cliffords)

    def _get_curve(self, result: Any) -> np.ndarray:
        return self.single_model.eval(result.params, m=self.fit_n_cliffords)

    def plotter(self, figures_dictionary):
        """Draws the |00> decays, and the leakage and reduced ideal decays.

        Args:
            figures_dictionary: takes the coupler's figure, under the coupler's name.
        """
        figure, (decay_axis, leakage_axis) = plt.subplots(ncols=2)
        self._plot_decays(decay_axis)
        self._plot_leakage(leakage_axis)
        figures_dictionary[self.coupler] = [figure]

    def _plot_decays(self, axis: Any) -> None:
        """Each seed's |00> probability and its fitted decay, interleaved dotted."""
        styles = {
            "x": self.number_cliffords_coord,
            "hue": self.seed_coord,
            "alpha": 0.2,
        }
        axis.plot(
            self.fit_n_cliffords,
            self.standard.curve_00,
            color="red",
            lw=3,
            label=rf"$p_{{SRB}}$: {self.standard.p:.3f}",
        )
        self.P00.sel({self.interleave_modes_coord: False}).plot(ax=axis, **styles)
        title = ""
        if self.interleaved is not None:
            self.P00.sel({self.interleave_modes_coord: True}).plot(
                ax=axis, ls=":", **styles
            )
            axis.plot(
                self.fit_n_cliffords,
                self.interleaved.curve_00,
                color="magenta",
                lw=3,
                label=f"$p_{{IRB}}$: {self.interleaved.p:.3f}",
            )
            title = rf"CZ fidelity = {self.cz_fidelity:.3f}"
        axis.set_ylabel(r"State |00$\rangle$ probability")
        axis.axhline(0.25, color="black")
        axis.legend()
        axis.set_title(title)

    def _plot_leakage(self, axis: Any) -> None:
        """Each seed's computational-subspace and reduced ideal probabilities, and Nakamura's fitted decays."""
        styles = {
            "x": self.number_cliffords_coord,
            "hue": self.seed_coord,
            "alpha": 0.2,
        }
        chi_1 = self.P00 + self.P01 + self.P10 + self.P11
        modes = [(False, self.standard, "SRB", "teal", "orchid")]
        if self.interleaved is not None:
            modes.append((True, self.interleaved, "IRB", "orange", "aqua"))
        for is_interleaved, *_ in modes:
            mode = {self.interleave_modes_coord: is_interleaved}
            chi_1.sel(mode).plot(ax=axis, **styles)
            reduced_ideal = (
                self.P00.sel(mode) - chi_1.sel(mode) / COMPUTATIONAL_SPACE_DIMENSION
            )
            reduced_ideal.plot(ax=axis, **styles)
        for _, decays, name, chi_1_colour, _ in modes:
            axis.plot(
                self.fit_n_cliffords,
                decays.curve_chi_1,
                color=chi_1_colour,
                lw=3,
                label=_get_leakage_label(decays, name),
            )
        for _, decays, name, _, ideal_colour in modes:
            axis.plot(
                self.fit_n_cliffords,
                decays.curve_ideal,
                color=ideal_colour,
                lw=3,
                label=rf"$\lambda_r^{{{name}}}$: {decays.lambda_r:.4f}",
            )
        axis.legend()
        axis.set_title(
            f"CZ fidelity (Nakamura paper): {self.average_fidelity_nakamura:0.3f}"
        )


def get_cz_fidelities(
    standard: DecayFits, interleaved: DecayFits | None
) -> tuple[float, float]:
    """The CZ's fidelity from the |00> decays' ratio, and Nakamura's from the leakage and reduced ideal decays.

    NaN without interleaved sequences, or for a standard decay fitted to zero.

    Args:
        standard: the decays of the standard sequences.
        interleaved: the decays of the sequences interleaved with the CZ, if measured.

    Returns:
        The CZ's fidelity, and Nakamura's.
    """
    if interleaved is None:
        return np.nan, np.nan
    l1_standard = (1 - standard.lambda_L) * (1 - standard.AM)
    l1_interleaved = (1 - interleaved.lambda_L) * (1 - interleaved.AM)
    one_minus_l1 = _get_ratio(1 - l1_interleaved, 1 - l1_standard)
    lambda_r = _get_ratio(interleaved.lambda_r, standard.lambda_r)
    return (
        0.25 + 0.75 * _get_ratio(interleaved.p, standard.p),
        3 / 4 * lambda_r + one_minus_l1 / 4,
    )


def _get_leakage_label(decays: DecayFits, name: str) -> str:
    """The leakage decay's lambda_L and A_M, and the leakage L1 and seepage L2 they give."""
    l1 = (1 - decays.lambda_L) * (1 - decays.AM)
    l2 = (1 - decays.lambda_L) * decays.AM
    return (
        rf"$\lambda_L^{{{name}}}$: {decays.lambda_L:.3f} $A_M^{{{name}}}$: {decays.AM:.3f}"
        "\n"
        rf"$L1^{{{name}}}$: {l1:.3f} $L2^{{{name}}}$: {l2:.3f}"
    )


def _get_ratio(numerator: float, denominator: float) -> float:
    """``numerator / denominator``, or NaN for a standard decay fitted to zero."""
    return numerator / denominator if denominator else np.nan
