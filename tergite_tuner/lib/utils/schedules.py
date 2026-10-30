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
"""Building blocks the measurements' schedules share."""

import itertools
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Literal

from tergite_tuner.backend import (
    ClockResource,
    DRAGPulse,
    ExtendedTransmon,
    Measure,
    Measure_RO1,
    Reset,
    Schedule,
    X,
)

AddPoint = Callable[[Schedule, str, dict[str, Any], int], None]


def get_multiplexed_schedule(
    name: str,
    transmons: Mapping[str, ExtendedTransmon],
    sweeps: Mapping[str, Mapping[str, Any]],
    add_point: AddPoint,
    repetitions: int,
    *,
    qubit_reset_ref_pt_new: Literal["start", "end"] | None = None,
    root_reset_duration: float | None = None,
) -> Schedule:
    """A schedule running each qubit through every point of its sweeps, all qubits in parallel.

    After a shared reset, each qubit is reset and then, for every point, ``add_point``
    adds its operations and measurement, followed by a reset of that qubit.

    Args:
        name: the schedule's name.
        transmons: the qubits, by name.
        sweeps: each swept setting's values per qubit, ordered as the node's samplespace,
            which ``configure_dataset`` reshapes with the first setting varying fastest.
        add_point: adds one point's operations to the schedule, given the qubit, the
            point's value of each setting, and the point's acquisition index.
        repetitions: how many times the schedule runs.
        qubit_reset_ref_pt_new: aligns each qubit's reset to the shared reset by its
            ``"start"`` (the default) or ``"end"``.
        root_reset_duration: the shared reset's duration, if not the qubits' own.
    """
    schedule = Schedule(name, repetitions)
    qubits = list(transmons)
    root_reset = (
        Reset(*qubits)
        if root_reset_duration is None
        else Reset(*qubits, duration=root_reset_duration)
    )
    root = schedule.add(root_reset, label="Reset")
    for qubit in next(iter(sweeps.values())):
        schedule.add(Reset(*qubits), ref_op=root, ref_pt_new=qubit_reset_ref_pt_new)
        for acq_index, point in enumerate(_get_points(sweeps, qubit)):
            add_point(schedule, qubit, point, acq_index)
            schedule.add(Reset(qubit))
    return schedule


def get_drive_clock(qubit: str, state: int) -> str:
    """The clock that drives ``qubit`` from ``state`` (0 or 1) to the state above it."""
    if state not in (0, 1):
        raise ValueError(f"Invalid qubit state: {state}")
    return f"{qubit}.{state}{state + 1}"


def get_measure_operation(state: int) -> type[Measure]:
    """The measurement that tells ``state`` (0 or 1) from the state above it."""
    if state == 0:
        return Measure
    if state == 1:
        return Measure_RO1
    raise ValueError(f"Invalid qubit state: {state}")


def add_12_clocks(
    schedule: Schedule, transmons: Mapping[str, ExtendedTransmon]
) -> None:
    for qubit, transmon in transmons.items():
        frequency = transmon.clock_freqs.f12()
        schedule.add_resource(ClockResource(name=f"{qubit}.12", freq=frequency))


def prepare_state(schedule: Schedule, transmon: ExtendedTransmon, state: int) -> Any:
    """Adds the pulses taking ``transmon`` from 0 to ``state``, returning the last one, or None for 0."""
    if state == 0:
        return None
    pulse = schedule.add(X(transmon.name))
    if state == 2:
        pulse = schedule.add(
            DRAGPulse(
                duration=transmon.r12.ef_duration(),
                G_amp=transmon.r12.ef_amp180(),
                D_amp=transmon.r12.ef_motzoi(),
                port=transmon.ports.microwave(),
                clock=f"{transmon.name}.12",
                phase=0,
            ),
        )
    return pulse


def _get_points(
    sweeps: Mapping[str, Mapping[str, Any]], qubit: str
) -> Iterator[dict[str, Any]]:
    names = list(reversed(sweeps))
    for values in itertools.product(*(sweeps[name][qubit] for name in names)):
        yield dict(zip(names, values, strict=True))
