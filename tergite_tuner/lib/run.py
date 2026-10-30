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
import pandas
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
from tergite_tuner.lib.base.utils.figure_utils import create_figure_with_top_band
from tergite_tuner.lib.spec import Fits, NodeSpec, get_coord_name, is_failed
from tergite_tuner.storage.fs.dataset import load_dataset, save_dataset
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
            spec.name.value, get_qubits(spec, session), session.couplers, session
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


def get_qubits(spec: NodeSpec, session: "SessionContext") -> list[str]:
    """The qubits the node measures: the session's, or the coupled ones of a coupler node."""
    if spec.element == "qubit":
        return list(session.qubits)
    return sorted(
        {qubit for coupler in session.couplers for qubit in coupler.split("_")}
    )


def compile_node(
    spec: NodeSpec,
    device: QuantumDevice,
    sweeps: Sweeps,
    session: "SessionContext | None" = None,
) -> CompiledSchedule:
    transmons = {qubit: device.get_element(qubit) for qubit in device.elements()}
    keywords = dict(spec.schedule_keywords)
    if spec.element == "coupler":
        keywords["edges"] = {edge: device.get_edge(edge) for edge in device.edges()}
    if spec.get_schedule_keywords is not None:
        keywords |= spec.get_schedule_keywords(session)
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
    """The node's dataset: its schedule run on ``hardware``, or dummy data in dummy mode.

    The schedule runs once per point of its outer and external sweeps, compiled again
    for each outer point, and each run's dataset gains a dimension per such setting.
    """
    sweeps = get_sweeps(spec, session)
    if spec.element == "coupler":
        validate_couplers(session.couplers)
        set_parking_currents(hardware, session)
    external_points = get_points(get_external_sweeps(spec, session))
    compiled_schedule = None
    dataset = xr.Dataset()
    runs = [
        (outer, external)
        for outer in get_points(get_outer_sweeps(spec, session))
        for external in external_points
    ]
    for index, (outer_point, external_point) in enumerate(runs):
        point_sweeps = sweeps | outer_point
        if compiled_schedule is None or spec.outer_sweeps:
            compiled_schedule = compile_node(spec, device, point_sweeps, session)
        if spec.set_external is not None:
            spec.set_external(hardware, external_point, index % len(external_points))
        point_dataset = _run_once(
            spec,
            hardware,
            compiled_schedule,
            point_sweeps | external_point,
            sweeps,
            session,
            list(device.elements()),
            (index, len(runs)),
        )
        point_dataset = _add_point_dimensions(
            point_dataset, outer_point | external_point
        )
        dataset = xr.merge(
            [point_dataset, dataset], join="outer", compat="no_conflicts"
        )
    if spec.reset_external is not None:
        spec.reset_external(hardware)
    logger.info("Finished measurement")
    return dataset


def get_outer_sweeps(spec: NodeSpec, session: "SessionContext") -> Sweeps:
    return _get_sweeps(spec.outer_sweeps, spec, session)


def get_external_sweeps(spec: NodeSpec, session: "SessionContext") -> Sweeps:
    return _get_sweeps(spec.external_sweeps, spec, session)


def get_points(sweeps: Sweeps) -> list[dict[str, dict[str, Any]]]:
    """Each point of ``sweeps``, as each setting's value per element; one empty point without any."""
    names = list(sweeps)
    counts = [len(next(iter(sweeps[name].values()))) for name in names]
    return [
        {
            name: {element: values[index] for element, values in sweeps[name].items()}
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
                        {
                            setting: _get_qubit_value(values, qubit)
                            for setting, values in sweeps.items()
                        },
                        session,
                    ),
                    order="F",
                )
            )
            for index, qubit in enumerate(get_qubits(spec, session))
        }
    )


def get_dataset(
    raw_dataset: xr.Dataset,
    sweeps: Sweeps,
    qubits: list[str],
    loops: int | None = None,
    couplers: list[str] | None = None,
) -> xr.Dataset:
    """The instruments' acquisitions, one variable per qubit, shaped and labelled by ``sweeps``, then ``loops``.

    A setting swept per coupler is labelled by the qubit's coupler. With ``couplers``,
    each qubit's variable belongs to its coupler, as the dataset's elements.
    """
    dataset = xr.Dataset(attrs={"elements": []})
    dimensions = samplespace_dimensions(sweeps, loops)
    for key in raw_dataset.data_vars:
        qubit = qubits[key % len(qubits)]
        coords = _get_qubit_coords(sweeps, qubit, loops)
        owner = _get_coupler(couplers, qubit) if couplers else qubit
        partial_dataset = xr.Dataset(coords=coords)
        partial_dataset[f"y{qubit}"] = (
            tuple(coords),
            raw_dataset[key].values.reshape(*dimensions, order="F"),
            {
                "qubit": qubit,
                "element": owner,
                "long_name": f"y{qubit}",
                "units": "NA",
            },
        )
        dataset = xr.merge([dataset, partial_dataset])
        dataset.attrs["elements"].append(owner)
    dataset.attrs["elements"] = sorted(set(dataset.attrs["elements"]))
    return dataset


