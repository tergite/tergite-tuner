# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Chalmers Next Labs 2024
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Module containing a schedule class for randomized benchmarking measurement.
"""

from typing import Literal

import numpy as np

from tergite_tuner.backend import (
    BinMode,
    ExtendedTransmon,
    IdlePulse,
    Loop,
    Measure_RO_3state_Opt,
    Reset,
    Rxy,
    Schedule,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.cliffords.clifford_group import (
    INTERLEAVED_CLIFFORDS,
    get_rxy_angles,
)
from tergite_tuner.lib.utils.cliffords.randomized_benchmarking import (
    randomized_benchmarking_sequence,
)


class RandomizedBenchmarkingMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)
        self.transmons = transmons

    def rb_shot(
        self,
        seeds: dict[str, int],
        number_of_cliffords: dict[str, np.ndarray],
        interleave_gate: dict[str, str],
        multiplexing: Literal["one_by_one", "parallel"],
    ):
        shot = Schedule("shot")
        shot.add(IdlePulse(16e-9))

        qubits = list(self.transmons.keys())

        root_relaxation = shot.add(Reset(*qubits), label="Start")

        # The outer for loop iterates over all qubits:
        for this_qubit, clifford_sequence_lengths in number_of_cliffords.items():
            seed = seeds[this_qubit]  # this is just an integer
            interleaving_gate = interleave_gate[this_qubit]

            rng = np.random.default_rng(seed)  # this is a generator

            if multiplexing == "parallel":
                shot.add(
                    Reset(this_qubit),
                    ref_op=root_relaxation,
                    label=f"root_{this_qubit}",
                )  # To enforce parallelism we refer to the root relaxation
            # this is redundant, but left here for explicity
            elif multiplexing == "one_by_one":
                pass
            else:
                raise ValueError(f"invalid keyword {multiplexing}")

            if interleaving_gate == "Standard":
                interleaving_clifford_id = None
            else:
                if interleaving_gate not in INTERLEAVED_CLIFFORDS:
                    raise NotImplementedError(
                        f"{interleaving_gate} not currently supported"
                    )
                interleaving_clifford_id = INTERLEAVED_CLIFFORDS[interleaving_gate]

            # The inner for loop iterates over the random clifford sequence lengths
            for acq_index, this_number_of_cliffords in enumerate(
                clifford_sequence_lengths
            ):
                # ends with the Clifford that inverts the rest
                clifford_sequence = randomized_benchmarking_sequence(
                    this_number_of_cliffords,
                    interleaved_clifford_idx=interleaving_clifford_id,
                    seed=rng,
                )
                self.single_qubit_rb_shot(
                    shot, clifford_sequence, this_qubit, acq_index
                )

        return shot

    def single_qubit_rb_shot(
        self,
        shot: Schedule,
        clifford_sequence: np.ndarray,
        this_qubit: str,
        acq_index: int,
    ) -> None:

        for clifford_idx in clifford_sequence:
            for theta, phi in get_rxy_angles(clifford_idx):
                shot.add(Rxy(qubit=this_qubit, theta=theta, phi=phi))

        shot.add(
            Measure_RO_3state_Opt(
                this_qubit, acq_index=acq_index, bin_mode=BinMode.APPEND
            ),
        )

        shot.add(Reset(this_qubit))

    def schedule_function(
        self,
        seeds: dict[str, int],
        number_of_cliffords: dict[str, np.ndarray],
        loop_repetitions: int,
        interleave_gate: dict[str, str],
        multiplexing: Literal["parallel", "one_by_one"] = "parallel",
    ) -> Schedule:
        schedule = Schedule("randomized_benchmarking", repetitions=1)

        rb_shot_schedule = self.rb_shot(
            seeds,
            number_of_cliffords,
            interleave_gate=interleave_gate,
            multiplexing=multiplexing,
        )

        schedule.add(rb_shot_schedule, control_flow=Loop(loop_repetitions))
        schedule.add(IdlePulse(20e-9))
        return schedule
