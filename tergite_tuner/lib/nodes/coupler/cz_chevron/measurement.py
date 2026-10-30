# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman, 2024
# (C) Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import numpy as np

from tergite_tuner.backend import (
    ExtendedCompositeSquareEdge,
    ExtendedTransmon,
    IdlePulse,
    Reset,
    Schedule,
    SetClockFrequency,
    SoftSquarePulse,
    X,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import (
    add_cz_clock,
    add_pair_measurement,
    get_cz_clock_frequency,
    get_repeated_schedule,
)


class CZChevronMeasurement(BaseMeasurement):

    def __init__(
        self,
        transmons: dict[str, ExtendedTransmon],
        couplers: dict[str, ExtendedCompositeSquareEdge],
    ):
        super().__init__(transmons, couplers)
        self.couplers = couplers

    def cz_chevron(
        self,
        cz_duration_values: dict[str, np.ndarray],
        cz_frequency_values: dict[str, float],
    ) -> Schedule:
        cz_schedule = Schedule("CZ_chevron")

        root = cz_schedule.add(IdlePulse(4e-9))
        for coupler, edge in self.couplers.items():
            cz_amplitude = edge.cz.square_amp()
            cz_durations = cz_duration_values[coupler]
            cz_frequency = cz_frequency_values[coupler]
            qubits = coupler.split(sep="_")
            cz_clock = add_cz_clock(cz_schedule, coupler, cz_frequency)
            cz_pulse_port = f"{coupler}:fl"
            cz_schedule.add(
                SetClockFrequency(
                    clock=cz_clock,
                    clock_freq_new=get_cz_clock_frequency(cz_frequency),
                ),
            )

            cz_schedule.add(
                Reset(*qubits), ref_op=root
            )  # To enforce parallelism we refer to the root operation

            for index, cz_duration in enumerate(cz_durations):
                starting_op = cz_schedule.add(IdlePulse(4e-9))

                for qubit in qubits:
                    operation_11 = cz_schedule.add(X(qubit), ref_op=starting_op)

                flux_pulse = cz_schedule.add(
                    SoftSquarePulse(
                        duration=cz_duration,
                        amp=cz_amplitude,
                        port=cz_pulse_port,
                        clock=cz_clock,
                    ),
                    ref_op=operation_11,
                )

                add_pair_measurement(cz_schedule, qubits, index, flux_pulse)

                cz_schedule.add(Reset(*qubits))
        return cz_schedule

    def schedule_function(
        self,
        cz_pulse_durations: dict[str, np.ndarray],
        cz_pulse_frequencies: dict[str, float],
        loop_repetitions: int,
        repetitions: int = 1,
    ) -> Schedule:

        cz_chevron_shot = self.cz_chevron(
            cz_duration_values=cz_pulse_durations,
            cz_frequency_values=cz_pulse_frequencies,
        )

        return get_repeated_schedule(
            "CZ_chevron", cz_chevron_shot, loop_repetitions, 8e-9, repetitions
        )
