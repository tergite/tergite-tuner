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

import itertools
import math
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
            dataset = measure(spec, hardware, device, session)
            save_serial_device(device, data_path)
            save_dataset(dataset, spec.name.value, data_path)
        finally:
            close_device_resources(device)
    fits = analyse_node(spec, data_path, session, should_save_plot)
    logger.info("analysis completed")
    return fits


def get_sweeps(spec: NodeSpec, session: "SessionContext") -> Sweeps:
    """Each of the schedule's swept settings' values per element, with the session's user samplespace applied."""
    return _get_sweeps(spec.sweeps, spec, session)


def get_elements(spec: NodeSpec, session: "SessionContext") -> list[str]:
    return list(session.couplers if spec.element == "coupler" else session.qubits)


def compile_node(
    spec: NodeSpec, device: QuantumDevice, sweeps: Sweeps
) -> CompiledSchedule:
    transmons = {qubit: device.get_element(qubit) for qubit in device.elements()}
    keywords = dict(spec.schedule_keywords)
    if spec.loops is not None:
        keywords["loop_repetitions"] = spec.loops
    schedule = spec.get_schedule(transmons, **sweeps, **keywords)
    return compile_schedule(schedule, device, name=spec.name.value)


def measure(
    spec: NodeSpec,
    hardware: Hardware,
    device: QuantumDevice,
    session: "SessionContext",
) -> xr.Dataset:
    """The node's dataset: its schedule run on ``hardware`` once per external point, or dummy data in dummy mode."""
    sweeps = get_sweeps(spec, session)
    compiled_schedule = compile_node(spec, device, sweeps)
    qubits = list(device.elements())
    points = get_external_points(get_external_sweeps(spec, session))
    dataset = xr.Dataset()
    for index, point in enumerate(points):
        if spec.set_external is not None:
            spec.set_external(hardware, point, index)
        point_dataset = _run_once(
            spec,
            hardware,
            compiled_schedule,
            sweeps,
            session,
            qubits,
            (index, len(points)),
        )
        for setting, values in point.items():
            # the external values are the same for every element
            value = next(iter(values.values()))
            point_dataset = point_dataset.expand_dims({setting: np.array([value])})
        dataset = xr.merge(
            [point_dataset, dataset], join="outer", compat="no_conflicts"
        )
    if spec.reset_external is not None:
        spec.reset_external(hardware)
    logger.info("Finished measurement")
    return dataset


def get_external_sweeps(spec: NodeSpec, session: "SessionContext") -> Sweeps:
    return _get_sweeps(spec.external_sweeps, spec, session)


def get_external_points(external_sweeps: Sweeps) -> list[dict[str, dict[str, Any]]]:
    """Each point of the external sweeps, as each setting's value per element; one empty point without any."""
    names = list(external_sweeps)
    counts = [len(next(iter(external_sweeps[name].values()))) for name in names]
    return [
        {
            name: {
                element: values[index]
                for element, values in external_sweeps[name].items()
            }
            for name, index in zip(names, indices, strict=True)
        }
        for indices in itertools.product(*(range(count) for count in counts))
    ]


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
                    ),
                    order="F",
                )
            )
            for index, qubit in enumerate(get_elements(spec, session))
        }
    )


def get_dataset(
    raw_dataset: xr.Dataset,
    sweeps: Sweeps,
    qubits: list[str],
    loops: int | None = None,
) -> xr.Dataset:
    """The instruments' acquisitions, one variable per qubit, shaped and labelled by ``sweeps``, then ``loops``."""
    dataset = xr.Dataset(attrs={"elements": []})
    dimensions = samplespace_dimensions(sweeps, loops)
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
        if loops is not None:
            coords["loops"] = ("loops", np.arange(loops), {"element_type": "NA"})
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
    fits = get_fits(spec, s21s, session)
    logger.info(f"Analysed {spec.name.value} in {time.perf_counter() - start:.2f} s")
    if should_save_plot:
        plot_elements(spec, s21s, fits, data_path, session)
    store_fits(spec, fits, session)
    return fits


def get_fits(
    spec: NodeSpec, s21s: Mapping[str, xr.DataArray], session: "SessionContext"
) -> dict[str, Fits | None]:
    return {element: spec.analyse(s21, session) for element, s21 in s21s.items()}


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
    rows = spec.plot_rows
    nrows = math.ceil(len(s21s) / PLOT_COLUMNS) * rows
    figure, axes = create_figure_with_top_band(nrows, min(PLOT_COLUMNS, len(s21s)))
    for index, (element, s21) in enumerate(s21s.items()):
        element_axes = _get_element_axes(axes, index, rows)
        spec.plot(element_axes, s21, fits[element] or {}, session)
        (element_axes[0] if rows > 1 else element_axes).set_title(f"Qubit {element}")
    name = spec.name.value
    figure.savefig(data_path / f"{name}_preview.png", bbox_inches="tight", dpi=100)
    figure.savefig(data_path / f"{name}.png", bbox_inches="tight", dpi=400)
    plt.close(figure)
    if spec.save_details is not None:
        for element, s21 in s21s.items():
            spec.save_details(s21, fits[element] or {}, data_path, session)
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


def _get_element_axes(axes: np.ndarray, index: int, rows: int) -> Any:
    """The ``index``-th element's axis, or its column of ``rows`` axes, in a grid of ``PLOT_COLUMNS``."""
    row, column = rows * (index // PLOT_COLUMNS), index % PLOT_COLUMNS
    return axes[row : row + rows, column] if rows > 1 else axes[row, column]


def _get_sweeps(
    sweep_fns: Mapping[str, Any], spec: NodeSpec, session: "SessionContext"
) -> Sweeps:
    elements = get_elements(spec, session)
    sweeps = {
        setting: {element: get_values(element, session) for element in elements}
        for setting, get_values in sweep_fns.items()
    }
    user_samplespace = session.user_samplespace.get(spec.name.value, {})
    unknown = user_samplespace.keys() - spec.sweeps.keys() - spec.external_sweeps.keys()
    if unknown:
        raise KeyError(f"{unknown} not in any samplespace")
    sweeps.update({k: v for k, v in user_samplespace.items() if k in sweep_fns})
    return sweeps


def _run_once(
    spec: NodeSpec,
    hardware: Hardware,
    compiled_schedule: CompiledSchedule,
    sweeps: Sweeps,
    session: "SessionContext",
    qubits: list[str],
    measurement: tuple[int, int],
) -> xr.Dataset:
    duration = compiled_schedule.get_schedule_duration()
    print_measurement_info(duration, measurement)
    start = time.perf_counter()
    raw_dataset = run_schedule(
        hardware.coordinator,
        compiled_schedule,
        timeout=duration + session.cluster_timeout,
    )
    logger.info(f"Measured {spec.name.value} in {time.perf_counter() - start:.2f} s")
    if session.cluster_mode == MeasurementMode.dummy:
        raw_dataset = get_dummy_dataset(spec, sweeps, session)
    return get_dataset(raw_dataset, sweeps, qubits, spec.loops)
