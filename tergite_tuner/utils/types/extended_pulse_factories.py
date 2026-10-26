# This code is part of Tergite
#
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Chalmers Next Labs 2026
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

from qblox_scheduler.operations import pulse_library
from qblox_scheduler.schedules import TimeableSchedule

from tergite_tuner.utils.logging import logger

# DRAGPulse's nr_sigma when it is given no sigma: sigma = duration / (2 * nr_sigma)
_DRAG_NR_SIGMA = 4


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
) -> TimeableSchedule:
    """
    An example composite pulse to implement a CZ gate.

    It applies the
    square pulse and then corrects for the phase shifts on both the qubits.

    Parameters
    ----------
    square_amp
        Amplitude of the square envelope.
    square_duration
        The square pulse duration in seconds.
    square_port
        Port of the pulse, must be capable of playing a complex waveform.
    square_clock
        Clock used to modulate the pulse.
    virt_z_parent_qubit_phase
        The phase shift in degrees applied to the parent qubit.
    virt_z_parent_qubit_clock
        The clock of which to shift the phase applied to the parent qubit.
    virt_z_child_qubit_phase
        The phase shift in degrees applied to the child qubit.
    virt_z_child_qubit_clock
        The clock of which to shift the phase applied to the child qubit.
    reference_magnitude : :class:`~qblox_scheduler.operations.pulse_library.ReferenceMagnitude`, optional
        Scaling value and unit for the unitless amplitude. Uses settings in
        hardware config if not provided.
    t0
        Time in seconds when to start the pulses relative to the start time
        of the Operation in the Schedule.

    Returns
    -------
    :
        The CZ pulse and its phase corrections, as a schedule.
    """

    if virt_z_parent_qubit_phase is float("nan"):
        virt_z_parent_qubit_phase = 0

    if virt_z_child_qubit_phase is float("nan"):
        virt_z_child_qubit_phase = 0

    composite_pulse = TimeableSchedule(composite_soft_square_pulse.__name__)
    start = composite_pulse.add(pulse_library.IdlePulse(duration=4e-9))
    # all parts start together, as quantify-scheduler's Operation.add_pulse placed them
    for part in (
        pulse_library.SoftSquarePulse(
            amplitude=square_amp,
            duration=square_duration,
            port=square_port,
            clock=square_clock,
            t0=t0,
        ),
        pulse_library.ShiftClockPhase(
            phase_shift=virt_z_parent_qubit_phase,
            clock=virt_z_parent_qubit_clock,
            t0=t0,
        ),
        pulse_library.ShiftClockPhase(
            phase_shift=virt_z_child_qubit_phase,
            clock=virt_z_child_qubit_clock,
            t0=t0,
        ),
        pulse_library.IdlePulse(4e-9),
    ):
        composite_pulse.add(part, ref_op=start, ref_pt="start")

    logger.info(f"{square_amp=}")
    logger.info(f"{square_duration=}")
    logger.info(f"{square_port=}")
    logger.info(f"{square_clock=}")
    logger.info(f"{virt_z_child_qubit_clock=}, {virt_z_child_qubit_phase=}")
    logger.info(f"{virt_z_parent_qubit_clock=}, {virt_z_parent_qubit_phase=}")

    return composite_pulse


def motzoi_to_beta(motzoi: float, duration: float) -> float:
    """DRAG ``beta`` of qblox-scheduler for quantify-scheduler's ``D_amp``, which motzoi is."""
    # the derivative term scales as D_amp / sigma in quantify, beta / sigma**2 in qblox
    return motzoi * duration / (2 * _DRAG_NR_SIGMA)
