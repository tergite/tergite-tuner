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

# Schedules lasting minutes (punchout: 264 s) build up float error in their absolute
# times beyond quantify's default tolerance of 1.1e-3 ns, and fail to compile.
GRID_TIME_TOLERANCE_NS = 5e-2

if TYPE_CHECKING:
    from quantify_scheduler import Schedule
    from quantify_scheduler.device_under_test.quantum_device import QuantumDevice
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

    def run_measurement() -> None:
        lab_ic.prepare(compiled_schedule)
        lab_ic.start()
        lab_ic.wait_done(timeout_sec=3600)

    def display_progress() -> None:
        steps = int(schedule_duration * 5)
        if cluster_status == MeasurementMode.dummy:
            progress_sleep = 0.004
        elif cluster_status == MeasurementMode.real:
            progress_sleep = 0.2
        for _ in tqdm.tqdm(range(steps), desc=compiled_schedule.name, colour="blue"):
            time.sleep(progress_sleep)

    thread_tqdm = threading.Thread(target=display_progress)
    thread_tqdm.start()
    thread_lab = threading.Thread(target=run_measurement)
    thread_lab.start()
    thread_lab.join()
    thread_tqdm.join()

    raw_dataset: xarray.Dataset = lab_ic.retrieve_acquisition()
    lab_ic.stop()

    return raw_dataset


def display_duration_information(
    schedule_duration: float, schedule_keywords: dict, measurement: tuple
) -> None:
    if "loop_repetitions" in schedule_keywords:
        schedule_duration *= schedule_keywords["loop_repetitions"]

    measurement_message = ""
    if measurement[1] > 1:
        measurement_message = f". Measurement {measurement[0] + 1} of {measurement[1]}"
    message = f"{schedule_duration:.2f} sec" + measurement_message
    logger.info(f"schedule_duration = {message}")


def compile_schedule(
    schedule: "Schedule", device: "QuantumDevice", name: str
) -> "CompiledSchedule":
    """Compiles ``schedule`` for ``device``, with the grid-time tolerance long schedules need."""
    from quantify_scheduler.backends import SerialCompiler
    from quantify_scheduler.backends.qblox import constants

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
