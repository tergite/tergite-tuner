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
"""Figures as data: what each axis draws, and how, comparable across versions.

A snapshot keeps a figure's size, its axes' places in it, and each axis's titles,
labels, limits, legend, texts and artists: lines, collections, images and patches,
with their colours, styles and sizes. It is taken before the figure is drawn, so it
holds what the code set, not what a platform's fonts make of it. Arrays longer than
``MAX_LISTED_VALUES`` are kept as their shape and statistics, per column for points.
"""

import math
import re
from collections.abc import Iterator, Mapping
from typing import Any

import numpy as np
from matplotlib import colors
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection, PathCollection, QuadMesh
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.text import Text

MAX_LISTED_VALUES = 32
# an array this narrow is points, as a line's x and y, each column kept apart
MAX_POINT_COLUMNS = 4
# colours of a collection coloured by value are kept as their count past this
MAX_LISTED_COLOURS = 8
RELATIVE_TOLERANCE = 1e-6
ABSOLUTE_TOLERANCE = 1e-12
# xarray's facet grids lay their axes out by the text's extents, which move with the
# process's matplotlib state; half a percent of the figure still catches a moved axis
POSITION_TOLERANCE = 0.005
NUMBER = re.compile(r"[-+]?\d+(?:\.(\d+))?(?:[eE]([-+]?\d+))?")


def get_figure_snapshot(figure: Figure) -> dict[str, Any]:
    """What ``figure`` draws, as JSON holds it.

    Args:
        figure: the figure, before it is drawn.

    Returns:
        The figure's size, texts and axes.
    """
    return {
        "size": _get_values(figure.get_size_inches()),
        "texts": [_get_text(text, has_position=True) for text in figure.texts],
        "axes": [_get_axes(axes) for axes in figure.axes],
    }


def get_mismatches(
    actual: Any, golden: Any, relative_tolerance: float = RELATIVE_TOLERANCE
) -> list[str]:
    """Where two snapshots differ: in structure, in text, or in a number past the tolerance.

    Args:
        actual: the snapshot taken now.
        golden: the snapshot recorded.
        relative_tolerance: how far a number may be from the golden's, relatively.

    Returns:
        Each difference, as its path and the two values; empty if they match.
    """
    actual_values = dict(_flatten(actual))
    golden_values = dict(_flatten(golden))
    mismatches = [
        f"{path}: missing, golden {golden_values[path]!r}"
        for path in golden_values.keys() - actual_values.keys()
    ] + [
        f"{path}: {actual_values[path]!r}, not in the golden"
        for path in actual_values.keys() - golden_values.keys()
    ]
    for path in sorted(actual_values.keys() & golden_values.keys()):
        value, expected = actual_values[path], golden_values[path]
        if "/position/" in path:
            is_close = _is_close(value, expected, 0, POSITION_TOLERANCE)
        else:
            is_close = _is_close(value, expected, relative_tolerance)
        if not is_close:
            mismatches.append(f"{path}: {value!r}, golden {expected!r}")
    return sorted(mismatches)


def _get_axes(axes: Axes) -> dict[str, Any]:
    legend = axes.get_legend()
    return {
        "position": _get_values(axes.get_position().bounds),
        "is_axis_on": axes.axison,
        "titles": {
            location: _get_text(text)
            for location, text in (
                ("left", axes._left_title),
                ("center", axes.title),
                ("right", axes._right_title),
            )
            if text.get_text()
        },
        "xlabel": _get_text(axes.xaxis.label),
        "ylabel": _get_text(axes.yaxis.label),
        "xlim": _get_values(axes.get_xlim()),
        "ylim": _get_values(axes.get_ylim()),
        "scales": [axes.get_xscale(), axes.get_yscale()],
        "lines": [_get_line(line) for line in axes.lines],
        "collections": [_get_collection(item) for item in axes.collections],
        "images": [_get_image(image) for image in axes.images],
        "patches": [_get_patch(patch) for patch in axes.patches],
        "texts": [_get_text(text, has_position=True) for text in axes.texts],
        "legend": (
            None if legend is None else [_get_text(text) for text in legend.get_texts()]
        ),
    }


def _get_line(line: Any) -> dict[str, Any]:
    return {
        "xy": _get_values(line.get_xydata()),
        "label": _get_label(line),
        "color": _get_colour(line.get_color()),
        "alpha": line.get_alpha(),
        "linestyle": line.get_linestyle(),
        "linewidth": line.get_linewidth(),
        "marker": str(line.get_marker()),
        "markersize": line.get_markersize(),
    }


