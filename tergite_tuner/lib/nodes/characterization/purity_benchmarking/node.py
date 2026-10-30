# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Purity benchmarking, which cannot run yet (REFACTOR.md step 9.7)."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.characterization.purity_benchmarking.analysis import (
    PurityBenchmarkingQubitAnalysis,
)
from tergite_tuner.lib.nodes.characterization.purity_benchmarking.measurement import (
    PurityBenchmarkingMeasurement,
)
from tergite_tuner.lib.spec import (
    NodeSpec,
    get_class_analyser,
    get_fixed_sweep,
    plot_class_analysis,
)
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

SEEDS = 4
CLIFFORDS = np.array([0, 2, 4, 8, 16, 128, 256, 512])
LOOPS = 500


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    number_of_cliffords: dict[str, np.ndarray],
    seeds: dict[str, int],
    **keywords: object,
) -> Schedule:
    """The schedule, which takes no ``loop_repetitions`` and so raises ``TypeError`` as the node always has."""
    return PurityBenchmarkingMeasurement(transmons).schedule_function(
        seeds, number_of_cliffords, **keywords
    )


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return np.zeros((len(sweeps["number_of_cliffords"]), LOOPS), dtype=complex)


PURITY_BENCHMARKING_SPECS = {
    NodeEnum.PURITY_BENCHMARKING: NodeSpec(
        name=NodeEnum.PURITY_BENCHMARKING,
        element="qubit",
        get_schedule=get_schedule,
        analyse=get_class_analyser(PurityBenchmarkingQubitAnalysis),
        qois={"purity_fidelity": "purity_fidelity"},
        sweeps={"number_of_cliffords": get_fixed_sweep(CLIFFORDS)},
        get_dummy_s21=get_dummy_s21,
        plot=plot_class_analysis,
        loops=LOOPS,
        outer_sweeps={"seeds": get_fixed_sweep(np.arange(SEEDS, dtype=np.int32))},
    )
}
