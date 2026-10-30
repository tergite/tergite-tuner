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
Module containing a schedule class for punchout (readout amplitude) calibration.
"""

import numpy as np

from tergite_tuner.backend import (
    BinMode,
    ClockResource,
    Schedule,
    SetClockFrequency,
    SquarePulse,
    SSBIntegrationComplex,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import get_multiplexed_schedule


class PunchoutMeasurement(BaseMeasurement):
    def __init__(self, transmons, qubit_state: int = 0):
        super().__init__(transmons)
        self.qubit_state = qubit_state
        self.transmons = transmons

    def schedule_function(
        self,
        ro_frequencies: dict[str, np.ndarray],
        ro_amplitudes: dict[str, np.ndarray],
        repetitions: int = 1024,
    ) -> Schedule:
        acq_channels = {qubit: channel for channel, qubit in enumerate(ro_amplitudes)}

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            clock = f"{qubit}.ro"
            ro_port = transmon.ports.readout()
            schedule.add(
                SetClockFrequency(clock=clock, clock_freq_new=point["ro_frequencies"]),
            )
            schedule.add(
                SquarePulse(
                    duration=transmon.measure.pulse_duration(),
                    amp=point["ro_amplitudes"],
                    port=ro_port,
                    clock=clock,
                ),
                ref_pt="end",
            )
            schedule.add(
                SSBIntegrationComplex(
                    duration=transmon.measure.integration_time(),
                    port=ro_port,
                    clock=clock,
                    acq_index=acq_index,
                    acq_channel=acq_channels[qubit],
                    bin_mode=BinMode.AVERAGE,
                ),
                ref_pt="start",
                rel_time=transmon.measure.acq_delay(),
                label=f"acquisition_{qubit}_{acq_index}",
            )

        schedule = get_multiplexed_schedule(
            "mltplx_punchout",
            self.transmons,
            {"ro_frequencies": ro_frequencies, "ro_amplitudes": ro_amplitudes},
            add_point,
            repetitions,
            qubit_reset_ref_pt_new="end",
        )
        for qubit, frequencies in ro_frequencies.items():
            schedule.add_resource(
                ClockResource(name=f"{qubit}.ro", freq=frequencies[0])
            )
        return schedule
