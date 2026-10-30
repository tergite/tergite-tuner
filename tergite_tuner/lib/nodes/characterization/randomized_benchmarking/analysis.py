# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2026
# (C) Copyright Amr Osman 2024
# (C) Copyright Michele Faucci Giannelli 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
from typing import TYPE_CHECKING, Any

import numpy as np
import xarray as xr

from tergite_tuner.lib.spec import ElementAnalysis, Fit, Fits
from tergite_tuner.lib.utils.analysis_models import ExpDecayModel
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

CURVE_POINTS = 400

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class RandomizedBenchmarkingQubitAnalysis(ElementAnalysis):
    """
    Analysis that fits an exponential decay function to randomized benchmarking data.
    """

    def __init__(self, s21: xr.DataArray, session: "SessionContext"):
        super().__init__(s21, session)
        self.fit_results = {}

    def analyse(self) -> Fits:
        model = ExpDecayModel()
        self._find_coords()
        iq_array = self.S21[self.data_var].assign_attrs(qubit=self.qubit)
        self.state_probabilities = calculate_probabilities(iq_array, self.session.state)
        self.fit_n_cliffords = np.linspace(
            self.number_cliffords.values[0],
            self.number_cliffords.values[-1],
            CURVE_POINTS,
        )

        standard = self.state_probabilities.sel(
            {self.interleave_gate_coord: "Standard"}
        )
        self.standard_p_value, self.standard_fit_y = self._fit_decay(
            model, standard.sel(state=0).mean(self.seed_coord)
        )
        self.leakage, self.fit_y2 = self._fit_leakage(
            model, standard.sel(state=2).mean(self.seed_coord)
        )
        interleaved_p = None
        if self.interleaved_gate is not None:
            interleaved = self.state_probabilities.sel(
                {self.interleave_gate_coord: self.interleaved_gate}
            )
            self.interleaved_p_value, self.interleaved_fit_y = self._fit_decay(
                model, interleaved.sel(state=0).mean(self.seed_coord)
            )
            interleaved_p = self.interleaved_p_value
        self.fidelity = get_rb_fidelity(self.standard_p_value, interleaved_p)
        return {
            "fidelity": Fit(self.fidelity, np.nan),
            "leakage": Fit(self.leakage, np.nan),
            "analysis": Fit(self),
        }

    def _find_coords(self) -> None:
        for coord in self.dataset[self.data_var].coords:
            if "cliffords" in coord:
                self.number_cliffords_coord = coord
                self.number_cliffords = self.S21[coord]
            elif "seed" in coord:
                self.seed_coord = coord
            elif "loops" in str(coord):
                self.loops_coord = coord
            elif "interleave" in str(coord):
                self.interleave_gate_coord = coord
                self.gates = self.S21[coord].values
                self.number_of_gates = self.S21[coord].size
                self.interleaved_gate = None
        if self.number_of_gates == 2:
            self.interleaved_gate = self.gates[1]

    def _fit_decay(
        self, model: ExpDecayModel, mean_0: xr.DataArray
    ) -> tuple[float, np.ndarray]:
        """The decay of |0>'s mean probability: its p, and the fitted curve."""
        cliffords = self.number_cliffords.values
        guess = model.guess(data=mean_0.values, m=cliffords)
        result = model.fit(mean_0.values, params=guess, m=cliffords)
        return result.params["p"].value, self._get_curve(model, result)

    def _fit_leakage(
        self, model: ExpDecayModel, mean_2: xr.DataArray
    ) -> tuple[float, np.ndarray]:
        """The leakage, one less the p of |2>'s rising population, and the fitted curve."""
        guess = model.guess(data=mean_2.values, m=self.number_cliffords)
        # an inverted decay
        guess["A"].value = -1 / 2
        guess["p"].value = 0.998
        result = model.fit(mean_2, params=guess, m=self.number_cliffords)
        return 1 - result.params["p"].value, self._get_curve(model, result)

    def _get_curve(self, model: ExpDecayModel, result: Any) -> np.ndarray:
        return model.eval(
            result.params, **{model.independent_vars[0]: self.fit_n_cliffords}
        )

    def plotter(self, ax):
        standard_probabilities = self.state_probabilities.sel(
            {self.interleave_gate_coord: "Standard"}
        )

        styles = dict(c="b", lw=0.5)
        standard_probabilities.sel(state=0).plot.line(
            ax=ax, x=self.number_cliffords_coord, **styles
        )
        styles = dict(c="r", lw=0.5)
        standard_probabilities.sel(state=1).plot.line(
            ax=ax, x=self.number_cliffords_coord, **styles
        )
        styles = dict(c="g", lw=0.5)
        standard_probabilities.sel(state=2).plot.line(
            ax=ax, x=self.number_cliffords_coord, **styles
        )
        ax.plot(
            self.fit_n_cliffords,
            self.standard_fit_y,
            "b--",
            lw=2,
            label=rf"$p_{{SRB}}$ = {self.standard_p_value:.4f}",
        )
        ax.plot(
            self.fit_n_cliffords,
            self.fit_y2,
            "g--",
            lw=2,
            label=f"leakage = {self.leakage:.4f}",
        )
        if self.interleaved_gate is not None:
            ax.plot(
                self.fit_n_cliffords,
                self.interleaved_fit_y,
                "c--",
                lw=2,
                label=rf"$p_{{IRB}}$ = {self.interleaved_p_value:.4f}",
            )
        ax.set_ylabel("population", fontsize=14)
        ax.set_xlabel("number of cliffords", fontsize=14)
        ax.legend()
        ax.tick_params(axis="both", which="major", labelsize=14)
        ax.set_title("")
        ax.grid()


def get_rb_fidelity(standard_p: float, interleaved_p: float | None) -> float:
    """The standard decay's p, or, interleaved, the gate's fidelity from the two decays."""
    if interleaved_p is None:
        return standard_p
    return 1 - 0.5 * (1 - interleaved_p / standard_p)
