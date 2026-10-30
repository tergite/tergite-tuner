# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Module containing a schedule class for resonator spectroscopy calibration.
"""

import numpy as np

from tergite_tuner.backend import (
    BinMode,
    ClockResource,
    ExtendedTransmon,
    Schedule,
    SetClockFrequency,
    SquarePulse,
    SSBIntegrationComplex,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import (
    add_12_clocks,
    get_multiplexed_schedule,
    prepare_state,
)


class ResonatorSpectroscopyMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon], *args):
        super().__init__(transmons)
        self.transmons = transmons

    def schedule_function(
        self,
        ro_frequencies: dict[str, np.ndarray],
        repetitions: int = 1024,
        qubit_state: int = 0,
    ) -> Schedule:
        """
        Generate a schedule for performing resonator spectroscopy to locate the resonators resonance frequency for multiple qubits.

        Schedule sequence
            Reset -> Spectroscopy pulse -> SSBIntegrationComplex (Measurement)

        Parameters
        ----------
        ro_frequencies
            The sweeping frequencies of the spectroscopy pulse for each qubit.
        repetitions
            The amount of times the Schedule will be repeated.

        Returns
        -------
        :
            An experiment schedule.
        """

        if qubit_state == 0:
            ro_str = "ro"
        elif qubit_state == 1:
            ro_str = "ro1"
        elif qubit_state == 2:
            ro_str = "ro2"
        else:
            raise ValueError("error state")
        acq_channels = {qubit: channel for channel, qubit in enumerate(ro_frequencies)}

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            ro_clock = f"{qubit}.{ro_str}"
            ro_port = transmon.ports.readout()
            schedule.add(
                SetClockFrequency(
                    clock=ro_clock, clock_freq_new=point["ro_frequencies"]
                )
            )
            prepare_state(schedule, transmon, qubit_state)
            ro_pulse = schedule.add(
                SquarePulse(
                    duration=transmon.measure.pulse_duration(),
                    amp=transmon.measure.pulse_amp(),
                    port=ro_port,
                    clock=ro_clock,
                ),
            )
            schedule.add(
                SSBIntegrationComplex(
                    duration=transmon.measure.integration_time(),
                    port=ro_port,
                    clock=ro_clock,
                    acq_index=acq_index,
                    acq_channel=acq_channels[qubit],
                    bin_mode=BinMode.AVERAGE,
                ),
                ref_op=ro_pulse,
                ref_pt="start",
                rel_time=transmon.measure.acq_delay(),
            )

        schedule = get_multiplexed_schedule(
            "multiplexed_resonator_spectroscopy",
            self.transmons,
            {"ro_frequencies": ro_frequencies},
            add_point,
            repetitions,
        )
        for qubit, frequencies in ro_frequencies.items():
            schedule.add_resource(
                ClockResource(name=f"{qubit}.{ro_str}", freq=frequencies[0])
            )
        if qubit_state == 2:
            add_12_clocks(schedule, self.transmons)
        return schedule
