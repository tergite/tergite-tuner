# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Chalmers Next Labs AB 2024, 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import Any, Tuple

import numpy as np

from tergite_tuner.backend import (
    X90,
    ExtendedCompositeSquareEdge,
    ExtendedTransmon,
    IdlePulse,
    Reset,
    ResetClockPhase,
    Rxy,
    Schedule,
    SoftSquarePulse,
    X,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import (
    add_cz_clock,
    add_pair_measurement,
    get_repeated_schedule,
)


class CZCalibrationMeasurement(BaseMeasurement):
    def __init__(
        self,
        transmons: dict[str, ExtendedTransmon],
        couplers: dict[str, ExtendedCompositeSquareEdge],
    ):
        super().__init__(transmons)
        self.transmons = transmons
        self.couplers = couplers

    def ro_shot(
        self,
        ramsey_phases: dict[str, np.ndarray],
        control_ons: dict[str, np.ndarray],
        cz_working_points: dict[str, Tuple[float, float]],
        coupler_dict: dict[str, dict],
    ) -> Schedule:
        shot = Schedule("cz_calibration_shot", repetitions=1)
        qubits = self.transmons.keys()
        root = shot.add(IdlePulse(4e-9))
        for coupler in self.couplers:
            cz_frequency, cz_duration = cz_working_points[coupler]
            pair = (
                coupler_dict[coupler]["control_qubit"],
                coupler_dict[coupler]["target_qubit"],
            )
            add_cz_clock(shot, coupler, cz_frequency)
            # To enforce parallelism we refer to the root operation
            shot.add(Reset(*qubits), ref_op=root)
            phases = ramsey_phases[pair[1]]
            for outer_index, control_on in enumerate(control_ons[coupler]):
                for inner_index, ramsey_phase in enumerate(phases):
                    self._add_point(
                        shot,
                        coupler,
                        pair,
                        (cz_duration, control_on, ramsey_phase),
                        outer_index * len(phases) + inner_index,
                    )
        return shot

    def _add_point(
        self,
        shot: Schedule,
        coupler: str,
        pair: tuple[str, str],
        point: tuple[float, bool, float],
        acq_index: int,
    ) -> None:
        """A Ramsey on the target around ``coupler``'s CZ pulse, the control flipped there and back if on."""
        control_qubit, target_qubit = pair
        cz_duration, is_control_on, ramsey_phase = point
        start = shot.add(IdlePulse(4e-9))
        shot.add(X90(target_qubit), ref_op=start)
        initial = self._add_control_pulse(
            shot, coupler, control_qubit, is_control_on, start
        )
        cz = self._add_cz(shot, coupler, cz_duration, initial)
        shot.add(Rxy(theta=90, phi=ramsey_phase, qubit=target_qubit), ref_op=cz)
        final = self._add_control_pulse(shot, coupler, control_qubit, is_control_on, cz)
        add_pair_measurement(shot, pair, acq_index, final)
        shot.add(Reset(control_qubit, target_qubit))

    def _add_control_pulse(
        self, shot: Schedule, coupler: str, qubit: str, is_on: bool, ref_op: Any
    ) -> Any:
        """Flips ``qubit`` if on, or idles as long, after ``ref_op``."""
        if is_on:
            return shot.add(X(qubit), ref_op=ref_op)
        r_xy_duration = self.transmons[coupler.split("_")[0]].rxy.duration()
        return shot.add(IdlePulse(r_xy_duration), ref_op=ref_op)

    def _add_cz(
        self, shot: Schedule, coupler: str, duration: float, ref_op: Any
    ) -> Any:
        """``coupler``'s CZ pulse after ``ref_op``, its clock's phase reset first."""
        clock = f"{coupler}.cz"
        shot.add(ResetClockPhase(clock=clock), ref_op=ref_op)
        return shot.add(
            SoftSquarePulse(
                duration=duration,
                amp=self.couplers[coupler].cz.square_amp(),
                port=f"{coupler}:fl",
                clock=clock,
            ),
        )

    def schedule_function(
        self,
        ramsey_phases: dict[str, np.ndarray],
        control_ons: dict[str, np.ndarray],
        loop_repetitions: int,
        working_points: dict[str, Tuple[float, float]],
        coupler_dict: dict[str, dict],
        repetitions: int = 1,
    ) -> Schedule:

        cz_phase_shot = self.ro_shot(
            ramsey_phases,
            control_ons,
            cz_working_points=working_points,
            coupler_dict=coupler_dict,
        )

        return get_repeated_schedule(
            "cz_calibration", cz_phase_shot, loop_repetitions, 16e-9, repetitions
        )
