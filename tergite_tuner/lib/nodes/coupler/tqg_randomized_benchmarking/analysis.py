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
from matplotlib.figure import Figure

from tergite_tuner.lib.spec import Fit, Fits, get_coupler_data, get_fits_from_result
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


class TwoQubitDecays(NamedTuple):
    """The two-qubit populations and their fitted decays, to plot.

    Attributes:
        p00: the probability of |00> per number of Cliffords, seed and mode.
        chi_1: the probability of staying in the computational subspace, likewise.
        curve_cliffords: the numbers of Cliffords the curves are evaluated at.
        standard: the decays of the standard sequences.
        interleaved: the decays of the sequences interleaved with the CZ, if measured.
        nakamura_fidelity: the CZ's fidelity from the leakage and reduced ideal decays.
        coords: the names of the ``cliffords``, ``seed`` and ``interleave``
            coordinates.
    """

    p00: xr.DataArray
    chi_1: xr.DataArray
    curve_cliffords: np.ndarray
    standard: DecayFits
    interleaved: DecayFits | None
    nakamura_fidelity: float
    coords: dict[str, str]


def analyse_cz_rb(dataset: xr.Dataset, session: "SessionContext") -> Fits:
    """Fits the decays of |00> and of the computational subspace over the number of Cliffords.

    Args:
        dataset: the coupler's variables, saved in real and imaginary parts.
        session: the session, whose device state holds the discriminators.

    Returns:
        The fit ``cz_fidelity``, marked ``failed`` if it, or Nakamura's fidelity,
        is not finite, as without interleaved sequences, and, to plot, the
        ``decays``.

    Raises:
        ValueError: if the dataset has a coordinate other than the Cliffords, the
            seeds, the loops and the interleave modes.
    """
    data = get_coupler_data(dataset, session)
    coords = _find_coords(data.s21)
    control = calculate_probabilities(data.control, session.state)
    target = calculate_probabilities(data.target, session.state)
    populations = [
        control.sel({"state": control_state}) * target.sel({"state": target_state})
        for control_state, target_state in ((0, 0), (0, 1), (1, 0), (1, 1))
    ]
    cliffords = data.s21[coords["cliffords"]].values
    standard, interleaved = _fit_modes(
        populations,
        cliffords,
        coords,
        is_interleaved=True in data.s21[coords["interleave"]].values,
    )
    cz_fidelity, nakamura_fidelity = get_cz_fidelities(standard, interleaved)
    is_successful = bool(np.isfinite([cz_fidelity, nakamura_fidelity]).all())
    decays = TwoQubitDecays(
        p00=populations[0],
        chi_1=populations[0] + populations[1] + populations[2] + populations[3],
        curve_cliffords=np.linspace(cliffords[0], cliffords[-1], CURVE_POINTS),
        standard=standard,
        interleaved=interleaved,
        nakamura_fidelity=nakamura_fidelity,
        coords=coords,
    )
    analysis_result = {"cz_fidelity": {"value": cz_fidelity, "error": 0}}
    return {
        **get_fits_from_result(analysis_result, is_successful),
        "decays": Fit(decays),
    }


def plot_cz_rb(fits: Fits) -> list[Figure]:
    """The |00> decays, and the leakage and reduced ideal decays.

    Args:
        fits: the coupler's fits.

    Returns:
        The coupler's one figure.
    """
    decays = fits["decays"].value
    figure, (decay_axis, leakage_axis) = plt.subplots(ncols=2)
    _plot_decays(decay_axis, decays, fits["cz_fidelity"].value)
    _plot_leakage(leakage_axis, decays)
    return [figure]


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


def _find_coords(s21: xr.Dataset) -> dict[str, str]:
    """The names of the Cliffords, seed, loops and interleave mode coordinates.

    Raises:
        ValueError: if the dataset has any other coordinate.
    """
    coords = {}
    for coord in s21.coords:
        coord = str(coord)
        for part in ("cliffords", "seed", "loops", "interleave"):
            if part in coord:
                coords[part] = coord
                break
        else:
            raise ValueError(f"Unexpected coordinate: {coord}")
    return coords


