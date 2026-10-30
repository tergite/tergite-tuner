# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman 2024
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
    X90,
    BinMode,
    ClockResource,
    DRAGPulse,
    ExtendedTransmon,
    Measure,
    Measure_RO1,
    Rxy,
    Schedule,
    X,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import get_multiplexed_schedule


class RamseyDetuningsMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)

    def schedule_function(
        self,
        artificial_detunings: dict[str, np.ndarray],
        ramsey_delays: dict[str, np.ndarray],
        repetitions: int = 1024,
        qubit_state: int = 0,
    ) -> Schedule:
        """
        Generate a schedule for performing a Ramsey fringe measurement on multiple qubits.
        Can be used both to finetune the qubit frequency and to measure the qubit dephasing time T_2. (1D parameter sweep)

        Schedule sequence
            Reset -> pi/2-pulse -> Idle(tau) -> pi/2-pulse -> Measure

        Parameters
        ----------
        artificial_detuning
            The artificial detuning of the qubit frequency, which is implemented by changing
            the phase of the second pi/2 pulse.
        ramsey_delays
            The wait times tau between the pi/2 pulses for each qubit
        repetitions
            The amount of times the Schedule will be repeated.

        Returns
        -------
        :
            An experiment schedule.
        """

        if qubit_state == 0:
            schedule_title = "multiplexed_ramsey_01"
            measure_function = Measure
        elif qubit_state == 1:
            schedule_title = "multiplexed_ramsey_12"
            measure_function = Measure_RO1
        else:
            raise ValueError(f"Invalid qubit state: {qubit_state}")

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            delay = point["ramsey_delays"]
            recovery_phase = np.rad2deg(
                2 * np.pi * point["artificial_detunings"] * delay
            )
            if qubit_state == 0:
                schedule.add(X90(qubit))
                schedule.add(
                    Rxy(theta=90, phi=recovery_phase, qubit=qubit), rel_time=delay
                )
            else:
                transmon = self.transmons[qubit]
                schedule.add(X(qubit))
                for phase, rel_time in ((0, 0), (recovery_phase, delay)):
                    schedule.add(
                        DRAGPulse(
                            duration=transmon.rxy.duration(),
                            G_amp=transmon.r12.ef_amp180() / 2,
                            D_amp=0,
                            port=transmon.ports.microwave(),
                            clock=f"{qubit}.12",
                            phase=phase,
                        ),
                        rel_time=rel_time,
                    )
            schedule.add(
                measure_function(qubit, acq_index=acq_index, bin_mode=BinMode.AVERAGE),
            )

        schedule = get_multiplexed_schedule(
            schedule_title,
            self.transmons,
            {
                "ramsey_delays": ramsey_delays,
                "artificial_detunings": artificial_detunings,
            },
            add_point,
            repetitions,
            qubit_reset_ref_pt_new="end",
        )
        if qubit_state == 1:
            for qubit, transmon in self.transmons.items():
                frequency = transmon.clock_freqs.f12()
                schedule.add_resource(ClockResource(name=f"{qubit}.12", freq=frequency))
        return schedule
