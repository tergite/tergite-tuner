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
"""A node as data: what it sweeps, measures, fits and stores."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

import numpy as np
import xarray as xr
from matplotlib import pyplot as plt
from matplotlib.figure import Figure

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.backend import Hardware
    from tergite_tuner.config.session import SessionContext

# an element's values of a swept setting
SweepFn = Callable[[str, "SessionContext"], np.ndarray]


class Fit(NamedTuple):
    """One value an analysis gives back, and its uncertainty.

    Attributes:
        value: the fitted value, or any object the analysis passes on to its plot.
        error: the value's uncertainty; 0 when it has none.
    """

    value: Any
    error: float = 0


Fits = Mapping[str, Fit]


class CouplerData(NamedTuple):
    """One coupler's dataset, as the coupler analyses read it.

    Attributes:
        coupler: the coupler.
        control_qubit: the coupler's control qubit.
        target_qubit: the coupler's target qubit.
        s21: both qubits' complex S21, a variable each.
        control: the control qubit's complex S21.
        target: the target qubit's complex S21.
    """

    coupler: str
    control_qubit: str
    target_qubit: str
    s21: xr.Dataset
    control: xr.DataArray
    target: xr.DataArray


@dataclass(frozen=True)
class NodeSpec:
    """One calibration node.

    Attributes:
        name: the node.
        element: whether the node calibrates each qubit or each coupler.
        get_schedule: the schedule, given the transmons by name and each swept
            setting's values per element.
        analyse: the fits of one element's S21, which has a coordinate per swept
            setting, named by ``get_coord_name``, given the session; None if the
            element failed.
        qois: the device state's field each fit is stored in; fits it does not name are not stored.
        sweeps: each swept setting's values for an element, in the order the dataset
            is reshaped: the first setting varies fastest.
        get_dummy_s21: an element's S21 in dummy mode, given its sweeps' values, with
            an axis per sweep.
        plot: draws an element's S21 and fits, on an axis, or on a column of
            ``plot_rows`` axes.
        loops: how many times the schedule repeats its shot, a last dimension of
            the dataset.
        plot_rows: how many axes ``plot`` draws on per element.
        save_details: saves an element's own figures in the node's data folder.
        outer_sweeps: settings of a schedule too large for one run, compiled and run
            once per point; the dataset gains a dimension per setting.
        qubit_sweeps: the settings of a coupler node swept per coupled qubit rather
            than per coupler.
        external_sweeps: settings outside the schedule, such as a coupler's current,
            each value of which takes a run of the schedule; the dataset gains a
            dimension per setting.
        set_external: sets an external sweep's point before its run, given the
            hardware, each setting's value per element and the point's index.
        reset_external: undoes the external settings after the last point.
        get_schedule_keywords: schedule keywords read from the session, such as each
            coupler's control and target qubits.
        get_analysis_keywords: an element's keywords for ``analyse``, read from the
            session.
    """

    name: NodeEnum
    element: Literal["qubit", "coupler"]
    get_schedule: Callable[..., Schedule]
    analyse: Callable[[xr.DataArray, "SessionContext"], Fits | None]
    qois: Mapping[str, str]
    sweeps: Mapping[str, SweepFn]
    get_dummy_s21: Callable[[str, Mapping[str, np.ndarray], "SessionContext"], Any]
    plot: Callable[[Any, xr.DataArray, Fits, "SessionContext"], None] | None = None
    schedule_keywords: Mapping[str, Any] = field(default_factory=dict)
    loops: int | None = None
    plot_rows: int = 1
    save_details: (
        Callable[[xr.DataArray, Fits, Path, "SessionContext"], None] | None
    ) = None
    outer_sweeps: Mapping[str, SweepFn] = field(default_factory=dict)
    qubit_sweeps: frozenset[str] = frozenset()
    external_sweeps: Mapping[str, SweepFn] = field(default_factory=dict)
    set_external: (
        Callable[["Hardware", Mapping[str, Mapping[str, Any]], int], None] | None
    ) = None
    reset_external: Callable[["Hardware"], None] | None = None
    get_schedule_keywords: Callable[["SessionContext"], Mapping[str, Any]] | None = None
    get_analysis_keywords: (
        Callable[[str, "SessionContext"], Mapping[str, Any]] | None
    ) = None


def get_fits_from_result(
    result: Mapping[str, Mapping[str, Any]], is_successful: bool
) -> Fits | None:
    """The fits of an analysis reporting ``{field: {"value": ..., "error": ...}}``.

    Args:
        result: each field's value and error.
        is_successful: whether the analysis succeeded; if not, the fits are marked
            ``failed``.

    Returns:
        A fit per field, plus ``failed`` if the analysis did not succeed.
    """
    fits = {name: Fit(item["value"], item["error"]) for name, item in result.items()}
    if not is_successful:
        # failed fits keep their values, to plot and inspect, but are not stored
        fits["failed"] = Fit(True)
    return fits


def is_failed(fits: Fits | None) -> bool:
    """Whether an element's analysis failed: it gave no fits, or marked them ``failed``.

    Args:
        fits: what the element's analysis gave back.

    Returns:
        True if the analysis failed.
    """
    return fits is None or "failed" in fits


def get_coupler_data(dataset: xr.Dataset, session: "SessionContext") -> CouplerData:
    """A coupler's dataset, saved in real and imaginary parts, as complex S21 per qubit.

    Args:
        dataset: the coupler's variables, which name the coupler.
        session: the session, whose device config names the coupler's control and
            target qubits.

    Returns:
        The coupler's data.

    Raises:
        ValueError: if a variable is of neither of the coupler's qubits.
    """
    coupler = dataset.attrs["coupler"]
    control_qubit, target_qubit = (
        session.device_config.get_control_target_qubit_pair_by_coupler(coupler)
    )
    s21 = dataset.isel(ReIm=0) + 1j * dataset.isel(ReIm=1)
    for var in s21.data_vars:
        s21[var].attrs = dataset[var].attrs
    variables = {}
    for var in s21.data_vars.values():
        if var.attrs["qubit"] not in (control_qubit, target_qubit):
            raise ValueError("No control or target qubits")
        variables[var.attrs["qubit"]] = var
    return CouplerData(
        coupler,
        control_qubit,
        target_qubit,
        s21,
        variables[control_qubit],
        variables[target_qubit],
    )


def get_coupler_figure_saver(
    draw: Callable[[Fits], list[Figure]],
) -> Callable[[xr.Dataset, Fits, Path, "SessionContext"], None]:
    """A ``save_details`` that draws a coupler's figures from its fits and saves them.

    Each figure is saved as ``<node>_<coupler>_<index>_preview.png``, then closed.

    Args:
        draw: the coupler's figures, given its fits.

    Returns:
        A ``NodeSpec.save_details`` taking the coupler's dataset, which names the node
        and the coupler, its fits, the node's data folder and the session; it saves
        nothing if the fits are empty.
    """

    def save(
        dataset: xr.Dataset, fits: Fits, data_path: Path, _session: "SessionContext"
    ) -> None:
        if not fits:
            return
        figures = draw(fits)
        _save_figures(
            figures, dataset.attrs["node"], dataset.attrs["coupler"], data_path
        )
        for figure in figures:
            plt.close(figure)

    return save


def get_class_schedule(measurement_cls: type) -> Callable[..., Schedule]:
    """A ``get_schedule`` that builds ``measurement_cls`` over the transmons, and over the edges in a coupler node.

    Args:
        measurement_cls: the measurement whose ``schedule_function`` makes the schedule.

    Returns:
        A ``NodeSpec.get_schedule`` taking the transmons, the edges if any, and the
        schedule's keywords.
    """

    def get_schedule(
        transmons: Mapping[str, ExtendedTransmon],
        edges: Mapping[str, Any] | None = None,
        **keywords: Any,
    ) -> Schedule:
        measurement = (
            measurement_cls(transmons)
            if edges is None
            else measurement_cls(transmons, edges)
        )
        return measurement.schedule_function(**keywords)

    return get_schedule


def get_fixed_sweep(values: np.ndarray) -> SweepFn:
    """A sweep over the same ``values`` for every element.

    Args:
        values: the setting's values.

    Returns:
        A sweep giving ``values`` for any element.
    """
    return lambda _element, _session: values


def get_waits_between_points(
    seconds: float,
) -> Callable[["Hardware", Mapping[str, Mapping[str, Any]], int], None]:
    """A ``set_external`` that lets the device settle ``seconds`` before every point but the first.

    Args:
        seconds: how long to wait before each point.

    Returns:
        A ``NodeSpec.set_external`` that waits on the hardware.
    """

    def wait(hardware: "Hardware", _point: Mapping, index: int) -> None:
        if index > 0:
            hardware.wait(seconds)

    return wait


def get_coord_name(quantity: str, element: str) -> str:
    """The name of an element's coordinate for a swept setting in the node's dataset.

    Args:
        quantity: the swept setting, such as ``mw_amplitudes``.
        element: the qubit or coupler.

    Returns:
        The coordinate's name, such as ``mw_amplitudesq00``.
    """
    return f"{quantity}{element}"


def _save_figures(
    figures: list[Figure], name: str, coupler: str, data_path: Path
) -> None:
    """Saves a coupler's figures as ``<node>_<coupler>_<index>_preview.png``, sized by their grid."""
    for index, figure in enumerate(figures):
        geometry = figure.axes[0].get_gridspec().get_geometry()
        nrows, ncols = geometry
        if geometry == (2, 3):
            figure.set_size_inches(14, 9)
        elif geometry == (1, 1):
            figure.set_size_inches(9, 6)
        elif geometry == (1, 2):
            figure.set_size_inches(12, 8)
        else:
            figure.set_size_inches(ncols * 6, nrows * 4)
        path = data_path / f"{name}_{coupler}_{index}_preview.png"
        figure.savefig(path, bbox_inches="tight", dpi=100)
