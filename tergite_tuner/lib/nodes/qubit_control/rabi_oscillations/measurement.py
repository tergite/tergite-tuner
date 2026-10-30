# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman 2024
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
    DRAGPulse,
    ExtendedTransmon,
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


class RabiOscillationsMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)
        self.transmons = transmons

    def schedule_function(
        self,
        mw_amplitudes: dict[str, np.ndarray],
        repetitions: int = 1024,
        qubit_state: int = 0,
    ) -> Schedule:
        """Drives each qubit with a DRAG pulse at each of its mw_amplitudes, then measures it."""
        measure = get_measure_operation(qubit_state)

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            if qubit_state == 0:
                duration = transmon.rxy.duration()
            else:
                duration = transmon.r12.ef_duration()
            prepare_state(schedule, transmon, qubit_state)
            schedule.add(
                DRAGPulse(
                    duration=duration,
                    G_amp=point["mw_amplitudes"],
                    D_amp=0,
                    port=transmon.ports.microwave(),
                    clock=get_drive_clock(qubit, qubit_state),
                    phase=0,
                ),
            )
            schedule.add(measure(qubit, acq_index=acq_index))

        schedule = get_multiplexed_schedule(
            f"rabi_{qubit_state}{qubit_state + 1}_oscillations",
            self.transmons,
            {"mw_amplitudes": mw_amplitudes},
            add_point,
            repetitions,
        )
        if qubit_state == 0:
            for qubit, transmon in self.transmons.items():
                frequency = transmon.clock_freqs.f01()
                schedule.add_resource(ClockResource(name=f"{qubit}.01", freq=frequency))
        else:
            add_12_clocks(schedule, self.transmons)
        return schedule


class NRabiOscillationsMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)
        self.transmons = transmons

    def schedule_function(
        self,
        mw_amplitudes_sweep: dict[str, np.ndarray],
        X_repetitions: dict[str, np.ndarray],
        repetitions: int = 1024,
        qubit_state: int = 0,
    ) -> Schedule:
        """Applies X_repetitions DRAG pulses at each of the mw_amplitudes_sweep, then measures."""
        measure = get_measure_operation(qubit_state)

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            if qubit_state == 0:
                duration = transmon.rxy.duration()
                amplitude = transmon.rxy.amp180()
                motzoi = transmon.rxy.motzoi()
            else:
                duration = transmon.r12.ef_duration()
                amplitude = transmon.r12.ef_amp180()
                motzoi = transmon.r12.ef_motzoi()
            prepare_state(schedule, transmon, qubit_state)
            pulse = DRAGPulse(
                duration=duration,
                G_amp=amplitude + point["mw_amplitudes_sweep"],
                D_amp=motzoi,
                port=transmon.ports.microwave(),
                clock=get_drive_clock(qubit, qubit_state),
                phase=0,
            )
            for _ in range(2 * point["X_repetitions"]):
                schedule.add(pulse)
            schedule.add(measure(qubit, acq_index=acq_index))

        schedule = get_multiplexed_schedule(
            "n_rabi_oscillations" if qubit_state == 0 else "n_rabi_12_oscillations",
            self.transmons,
            {
                "mw_amplitudes_sweep": mw_amplitudes_sweep,
                "X_repetitions": X_repetitions,
            },
            add_point,
            repetitions,
        )
        if qubit_state == 1:
            add_12_clocks(schedule, self.transmons)
        return schedule
