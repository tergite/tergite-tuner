# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Chalmers Next Labs 2024, 2025, 2026
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""CZ local phases: each qubit's dynamic phase from the CZ."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.lib.nodes.coupler.cz_local_phases.analysis import (
    CZLocalPhasesCouplerAnalysis,
)
from tergite_tuner.lib.nodes.coupler.cz_local_phases.measurement import (
    CZLocalPhasesMeasurement,
)
from tergite_tuner.lib.nodes.coupler.utils import get_coupler_keywords, get_random_shots
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


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return get_random_shots(sweeps, LOOPS, ("local_phases", "gate_modes", "swap"))


CZ_LOCAL_PHASES_SPECS = {
    NodeEnum.CZ_LOCAL_PHASES: NodeSpec(
        name=NodeEnum.CZ_LOCAL_PHASES,
        element="coupler",
        get_schedule=get_class_schedule(CZLocalPhasesMeasurement),
        analyse=get_coupler_analyser(CZLocalPhasesCouplerAnalysis),
        qois={
            "cz_dynamic_control": "cz_dynamic_control",
            "cz_dynamic_target": "cz_dynamic_target",
        },
        sweeps={
            "local_phases": get_fixed_sweep(np.linspace(0, 360, 31)),
            "gate_modes": get_fixed_sweep(np.array([True, False])),
            "swap": get_fixed_sweep(np.array([False, True])),
        },
        get_dummy_s21=get_dummy_s21,
        loops=LOOPS,
        qubit_sweeps=frozenset({"local_phases"}),
        get_schedule_keywords=get_coupler_keywords,
        save_details=save_coupler_figures,
    )
}
