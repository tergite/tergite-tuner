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
"""Schedules as data: what a device plays and acquires, and when, comparable across versions.

A snapshot is a device-compiled schedule's clocks, repetitions and events: each pulse,
acquisition and loop at its absolute time. Events of one kind, alike but for their numbers,
share a row: the numbers that vary are columns, one value per event. A sweep repeats one
shot with other numbers, so its snapshot keeps the shot's few kinds of events once.

The module imports only numpy, and reads schedules by their attributes: the snapshot of
an older quantify-scheduler's schedule is taken with the same code.
"""

import json
import math
import re
from collections.abc import Iterator, Mapping
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

# below the last bits in which platforms' maths libraries differ
SIGNIFICANT_DIGITS = 9
# what a snapshot file keeps of each number: past the tolerance, short of the noise
STORED_DIGITS = 12
RELATIVE_TOLERANCE = 1e-9
# a picosecond, a nano-volt: far below any setting a schedule takes
ABSOLUTE_TOLERANCE = 1e-12
MAX_REPORTED_ROWS = 5
NUMBER_LIST = re.compile(r"\[[-+.\de\s,]*\]")


def compile_to_device(schedule: Any, device: Any, name: str) -> Any:
    """Compiles ``schedule``'s gates into ``device``'s pulses, timed absolutely, without hardware.

    Args:
        schedule: the schedule.
        device: the quantum device whose elements and edges translate the gates.
        name: the compiler's name.

    Returns:
        The device-compiled schedule.
    """
    config = device.generate_compilation_config().model_copy(
        update={"hardware_compilation_config": None}
    )
    return config.backend(name=name).compile(schedule=schedule, config=config)


def get_snapshot(schedule: Any) -> dict[str, Any]:
    """A device-compiled schedule's clocks, repetitions and events, its alike events grouped.

    Args:
        schedule: a schedule compiled by ``compile_to_device``.

    Returns:
        ``repetitions``; ``clocks``, each clock's frequency; and ``events``, a list of
        groups, each with the ``fields`` its events share and the ``columns`` they vary in.
    """
    groups: dict[str, list[dict[str, float]]] = {}
    for event in _iterate_events(schedule, 0.0):
        fields = {
            key: _round_nested(value)
            for key, value in event.items()
            if not _is_number(value)
        }
        numbers = {
            key: float(value) for key, value in event.items() if _is_number(value)
        }
        key = json.dumps({"fields": fields, "columns": sorted(numbers)}, sort_keys=True)
        groups.setdefault(key, []).append(numbers)
    return {
        "repetitions": schedule.repetitions,
        "clocks": dict(sorted(_get_clocks(schedule).items())),
        "events": [_get_group(key, rows) for key, rows in sorted(groups.items())],
    }


def find_differences(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> list[str]:
    """How ``actual`` differs from ``expected``, two snapshots, beyond the tolerances.

    Args:
        expected: the snapshot taken as right.
        actual: the snapshot to check.

    Returns:
        One line per difference; empty if they match.
    """
    differences = []
    if expected["repetitions"] != actual["repetitions"]:
        differences.append(
            f"repetitions: {expected['repetitions']} != {actual['repetitions']}"
        )
    differences += _find_clock_differences(expected["clocks"], actual["clocks"])
    expected_groups = {_get_group_key(group): group for group in expected["events"]}
    actual_groups = {_get_group_key(group): group for group in actual["events"]}
    for key in sorted(expected_groups.keys() - actual_groups.keys()):
        differences.append(f"missing {_describe(expected_groups[key])}")
    for key in sorted(actual_groups.keys() - expected_groups.keys()):
        differences.append(f"unexpected {_describe(actual_groups[key])}")
    for key in sorted(expected_groups.keys() & actual_groups.keys()):
        differences += _find_row_differences(expected_groups[key], actual_groups[key])
    return differences


def find_value_differences(expected: Any, actual: Any, path: str = "") -> list[str]:
    """How ``actual`` differs from ``expected``, nested mappings and lists, beyond the tolerances.

    Args:
        expected: the values taken as right, as ``to_plain`` gives them.
        actual: the values to check, as ``to_plain`` gives them.
        path: where in an enclosing structure the values sit, for the report.

    Returns:
        One line per difference; empty if they match.
    """
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        differences = [
            f"{path}/{key}: {'missing' if key in expected else 'unexpected'}"
            for key in sorted(expected.keys() ^ actual.keys())
        ]
        for key in sorted(expected.keys() & actual.keys()):
            differences += find_value_differences(
                expected[key], actual[key], f"{path}/{key}"
            )
        return differences
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: {len(actual)} values, not {len(expected)}"]
        return [
            difference
            for index, (wanted, found) in enumerate(zip(expected, actual, strict=True))
            for difference in find_value_differences(wanted, found, f"{path}[{index}]")
        ]
    if _is_number(expected) and _is_number(actual):
        is_equal = _is_close(expected, actual)
    else:
        is_equal = expected == actual
    return [] if is_equal else [f"{path}: {actual!r} != {expected!r}"]


def to_sweeps(values: Mapping[str, Any]) -> dict[str, Any]:
    """Sweeps as a schedule takes them, from their ``to_plain`` form: each list an array.

    Args:
        values: each setting's values per element, or a point's value per element.

    Returns:
        The same mapping, its lists numpy arrays.
    """
    return {
        key: to_sweeps(item)
        if isinstance(item, Mapping)
        else np.asarray(item)
        if isinstance(item, list)
        else item
        for key, item in values.items()
    }


def write_snapshot_file(path: Path, record: Mapping[str, Any]) -> None:
    """Writes ``record`` as JSON, each list of numbers on one line.

    Args:
        path: the file.
        record: snapshots and what they were taken of, as ``to_plain`` gives them.
    """
    text = json.dumps(record, indent=1, sort_keys=True)
    text = NUMBER_LIST.sub(lambda match: re.sub(r"\s+", "", match[0]), text)
    path.write_text(text + "\n")


def read_snapshot_file(path: Path) -> dict[str, Any]:
    """The record ``write_snapshot_file`` wrote to ``path``."""
    return json.loads(path.read_text())


def to_plain(value: Any) -> Any:
    """``value`` as JSON holds it.

    Args:
        value: numbers, strings, enums, arrays and mappings of them.

    Returns:
        The value in Python's own types; anything else as its ``repr``.
    """
    if isinstance(value, Enum):
        return to_plain(value.value)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value)
    if isinstance(value, (complex, np.complexfloating)):
        return [float(value.real), float(value.imag)]
    if isinstance(value, Mapping):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return to_plain(value.tolist())
    if isinstance(value, (list, tuple, range)):
        return [to_plain(item) for item in value]
    if value is None or isinstance(value, str):
        return value
    return repr(value)


