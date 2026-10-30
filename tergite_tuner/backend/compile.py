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

import time

from quantify_scheduler import Schedule
from quantify_scheduler.backends import SerialCompiler
from quantify_scheduler.backends.qblox import constants
from quantify_scheduler.device_under_test.quantum_device import QuantumDevice
from quantify_scheduler.schedules.schedule import CompiledSchedule

from tergite_tuner.utils.logging import logger

# Schedules lasting minutes (punchout: 264 s) build up float error in their absolute
# times beyond quantify's default tolerance of 1.1e-3 ns, and fail to compile.
GRID_TIME_TOLERANCE_NS = 5e-2


def compile_schedule(
    schedule: Schedule, device: QuantumDevice, name: str
) -> CompiledSchedule:
    """Compiles ``schedule`` for ``device``, with the grid-time tolerance long schedules need."""
    default_tolerance = constants.GRID_TIME_TOLERANCE_TIME
    constants.GRID_TIME_TOLERANCE_TIME = GRID_TIME_TOLERANCE_NS
    try:
        start = time.perf_counter()
        compiled_schedule = SerialCompiler(name=f"{name}_compiler").compile(
            schedule=schedule, config=device.generate_compilation_config()
        )
        logger.info(f"Compiled {name} in {time.perf_counter() - start:.2f} s")
        return compiled_schedule
    finally:
        constants.GRID_TIME_TOLERANCE_TIME = default_tolerance
