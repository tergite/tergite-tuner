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
"""Running a node spec: sweep, measure, analyse, plot and store."""

import math
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from tergite_tuner.backend import (
    CompiledSchedule,
    Hardware,
    QuantumDevice,
    close_device_resources,
    compile_schedule,
    configure_device,
    run_schedule,
    save_serial_device,
)
from tergite_tuner.exc import MissingCalibrationStatusError
from tergite_tuner.lib.base.utils.figure_utils import create_figure_with_top_band
from tergite_tuner.lib.spec import Fits, NodeSpec, get_coord_name
from tergite_tuner.storage.fs.dataset import load_dataset, save_dataset
from tergite_tuner.utils.dicts import insert_nested_key
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.logging.visuals import print_measurement_info
from tergite_tuner.utils.measurement import samplespace_dimensions
from tergite_tuner.utils.types.enums import MeasurementMode

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

Sweeps = dict[str, dict[str, np.ndarray]]

PLOT_COLUMNS = 5


def calibrate(
    spec: NodeSpec,
    session: "SessionContext",
    hardware: Hardware | None,
    data_path: Path,
    should_save_plot: bool,
) -> dict[str, Fits | None]:
    """Measures ``spec``'s node, unless re-analysing, then analyses and stores it."""
    if session.cluster_mode != MeasurementMode.re_analyse:
        device = configure_device(
            spec.name.value, session.qubits, session.couplers, session
        )
        try:
            dataset = measure(
                spec, hardware, device, get_sweeps(spec, session), session
            )
            save_serial_device(device, data_path)
            save_dataset(dataset, spec.name.value, data_path)
        finally:
            close_device_resources(device)
    fits = analyse_node(spec, data_path, session, should_save_plot)
    logger.info("analysis completed")
    return fits


def get_sweeps(spec: NodeSpec, session: "SessionContext") -> Sweeps:
    """Each swept setting's values per element, with the session's user samplespace applied."""
    elements = get_elements(spec, session)
    sweeps = {
        setting: {element: get_values(element, session) for element in elements}
        for setting, get_values in spec.sweeps.items()
    }
    for setting, values in session.user_samplespace.get(spec.name.value, {}).items():
        if setting not in sweeps:
            raise KeyError(f"{setting} not in any samplespace")
        sweeps[setting] = values
    return sweeps


def get_elements(spec: NodeSpec, session: "SessionContext") -> list[str]:
    return list(session.couplers if spec.element == "coupler" else session.qubits)


def compile_node(
    spec: NodeSpec, device: QuantumDevice, sweeps: Sweeps
) -> CompiledSchedule:
    transmons = {qubit: device.get_element(qubit) for qubit in device.elements()}
    schedule = spec.get_schedule(transmons, **sweeps, **spec.schedule_keywords)
    return compile_schedule(schedule, device, name=spec.name.value)


def measure(
    spec: NodeSpec,
    hardware: Hardware,
    device: QuantumDevice,
    sweeps: Sweeps,
    session: "SessionContext",
) -> xr.Dataset:
    """The node's dataset: its schedule run on ``hardware``, or dummy data in dummy mode."""
    compiled_schedule = compile_node(spec, device, sweeps)
    duration = compiled_schedule.get_schedule_duration()
    print_measurement_info(duration, (1, 1))

    start = time.perf_counter()
    raw_dataset = run_schedule(
        hardware.coordinator,
        compiled_schedule,
        timeout=duration + session.cluster_timeout,
    )
    logger.info(f"Measured {spec.name.value} in {time.perf_counter() - start:.2f} s")

    if session.cluster_mode == MeasurementMode.dummy:
        raw_dataset = get_dummy_dataset(spec, sweeps, session)
    logger.info("Finished measurement")
    return get_dataset(raw_dataset, sweeps, list(device.elements()))


def get_dummy_dataset(
    spec: NodeSpec, sweeps: Sweeps, session: "SessionContext"
) -> xr.Dataset:
    """The acquisitions ``spec``'s dummy model gives, one variable per qubit, as the instruments return them."""
    return xr.Dataset(
        {
            index: xr.DataArray(
                np.ravel(
                    spec.get_dummy_s21(
                        qubit,
                        {setting: values[qubit] for setting, values in sweeps.items()},
                        session,
                    )
                )
            )
            for index, qubit in enumerate(get_elements(spec, session))
        }
    )


def get_dataset(
    raw_dataset: xr.Dataset, sweeps: Sweeps, qubits: list[str]
) -> xr.Dataset:
    """The instruments' acquisitions, one variable per qubit, shaped and labelled by ``sweeps``."""
    dataset = xr.Dataset(attrs={"elements": []})
    dimensions = samplespace_dimensions(sweeps)
    for key in raw_dataset.data_vars:
        qubit = qubits[key % len(qubits)]
        coords = {}
        for quantity, values in sweeps.items():
            coord_name = get_coord_name(quantity, qubit)
            coord_attrs = {
                "element_type": "qubit",
                "qubit": qubit,
                "measured_qubit": qubit,
                "long_name": coord_name,
                "units": "NA",
            }
            coords[coord_name] = (coord_name, values[qubit], coord_attrs)
        partial_dataset = xr.Dataset(coords=coords)
        partial_dataset[f"y{qubit}"] = (
            tuple(coords),
            raw_dataset[key].values.reshape(*dimensions, order="F"),
            {"qubit": qubit, "element": qubit, "long_name": f"y{qubit}", "units": "NA"},
        )
        dataset = xr.merge([dataset, partial_dataset])
        dataset.attrs["elements"].append(qubit)
    dataset.attrs["elements"] = sorted(set(dataset.attrs["elements"]))
    return dataset


