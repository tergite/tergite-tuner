# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Chalmers Next Labs 2026
# (C) Copyright Abdullah Al Amin 2026
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
    ClockResource,
    ExtendedTransmon,
    Reset,
    Schedule,
    SetClockFrequency,
    SquarePulse,
    SSBIntegrationComplex,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import add_12_clocks, prepare_state


class ROFrequencyOptimizationMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)
        self.transmons = transmons

    def measure(self, schedule: Schedule, transmon: ExtendedTransmon, acq_index: int):

        this_qubit = transmon.name
        measure = transmon.measure
        acq_cha = measure.acq_channel()
        this_ro_clock = f"{this_qubit}." + self.ro_str

        ro_pulse = schedule.add(
            SquarePulse(
                duration=measure.pulse_duration(),
                amp=measure.pulse_amp(),
                port=transmon.ports.readout(),
                clock=this_ro_clock,
            )
        )
        schedule.add(
            SSBIntegrationComplex(
                duration=measure.integration_time(),
                port=transmon.ports.readout(),
                clock=this_ro_clock,
                acq_index=acq_index,
                acq_channel=acq_cha,
            ),
            ref_op=ro_pulse,
            ref_pt="start",
            rel_time=measure.acq_delay(),
        )

        schedule.add(Reset(this_qubit))

    def measure_first_excited(
        self, schedule: Schedule, transmon: ExtendedTransmon, acq_index: int
    ):
        prepare_state(schedule, transmon, 1)
        self.measure(schedule, transmon, acq_index)

    def measure_second_excited(
        self, schedule: Schedule, transmon: ExtendedTransmon, acq_index: int
    ):
        prepare_state(schedule, transmon, 2)
        self.measure(schedule, transmon, acq_index)
        schedule.add(Reset(transmon.name))

    def schedule_function(
        self,
        ro_opt_frequencies: dict[str, np.ndarray],
        qubit_states: dict[str, list[int]],
        repetitions: int = 1024,
    ) -> Schedule:
        schedule = Schedule("ro_frequency_optimization", repetitions)

        qubits = self.transmons.keys()
        if len(qubit_states[list(qubits)[0]]) == 2:
            self.ro_str = "ro_2st_opt"
        elif len(qubit_states[list(qubits)[0]]) == 3:
            self.ro_str = "ro_3st_opt"
        else:
            raise ValueError("invalid number of states")

        # Initialize ClockResource with the first frequency value
        for this_qubit, ro_array_val in ro_opt_frequencies.items():
            this_ro_clock = f"{this_qubit}." + self.ro_str
            schedule.add_resource(
                ClockResource(name=this_ro_clock, freq=ro_array_val[0])
            )

        if len(qubit_states[list(qubits)[0]]) == 3:
            add_12_clocks(schedule, self.transmons)

        root_relaxation = schedule.add(Reset(*qubits), label="Reset")

        # The first for loop iterates over all qubits:
        for this_qubit, ro_f_values in ro_opt_frequencies.items():

            this_transmon = self.transmons[this_qubit]

            schedule.add(
                Reset(*qubits), ref_op=root_relaxation
            )  # To enforce parallelism we refer to the root relaxation

            this_ro_clock = f"{this_qubit}." + self.ro_str

            this_qubit_states = qubit_states[this_qubit]

            number_of_frequencies = len(ro_f_values)

            for acq_index, ro_frequency in enumerate(ro_f_values):
                schedule.add(
                    SetClockFrequency(clock=this_ro_clock, clock_freq_new=ro_frequency),
                )

                # The third for loop iterates over all qubit states
                for qubit_state in this_qubit_states:
                    if qubit_state == 0:
                        this_index = acq_index
                        self.measure(schedule, this_transmon, this_index)
                    # repeat for when the qubit is at |1>
                    elif qubit_state == 1:
                        this_index = acq_index + number_of_frequencies
                        self.measure_first_excited(schedule, this_transmon, this_index)
                    # repeat for when the qubit is at |2>
                    elif qubit_state == 2:
                        this_index = acq_index + 2 * number_of_frequencies
                        self.measure_second_excited(schedule, this_transmon, this_index)

        return schedule
