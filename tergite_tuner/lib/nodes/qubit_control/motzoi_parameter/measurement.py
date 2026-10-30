# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2026
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Abdullah Al Amin 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
Module containing a schedule class for DRAG pulse motzoi parameter calibration.
"""

import numpy as np

from tergite_tuner.backend import (
    BinMode,
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


class MotzoiParameterMeasurement(BaseMeasurement):
    def __init__(self, transmons: dict[str, ExtendedTransmon]):
        super().__init__(transmons)
        self.transmons = transmons

    def schedule_function(
        self,
        mw_motzois: dict[str, np.ndarray],
        X_repetitions: int | dict[str, np.ndarray],
        repetitions: int = 1024,
        qubit_state: int = 0,
    ) -> Schedule:
        """Applies a DRAG pulse and its inverse X_repetitions times at each of the mw_motzois, then measures.

        The repetitions amplify the phase error that the right motzoi cancels.
        """
        if qubit_state == 0:
            schedule_title = "motzoi_01_parameter"
            measure_function = Measure
        elif qubit_state == 1:
            schedule_title = "motzoi_12_parameter"
            measure_function = Measure_RO1
        else:
            raise ValueError(f"Invalid qubit state: {qubit_state}")
        phases = (0, 180, 90, 270) if qubit_state == 0 else (0, 180)

        def add_point(
            schedule: Schedule, qubit: str, point: dict, acq_index: int
        ) -> None:
            transmon = self.transmons[qubit]
            if qubit_state == 0:
                amplitude = transmon.rxy.amp180()
                clock = f"{qubit}.01"
            else:
                amplitude = transmon.r12.ef_amp180()
                clock = f"{qubit}.12"
                schedule.add(X(qubit))
            for _ in range(point["X_repetitions"]):
                # each pulse is followed by its inverse, 180 degrees on
                for phase in phases:
                    schedule.add(
                        DRAGPulse(
                            duration=transmon.rxy.duration(),
                            G_amp=amplitude,
                            D_amp=point["mw_motzois"],
                            port=transmon.ports.microwave(),
                            clock=clock,
                            phase=phase,
                        ),
                    )
            schedule.add(
                measure_function(qubit, acq_index=acq_index, bin_mode=BinMode.AVERAGE),
            )

        schedule = get_multiplexed_schedule(
            schedule_title,
            self.transmons,
            {"mw_motzois": mw_motzois, "X_repetitions": X_repetitions},
            add_point,
            repetitions,
            qubit_reset_ref_pt_new="end",
            root_reset_duration=4e-9,
        )
        for qubit, transmon in self.transmons.items():
            frequency_01 = transmon.clock_freqs.f01()
            schedule.add_resource(ClockResource(name=f"{qubit}.01", freq=frequency_01))
            if qubit_state == 1:
                frequency_12 = transmon.clock_freqs.f12()
                schedule.add_resource(
                    ClockResource(name=f"{qubit}.12", freq=frequency_12)
                )
        return schedule
