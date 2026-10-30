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

    def __init__(self, dataset: xr.Dataset, session: "SessionContext", **keywords: Any):
        super().__init__(dataset, session, **keywords)
        self.single_model = ExpDecayModel(inverted=False)

    def state_probabilities(self, c_qubit_state: int, t_qubit_state: int):
        c_state_probs = self.control_qubit_probabilities.sel({"state": c_qubit_state})
        t_state_probs = self.target_qubit_probabilities.sel({"state": t_qubit_state})
        return c_state_probs * t_state_probs

    def analyse(self) -> Fits | None:
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

        fig, axs = plt.subplots(ncols=2)

        computational_space_dimension = 4

        standard_probs_00 = self.P00.sel({self.interleave_modes_coord: False})

        comp_space_probs = self.P00 + self.P01 + self.P10 + self.P11

        # Standard exponential plots
        ############################
        title = ""
        axs[0].plot(
            self.fit_n_cliffords,
            self.standard.curve_00,
            color="red",
            lw=3,
            label=rf"$p_{{SRB}}$: {self.standard.p:.3f}",
        )
        styles = {"hue": self.seed_coord, "alpha": 0.2}
        standard_probs_00.plot(ax=axs[0], x=self.number_cliffords_coord, **styles)

        standard_probs_chi_1 = comp_space_probs.sel(
            {self.interleave_modes_coord: False}
        )
        standard_probs_reduced_ideal = (
            standard_probs_00 - standard_probs_chi_1 / computational_space_dimension
        )
        interleaved_probs_00 = self.P00.sel({self.interleave_modes_coord: False})
        interleaved_probs_chi_1 = comp_space_probs.sel(
            {self.interleave_modes_coord: False}
        )
        interleaved_probs_reduced_ideal = (
            interleaved_probs_00
            - interleaved_probs_chi_1 / computational_space_dimension
        )
        if True in self.interleave_modes:
            interleaved_probs_00 = self.P00.sel({self.interleave_modes_coord: True})
            interleaved_probs_00.plot(
                ax=axs[0],
                x=self.number_cliffords_coord,
                hue=self.seed_coord,
                alpha=0.2,
                ls=":",
            )
            axs[0].plot(
                self.fit_n_cliffords,
                self.interleaved.curve_00,
                color="magenta",
                lw=3,
                label=f"$p_{{IRB}}$: {self.interleaved.p:.3f}",
            )
            # fidelity based on simple exponential fits
            title = rf"CZ fidelity = {self.cz_fidelity:.3f}"
        axs[0].set_ylabel(r"State |00$\rangle$ probability")
        axs[0].axhline(0.25, color="black")
        axs[0].legend()
        axs[0].set_title(title)
        ############################

        # Leakage RB plots from Nakamura's paper
        ########################################
        styles = {"hue": self.seed_coord, "alpha": 0.2}
        standard_probs_chi_1.plot(ax=axs[1], x=self.number_cliffords_coord, **styles)
        standard_probs_reduced_ideal.plot(
            ax=axs[1], x=self.number_cliffords_coord, **styles
        )
        interleaved_probs_chi_1.plot(ax=axs[1], x=self.number_cliffords_coord, **styles)
        interleaved_probs_reduced_ideal.plot(
            ax=axs[1], x=self.number_cliffords_coord, **styles
        )

        lambda_standard_str = rf"$\lambda_L^{{SRB}}$: {self.standard.lambda_L:.3f}"
        A_standard_str = rf"$A_M^{{SRB}}$: {self.standard.AM:.3f}"
        L1_standard = (1 - self.standard.lambda_L) * (1 - self.standard.AM)
        L2_standard = (1 - self.standard.lambda_L) * self.standard.AM
        L1_standard_str = rf"$L1^{{SRB}}$: {L1_standard:.3f}"
        L2_standard_str = rf"$L2^{{SRB}}$: {L2_standard:.3f}"
        standard_label = (
            lambda_standard_str
            + " "
            + A_standard_str
            + "\n"
            + L1_standard_str
            + " "
            + L2_standard_str,
        )
        lambda_interleaved_str = (
            rf"$\lambda_L^{{IRB}}$: {self.interleaved.lambda_L:.3f}"
        )
        A_interleaved_str = rf"$A_M^{{IRB}}$: {self.interleaved.AM:.3f}"
        L1_interleaved = (1 - self.interleaved.lambda_L) * (1 - self.interleaved.AM)
        L2_interleaved = (1 - self.interleaved.lambda_L) * self.interleaved.AM
        L1_interleaved_str = rf"$L1^{{IRB}}$: {L1_interleaved:.3f}"
        L2_interleaved_str = rf"$L2^{{IRB}}$: {L2_interleaved:.3f}"
        interleaved_label = (
            lambda_interleaved_str
            + " "
            + A_interleaved_str
            + "\n"
            + L1_interleaved_str
            + " "
            + L2_interleaved_str,
        )

        axs[1].plot(
            self.fit_n_cliffords,
            self.standard.curve_chi_1,
            color="teal",
            lw=3,
            label=standard_label,
        )
        axs[1].plot(
            self.fit_n_cliffords,
            self.interleaved.curve_chi_1,
            color="orange",
            lw=3,
            label=interleaved_label,
        )
        axs[1].plot(
            self.fit_n_cliffords,
            self.standard.curve_ideal,
            color="orchid",
            lw=3,
            label=rf"$\lambda_r^{{SRB}}$: {self.standard.lambda_r:.4f}",
        )
        axs[1].plot(
            self.fit_n_cliffords,
            self.interleaved.curve_ideal,
            color="aqua",
            lw=3,
            label=rf"$\lambda_r^{{SRB}}$: {self.interleaved.lambda_r:.3f}",
        )
        axs[1].legend()
        axs[1].set_title(
            f"CZ fidelity (Nakamura paper): {self.average_fidelity_nakamura:0.3f}"
        )

        figures_dictionary[self.coupler] = [fig]


def get_cz_fidelities(
    standard: DecayFits, interleaved: DecayFits | None
) -> tuple[float, float]:
    """The CZ's fidelity from the |00> decays' ratio, and Nakamura's from the leakage and reduced ideal decays.

    NaN without interleaved sequences, or for a standard decay fitted to zero.
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


def _get_ratio(numerator: float, denominator: float) -> float:
    """``numerator / denominator``, or NaN for a standard decay fitted to zero."""
    return numerator / denominator if denominator else np.nan
