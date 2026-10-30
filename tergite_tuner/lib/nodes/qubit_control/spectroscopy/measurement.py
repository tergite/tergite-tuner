# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Module containing a schedule class for two-tone (qubit) spectroscopy calibration.
"""

from functools import partial

import numpy as np

from tergite_tuner.backend import (
    BinMode,
    ClockResource,
    ExtendedTransmon,
    Measure,
    Schedule,
    SetClockFrequency,
    SoftSquarePulse,
    long_square_pulse,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import (
    get_drive_clock,
    get_measure_operation,
    get_multiplexed_schedule,
    prepare_state,
)
from tergite_tuner.utils.logging import logger


class TwoTonesMultidimMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon], *args):
        super().__init__(transmons)

        self.transmons = transmons

    def schedule_function(
        self,
        spec_frequencies: dict[str, np.ndarray],
        spec_pulse_amplitudes: dict[str, np.ndarray] = None,
        repetitions: int = 1024,
        qubit_state: int = 0,
    ) -> Schedule:
        """Sweeps each qubit's drive frequency and amplitude from ``qubit_state``, all qubits in parallel."""
        if spec_pulse_amplitudes is None:
            spec_pulse_amplitudes = {}
            for qubit in spec_frequencies:
                amplitude = self.transmons[qubit].spec.spec_ampl_optimal()
                logger.info(f"setting optimal spec_amplitude for {qubit} {amplitude}")
                spec_pulse_amplitudes[qubit] = [amplitude]

        schedule = get_multiplexed_schedule(
            "qubit_spectroscopy",
            self.transmons,
            {
                "spec_pulse_amplitudes": spec_pulse_amplitudes,
                "spec_frequencies": spec_frequencies,
            },
            partial(
                self._add_point,
                qubit_state=qubit_state,
                spec_pulse_amplitudes=spec_pulse_amplitudes,
            ),
            repetitions,
        )
        for qubit, frequencies in spec_frequencies.items():
            schedule.add_resource(
                ClockResource(
                    name=get_drive_clock(qubit, qubit_state), freq=frequencies[0]
                )
            )
        return schedule

    def _add_point(
        self,
        schedule: Schedule,
        qubit: str,
        point: dict,
        acq_index: int,
        *,
        qubit_state: int,
        spec_pulse_amplitudes: dict[str, np.ndarray],
    ) -> None:
        transmon = self.transmons[qubit]
        duration = transmon.spec.spec_duration()
        clock = get_drive_clock(qubit, qubit_state)
        # long pulses would not fit in the waveform memory
        pulse = long_square_pulse if duration > 6e-6 else SoftSquarePulse
        # the amplitudes vary fastest, so the frequency changes once per sweep of them
        if acq_index % len(spec_pulse_amplitudes[qubit]) == 0:
            schedule.add(
                SetClockFrequency(
                    clock=clock, clock_freq_new=point["spec_frequencies"]
                ),
            )
        prepare_state(schedule, transmon, qubit_state)
        schedule.add(
            pulse(
                duration=duration,
                amp=point["spec_pulse_amplitudes"],
                port=transmon.ports.microwave(),
                clock=clock,
            ),
        )
        measure_operation = get_measure_operation(qubit_state)
        schedule.add(
            measure_operation(qubit, acq_index=acq_index, bin_mode=BinMode.AVERAGE),
        )


class TwoTonesAmplitudeMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)

    def schedule_function(
        self,
        spec_frequencies: dict[str, np.ndarray],
        spec_pulse_amplitudes: dict[str, float],
    ) -> Schedule:

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            duration = transmon.spec.spec_duration()
            clock = f"{qubit}.01"
            # long pulses would not fit in the waveform memory
            pulse = long_square_pulse if duration > 6.5e-6 else SoftSquarePulse
            schedule.add(
                SetClockFrequency(
                    clock=clock, clock_freq_new=point["spec_frequencies"]
                ),
            )
            schedule.add(
                pulse(
                    duration=duration,
                    amp=spec_pulse_amplitudes[qubit],
                    port=transmon.ports.microwave(),
                    clock=clock,
                ),
            )
            schedule.add(Measure(qubit, acq_index=acq_index))

        schedule = get_multiplexed_schedule(
            "qubit_spectroscopy",
            self.transmons,
            {"spec_frequencies": spec_frequencies},
            add_point,
            repetitions=1024,
        )
        for qubit, frequencies in spec_frequencies.items():
            schedule.add_resource(
                ClockResource(name=f"{qubit}.01", freq=frequencies[0])
            )
        return schedule