def analyse_node(
    spec: NodeSpec, data_path: Path, session: "SessionContext", should_save_plot: bool
) -> dict[str, Fits | None]:
    """Analyses the node's saved dataset in ``data_path`` and stores the fits in Redis."""
    data_path = Path(data_path)
    start = time.perf_counter()
    s21s = get_element_s21s(load_dataset(spec.name.value, data_path))
    fits = get_fits(spec, s21s)
    logger.info(f"Analysed {spec.name.value} in {time.perf_counter() - start:.2f} s")
    if should_save_plot:
        plot_elements(spec, s21s, fits, data_path, session)
    store_fits(spec, fits, session)
    return fits


def get_fits(
    spec: NodeSpec, s21s: Mapping[str, xr.DataArray]
) -> dict[str, Fits | None]:
    return {element: spec.analyse(s21) for element, s21 in s21s.items()}


def get_element_s21s(dataset: xr.Dataset) -> dict[str, xr.DataArray]:
    """Each element's complex S21 from a saved dataset, which splits it into real and imaginary parts, by qubit number."""
    s21s = {}
    for data_var in dataset.data_vars.values():
        s21 = data_var.isel(ReIm=0) + 1j * data_var.isel(ReIm=1)
        s21.attrs = data_var.attrs
        s21s[data_var.attrs["element"]] = s21
    return dict(sorted(s21s.items(), key=lambda item: int(item[0][1:])))


def plot_elements(
    spec: NodeSpec,
    s21s: Mapping[str, xr.DataArray],
    fits: Mapping[str, Fits | None],
    data_path: Path,
    session: "SessionContext",
) -> None:
    """Plots each element in a grid and saves it at 100 and 400 dpi in ``data_path``."""
    if spec.plot is None:
        return
    nrows = math.ceil(len(s21s) / PLOT_COLUMNS)
    figure, axes = create_figure_with_top_band(nrows, min(PLOT_COLUMNS, len(s21s)))
    for index, (element, s21) in enumerate(s21s.items()):
        axis = axes[index // PLOT_COLUMNS, index % PLOT_COLUMNS]
        spec.plot(axis, s21, fits[element] or {}, session)
        axis.set_title(f"Qubit {element}")
    name = spec.name.value
    figure.savefig(data_path / f"{name}_preview.png", bbox_inches="tight", dpi=100)
    figure.savefig(data_path / f"{name}.png", bbox_inches="tight", dpi=400)
    plt.close(figure)
    logger.info(f"Plots saved to {data_path}")


def store_fits(
    spec: NodeSpec, fits: Mapping[str, Fits | None], session: "SessionContext"
) -> None:
    """Stores the fits ``spec`` names in each element's Redis record, and marks the elements calibrated."""
    collection = "couplers" if spec.element == "coupler" else "transmons"
    redis_data = {}
    for element, element_fits in fits.items():
        if element_fits is None:
            logger.warning(f"Analysis failed for {element}")
            continue
        insert_nested_key(
            redis_data,
            path=(collection, element),
            value=get_redis_record(spec.qois, element_fits),
        )
        insert_nested_key(
            redis_data, path=("cs", element, spec.name.value), value="calibrated"
        )
    session.redis_store.save_many(redis_data)
    session.update_redis_fields_log(spec.qois.values())


def get_redis_record(qois: Mapping[str, str], fits: Fits) -> dict[str, object]:
    record = {}
    for name, fit in fits.items():
        if name in qois:
            record[qois[name]] = fit.value
            record[f"{qois[name]}_error"] = fit.error
    return record


def mark_not_calibrated(spec: NodeSpec, session: "SessionContext") -> None:
    """Marks the node not calibrated on each of its elements that has no status yet."""
    elements = get_elements(spec, session)
    statuses = session.redis_store.find_many("cs", pks=elements).get("cs", {})
    session.redis_store.save_many(
        {
            "cs": {
                element: {spec.name.value: "not_calibrated"}
                for element in elements
                if spec.name.value not in statuses.get(element, {})
            }
        }
    )


def is_in_spec(name: str, elements: Iterable[str], session: "SessionContext") -> bool:
    """Whether node ``name`` is calibrated on every one of ``elements``."""
    for element in elements:
        status = session.redis.hget(f"cs:{element}", name)
        if status == "not_calibrated":
            return False
        if status != "calibrated":
            raise MissingCalibrationStatusError(
                f"No calibration status of {name} for {element}"
            )
    return True
