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
"""Purity benchmarking: the decay of the state's purity over random Clifford sequences, which gives the incoherent error."""

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
LENGTHS = np.array([0, 2, 4, 8, 16, 128, 256, 512])
# each length once per basis (X, Y, Z), then the calibration points |0>, |1> and |2>
CLIFFORDS = np.concatenate([np.repeat(LENGTHS, 3), [0, 1, 2]])
REPETITIONS = 500
# the purity's decay per Clifford, which the analysis fits
DUMMY_UNITARITY = 0.99


def get_schedule(
    transmons: Mapping[str, ExtendedTransmon],
    number_of_cliffords: dict[str, np.ndarray],
    seeds: dict[str, int],
    repetitions: int,
) -> Schedule:
    return PurityBenchmarkingMeasurement(transmons).schedule_function(
        seeds, number_of_cliffords, repetitions
    )


def get_dummy_s21(
    _qubit: str, sweeps: Mapping[str, np.ndarray], _session: "SessionContext"
) -> np.ndarray:
    """A Bloch vector along Z, its purity falling by ``DUMMY_UNITARITY`` per Clifford, as |1> populations."""
    lengths = sweeps["number_of_cliffords"][:-3:3]
    z_population = (1 + np.sqrt(DUMMY_UNITARITY**lengths)) / 2
    bases = np.stack([np.full_like(z_population, 0.5)] * 2 + [z_population], axis=1)
    return np.concatenate([bases.ravel(), [0.0, 1.0, 0.5]]).astype(complex)


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
        schedule_keywords={"repetitions": REPETITIONS},
        outer_sweeps={"seeds": get_fixed_sweep(np.arange(SEEDS, dtype=np.int32))},
    )
}
