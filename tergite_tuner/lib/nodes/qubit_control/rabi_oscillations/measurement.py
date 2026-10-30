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
    Measure,
    Measure_RO1,
    Schedule,
    X,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import get_multiplexed_schedule


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
        if qubit_state == 0:
            schedule_title = "rabi_01_oscillations"
            measure_function = Measure
        elif qubit_state == 1:
            schedule_title = "rabi_12_oscillations"
            measure_function = Measure_RO1
        else:
            raise ValueError(f"Invalid qubit state: {qubit_state}")

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            if qubit_state == 0:
                clock = f"{qubit}.01"
                duration = transmon.rxy.duration()
            else:
                clock = f"{qubit}.12"
                duration = transmon.r12.ef_duration()
                schedule.add(X(qubit))
            schedule.add(
                DRAGPulse(
                    duration=duration,
                    G_amp=point["mw_amplitudes"],
                    D_amp=0,
                    port=transmon.ports.microwave(),
                    clock=clock,
                    phase=0,
                ),
            )
            schedule.add(measure_function(qubit, acq_index=acq_index))

        schedule = get_multiplexed_schedule(
            schedule_title,
            self.transmons,
            {"mw_amplitudes": mw_amplitudes},
            add_point,
            repetitions,
        )
        for qubit, transmon in self.transmons.items():
            if qubit_state == 0:
                frequency = transmon.clock_freqs.f01()
                schedule.add_resource(ClockResource(name=f"{qubit}.01", freq=frequency))
            else:
                frequency = transmon.clock_freqs.f12()
                schedule.add_resource(ClockResource(name=f"{qubit}.12", freq=frequency))
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
        if qubit_state == 0:
            schedule_title = "n_rabi_oscillations"
            measure_function = Measure
        elif qubit_state == 1:
            schedule_title = "n_rabi_12_oscillations"
            measure_function = Measure_RO1
        else:
            raise ValueError(f"Invalid qubit state: {qubit_state}")

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            if qubit_state == 0:
                duration = transmon.rxy.duration()
                amplitude = transmon.rxy.amp180()
                motzoi = transmon.rxy.motzoi()
                clock = f"{qubit}.01"
            else:
                duration = transmon.r12.ef_duration()
                amplitude = transmon.r12.ef_amp180()
                motzoi = transmon.r12.ef_motzoi()
                clock = f"{qubit}.12"
                schedule.add(X(qubit))
            pulse = DRAGPulse(
                duration=duration,
                G_amp=amplitude + point["mw_amplitudes_sweep"],
                D_amp=motzoi,
                port=transmon.ports.microwave(),
                clock=clock,
                phase=0,
            )
            for _ in range(2 * point["X_repetitions"]):
                schedule.add(pulse)
            schedule.add(measure_function(qubit, acq_index=acq_index))

        schedule = get_multiplexed_schedule(
            schedule_title,
            self.transmons,
            {
                "mw_amplitudes_sweep": mw_amplitudes_sweep,
                "X_repetitions": X_repetitions,
            },
            add_point,
            repetitions,
        )
        if qubit_state == 1:
            for qubit, transmon in self.transmons.items():
                frequency = transmon.clock_freqs.f12()
                schedule.add_resource(ClockResource(name=f"{qubit}.12", freq=frequency))
        return schedule
