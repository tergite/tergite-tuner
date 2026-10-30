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

# the readout clock for two- and three-state discrimination
READOUT_CLOCKS = {2: "ro_2st_opt", 3: "ro_3st_opt"}


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
        qubits = list(self.transmons)
        number_of_states = len(qubit_states[qubits[0]])
        if number_of_states not in READOUT_CLOCKS:
            raise ValueError("invalid number of states")
        self.ro_str = READOUT_CLOCKS[number_of_states]
        for qubit, frequencies in ro_opt_frequencies.items():
            schedule.add_resource(
                ClockResource(name=f"{qubit}.{self.ro_str}", freq=frequencies[0])
            )
        if number_of_states == 3:
            add_12_clocks(schedule, self.transmons)

        measurements = {
            0: self.measure,
            1: self.measure_first_excited,
            2: self.measure_second_excited,
        }
        root_relaxation = schedule.add(Reset(*qubits), label="Reset")
        for qubit, frequencies in ro_opt_frequencies.items():
            # To enforce parallelism we refer to the root relaxation
            schedule.add(Reset(*qubits), ref_op=root_relaxation)
            for acq_index, frequency in enumerate(frequencies):
                schedule.add(
                    SetClockFrequency(
                        clock=f"{qubit}.{self.ro_str}", clock_freq_new=frequency
                    ),
                )
                for state in qubit_states[qubit]:
                    measurements[state](
                        schedule,
                        self.transmons[qubit],
                        acq_index + int(state) * len(frequencies),
                    )
        return schedule
