# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman, 2024
# (C) Chalmers Next Labs 2025
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""CZ parametrization: the CZ pulse's frequency and amplitude, and the coupler's parking current."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.stats import multivariate_normal

from tergite_tuner.lib.nodes.coupler.cz_parametrization.analysis import (
    CZParametrizationCouplerAnalysis,
)
from tergite_tuner.lib.nodes.coupler.cz_parametrization.measurement import (
    CZParametrizationMeasurement,
)
from tergite_tuner.lib.nodes.coupler.utils import (
    get_coupler_value,
    get_phase_path,
    get_transition_frequency,
    set_dc_currents,
)
from tergite_tuner.lib.spec import (
    NodeSpec,
    get_class_schedule,
    get_coupler_analyser,
    get_fixed_sweep,
    save_coupler_figures,
)
from tergite_tuner.lib.utils.classification_functions import generate_iq_shots
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

LOOPS = 128
AMPLITUDES = np.linspace(0.50, 0.95, 25)


def get_frequencies(coupler: str, session: "SessionContext") -> np.ndarray:
    """28 frequencies from 10 MHz below to 4 MHz above the coupler's CZ transition."""
    return np.linspace(-10e6, 4e6, 28) + get_transition_frequency(coupler, session)


def get_parking_current(coupler: str, session: "SessionContext") -> np.ndarray:
    return np.array(
        [float(get_coupler_value(coupler, "initial_parking_current", session))]
    )


def get_analysis_keywords(coupler: str, session: "SessionContext") -> dict[str, Any]:
    return {"phase_path": get_phase_path(coupler, session)}


def get_dummy_s21(
    qubit: str, sweeps: Mapping[str, np.ndarray], session: "SessionContext"
) -> np.ndarray:
    """Shots whose probabilities make a blob over amplitude and frequency, a peak for one qubit and a dip for the other."""
    amplitudes, frequencies = (
        sweeps["cz_pulse_amplitudes"],
        sweeps["cz_pulse_frequencies"],
    )
    distribution = multivariate_normal(cov=np.eye(2), mean=np.zeros(2))
    x, y = np.meshgrid(
        np.linspace(-3, 3, num=len(frequencies)),
        np.linspace(-3, 3, num=len(amplitudes)),
    )
    peaks = distribution.pdf(np.dstack((x, y)))
    peaks /= peaks.max()
    zeros = np.zeros_like(peaks)
    is_first = any(coupler.split("_")[0] == qubit for coupler in session.couplers)
    probabilities = [peaks, 1 - peaks, zeros] if is_first else [zeros, 1 - peaks, peaks]
    return np.ravel(
        generate_iq_shots(np.array(probabilities), qubit, LOOPS, session.redis)
    )


CZ_PARAMETRIZATION_SPECS = {
    NodeEnum.CZ_PARAMETRIZATION: NodeSpec(
        name=NodeEnum.CZ_PARAMETRIZATION,
        element="coupler",
        get_schedule=get_class_schedule(CZParametrizationMeasurement),
        analyse=get_coupler_analyser(CZParametrizationCouplerAnalysis),
        get_analysis_keywords=get_analysis_keywords,
        qois={
            "cz_pulse_frequency": "cz_pulse_frequency",
            "cz_pulse_amplitude": "cz_pulse_amplitude",
            "parking_current": "parking_current",
        },
        sweeps={
            "cz_pulse_amplitudes": get_fixed_sweep(AMPLITUDES),
            "cz_pulse_frequencies": get_frequencies,
        },
        get_dummy_s21=get_dummy_s21,
        loops=LOOPS,
        external_sweeps={"dc_currents": get_parking_current},
        set_external=set_dc_currents,
        save_details=save_coupler_figures,
    )
}