def _iterate_events(operation: Any, start: float) -> Iterator[dict[str, Any]]:
    """Each pulse, acquisition and loop of ``operation``, which starts at ``start``."""
    if hasattr(operation, "schedulables"):
        for schedulable in operation.schedulables.values():
            child = operation.operations[schedulable["operation_id"]]
            yield from _iterate_events(child, start + schedulable["abs_time"])
        return
    control_flow = operation.data.get("control_flow_info")
    if control_flow is not None:
        settings = {
            key: to_plain(value)
            for key, value in control_flow.items()
            if key not in ("body", "t0")
        }
        yield {"kind": "control_flow", **settings, "t": start}
        yield from _iterate_events(operation.body, start)
        return
    for kind in ("pulse_info", "acquisition_info"):
        for info in operation.data.get(kind) or []:
            event = {key: to_plain(value) for key, value in info.items() if key != "t0"}
            yield {"kind": kind, **event, "t": start + info["t0"]}


def _get_clocks(schedule: Any) -> dict[str, float]:
    clocks = {
        name: float(resource.data["freq"])
        for name, resource in schedule.resources.items()
        if resource.data.get("freq") is not None
    }
    for operation in schedule.operations.values():
        child = getattr(operation, "body", operation)
        if hasattr(child, "resources"):
            clocks |= _get_clocks(child)
    return clocks


def _get_group(key: str, rows: list[dict[str, float]]) -> dict[str, Any]:
    """A group's shared fields and its columns, a constant column kept as its one value."""
    names = json.loads(key)["columns"]
    rows = sorted(rows, key=lambda row: [_round(row[name]) for name in names])
    columns = {}
    for name in names:
        values = [_round(row[name], STORED_DIGITS) for row in rows]
        is_constant = all(value == values[0] for value in values)
        columns[name] = values[0] if is_constant else values
    return {"fields": json.loads(key)["fields"], "count": len(rows), "columns": columns}


def _find_clock_differences(
    expected: Mapping[str, float], actual: Mapping[str, float]
) -> list[str]:
    return [
        f"clock {name}: {expected.get(name)} != {actual.get(name)}"
        for name in sorted(expected.keys() | actual.keys())
        if name not in expected
        or name not in actual
        or not _is_close(expected[name], actual[name])
    ]


def _find_row_differences(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> list[str]:
    label = _describe(expected)
    if expected["count"] != actual["count"]:
        return [f"{label}: {actual['count']} events, not {expected['count']}"]
    differences = []
    for name in expected["columns"]:
        wanted = np.broadcast_to(expected["columns"][name], expected["count"])
        found = np.broadcast_to(actual["columns"][name], actual["count"])
        rows = np.flatnonzero(
            ~np.isclose(found, wanted, rtol=RELATIVE_TOLERANCE, atol=ABSOLUTE_TOLERANCE)
        )
        if len(rows):
            shown = ", ".join(
                f"row {row}: {found[row]!r} != {wanted[row]!r}"
                for row in rows[:MAX_REPORTED_ROWS]
            )
            differences.append(f"{label}: {name} differs in {len(rows)} rows ({shown})")
    return differences


def _get_group_key(group: Mapping[str, Any]) -> str:
    return json.dumps(
        {"fields": group["fields"], "columns": sorted(group["columns"])}, sort_keys=True
    )


def _describe(group: Mapping[str, Any]) -> str:
    fields = ", ".join(
        f"{key}={value}"
        for key, value in group["fields"].items()
        if key in ("kind", "wf_func", "port", "clock", "protocol")
    )
    return f"{group['count']} x [{fields}] varying in {sorted(group['columns'])}"


def _round_nested(value: Any) -> Any:
    """``value`` with the numbers inside its lists and mappings rounded to ``SIGNIFICANT_DIGITS``."""
    if isinstance(value, list):
        return [
            _round(item) if _is_number(item) else _round_nested(item) for item in value
        ]
    if isinstance(value, dict):
        return {key: _round_nested(item) for key, item in value.items()}
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_close(expected: float, actual: float) -> bool:
    return math.isclose(
        actual, expected, rel_tol=RELATIVE_TOLERANCE, abs_tol=ABSOLUTE_TOLERANCE
    )


def _round(value: float, digits: int = SIGNIFICANT_DIGITS) -> float:
    return float(f"{value:.{digits}g}")
