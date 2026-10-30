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

import numpy as np

from tergite_tuner.backend import (
    BinMode,
    ClockResource,
    ExtendedTransmon,
    Measure,
    Measure_RO1,
    Schedule,
    SetClockFrequency,
    SoftSquarePulse,
    X,
    long_square_pulse,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import get_multiplexed_schedule
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
        """
        Generate a schedule for performing two-tone (qubit) spectroscopy to locate the qubits resonance frequency for multiple qubits.

        Schedule sequence
            Reset -> Spectroscopy pulse -> Measure

        Parameters
        ----------
        repetitions
            The amount of times the Schedule will be repeated.

        Returns
        -------
        :
            An experiment schedule.
        """

        if qubit_state == 0:
            measure_function = Measure
            clock_name = "01"
        elif qubit_state == 1:
            measure_function = Measure_RO1
            clock_name = "12"
        else:
            raise ValueError(f"Invalid qubit state: {qubit_state}")

        if spec_pulse_amplitudes is None:
            spec_pulse_amplitudes = {}
            for qubit in spec_frequencies:
                amplitude = self.transmons[qubit].spec.spec_ampl_optimal()
                logger.info(f"setting optimal spec_amplitude for {qubit} {amplitude}")
                spec_pulse_amplitudes[qubit] = [amplitude]

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            duration = transmon.spec.spec_duration()
            clock = f"{qubit}.{clock_name}"
            # long pulses would not fit in the waveform memory
            pulse = long_square_pulse if duration > 6e-6 else SoftSquarePulse
            if acq_index % len(spec_pulse_amplitudes[qubit]) == 0:
                schedule.add(
                    SetClockFrequency(
                        clock=clock, clock_freq_new=point["spec_frequencies"]
                    ),
                )
            if qubit_state == 1:
                schedule.add(X(qubit))
            schedule.add(
                pulse(
                    duration=duration,
                    amp=point["spec_pulse_amplitudes"],
                    port=transmon.ports.microwave(),
                    clock=clock,
                ),
            )
            schedule.add(
                measure_function(qubit, acq_index=acq_index, bin_mode=BinMode.AVERAGE),
            )

        schedule = get_multiplexed_schedule(
            "qubit_spectroscopy",
            self.transmons,
            {
                "spec_pulse_amplitudes": spec_pulse_amplitudes,
                "spec_frequencies": spec_frequencies,
            },
            add_point,
            repetitions,
        )
        for qubit, frequencies in spec_frequencies.items():
            schedule.add_resource(
                ClockResource(name=f"{qubit}.{clock_name}", freq=frequencies[0])
            )
        return schedule


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
