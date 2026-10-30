# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Single-qubit randomized benchmarking, standard and interleaved."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.lib.nodes.characterization.randomized_benchmarking.analysis import (
    RandomizedBenchmarkingQubitAnalysis,
)
from tergite_tuner.lib.nodes.characterization.randomized_benchmarking.measurement import (
    RandomizedBenchmarkingMeasurement,
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

SEEDS = 6
CLIFFORDS = np.array([0, 8, 32, 512, 1200])
# "Standard" runs without an interleaved gate, which can be X, Y, X90 or Y90
INTERLEAVE_GATES = np.array(["Standard", "Y90"])
LOOPS = 500


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    number_of_cliffords: dict[str, np.ndarray],
    seeds: dict[str, int],
    interleave_gate: dict[str, str],
    loop_repetitions: int,
    multiplexing: str,
) -> Schedule:
    return RandomizedBenchmarkingMeasurement(transmons).schedule_function(
        seeds, number_of_cliffords, loop_repetitions, interleave_gate, multiplexing
    )


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    return np.random.default_rng(0).random((len(sweeps["number_of_cliffords"]), LOOPS))


RANDOMIZED_BENCHMARKING_SPECS = {
    NodeEnum.RANDOMIZED_BENCHMARKING: NodeSpec(
        name=NodeEnum.RANDOMIZED_BENCHMARKING,
        element="qubit",
        get_schedule=get_schedule,
        analyse=get_class_analyser(RandomizedBenchmarkingQubitAnalysis),
        qois={"fidelity": "fidelity", "leakage": "leakage"},
        sweeps={"number_of_cliffords": get_fixed_sweep(CLIFFORDS)},
        get_dummy_s21=get_dummy_s21,
        plot=plot_class_analysis,
        schedule_keywords={"multiplexing": "parallel"},
        loops=LOOPS,
        outer_sweeps={
            "seeds": get_fixed_sweep(np.arange(SEEDS, dtype=np.int32)),
            "interleave_gate": get_fixed_sweep(INTERLEAVE_GATES),
        },
    )
}
