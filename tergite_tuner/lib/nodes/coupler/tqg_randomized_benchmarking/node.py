# This code is part of Tergite
#
# (C) Copyright Amr Osman 2024
# (C) Copyright Eleftherios Moschandreou 2025, 2026
# (C) Copyright Pontus Vikstål 2025
# (C) Copyright Chalmers Next Labs 2025, 2026
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Two-qubit randomized benchmarking of each coupler's CZ, standard and interleaved."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.analysis import (
    CZRBCouplerAnalysis,
)
from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.measurement import (
    CZRBMeasurement,
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

SEEDS = 7
CLIFFORDS = np.array([0, 1, 2, 3, 4, 8, 16, 32, 48, 64])
LOOPS = 500


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    """Random IQ shots for a dummy run.

    Args:
        _qubit: unused; part of the ``get_dummy_s21`` signature.
        sweeps: each swept setting's values.
        _session: unused; part of the ``get_dummy_s21`` signature.

    Returns:
        Shots with an axis per number of Cliffords, interleave mode and loop.
    """
    return get_random_shots(sweeps, LOOPS, ("number_of_cliffords", "interleave_modes"))


CZ_RB_SPECS = {
    NodeEnum.CZ_RB: NodeSpec(
        name=NodeEnum.CZ_RB,
        element="coupler",
        get_schedule=get_class_schedule(CZRBMeasurement),
        analyse=get_coupler_analyser(CZRBCouplerAnalysis),
        qois={"cz_fidelity": "cz_fidelity"},
        sweeps={
            "number_of_cliffords": get_fixed_sweep(CLIFFORDS),
            "interleave_modes": get_fixed_sweep(np.array([False, True])),
        },
        get_dummy_s21=get_dummy_s21,
        loops=LOOPS,
        outer_sweeps={"seeds": get_fixed_sweep(np.arange(SEEDS, dtype=np.int32))},
        get_schedule_keywords=get_coupler_keywords,
        save_details=save_coupler_figures,
    )
}
