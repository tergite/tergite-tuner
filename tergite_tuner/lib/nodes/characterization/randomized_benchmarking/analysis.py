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
from typing import TYPE_CHECKING, Any, NamedTuple

import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits
from tergite_tuner.lib.utils.analysis_models import ExpDecayModel
from tergite_tuner.lib.utils.classification_functions import calculate_probabilities

CURVE_POINTS = 400

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class DecayCurves(NamedTuple):
    """The fitted decays, evaluated to plot.

    Attributes:
        cliffords: the numbers of Cliffords the curves are evaluated at.
        standard: the |0> population's decay without an interleaved gate.
        leakage: the |2> population's rise.
        interleaved: the |0> population's decay with the gate interleaved, or None
            if there is none.
    """

    cliffords: np.ndarray
    standard: np.ndarray
    leakage: np.ndarray
    interleaved: np.ndarray | None


def analyse_randomized_benchmarking(
    s21: xr.DataArray, session: "SessionContext"
) -> Fits:
    """Fits the decay of the |0> population, averaged over the seeds, against the number of Cliffords.

    The shots are classified into |0>, |1> and |2> with the qubit's stored
    discriminator. Interleaved, the fidelity is the interleaved gate's.

    Args:
        s21: the qubit's shots over interleaved gate, seed, number of Cliffords and loop.
        session: the session, whose device state holds the discriminator.

    Returns:
        ``fidelity``, the decay's p or the interleaved gate's fidelity, ``leakage``,
        from the rise of |2>, and, to plot, the ``probabilities`` without an
        interleaved gate, ``standard_p``, ``interleaved_p`` and the ``curves``.
    """
    gate_coord = _find_coord(s21, "interleave")
    gates = s21[gate_coord].values
    probabilities = calculate_probabilities(s21, session.state)
    standard = probabilities.sel({gate_coord: "Standard"})
    interleaved = probabilities.sel({gate_coord: gates[1]}) if gates.size == 2 else None
    standard_p, interleaved_p, leakage, curves = _fit_decays(
        standard,
        interleaved,
        s21[_find_coord(s21, "cliffords")],
        _find_coord(s21, "seed"),
    )
    return {
        "fidelity": Fit(get_rb_fidelity(standard_p, interleaved_p), np.nan),
        "leakage": Fit(leakage, np.nan),
        "probabilities": Fit(standard),
        "standard_p": Fit(standard_p),
        "interleaved_p": Fit(interleaved_p),
        "curves": Fit(curves),
    }


def plot_randomized_benchmarking(
    axis: Axes, _s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """Draws each state's population against the number of Cliffords, and the fitted decays.

    Args:
        axis: the axis to draw on.
        _s21: unused; part of the ``plot`` signature.
        fits: the qubit's fits; nothing is drawn if empty.
        _session: unused; part of the ``plot`` signature.
    """
    if not fits:
        return
    probabilities = fits["probabilities"].value
    cliffords_coord = _find_coord(probabilities, "cliffords")
    for state, colour in ((0, "b"), (1, "r"), (2, "g")):
        probabilities.sel(state=state).plot.line(
            ax=axis, x=cliffords_coord, c=colour, lw=0.5
        )
    curves = fits["curves"].value
    standard_p = fits["standard_p"].value
    axis.plot(
        curves.cliffords,
        curves.standard,
        "b--",
        lw=2,
        label=rf"$p_{{SRB}}$ = {standard_p:.4f}",
    )
    axis.plot(
        curves.cliffords,
        curves.leakage,
        "g--",
        lw=2,
        label=f"leakage = {fits['leakage'].value:.4f}",
    )
    if curves.interleaved is not None:
        axis.plot(
            curves.cliffords,
            curves.interleaved,
            "c--",
            lw=2,
            label=rf"$p_{{IRB}}$ = {fits['interleaved_p'].value:.4f}",
        )
    axis.set_ylabel("population", fontsize=14)
    axis.set_xlabel("number of cliffords", fontsize=14)
    axis.legend()
    axis.tick_params(axis="both", which="major", labelsize=14)
    axis.set_title("")
    axis.grid()


def get_rb_fidelity(standard_p: float, interleaved_p: float | None) -> float:
    """The standard decay's p, or, interleaved, the gate's fidelity from the two decays.

    Args:
        standard_p: the p of the decay without an interleaved gate.
        interleaved_p: the p of the decay with the gate interleaved, or None if
            there is none.

    Returns:
        The fidelity.
    """
    if interleaved_p is None:
        return standard_p
    return 1 - 0.5 * (1 - interleaved_p / standard_p)


def _find_coord(array: xr.DataArray, part: str) -> str:
    """The array's coordinate whose name holds ``part``; recorded datasets differ in the suffix."""
    return next(str(coord) for coord in array.coords if part in str(coord))


def _fit_decays(
    standard: xr.DataArray,
    interleaved: xr.DataArray | None,
    cliffords: xr.DataArray,
    seed_coord: str,
) -> tuple[float, float | None, float, DecayCurves]:
    """The p of |0>'s decay without and with the interleaved gate, the leakage, and their curves."""
    model = ExpDecayModel()
    curve_cliffords = np.linspace(
        cliffords.values[0], cliffords.values[-1], CURVE_POINTS
    )
    standard_p, standard_curve = _fit_decay(
        model, standard.sel(state=0).mean(seed_coord), cliffords, curve_cliffords
    )
    leakage, leakage_curve = _fit_leakage(
        model, standard.sel(state=2).mean(seed_coord), cliffords, curve_cliffords
    )
    interleaved_p, interleaved_curve = None, None
    if interleaved is not None:
        interleaved_p, interleaved_curve = _fit_decay(
            model,
            interleaved.sel(state=0).mean(seed_coord),
            cliffords,
            curve_cliffords,
        )
    curves = DecayCurves(
        curve_cliffords, standard_curve, leakage_curve, interleaved_curve
    )
    return standard_p, interleaved_p, leakage, curves


def _fit_decay(
    model: ExpDecayModel,
    mean_0: xr.DataArray,
    cliffords: xr.DataArray,
    curve_cliffords: np.ndarray,
) -> tuple[float, np.ndarray]:
    """The decay of |0>'s mean probability: its p, and the fitted curve."""
    guess = model.guess(data=mean_0.values, m=cliffords.values)
    result = model.fit(mean_0.values, params=guess, m=cliffords.values)
    return result.params["p"].value, _get_curve(model, result, curve_cliffords)


def _fit_leakage(
    model: ExpDecayModel,
    mean_2: xr.DataArray,
    cliffords: xr.DataArray,
    curve_cliffords: np.ndarray,
) -> tuple[float, np.ndarray]:
    """The leakage, one less the p of |2>'s rising population, and the fitted curve."""
    guess = model.guess(data=mean_2.values, m=cliffords)
    # an inverted decay
    guess["A"].value = -1 / 2
    guess["p"].value = 0.998
    result = model.fit(mean_2, params=guess, m=cliffords)
    return 1 - result.params["p"].value, _get_curve(model, result, curve_cliffords)


def _get_curve(
    model: ExpDecayModel, result: Any, curve_cliffords: np.ndarray
) -> np.ndarray:
    return model.eval(result.params, **{model.independent_vars[0]: curve_cliffords})
