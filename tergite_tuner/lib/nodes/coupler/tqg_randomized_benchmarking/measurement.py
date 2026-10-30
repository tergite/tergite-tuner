# This code is part of Tergite
#
# (C) Copyright Amr Osman 2024
# (C) Copyright Eleftherios Moschandreou 2025, 2026
# (C) Copyright Chalmers Next Labs 2025, 2026
# (C) Copyright Pontus Vikstål 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from itertools import groupby
from operator import itemgetter
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray

from tergite_tuner.backend import (
    CZ,
    X90,
    Y90,
    ExtendedCompositeSquareEdge,
    ExtendedTransmon,
    IdlePulse,
    Reset,
    Rxy,
    Schedule,
    X,
    Y,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.cliffords.clifford_group import (
    TwoQubitClifford,
)
from tergite_tuner.lib.utils.cliffords.randomized_benchmarking import (
    randomized_benchmarking_sequence,
)
from tergite_tuner.lib.utils.schedules import (
    add_cz_clock,
    add_pair_measurement,
    get_repeated_schedule,
)
from tergite_tuner.utils.logging import logger

# Constants
IDLE_TIME = 12e-9
# the CZ in the two-qubit group, interleaved unless another Clifford is given
CZ_CLIFFORD_INDEX = 4368
# PycQED's single-qubit gates; its identity "I" idles, see CZRBMeasurement._get_gate
GATES = {
    "X180": X,
    "X90": X90,
    "Y180": Y,
    "Y90": Y90,
    "mX90": lambda qubit: Rxy(qubit=qubit, phi=0.0, theta=-90.0),
    "mY90": lambda qubit: Rxy(qubit=qubit, phi=90.0, theta=-90.0),
}
# Frequency used for the downconversion of the readout signal. This was
# previously sourced from the global config; if it ever needs to vary
# per-device, surface it through the device configuration instead.


class CZRBMeasurement(BaseMeasurement):

    def __init__(
        self,
        transmons: dict[str, ExtendedTransmon],
        couplers: dict[str, ExtendedCompositeSquareEdge],
    ):
        super().__init__(transmons)
        self.transmons = transmons
        self.couplers = couplers

    def align_cliffords(self, coupler: str, clifford_sequence: list) -> list:
        """
        The initial TwoQubitClifford decomposition,
        returns decompositions of Operations that look like:
        q0      O1 -- O2                 -- O5
        q1               -- O3                 -- O6
        coupler                -- O4=CZ

        i.e. the single qubit Operations are run consequantly for both qubits.
        This method aligns the single qubit operations, so they are run in parallel
        while padding with Identity operations where necessary:
        q0      O1 -- O2         -- O5
        q1      O3 --  I         -- O6
        coupler         -- O4=CZ
        """

        def pad_operations(operation_group: dict):
            for qubit, ops in operation_group.items():
                max_len = max(len(ops) for ops in operation_group.values())
                while len(ops) < max_len:
                    ops.insert(0, "I")

        operation_group = {}
        grouped_operations = []
        for qubit, operation in groupby(clifford_sequence, key=itemgetter(1)):
            operations = [op[0] for op in operation]
            if type(qubit) is str:
                operation_group[qubit] = operations
            elif type(qubit) is list:
                if operation_group != {}:
                    pad_operations(operation_group)

                    grouped_operations.append(operation_group.copy())
                    operation_group.clear()
                operation_group[coupler] = operations
                grouped_operations.append(operation_group.copy())
                operation_group.clear()

        if operation_group != {}:
            pad_operations(operation_group)
        grouped_operations.append(operation_group.copy())
        return grouped_operations

    def add_coupler_clock_resources(self, schedule: Schedule, coupler: str) -> None:
        """
        Add a clock resource for the coupler's "CZ" (controlled-Z) gate to the schedule
        The frequency is adjusted by subtracting the coupler's "CZ" frequency from the downconversion factor

        Args:
            schedule: The schedule to add resources to
            coupler: Name identifier for the coupler
        """
        add_cz_clock(schedule, coupler, self.couplers[coupler].clock_freqs.cz_freq())

    def ro_shot(
        self,
        seeds: dict[str, int],
        number_of_cliffords: dict[str, np.ndarray],
        interleave_modes: dict[str, np.ndarray],
        apply_inverse_gate: bool,
        coupler_dict: dict[str, dict],
        interleaving_clifford_id: Optional[int] = None,
    ) -> Schedule:
        shot = Schedule("shot")
        coupler_names = list(self.couplers.keys())
        if len(coupler_names) != 1:
            raise ValueError(
                f"Two-qubit RB benchmarks one coupler at a time, got {coupler_names}"
            )
        coupler = coupler_names[0]
        qubits = (
            coupler_dict[coupler]["control_qubit"],
            coupler_dict[coupler]["target_qubit"],
        )
        self.rxy_duration = self.transmons[qubits[0]].rxy.duration()

        # the common reference, so the qubits can be operated in parallel
        shot.add(Reset(*qubits), label="Start")
        lengths = list(number_of_cliffords.values())[0]
        for mode_index, is_interleaved in enumerate(list(interleave_modes.values())[0]):
            interleaved_id = None
            if is_interleaved:
                interleaved_id = (
                    CZ_CLIFFORD_INDEX
                    if interleaving_clifford_id is None
                    else interleaving_clifford_id
                )
            for acq_index, length in enumerate(lengths):
                sequence: NDArray[np.int_] = randomized_benchmarking_sequence(
                    number_of_cliffords=length,
                    apply_inverse=apply_inverse_gate,
                    clifford_group=2,
                    interleaved_clifford_idx=interleaved_id,
                    seed=seeds[coupler],
                )
                for clifford_idx in sequence:
                    self._add_clifford(shot, clifford_idx, coupler, qubits)
                final = shot.add(IdlePulse(4e-9))
                add_pair_measurement(
                    shot, qubits, mode_index * len(lengths) + acq_index, final
                )
                shot.add(Reset(*qubits))
        return shot

    def _add_clifford(
        self, shot: Schedule, clifford_idx: int, coupler: str, qubits: tuple[str, str]
    ) -> None:
        """The Clifford's gates, its CZs between groups of single-qubit gates."""
        decomposition = TwoQubitClifford(clifford_idx).gate_decomposition
        for group in self.align_cliffords(coupler, decomposition):
            if coupler in group:
                shot.add(CZ(*qubits))
            else:
                self._add_single_qubit_gates(shot, group, qubits)

    def _add_single_qubit_gates(
        self, shot: Schedule, group: dict, qubits: tuple[str, str]
    ) -> None:
        """The control's gates, then the target's from the same start: PycQED's q0 and q1."""
        root = shot.add(IdlePulse(4e-9))
        for name in group["q0"]:
            shot.add(self._get_gate(name, qubits[0]))
        shot.add(IdlePulse(4e-9), ref_op=root)
        for name in group["q1"]:
            shot.add(self._get_gate(name, qubits[1]))

    def _get_gate(self, name: str, qubit: str) -> Any:
        """PycQED's gate ``name`` on ``qubit``; its identity idles for an Rxy's duration."""
        if name == "I":
            return IdlePulse(duration=self.rxy_duration)
        return GATES[name](qubit)

    def schedule_function(
        self,
        seeds: dict[str, int],
        loop_repetitions: int,
        number_of_cliffords: dict[str, np.ndarray],
        interleave_modes: dict[str, np.ndarray],
        coupler_dict: dict[str, dict],
        interleaving_clifford_id: Optional[int] = None,
        apply_inverse_gate: bool = True,
    ) -> Schedule:
        """Two-qubit randomized benchmarking of one coupler, repeated loop_repetitions times.

        For each interleave mode and number of Cliffords, a random sequence from seeds, interleaved
        with interleaving_clifford_id (the CZ by default) in the interleaved mode and followed by its
        inverse when apply_inverse_gate, then a three-state measurement of both qubits.
        """

        if interleaving_clifford_id is None:
            name = "tqg_randomized_benchmarking_ssro"
        else:
            name = "tqg_randomized_benchmarking_interleaved_ssro"
        logger.info(f"interleaved or not: {name}")

        rb_shot = self.ro_shot(
            seeds=seeds,
            number_of_cliffords=number_of_cliffords,
            interleave_modes=interleave_modes,
            interleaving_clifford_id=interleaving_clifford_id,
            apply_inverse_gate=apply_inverse_gate,
            coupler_dict=coupler_dict,
        )

        schedule = get_repeated_schedule(name, rb_shot, loop_repetitions, IDLE_TIME)
        for coupler in self.couplers:
            self.add_coupler_clock_resources(schedule=schedule, coupler=coupler)

        return schedule