def analyse_node(
    spec: NodeSpec, data_path: Path, session: "SessionContext", should_save_plot: bool
) -> dict[str, Fits | None]:
    """Analyses the node's saved dataset in ``data_path`` and writes the fits into the session's state."""
    data_path = Path(data_path)
    start = time.perf_counter()
    dataset = load_dataset(spec.name.value, data_path)
    if spec.element == "coupler":
        s21s = get_coupler_datasets(dataset, spec.name.value)
    else:
        s21s = get_element_s21s(dataset)
    fits = get_fits(spec, s21s, session)
    logger.info(f"Analysed {spec.name.value} in {time.perf_counter() - start:.2f} s")
    if should_save_plot:
        plot_elements(spec, s21s, fits, data_path, session)
    store_fits(spec, fits, session)
    return fits


def get_fits(
    spec: NodeSpec, s21s: Mapping[str, xr.DataArray], session: "SessionContext"
) -> dict[str, Fits | None]:
    return {
        element: spec.analyse(
            s21, session, **get_analysis_keywords(spec, element, session)
        )
        for element, s21 in s21s.items()
    }


def get_analysis_keywords(
    spec: NodeSpec, element: str, session: "SessionContext"
) -> Mapping[str, Any]:
    if spec.get_analysis_keywords is None:
        return {}
    return spec.get_analysis_keywords(element, session)


def get_element_s21s(dataset: xr.Dataset) -> dict[str, xr.DataArray]:
    """Each element's complex S21 from a saved dataset, which splits it into real and imaginary parts, by qubit number."""
    s21s = {}
    for data_var in dataset.data_vars.values():
        s21 = data_var.isel(ReIm=0) + 1j * data_var.isel(ReIm=1)
        s21.attrs = data_var.attrs
        s21s[data_var.attrs["element"]] = s21
    return dict(sorted(s21s.items(), key=lambda item: int(item[0][1:])))


def get_coupler_datasets(dataset: xr.Dataset, name: str) -> dict[str, xr.Dataset]:
    """Each coupler's variables from a saved dataset, still split into real and imaginary parts."""
    couplers = sorted({var.attrs["element"] for var in dataset.data_vars.values()})
    return {
        coupler: xr.merge(
            [
                var
                for var in dataset.data_vars.values()
                if var.attrs["element"] == coupler
            ]
        ).assign_attrs(coupler=coupler, node=name)
        for coupler in couplers
    }


def plot_elements(
    spec: NodeSpec,
    s21s: Mapping[str, xr.DataArray],
    fits: Mapping[str, Fits | None],
    data_path: Path,
    session: "SessionContext",
) -> None:
    """Plots each element in a grid and saves it at 100 and 400 dpi in ``data_path``."""
    if spec.save_details is not None:
        for element, s21 in s21s.items():
            spec.save_details(s21, fits[element] or {}, data_path, session)
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
    logger.info(f"Plots saved to {data_path}")


def store_fits(
    spec: NodeSpec, fits: Mapping[str, Fits | None], session: "SessionContext"
) -> None:
    """Writes the fits ``spec`` names into the session's state, with each element's status."""
    collection = "couplers" if spec.element == "coupler" else "transmons"
    records = {collection: {}, "cs": {}}
    for element, element_fits in fits.items():
        if is_failed(element_fits):
            logger.warning(f"Analysis failed for {element}")
            records["cs"][element] = {spec.name.value: "not_calibrated"}
            continue
        records[collection][element] = get_qoi_values(spec.qois, element_fits)
        records["cs"][element] = {spec.name.value: "calibrated"}
    session.state.write(records)


def get_qoi_values(qois: Mapping[str, str], fits: Fits) -> dict[str, object]:
    """Each fit ``qois`` names, and its error, by the field it is stored in."""
    values = {}
    for name, fit in fits.items():
        if name in qois:
            values[qois[name]] = fit.value
            values[f"{qois[name]}_error"] = fit.error
    return values


def is_in_spec(name: str, elements: Iterable[str], session: "SessionContext") -> bool:
    """Whether node ``name`` is calibrated on every one of ``elements``."""
    return all(
        session.state.read("cs", element, name) == "calibrated" for element in elements
    )


