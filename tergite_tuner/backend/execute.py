# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


import xarray
from quantify_scheduler.instrument_coordinator.instrument_coordinator import (
    CompiledSchedule,
    InstrumentCoordinator,
)


def run_schedule(
    coordinator: InstrumentCoordinator,
    compiled_schedule: CompiledSchedule,
    timeout: float,
) -> xarray.Dataset:
    """Runs ``compiled_schedule`` on the instruments, waiting ``timeout`` seconds at most, and returns their acquisitions."""
    coordinator.prepare(compiled_schedule)
    coordinator.start()
    coordinator.wait_done(timeout_sec=timeout)
    acquisitions = coordinator.retrieve_acquisition()
    coordinator.stop()
    return acquisitions
