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

from functools import partial

import numpy as np

from tergite_tuner.backend import (
    X90,
    BinMode,
    DRAGPulse,
    ExtendedTransmon,
    Rxy,
    Schedule,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import (
    add_12_clocks,
    get_drive_clock,
    get_measure_operation,
    get_multiplexed_schedule,
    prepare_state,
)


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
        """Two pi/2 pulses ``ramsey_delays`` apart, the second's phase advanced by each artificial detuning."""
        schedule = get_multiplexed_schedule(
            f"multiplexed_ramsey_{qubit_state}{qubit_state + 1}",
            self.transmons,
            {
                "ramsey_delays": ramsey_delays,
                "artificial_detunings": artificial_detunings,
            },
            partial(self._add_point, qubit_state=qubit_state),
            repetitions,
            qubit_reset_ref_pt_new="end",
        )
        if qubit_state == 1:
            add_12_clocks(schedule, self.transmons)
        return schedule

    def _add_point(
        self,
        schedule: Schedule,
        qubit: str,
        point: dict,
        acq_index: int,
        *,
        qubit_state: int,
    ) -> None:
        delay = point["ramsey_delays"]
        recovery_phase = np.rad2deg(2 * np.pi * point["artificial_detunings"] * delay)
        if qubit_state == 0:
            schedule.add(X90(qubit))
            schedule.add(Rxy(theta=90, phi=recovery_phase, qubit=qubit), rel_time=delay)
        else:
            transmon = self.transmons[qubit]
            prepare_state(schedule, transmon, qubit_state)
            for phase, rel_time in ((0, 0), (recovery_phase, delay)):
                schedule.add(
                    DRAGPulse(
                        duration=transmon.rxy.duration(),
                        G_amp=transmon.r12.ef_amp180() / 2,
                        D_amp=0,
                        port=transmon.ports.microwave(),
                        clock=get_drive_clock(qubit, qubit_state),
                        phase=phase,
                    ),
                    rel_time=rel_time,
                )
        measure_operation = get_measure_operation(qubit_state)
        schedule.add(
            measure_operation(qubit, acq_index=acq_index, bin_mode=BinMode.AVERAGE),
        )
