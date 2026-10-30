# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2026
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
    BinMode,
    ClockResource,
    ExtendedTransmon,
    IdlePulse,
    LoopOperation,
    Reset,
    Schedule,
    SquarePulse,
    SSBIntegrationComplex,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import add_12_clocks, prepare_state


class ROAmplitudeOptimizationMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)

        self.transmons = transmons

    def ro_shot(
        self,
        ro_amplitudes: dict[str, np.ndarray],
        qubit_states: dict[str, np.ndarray],
        qubit_state: int = 1,
    ) -> Schedule:
        shot = Schedule("ro_amplitude_optimization_shots", repetitions=1)
        clock_suffix = self._add_clocks(shot, qubit_state)
        qubits = self.transmons.keys()
        root_relaxation = shot.add(Reset(*qubits), label="Reset")
        for acq_channel, (qubit, amplitudes) in enumerate(ro_amplitudes.items()):
            # To enforce parallelism we refer to the root relaxation
            shot.add(Reset(*qubits), ref_op=root_relaxation)
            levels = qubit_states[qubit]
            for amplitude_index, amplitude in enumerate(amplitudes):
                for level_index, level in enumerate(levels):
                    self._add_readout(
                        shot,
                        self.transmons[qubit],
                        level,
                        amplitude,
                        f"{qubit}.{clock_suffix}",
                        (amplitude_index * len(levels) + level_index, acq_channel),
                    )
                    shot.add(Reset(qubit))
        return shot

    def _add_clocks(self, shot: Schedule, qubit_state: int) -> str:
        """Adds each qubit's optimal readout clock for 2 or 3 states and returns the clocks' suffix."""
        if qubit_state not in (1, 2):
            raise ValueError(f"Invalid state {qubit_state}")
        suffix = "ro_2st_opt" if qubit_state == 1 else "ro_3st_opt"
        for qubit, transmon in self.transmons.items():
            clocks = transmon.extended_clock_freqs
            frequency = (
                clocks.readout_2state_opt()
                if qubit_state == 1
                else clocks.readout_3state_opt()
            )
            shot.add_resource(ClockResource(name=f"{qubit}.{suffix}", freq=frequency))
        if qubit_state == 2:
            add_12_clocks(shot, self.transmons)
        return suffix

    def _add_readout(
        self,
        shot: Schedule,
        transmon: ExtendedTransmon,
        level: int,
        amplitude: float,
        clock: str,
        acquisition: tuple[int, int],
    ) -> None:
        """Prepares ``level`` and reads it out at ``amplitude`` into ``acquisition``'s index and channel."""
        if level == 0:
            preparation = shot.add(IdlePulse(transmon.rxy.duration()))
        elif level in (1, 2):
            preparation = prepare_state(shot, transmon, level)
        else:
            raise ValueError("State Input Error")
        acq_index, acq_channel = acquisition
        port = transmon.ports.readout()
        ro_pulse = shot.add(
            SquarePulse(
                duration=transmon.measure.pulse_duration(),
                amp=amplitude,
                port=port,
                clock=clock,
            ),
            ref_op=preparation,
        )
        shot.add(
            SSBIntegrationComplex(
                duration=transmon.measure.integration_time(),
                port=port,
                clock=clock,
                acq_index=acq_index,
                acq_channel=acq_channel,
                bin_mode=BinMode.APPEND,
            ),
            ref_op=ro_pulse,
            ref_pt="start",
            rel_time=transmon.measure.acq_delay(),
        )

    def schedule_function(
        self,
        ro_amplitudes: dict[str, np.ndarray],
        qubit_states: dict[str, np.ndarray],
        loop_repetitions: int,
        qubit_state: int = 1,
    ) -> Schedule:
        schedule = Schedule("RO_amplitude_optimization", repetitions=1)
        ro_shot_schedule = self.ro_shot(ro_amplitudes, qubit_states, qubit_state)

        schedule.add(IdlePulse(8e-9))
        schedule.add(LoopOperation(body=ro_shot_schedule, repetitions=loop_repetitions))
        schedule.add(IdlePulse(8e-9))
        return schedule