def validate_couplers(couplers: list[str]) -> None:
    """Raises ``ValueError`` if two couplers, or a coupler's own ends, share a qubit."""
    qubits = [qubit for coupler in couplers for qubit in coupler.split("_")]
    if len(qubits) > len(set(qubits)):
        logger.info("Couplers share qubits")
        raise ValueError("Improper Couplers")


def set_parking_currents(hardware: Hardware, session: "SessionContext") -> None:
    """Sets each coupler's parking current, which CZ parametrization may have updated; not when recalibrating."""
    currents = {
        coupler: session.state.read("couplers", coupler, "parking_current")
        for coupler in session.couplers
    }
    if None in currents.values():
        logger.error(f"Some couplers are missing currents: {currents}")
        return
    if session.is_recalibration:
        logger.debug("Skipping setting DC currents")
        return
    logger.status("Setting updated DC currents")
    hardware.spi.set_dac_current(currents)


def _get_element_axes(axes: np.ndarray, index: int, rows: int) -> Any:
    """The ``index``-th element's axis, or its column of ``rows`` axes, in a grid of ``PLOT_COLUMNS``."""
    row, column = rows * (index // PLOT_COLUMNS), index % PLOT_COLUMNS
    return axes[row : row + rows, column] if rows > 1 else axes[row, column]


def _get_sweeps(
    sweep_fns: Mapping[str, Any], spec: NodeSpec, session: "SessionContext"
) -> Sweeps:
    elements = get_elements(spec, session)
    qubits = get_qubits(spec, session)
    sweeps = {
        setting: {
            element: get_values(element, session)
            for element in (qubits if setting in spec.qubit_sweeps else elements)
        }
        for setting, get_values in sweep_fns.items()
    }
    user_samplespace = session.user_samplespace.get(spec.name.value, {})
    unknown = (
        user_samplespace.keys()
        - spec.sweeps.keys()
        - spec.outer_sweeps.keys()
        - spec.external_sweeps.keys()
    )
    if unknown:
        raise KeyError(f"{unknown} not in any samplespace")
    sweeps.update({k: v for k, v in user_samplespace.items() if k in sweep_fns})
    return sweeps


def _run_once(
    spec: NodeSpec,
    hardware: Hardware,
    compiled_schedule: CompiledSchedule,
    point_sweeps: Sweeps,
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
        raw_dataset = get_dummy_dataset(spec, point_sweeps, session)
    couplers = get_elements(spec, session) if spec.element == "coupler" else None
    return get_dataset(raw_dataset, sweeps, qubits, spec.loops, couplers)


def _add_point_dimensions(
    dataset: xr.Dataset, point: Mapping[str, Mapping[str, Any]]
) -> xr.Dataset:
    """``dataset`` with a dimension per setting of ``point``, which is the same for every element."""
    for setting, values in point.items():
        value = next(iter(values.values()))
        if np.ndim(value) == 0:
            dataset = dataset.expand_dims({setting: np.array([value])})
            continue
        # a point of several values, such as a working point's frequency and duration
        index = pandas.MultiIndex.from_tuples([tuple(value)], names=["l1", "l2"])
        dataset = dataset.expand_dims({setting: index})
        dataset = dataset.assign_coords({setting: (setting, index)})
    return dataset


def _get_coupler(values: Mapping[str, Any], qubit: str) -> str:
    return next(element for element in values if qubit in element.split("_"))


def _get_qubit_value(values: Mapping[str, Any], qubit: str) -> Any:
    """``qubit``'s value of a setting swept per qubit or per coupler."""
    return values[qubit] if qubit in values else values[_get_coupler(values, qubit)]


def _get_qubit_coords(
    sweeps: Sweeps, qubit: str, loops: int | None
) -> dict[str, tuple[str, np.ndarray, dict[str, str]]]:
    """A coordinate per setting, named by the qubit or, for a setting swept per coupler, its coupler; then the loops."""
    coords = {}
    for quantity, values in sweeps.items():
        element = qubit if qubit in values else _get_coupler(values, qubit)
        element_type = "qubit" if element == qubit else "coupler"
        coord_name = get_coord_name(quantity, element)
        coord_attrs = {
            "element_type": element_type,
            element_type: element,
            "measured_qubit": qubit,
            "long_name": coord_name,
            "units": "NA",
        }
        coords[coord_name] = (coord_name, np.atleast_1d(values[element]), coord_attrs)
    if loops is not None:
        coords["loops"] = ("loops", np.arange(loops), {"element_type": "NA"})
    return coords