def _fit_modes(
    populations: list[xr.DataArray],
    cliffords: np.ndarray,
    coords: dict[str, str],
    is_interleaved: bool,
) -> tuple[DecayFits, DecayFits | None]:
    """The standard sequences' decays, and the interleaved ones' if measured."""
    model = ExpDecayModel(inverted=False)
    curve_cliffords = np.linspace(cliffords[0], cliffords[-1], CURVE_POINTS)
    mean_00 = populations[0].mean(coords["seed"])
    # the probability of staying in the computational subspace
    mean_chi_1 = sum(population.mean(coords["seed"]) for population in populations)
    modes = (False, True) if is_interleaved else (False,)
    fitted = [
        _fit_decays(
            model,
            mean_00.sel({coords["interleave"]: mode}),
            mean_chi_1.sel({coords["interleave"]: mode}),
            cliffords,
            curve_cliffords,
        )
        for mode in modes
    ]
    return fitted[0], fitted[1] if is_interleaved else None


def _fit_decays(
    model: ExpDecayModel,
    mean_00: xr.DataArray,
    mean_chi_1: xr.DataArray,
    cliffords: np.ndarray,
    curve_cliffords: np.ndarray,
) -> DecayFits:
    """The decays of |00>, of the computational subspace and of the reduced ideal probability, in one mode."""
    reduced_ideal = mean_00 - mean_chi_1 / COMPUTATIONAL_SPACE_DIMENSION
    results = []
    for data in (mean_00, mean_chi_1, reduced_ideal):
        guess = model.guess(data=data.values, m=cliffords)
        results.append(model.fit(data.values, params=guess, m=cliffords))
    fit_00, fit_chi_1, fit_ideal = results
    return DecayFits(
        p=fit_00.params["p"].value,
        lambda_L=fit_chi_1.params["p"].value,
        AM=fit_chi_1.params["A"].value,
        lambda_r=fit_ideal.params["p"].value,
        curve_00=model.eval(fit_00.params, m=curve_cliffords),
        curve_chi_1=model.eval(fit_chi_1.params, m=curve_cliffords),
        curve_ideal=model.eval(fit_ideal.params, m=curve_cliffords),
    )


def _plot_decays(axis: Any, decays: TwoQubitDecays, cz_fidelity: float) -> None:
    """Each seed's |00> probability and its fitted decay, interleaved dotted."""
    interleave = decays.coords["interleave"]
    styles = {
        "x": decays.coords["cliffords"],
        "hue": decays.coords["seed"],
        "alpha": 0.2,
    }
    axis.plot(
        decays.curve_cliffords,
        decays.standard.curve_00,
        color="red",
        lw=3,
        label=rf"$p_{{SRB}}$: {decays.standard.p:.3f}",
    )
    decays.p00.sel({interleave: False}).plot(ax=axis, **styles)
    title = ""
    if decays.interleaved is not None:
        decays.p00.sel({interleave: True}).plot(ax=axis, ls=":", **styles)
        axis.plot(
            decays.curve_cliffords,
            decays.interleaved.curve_00,
            color="magenta",
            lw=3,
            label=f"$p_{{IRB}}$: {decays.interleaved.p:.3f}",
        )
        title = rf"CZ fidelity = {cz_fidelity:.3f}"
    axis.set_ylabel(r"State |00$\rangle$ probability")
    axis.axhline(0.25, color="black")
    axis.legend()
    axis.set_title(title)


def _plot_leakage(axis: Any, decays: TwoQubitDecays) -> None:
    """Each seed's computational-subspace and reduced ideal probabilities, and Nakamura's fitted decays."""
    interleave = decays.coords["interleave"]
    styles = {
        "x": decays.coords["cliffords"],
        "hue": decays.coords["seed"],
        "alpha": 0.2,
    }
    modes = [(False, decays.standard, "SRB", "teal", "orchid")]
    if decays.interleaved is not None:
        modes.append((True, decays.interleaved, "IRB", "orange", "aqua"))
    for is_interleaved, *_ in modes:
        mode = {interleave: is_interleaved}
        decays.chi_1.sel(mode).plot(ax=axis, **styles)
        reduced_ideal = (
            decays.p00.sel(mode)
            - decays.chi_1.sel(mode) / COMPUTATIONAL_SPACE_DIMENSION
        )
        reduced_ideal.plot(ax=axis, **styles)
    for _, mode_decays, name, chi_1_colour, _ in modes:
        axis.plot(
            decays.curve_cliffords,
            mode_decays.curve_chi_1,
            color=chi_1_colour,
            lw=3,
            label=_get_leakage_label(mode_decays, name),
        )
    for _, mode_decays, name, _, ideal_colour in modes:
        axis.plot(
            decays.curve_cliffords,
            mode_decays.curve_ideal,
            color=ideal_colour,
            lw=3,
            label=rf"$\lambda_r^{{{name}}}$: {mode_decays.lambda_r:.4f}",
        )
    axis.legend()
    axis.set_title(f"CZ fidelity (Nakamura paper): {decays.nakamura_fidelity:0.3f}")
