# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Michele Faucci Giannelli 2024, 2025
# (C) Copyright Theresa Fuchs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import TYPE_CHECKING

import lmfit
import numpy as np
import xarray as xr
from matplotlib.axes import Axes

from tergite_tuner.lib.spec import Fit, Fits, get_coord_name
from tergite_tuner.lib.utils.fitting_models import fft_freq_phase_guess
from tergite_tuner.utils.logging import logger

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


def cos_func(
    x: float,
    frequency: float,
    amplitude: float,
    offset: float,
    x0: float,
    phase: float = 0,
) -> float:
    """
    Generate a cosine function with exponential decay.
    Args:
        x (float): The input value.
        frequency (float): The frequency of the cosine wave.
        amplitude (float): The amplitude of the cosine wave.
        offset (float): The offset to be added to the cosine wave.
        x0 (float): The decay constant for the exponential decay.
        phase (float, optional): The phase shift of the cosine wave. Defaults to 0.
    Returns:
        float: The value of the cosine function with exponential decay at x.
    """

    return (
        amplitude * np.cos(2 * np.pi * frequency * (x + phase)) * np.exp(-x / x0)
        + offset
    )


class T2Model(lmfit.model.Model):
    """
    Generate a cosine model that can be fit to Rabi oscillation data.
    """

    def __init__(self, *args, **kwargs):
        # Pass in the defining equation so the user doesn't have to later.
        super().__init__(cos_func, *args, **kwargs)

        # Enforce oscillation frequency is positive
        self.set_param_hint("frequency", min=0)

        # Fix the phase at pi so that the ouput is at a minimum when drive_amp=0
        self.set_param_hint("phase", min=-0.5, max=0.5)

        # Pi-pulse amplitude can be derived from the oscillation frequency
        self.set_param_hint("duration", expr="1/frequency", vary=False)
        self.set_param_hint("swap", expr="1/(2*frequency)-phase", vary=False)
        self.set_param_hint("cz", expr="2/(2*frequency)-phase", vary=False)

    def guess(self, data, **kws) -> lmfit.parameter.Parameters:
        """Guesses the starting parameters of a fit to ``data``.

        Args:
            data: the values to fit, at each delay.
            **kws: ``x``, the delays, and any parameter values to use instead of
                the guesses.

        Returns:
            The guessed parameters, or None without ``x``.
        """
        x = kws.get("x", None)
        if x is None:
            return None

        amp_guess = abs(max(data) - min(data)) / 2  # amp is positive by convention
        offs_guess = np.mean(data)

        # Frequency guess is obtained using a fast fourier transform (FFT).
        freq_guess, _ = fft_freq_phase_guess(data, x)

        self.set_param_hint("x0", value=x[-1] / 2, min=0)
        self.set_param_hint("frequency", value=freq_guess, min=0)
        self.set_param_hint("amplitude", value=amp_guess, min=-1.5 * amp_guess)
        self.set_param_hint("offset", value=offs_guess)

        params = self.make_params()
        return lmfit.models.update_param_vals(params, self.prefix, **kws)


def analyse_decay(
    s21: xr.DataArray,
    _session: "SessionContext",
    model: lmfit.Model,
    time_parameter: str,
    repetitions_coord: str,
    guess_variable: str,
) -> Fits | None:
    """The ``time`` the decay's ``time_parameter`` averages over the repetitions, with their spread as error.

    Delays are in microseconds, and ``|S21|`` in microvolts. None if a repetition cannot be
    fitted: an oscillation guessed at 0 Hz divides by zero in the model's expressions.

    Args:
        s21: the qubit's S21, a point per delay and repetition.
        _session: unused; part of the ``analyse`` signature.
        model: the decay to fit.
        time_parameter: the model's parameter that is the decay time.
        repetitions_coord: the dimension of the repetitions.
        guess_variable: the name ``model.guess`` takes the delays by.

    Returns:
        ``time``, the mean decay time in microseconds with the repetitions' spread as
        error, and ``params``, the mean fit's parameters, to plot; None if a repetition
        cannot be fitted.
    """
    delays = s21.coords[get_coord_name("delays", s21.attrs["qubit"])].values * 1e6
    magnitudes = np.abs(s21)
    fit_variable = model.independent_vars[0]
    results = []
    for index in range(s21.sizes[repetitions_coord]):
        repetition = magnitudes.isel({repetitions_coord: index}).values.flatten() * 1e6
        try:
            guess = model.guess(data=repetition, **{guess_variable: delays})
            results.append(
                model.fit(repetition, params=guess, **{fit_variable: delays})
            )
        except ZeroDivisionError:
            logger.warning(
                f"Repetition {index} of {s21.attrs['qubit']} cannot be fitted"
            )
            return None

    times = [result.params[time_parameter].value for result in results]
    params = results[-1].params.copy()
    for name in (time_parameter, "offset", "amplitude"):
        params[name].value = np.mean([result.params[name].value for result in results])
    return {"time": Fit(np.mean(times), np.std(times)), "params": Fit(params)}


def plot_decay(
    axis: Axes,
    s21: xr.DataArray,
    fits: Fits,
    _session: "SessionContext",
    model: lmfit.Model,
    time_parameter: str,
    repetitions_coord: str,
    label: str,
    should_show_spread: bool,
) -> None:
    """Each repetition, and the mean fit, with its one-sigma band if ``should_show_spread``.

    Args:
        axis: the axis to draw on.
        s21: the qubit's S21, a point per delay and repetition.
        fits: the qubit's fits from ``analyse_decay``; only the repetitions are drawn if empty.
        _session: unused; part of the ``plot`` signature.
        model: the fitted decay.
        time_parameter: the model's parameter that is the decay time.
        repetitions_coord: the dimension of the repetitions.
        label: the decay time's name in the legend, such as ``T1``.
        should_show_spread: whether to shade the band one spread either side of the mean.
    """
    delays = _plot_repetitions(axis, s21, repetitions_coord)
    if fits:
        fit_delays = np.linspace(delays[0], delays[-1], 400)
        time, spread = fits["time"]
        params = fits["params"].value
        axis.plot(
            fit_delays,
            _get_decay_with(model, params, time_parameter, time, fit_delays),
            color="red",
            label=f"Mean {label} = {time:.1f} ± {spread:.1f} μs",
        )
        if should_show_spread:
            axis.fill_between(
                fit_delays,
                *(
                    _get_decay_with(model, params, time_parameter, bound, fit_delays)
                    for bound in (time - spread, time + spread)
                ),
                color="red",
                alpha=0.2,
                label="±1σ",
            )
        axis.legend()
    axis.set_xlabel("Delay (μs)")
    axis.set_ylabel("|S21| (V)")
    axis.grid()


def _get_decay_with(
    model: lmfit.Model,
    params: lmfit.Parameters,
    time_parameter: str,
    time: float,
    delays: np.ndarray,
) -> np.ndarray:
    """The fitted decay with ``time_parameter`` set to ``time``."""
    params = params.copy()
    params[time_parameter].value = time
    return model.eval(params=params, **{model.independent_vars[0]: delays})


def _plot_repetitions(
    axis: Axes, s21: xr.DataArray, repetitions_coord: str
) -> np.ndarray:
    """Draws each repetition's ``|S21|`` in microvolts and returns the delays in microseconds."""
    delays = s21.coords[get_coord_name("delays", s21.attrs["qubit"])].values * 1e6
    magnitudes = np.abs(s21)
    for index in range(s21.sizes[repetitions_coord]):
        repetition = magnitudes.isel({repetitions_coord: index}).values.flatten() * 1e6
        axis.plot(delays, repetition, alpha=0.3)
    return delays
