# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024
# (C) Copyright Chalmers Next Labs 2026
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

import numpy as np
import tqdm
import xarray

from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.types.enums import MeasurementMode

if TYPE_CHECKING:
    from qblox_scheduler.backends import SerialCompiler
    from qblox_scheduler.instrument_coordinator.instrument_coordinator import (
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

    raw_dataset = _flatten_acquisitions(lab_ic.retrieve_acquisition())
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


def get_compiler(prefix: str = "default") -> "SerialCompiler":
    """
    This is in a function, so, we can have a local import of qblox-scheduler.

    Returns:
        SerialCompiler with given prefix name
    """
    from qblox_scheduler.backends import SerialCompiler

    return SerialCompiler(name=f"{prefix}_compiler")


def _flatten_acquisitions(dataset: xarray.Dataset) -> xarray.Dataset:
    """Orders each label's values by repetition then acq_index, as quantify-scheduler did.

    qblox-scheduler has no acq_index: the schedules tag each acquisition with an
    ``acq_index`` coordinate instead, and repetitions come back interleaved with it.
    """
    flat = xarray.Dataset()
    for label in sorted(dataset.data_vars):
        data = dataset[label]
        keys = [data[c].values for c in ("acq_index", "repetition") if c in data.coords]
        values = data.values[np.lexsort(keys)] if keys else data.values
        flat[label] = xarray.DataArray(values)
    return flat
