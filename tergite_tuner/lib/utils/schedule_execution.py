# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import threading
import time
from typing import TYPE_CHECKING

import tqdm
import xarray

from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.types.enums import MeasurementMode

if TYPE_CHECKING:
    from quantify_scheduler.instrument_coordinator.instrument_coordinator import (
        CompiledSchedule,
        InstrumentCoordinator,
    )


def execute_schedule(
    compiled_schedule: "CompiledSchedule",
    schedule_duration: float,
    lab_ic: "InstrumentCoordinator",
    cluster_status,
) -> xarray.Dataset:
    logger.info("Starting measurement")

    def display_progress() -> None:
        steps = int(schedule_duration * 5)
        if cluster_status == MeasurementMode.dummy:
            progress_sleep = 0.004
        elif cluster_status == MeasurementMode.real:
            progress_sleep = 0.2
        for _ in tqdm.tqdm(range(steps), desc=compiled_schedule.name, colour="blue"):
            time.sleep(progress_sleep)

    # the instruments run in this thread, so that their errors reach the caller
    thread_tqdm = threading.Thread(target=display_progress, daemon=True)
    thread_tqdm.start()
    lab_ic.prepare(compiled_schedule)
    lab_ic.start()
    lab_ic.wait_done(timeout_sec=3600)
    thread_tqdm.join()

    raw_dataset: xarray.Dataset = lab_ic.retrieve_acquisition()
    lab_ic.stop()

    return raw_dataset
