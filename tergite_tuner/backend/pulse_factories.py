# This code is part of Tergite
#
# (C) Copyright Liangyu Chen 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
#
# This is a modification of the following code:
# Repository: https://gitlab.com/quantify-os/quantify-scheduler
# Licensed according to the LICENCE file on the main branch
"""
A module containing factory functions for pulses on the quantum-device layer.

These factories are used to take a parametrized representation of on a operation
and use that to create an instance of the operation itself.
"""

import math

from quantify_scheduler.operations import pulse_library

from tergite_tuner.utils.logging import logger


def composite_soft_square_pulse(  # pylint: disable=too-many-arguments
    square_amp: float,
    square_duration: float,
    square_port: str,
    square_clock: str,
    virt_z_parent_qubit_phase: float,
    virt_z_parent_qubit_clock: str,
    virt_z_child_qubit_phase: float,
    virt_z_child_qubit_clock: str,
    reference_magnitude: pulse_library.ReferenceMagnitude | None = None,
    t0: float = 0,
) -> pulse_library.SoftSquarePulse:
    """A CZ: a soft square pulse, with each qubit's clock shifted by its phase, in degrees, at the start.

    ``reference_magnitude`` is unused; quantify-scheduler's pulse factories take it.
    """
    composite_pulse = pulse_library.IdlePulse(duration=4e-9)
    composite_pulse.add_pulse(
        pulse_library.SoftSquarePulse(
            amp=square_amp,
            duration=square_duration,
            port=square_port,
            clock=square_clock,
            t0=t0,
        )
    )

    # an uncalibrated phase correction is NaN
    for phase, clock in (
        (virt_z_parent_qubit_phase, virt_z_parent_qubit_clock),
        (virt_z_child_qubit_phase, virt_z_child_qubit_clock),
    ):
        composite_pulse.add_pulse(
            pulse_library.ShiftClockPhase(
                phase_shift=0 if math.isnan(phase) else phase, clock=clock, t0=t0
            )
        )
    composite_pulse.add_pulse(pulse_library.IdlePulse(4e-9))

    logger.info(f"{square_amp=}")
    logger.info(f"{square_duration=}")
    logger.info(f"{square_port=}")
    logger.info(f"{square_clock=}")
    logger.info(f"{virt_z_child_qubit_clock=}, {virt_z_child_qubit_phase=}")
    logger.info(f"{virt_z_parent_qubit_clock=}, {virt_z_parent_qubit_phase=}")

    return composite_pulse
