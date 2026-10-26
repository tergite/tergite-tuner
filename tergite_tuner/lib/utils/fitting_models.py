# This code is part of Tergite
#
# (C) Copyright 2020, The Quantify consortium.
# (C) Copyright Chalmers Next Labs 2026
#
# Copied from quantify_core.analysis.fitting_models (quantify-core 0.8.1,
# https://gitlab.com/quantify-os/quantify-core), which qblox-scheduler does not
# replace, under its BSD 3-Clause License:
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this
#    list of conditions and the following disclaimer in the documentation and/or
#    other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors may
#    be used to endorse or promote products derived from this software without
#    specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""lmfit models and fit functions that the node analyses use."""

from typing import Tuple

import lmfit
import numpy as np


def hanger_func_complex_SI(
    f: float,
    fr: float,
    Ql: float,
    Qe: float,
    A: float,
    theta: float,
    phi_v: float,
    phi_0: float,
    alpha: float = 1,
) -> complex:
    """S21 of a hanger (lambda/4) resonator, eq. S4 of Bruno et al. (2015), arXiv:1502.04082."""
    slope_corr = 1 + alpha * (f - fr) / fr
    hanger_contribution = 1 - Ql / Qe * np.exp(1j * theta) / (
        1 + 2.0j * Ql * (f - fr) / fr
    )
    propagation_delay_corr = np.exp(1j * (phi_v * f + phi_0))
    return A * slope_corr * hanger_contribution * propagation_delay_corr


def exp_decay_func(
    t: float,
    tau: float,
    amplitude: float,
    offset: float,
    n_factor: float,
) -> float:
    return amplitude * np.exp(-((t / tau) ** n_factor)) + offset


def exp_damp_osc_func(
    t: float,
    tau: float,
    n_factor: float,
    frequency: float,
    phase: float,
    amplitude: float,
    offset: float,
):
    oscillation = amplitude * (np.cos(2 * np.pi * frequency * t + phase))
    exp_decay = np.exp(-((t / tau) ** n_factor))
    return oscillation * exp_decay + offset


def fft_freq_phase_guess(data: np.ndarray, t: np.ndarray) -> Tuple[float, float]:
    """Frequency and phase guesses for a cosine fit; ``t`` must be evenly spaced."""
    # the second half of the spectrum holds the negative frequencies
    power = np.fft.fft(data)[: len(data) // 2]
    freq = np.fft.fftfreq(len(data), t[1] - t[0])[: len(power)]
    power[0] = 0

    abs_power = np.abs(power)
    freq_guess = abs(freq[abs_power == max(abs_power)][0])
    # data == max(data) can hold at several points, so take the first
    ph_guess = 2 * np.pi - (2 * np.pi * t[data == max(data)] * freq_guess)[0]

    return freq_guess, ph_guess


class ResonatorModel(lmfit.model.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(hanger_func_complex_SI, *args, **kwargs)
        self.set_param_hint("Ql", min=0)
        self.set_param_hint("Qe", min=0)
        self.set_param_hint("Qi", expr="1./(1./Ql-1./Qe*cos(theta))", vary=False)
        self.set_param_hint("Qc", expr="Qe/cos(theta)", vary=False)

    def guess(self, data, **kws) -> lmfit.parameter.Parameters:
        f = kws.get("f")
        if f is None:
            return None

        fmin = f.min()
        fmax = f.max()
        fr_guess = f[np.abs(data).argmin()]
        # assumes the data spans the whole resonance and samples it finely enough
        Q_min = 0.1 * (fr_guess / (fmax - fmin))
        delta_f = np.diff(f)
        Q_max = fr_guess / delta_f[delta_f > 0].min()
        Q_guess = np.sqrt(Q_min * Q_max)
        phi_0_guess, phi_v_guess = _resonator_phase_guess(data, f)

        self.set_param_hint("fr", value=fr_guess, min=fmin, max=fmax)
        self.set_param_hint("Ql", value=Q_guess * 1.01, min=Q_min, max=Q_max)
        self.set_param_hint("Qe", value=Q_guess * 0.99, min=0)
        self.set_param_hint("A", value=np.mean(abs(data)), min=0)
        self.set_param_hint("theta", value=0, min=-np.pi / 2, max=np.pi / 2)
        self.set_param_hint("phi_0", value=phi_0_guess)
        self.set_param_hint("phi_v", value=phi_v_guess)
        self.set_param_hint("alpha", value=0, min=-1, max=1)

        params = self.make_params()
        return lmfit.models.update_param_vals(params, self.prefix, **kws)


class ExpDecayModel(lmfit.model.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(exp_decay_func, *args, **kwargs)
        self.set_param_hint("tau", min=0)
        self.set_param_hint("amplitude", vary=True)
        self.set_param_hint("offset", vary=True)
        self.set_param_hint("n_factor", expr="1", vary=False)

    def guess(self, data, **kws) -> lmfit.parameter.Parameters:
        delay = kws.get("delay")
        if delay is None:
            return None

        self.set_param_hint("offset", value=data[-1])
        self.set_param_hint("amplitude", value=data[0] - data[-1])
        self.set_param_hint("tau", value=np.median(delay), min=0)

        params = self.make_params()
        return lmfit.models.update_param_vals(params, self.prefix, **kws)


def _resonator_phase_guess(s21: np.ndarray, freq: np.ndarray) -> Tuple[float, float]:
    """Phase offset and phase velocity, from the median step between phases."""
    phase = np.angle(s21)
    phi_v = np.median(np.diff(phase)) / np.median(np.diff(freq))
    phi_0 = phase[0] - phi_v * freq[0]
    return phi_0, phi_v
