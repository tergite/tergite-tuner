# This code is part of Tergite
#
# (C) Copyright Joel Sandås 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Module containing a schedule class for purity benchmarking measurement.
"""

import numpy as np

from tergite_tuner.backend import (
    X90,
    ExtendedTransmon,
    H,
    Measure,
    Reset,
    Rxy,
    Schedule,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.cliffords.clifford_group import get_rxy_angles
from tergite_tuner.lib.utils.cliffords.randomized_benchmarking import (
    randomized_benchmarking_sequence,
)
from tergite_tuner.lib.utils.schedules import prepare_state


class PurityBenchmarkingMeasurement(BaseMeasurement):
    """Class that contains measurement scheduele for purity benchmarking"""

    def __init__(self, transmons: dict[str, ExtendedTransmon], qubit_state: int = 0):
        super().__init__(transmons)
        self.qubit_state = qubit_state
        self.transmons = transmons
        # Initialize dictionaries to store raw measurement data for each qubit and each basis

    def schedule_function(
        self,
        seeds: dict[str, int],
        number_of_cliffords: dict[str, np.ndarray],
        repetitions: int = 1024,
    ) -> Schedule:
        """Each qubit's random Clifford sequences, each measured in X, Y and Z, then the calibration points."""
        schedule = Schedule("purity_benchmarking", repetitions)
        qubits = self.transmons.keys()
        # This is the common reference operation so the qubits can be operated in parallel
        root_relaxation = schedule.add(Reset(*qubits), label="Start")
        for qubit, lengths in number_of_cliffords.items():
            rng = np.random.default_rng(seeds[qubit])
            schedule.add(Reset(*qubits), ref_op=root_relaxation, ref_pt="end")
            acq_index = 0
            # the last three lengths are the calibration points'; each length runs once
            for length in np.unique(lengths[:-3]):
                sequence = randomized_benchmarking_sequence(
                    length, apply_inverse=False, seed=rng
                )
                # purity needs all three
                for basis in ("X", "Y", "Z"):
                    self._add_basis_measurement(
                        schedule, qubit, sequence, basis, acq_index
                    )
                    acq_index += 1
            self._add_calibration_points(schedule, qubit, acq_index)
        return schedule

    def _add_basis_measurement(
        self,
        schedule: Schedule,
        qubit: str,
        sequence: np.ndarray,
        basis: str,
        acq_index: int,
    ) -> None:
        """Applies ``sequence``'s Cliffords, then rotates ``basis`` onto Z and measures."""
        for clifford in sequence:
            for theta, phi in get_rxy_angles(clifford):
                schedule.add(Rxy(qubit=qubit, theta=theta, phi=phi))
        if basis == "X":
            schedule.add(H(qubit))
        elif basis == "Y":
            schedule.add(X90(qubit))
        schedule.add(Measure(qubit, acq_index=acq_index))
        schedule.add(Reset(qubit))

    def _add_calibration_points(
        self, schedule: Schedule, qubit: str, acq_index: int
    ) -> None:
        """Measures |0>, |1> and |2> from ``acq_index`` on; the analysis does not use |2>."""
        schedule.add(Reset(qubit))
        for state in (0, 1, 2):
            prepare_state(schedule, self.transmons[qubit], state)
            schedule.add(Measure(qubit, acq_index=acq_index + state))
            schedule.add(Reset(qubit))
