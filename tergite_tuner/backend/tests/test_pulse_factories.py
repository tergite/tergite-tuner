# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
import math

from tergite_tuner.backend.pulse_factories import composite_soft_square_pulse


def test_cz_shifts_no_phase_for_an_uncalibrated_correction():
    pulse = composite_soft_square_pulse(
        square_amp=0.1,
        square_duration=100e-9,
        square_port="q00_q01:fl",
        square_clock="q00_q01.cz",
        virt_z_parent_qubit_phase=math.nan,
        virt_z_parent_qubit_clock="q00.01",
        virt_z_child_qubit_phase=12.5,
        virt_z_child_qubit_clock="q01.01",
    )

    shifts = {
        info["clock"]: info["phase_shift"]
        for info in pulse.data["pulse_info"]
        if "phase_shift" in info
    }
    assert shifts == {"q00.01": 0, "q01.01": 12.5}
