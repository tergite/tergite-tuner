# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman, 2024
# (C) Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


from functools import partial
from typing import TYPE_CHECKING, NamedTuple

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.figure import Figure

from tergite_tuner.lib.nodes.coupler.cz_parametrization.analysis import (
    get_cz_probabilities,
)
from tergite_tuner.lib.spec import Fit, Fits, get_coupler_data, get_fits_from_result
from tergite_tuner.lib.utils.analysis_models import SineOscillatingModel

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


CURVE_POINTS = 200


class Chevron(NamedTuple):
    """Both qubits' populations over CZ frequency and duration, and the working points, to plot.

    Attributes:
        probabilities: both qubits' state populations.
        frequencies: the working points' CZ frequencies.
        durations_in_ns: the working points' CZ durations, in nanoseconds.
        frequencies_coord: the name of the CZ frequencies' coordinate.
    """

    probabilities: xr.DataArray
    frequencies: np.ndarray
    durations_in_ns: np.ndarray
    frequencies_coord: str


def analyse_cz_chevron(
    dataset: xr.Dataset, session: "SessionContext", phase_path: str
) -> Fits:
    """The (frequency, duration) points where the chevron returns to |11>, as CZ working points.

    Each frequency's leads along the phase path are fitted with a sine over the
    durations, and its period is the frequency's working duration.

    Args:
        dataset: the coupler's variables, saved in real and imaginary parts.
        session: the session, whose device state holds the discriminators.
        phase_path: ``via_20`` or ``via_02``.

    Returns:
        The fits ``cz_working_frequencies`` and ``cz_working_durations_in_ns``,
        each a list written as a string, and, to plot, the ``chevron``.
    """
    data = get_coupler_data(dataset, session)
    probabilities, coords = get_cz_probabilities(data, session)
    durations = probabilities[coords["durations"]].values
    control_leads, target_leads = get_chevron_leads(
        probabilities.sel({"qubit": data.control_qubit}),
        probabilities.sel({"qubit": data.target_qubit}),
        phase_path,
    )
    model = SineOscillatingModel()
    model.set_param_hint("optimal_duration", expr="1/frequency", vary=False)
    # a sine fitted to each frequency's column of durations
    cz_durations, _ = xr.apply_ufunc(
        partial(
            _fit_period,
            model,
            durations=durations,
            plot_durations=np.linspace(durations[0], durations[-1], CURVE_POINTS),
        ),
        control_leads + target_leads,
        input_core_dims=[[coords["durations"]]],
        output_core_dims=[["cz_pulse_durations"], ["plot_points"]],
        vectorize=True,
    )
    # the rejected fits' columns go
    cz_durations = cz_durations.dropna(dim=coords["frequencies"])
    durations_in_ns = get_durations_in_ns(cz_durations.values.flatten())
    frequencies = cz_durations[coords["frequencies"]].values
    analysis_result = {
        "cz_working_frequencies": {
            "value": str(frequencies.astype(int).tolist()),
            "error": 0,
        },
        "cz_working_durations_in_ns": {
            "value": str(durations_in_ns.tolist()),
            "error": 0,
        },
    }
    chevron = Chevron(
        probabilities, frequencies, durations_in_ns, coords["frequencies"]
    )
    return {**get_fits_from_result(analysis_result, True), "chevron": Fit(chevron)}


def plot_cz_chevron(fits: Fits) -> list[Figure]:
    """Each qubit's state populations over frequency and duration, with the working points.

    Args:
        fits: the coupler's fits.

    Returns:
        The coupler's one figure.
    """
    chevron = fits["chevron"].value
    chevron.probabilities.plot(
        x=chevron.frequencies_coord, cmap="RdBu_r", row="qubit", col="state"
    )
    figure = plt.gcf()
    # every working point is selected, and drawn on every one of the six faceting axes
    if not chevron.durations_in_ns.size:
        return [figure]
    for axis in figure.axes:
        axis.plot(
            chevron.frequencies,
            chevron.durations_in_ns * 1e-9,
            marker="8",
            ls="",
            color="yellow",
        )
        axis.plot(
            chevron.frequencies,
            chevron.durations_in_ns * 1e-9,
            marker="*",
            markersize=12,
            ls="",
            color="yellow",
        )
    return [figure]


def get_chevron_leads(
    control: xr.DataArray, target: xr.DataArray, phase_path: str
) -> tuple[xr.DataArray, xr.DataArray]:
    """Each qubit's population at its end of the phase path, less its |1>: |2> for the control and |0> for the target via 20, the reverse via 02.

    Args:
        control: the control's state populations.
        target: the target's state populations.
        phase_path: ``via_20`` or ``via_02``.

    Returns:
        The control's lead and the target's lead.

    Raises:
        ValueError: if the phase path is neither.
    """
    ends = {"via_20": (2, 0), "via_02": (0, 2)}
    if phase_path not in ends:
        raise ValueError(f"Invalid phase path:{phase_path}")
    control_end, target_end = ends[phase_path]
    return (
        control.sel({"state": control_end}) - control.sel({"state": 1}),
        target.sel({"state": target_end}) - target.sel({"state": 1}),
    )


def get_durations_in_ns(durations: np.ndarray) -> np.ndarray:
    """Durations in seconds, rounded down to whole nanoseconds and then to multiples of 4 ns.

    Args:
        durations: the durations, in seconds.

    Returns:
        The durations in whole nanoseconds, multiples of 4.
    """
    # rounded to a millionth of a nanosecond first, so 100e-9 is 100 ns, not 99
    nanoseconds = np.floor(np.round(durations * 1e9, 6)).astype(int)
    return (nanoseconds // 4) * 4


def _fit_period(
    model: SineOscillatingModel,
    data: np.ndarray,
    durations: np.ndarray,
    plot_durations: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Fits a sine to one frequency's leads over the CZ durations.

    Returns:
        The fitted period as the CZ duration, NaN if the fit failed, did not
        converge or its oscillations are too weak, and the fitted curve over the
        plot's durations.
    """
    guess = model.guess(data, x=durations)
    try:
        fit = model.fit(data, params=guess, x=durations)
        duration = fit.values["optimal_duration"]
        amplitude = fit.values["amplitude"]
        fit_data = model.eval(fit.params, x=plot_durations)
        # discard weak oscillations, and fits that stopped unconverged: where
        # those stop depends on the process's and the platform's last bits
        if amplitude < 0.30 or not fit.success:
            duration = np.nan
        return np.array([duration]), np.array([fit_data])
    except Exception:
        return np.array([np.nan]), np.array([np.nan])
