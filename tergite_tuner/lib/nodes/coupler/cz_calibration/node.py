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
"""CZ calibration: the working point whose CZ shifts the target's phase closest to 180 degrees."""

import ast
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import numpy as np

from tergite_tuner.lib.nodes.coupler.cz_calibration.analysis import (
    CZCalibrationCouplerAnalysis,
)
from tergite_tuner.lib.nodes.coupler.cz_calibration.measurement import (
    CZCalibrationMeasurement,
)
from tergite_tuner.lib.nodes.coupler.utils import (
    get_coupler_keywords,
    get_coupler_value,
    get_random_shots,
)
from tergite_tuner.lib.spec import (
    NodeSpec,
    get_class_schedule,
    get_coupler_analyser,
    get_fixed_sweep,
    save_coupler_figures,
)
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

LOOPS = 512
# a fixed-duration coupler's working points sweep its frequency this far either side
FIXED_DURATION_WIDTH, FIXED_DURATION_POINTS = 0.2e6, 20


def get_working_points(coupler: str, session: "SessionContext") -> np.ndarray:
    """The (frequency, duration) pairs CZ chevron found, or, on a fixed-duration coupler, frequencies around the stored one."""
    if coupler in session.fixed_duration_couplers:
        duration = float(get_coupler_value(coupler, "cz_pulse_duration", session))
        frequency = float(get_coupler_value(coupler, "cz_pulse_frequency", session))
        frequencies = np.linspace(
            frequency - FIXED_DURATION_WIDTH,
            frequency + FIXED_DURATION_WIDTH,
            FIXED_DURATION_POINTS,
        )
        return np.array(list(zip(frequencies, [duration] * FIXED_DURATION_POINTS)))
    frequencies = _parse_list(
        get_coupler_value(coupler, "cz_working_frequencies", session)
    )
    durations_in_ns = _parse_list(
        get_coupler_value(coupler, "cz_working_durations_in_ns", session)
    )
    return np.array(list(zip(frequencies, np.array(durations_in_ns) * 1e-9)))


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return get_random_shots(sweeps, LOOPS, ("ramsey_phases", "control_ons"))


CZ_CALIBRATION_SPECS = {
    NodeEnum.CZ_CALIBRATION: NodeSpec(
        name=NodeEnum.CZ_CALIBRATION,
        element="coupler",
        get_schedule=get_class_schedule(CZCalibrationMeasurement),
        analyse=get_coupler_analyser(CZCalibrationCouplerAnalysis),
        qois={
            "cz_pulse_frequency": "cz_pulse_frequency",
            "cz_pulse_duration": "cz_pulse_duration",
            "cz_phase": "cz_phase",
        },
        sweeps={
            "ramsey_phases": get_fixed_sweep(np.linspace(0, 420, 30)),
            "control_ons": get_fixed_sweep(np.array([False, True])),
        },
        get_dummy_s21=get_dummy_s21,
        loops=LOOPS,
        qubit_sweeps=frozenset({"ramsey_phases"}),
        outer_sweeps={"working_points": get_working_points},
        get_schedule_keywords=get_coupler_keywords,
        save_details=save_coupler_figures,
    )
}


def _parse_list(value: Any) -> Any:
    """A list as stored, or as written in a string by an earlier store."""
    return ast.literal_eval(value) if isinstance(value, str) else value
