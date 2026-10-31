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

from tergite_tuner.backend import ExtendedTransmon, Schedule
from tergite_tuner.utils.types.node_enum import NodeEnum

if TYPE_CHECKING:
    from tergite_tuner.backend import Hardware
    from tergite_tuner.config.session import SessionContext

# an element's values of a swept setting
SweepFn = Callable[[str, "SessionContext"], np.ndarray]


class Fit(NamedTuple):
    value: Any
    error: float = 0


Fits = Mapping[str, Fit]


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


class ElementAnalysis:
    """Base of the analyses that keep state between fitting and plotting one element."""

    def __init__(self, s21: xr.DataArray, session: "SessionContext"):
        self.qubit = s21.attrs["qubit"]
        self.data_var = f"y{self.qubit}"
        self.S21 = s21.to_dataset(name=self.data_var)
        self.dataset = self.S21
        self.magnitudes = np.abs(self.S21)
        self.session = session

    def analyse(self) -> Fits | None:
        raise NotImplementedError


class CouplerAnalysis:
    """Base of the coupler analyses: one coupler's variables, saved in real and imaginary parts.

    ``keywords`` become attributes, as the node's analysis keywords for the coupler.
    """

    def __init__(self, dataset: xr.Dataset, session: "SessionContext", **keywords: Any):
        self.session = session
        self.name = dataset.attrs["node"]
        self.coupler = dataset.attrs["coupler"]
        self.control_qubit, self.target_qubit = (
            session.device_config.get_control_target_qubit_pair_by_coupler(self.coupler)
        )
        self.dataset = dataset
        self.coord = dataset.coords
        self.data_var = list(dataset.data_vars)[0]
        self.S21 = dataset.isel(ReIm=0) + 1j * dataset.isel(ReIm=1)
        for var in self.S21.data_vars:
            self.S21[var].attrs = dataset[var].attrs
        self.magnitudes = np.abs(self.S21)
        for var in self.S21.data_vars.values():
            if var.attrs["qubit"] == self.control_qubit:
                self.control_qubit_data_var = var
            elif var.attrs["qubit"] == self.target_qubit:
                self.target_qubit_data_var = var
            else:
                raise ValueError("No control or target qubits")
        for name, value in keywords.items():
            setattr(self, name, value)

    def analyse(self) -> Fits | None:
        raise NotImplementedError


def get_fits_from_result(
    result: Mapping[str, Mapping[str, Any]], is_successful: bool
) -> Fits | None:
    """The fits of an analysis reporting ``{field: {"value": ..., "error": ...}}``."""
    fits = {name: Fit(item["value"], item["error"]) for name, item in result.items()}
    if not is_successful:
        # failed fits keep their values, to plot and inspect, but are not stored
        fits["failed"] = Fit(True)
    return fits


def is_failed(fits: Fits | None) -> bool:
    """Whether an element's analysis failed: it gave no fits, or marked them ``failed``."""
    return fits is None or "failed" in fits


def get_coupler_analyser(
    analysis_cls: type[CouplerAnalysis],
) -> Callable[..., Fits | None]:
    """An ``analyse`` that builds an ``analysis_cls`` for the coupler and keeps its figures in the fits.

    The figures are drawn here so the analysis, as large as the dataset, is freed before they are saved.
    """

    def analyse(
        dataset: xr.Dataset, session: "SessionContext", **keywords: Any
    ) -> Fits | None:
        analysis = analysis_cls(dataset, session, **keywords)
        fits = analysis.analyse()
        if fits is None:
            return None
        figures = {}
        analysis.plotter(figures_dictionary=figures)
        for figure in figures.get(analysis.coupler, []):
            # out of pyplot's registry, so a run that saves no plots does not keep them open
            plt.close(figure)
        return {**fits, "figures": Fit(figures.get(analysis.coupler, []))}

    return analyse


def save_coupler_figures(
    dataset: xr.Dataset, fits: Fits, data_path: Path, _session: "SessionContext"
) -> None:
    """Saves the figures in the fits as ``<node>_<coupler>_<index>_preview.png``."""
    if not fits:
        return
    name, coupler = dataset.attrs["node"], dataset.attrs["coupler"]
    for index, figure in enumerate(fits["figures"].value):
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


def get_class_schedule(measurement_cls: type) -> Callable[..., Schedule]:
    """A ``get_schedule`` that builds ``measurement_cls`` over the transmons, and over the edges in a coupler node."""

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


def get_class_analyser(
    analysis_cls: type[ElementAnalysis],
) -> Callable[[xr.DataArray, "SessionContext"], Fits | None]:
    """An ``analyse`` that builds an ``analysis_cls`` for the element and runs it."""
    return lambda s21, session: analysis_cls(s21, session).analyse()


def plot_class_analysis(
    axis: Any, _s21: xr.DataArray, fits: Fits, _session: "SessionContext"
) -> None:
    """A ``plot`` for the analysis object an ``ElementAnalysis`` puts in its fits."""
    if fits:
        fits["analysis"].value.plotter(axis)


def get_fixed_sweep(values: np.ndarray) -> SweepFn:
    """A sweep over the same ``values`` for every element."""
    return lambda _element, _session: values


def get_waits_between_points(
    seconds: float,
) -> Callable[["Hardware", Mapping[str, Mapping[str, Any]], int], None]:
    """A ``set_external`` that lets the device settle ``seconds`` before every point but the first."""

    def wait(hardware: "Hardware", _point: Mapping, index: int) -> None:
        if index > 0:
            hardware.wait(seconds)

    return wait


def get_coord_name(quantity: str, element: str) -> str:
    return f"{quantity}{element}"