def _get_collection(collection: Any) -> dict[str, Any]:
    values = collection.get_array()
    record = {
        "type": type(collection).__name__,
        "label": _get_label(collection),
        "offsets": _get_values(collection.get_offsets()),
        "facecolors": _get_colours(collection.get_facecolor()),
        "values": None if values is None else _get_values(values),
        "cmap": None if values is None else collection.get_cmap().name,
        "clim": None if values is None else _get_values(collection.get_clim()),
    }
    if isinstance(collection, PathCollection):
        record["sizes"] = _get_values(collection.get_sizes())
    elif isinstance(collection, QuadMesh):
        record["coordinates"] = _get_values(collection.get_coordinates())
    elif isinstance(collection, LineCollection):
        record["segments"] = [
            _get_values(segment) for segment in collection.get_segments()
        ]
    return record


def _get_image(image: Any) -> dict[str, Any]:
    return {
        "values": _get_values(image.get_array()),
        "cmap": image.get_cmap().name,
        "clim": _get_values(image.get_clim()),
        "extent": _get_values(image.get_extent()),
    }


def _get_patch(patch: Any) -> dict[str, Any]:
    record = {
        "type": type(patch).__name__,
        "facecolor": _get_colour(patch.get_facecolor()),
        "label": _get_label(patch),
    }
    if isinstance(patch, Rectangle):
        record["bounds"] = _get_values(
            (*patch.get_xy(), patch.get_width(), patch.get_height())
        )
    return record


def _get_text(text: Text, has_position: bool = False) -> dict[str, Any]:
    record = {
        "text": text.get_text(),
        "size": text.get_fontsize(),
        "weight": str(text.get_fontweight()),
        "color": _get_colour(text.get_color()),
    }
    if has_position:
        record["position"] = _get_values(text.get_position())
    return record


def _get_label(artist: Any) -> str | None:
    """The artist's legend label, or None for the ``_child`` labels matplotlib numbers by creation order."""
    label = artist.get_label()
    return None if label.startswith("_") else label


def _get_colour(colour: Any) -> str:
    return colors.to_hex(colour, keep_alpha=True)


def _get_colours(colours: Any) -> list[str] | int:
    unique = list(dict.fromkeys(_get_colour(colour) for colour in colours))
    return unique if len(unique) <= MAX_LISTED_COLOURS else len(unique)


def _get_values(values: Any) -> Any:
    """Numbers as a list, or, if more than ``MAX_LISTED_VALUES``, as their shape and statistics."""
    array = np.ma.filled(np.ma.asarray(values, dtype=float), np.nan)
    if array.size <= MAX_LISTED_VALUES:
        return _to_plain(array.tolist())
    is_points = array.ndim == 2 and array.shape[1] <= MAX_POINT_COLUMNS
    columns = list(array.T) if is_points else [array.ravel()]
    statistics = [_get_statistics(column) for column in columns]
    return {
        "shape": list(array.shape),
        **({"columns": statistics} if is_points else statistics[0]),
    }


def _get_statistics(values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    if not finite.size:
        return {"nans": int(values.size)}
    return {
        "nans": int(values.size - finite.size),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "mean": float(finite.mean()),
        "std": float(finite.std()),
    }


def _to_plain(value: Any) -> Any:
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return None if isinstance(value, float) and math.isnan(value) else value


def _flatten(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _flatten(item, f"{path}/{key}")
    elif isinstance(value, list):
        yield f"{path}/length", len(value)
        for index, item in enumerate(value):
            yield from _flatten(item, f"{path}/{index}")
    else:
        yield path, value


def _is_close(
    value: Any,
    expected: Any,
    relative_tolerance: float,
    absolute_tolerance: float = ABSOLUTE_TOLERANCE,
) -> bool:
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    is_expected_number = isinstance(expected, (int, float)) and not isinstance(
        expected, bool
    )
    if isinstance(value, str) and isinstance(expected, str):
        return _is_text_close(value, expected, relative_tolerance)
    if not (is_number and is_expected_number):
        return value == expected
    return math.isclose(
        value, expected, rel_tol=relative_tolerance, abs_tol=absolute_tolerance
    )


def _is_text_close(text: str, expected: str, relative_tolerance: float) -> bool:
    """Whether two texts are the same but for their numbers, each within the tolerance or, printed with decimals, a unit of its last digit."""
    if NUMBER.sub("#", text) != NUMBER.sub("#", expected):
        return False
    for number, expected_number in zip(
        NUMBER.finditer(text), NUMBER.finditer(expected), strict=True
    ):
        decimals, exponent = expected_number.groups()
        # a printed decimal may round either way; an integer, such as a qubit's, may not
        last_digit = (
            10.0 ** (int(exponent or 0) - len(decimals or "")) * (1 + 1e-9)
            if decimals or exponent
            else 0
        )
        difference = abs(float(number.group()) - float(expected_number.group()))
        if difference > max(
            relative_tolerance * abs(float(expected_number.group())), last_digit
        ):
            return False
    return True
