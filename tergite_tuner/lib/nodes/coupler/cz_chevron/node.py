# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman, 2024
# (C) Chalmers Next Labs 2025, 2026
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""CZ chevron: the CZ's working points of frequency and duration."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np

from tergite_tuner.lib.nodes.coupler.cz_chevron.analysis import CZChevronCouplerAnalysis
from tergite_tuner.lib.nodes.coupler.cz_chevron.measurement import CZChevronMeasurement
from tergite_tuner.lib.nodes.coupler.utils import (
    get_coupler_value,
    get_phase_path,
    get_random_shots,
)
from tergite_tuner.lib.spec import (
    NodeSpec,
    get_class_schedule,
    get_coupler_analyser,
    save_coupler_figures,
)
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

LOOPS = 512 // 4
WORKING_POINTS = 15


def get_frequencies(coupler: str, session: "SessionContext") -> np.ndarray:
    """Thirty frequencies over 6 MHz around the coupler's known CZ frequency."""
    frequency = float(get_coupler_value(coupler, "cz_pulse_frequency", session))
    return np.linspace(-3.0e6, 3.0e6, 30) + frequency


def get_durations(coupler: str, session: "SessionContext") -> np.ndarray:
    """From 24 ns, in 8 ns steps, to twice the known half duration, in 4 ns, plus 40 ns of slack."""
    half_duration = float(get_coupler_value(coupler, "cz_half_duration", session))
    max_duration_in_ns = (round(2 * half_duration / 1e-9) // 4) * 4 + 40
    return np.arange(24e-9, max_duration_in_ns * 1e-9, 8e-9)


def get_analysis_keywords(coupler: str, session: "SessionContext") -> dict[str, Any]:
    return {
        "phase_path": get_phase_path(coupler, session),
        "number_of_working_points": WORKING_POINTS,
    }


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return get_random_shots(sweeps, LOOPS, ("cz_pulse_durations",))


CZ_CHEVRON_SPECS = {
    NodeEnum.CZ_CHEVRON: NodeSpec(
        name=NodeEnum.CZ_CHEVRON,
        element="coupler",
        get_schedule=get_class_schedule(CZChevronMeasurement),
        analyse=get_coupler_analyser(CZChevronCouplerAnalysis),
        get_analysis_keywords=get_analysis_keywords,
        qois={
            "cz_working_frequencies": "cz_working_frequencies",
            "cz_working_durations_in_ns": "cz_working_durations_in_ns",
        },
        sweeps={"cz_pulse_durations": get_durations},
        get_dummy_s21=get_dummy_s21,
        loops=LOOPS,
        outer_sweeps={"cz_pulse_frequencies": get_frequencies},
        save_details=save_coupler_figures,
    )
}
