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

from typing import Tuple

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
    ):
        shot = Schedule("cz_calibration_shot", repetitions=1)

        qubits = self.transmons.keys()
        root = shot.add(IdlePulse(4e-9))

        for this_coupler in self.couplers:

            cz_frequency, cz_duration = cz_working_points[this_coupler]
            control_on_values = control_ons[this_coupler]
            control_qubit = coupler_dict[this_coupler]["control_qubit"]
            target_qubit = coupler_dict[this_coupler]["target_qubit"]

            # unpack the static parameters:
            this_edge = self.couplers[this_coupler]
            cz_amplitude = this_edge.cz.square_amp()
            cz_clock = f"{this_coupler}.cz"
            cz_pulse_port = f"{this_coupler}:fl"

            add_cz_clock(shot, this_coupler, cz_frequency)

            connected_qubits = this_coupler.split("_")
            first_qubit = connected_qubits[0]
            first_transmon = self.transmons[first_qubit]
            r_xy_duration = first_transmon.rxy.duration()

            shot.add(
                Reset(*qubits), ref_op=root
            )  # To enforce parallelism we refer to the root operation

            ramsey_phases_values = ramsey_phases[target_qubit]
            number_of_inners = len(ramsey_phases_values)
            for outer_index, control_on in enumerate(control_on_values):

                for inner_index, ramsey_phase in enumerate(ramsey_phases_values):
                    starting_op = shot.add(IdlePulse(4e-9))

                    this_index = outer_index * number_of_inners + inner_index
                    initial = shot.add(X90(target_qubit), ref_op=starting_op)
                    if control_on:
                        initial = shot.add(X(control_qubit), ref_op=starting_op)
                    else:
                        initial = shot.add(IdlePulse(r_xy_duration), ref_op=starting_op)

                    shot.add(ResetClockPhase(clock=cz_clock), ref_op=initial)
                    cz = shot.add(
                        SoftSquarePulse(
                            duration=cz_duration,
                            amp=cz_amplitude,
                            port=cz_pulse_port,
                            clock=cz_clock,
                        ),
                    )

                    final = shot.add(
                        Rxy(theta=90, phi=ramsey_phase, qubit=target_qubit),
                        ref_op=cz,
                    )
                    if control_on:
                        final = shot.add(X(control_qubit), ref_op=cz)
                    else:
                        final = shot.add(IdlePulse(r_xy_duration), ref_op=cz)

                    add_pair_measurement(
                        shot, (control_qubit, target_qubit), this_index, final
                    )

                    shot.add(Reset(control_qubit, target_qubit))

        return shot

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
