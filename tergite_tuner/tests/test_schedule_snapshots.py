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
"""Checks each node's sweeps and the pulses its schedules play against recorded snapshots.

A snapshot in fixtures/goldens/schedule_snapshots records a node's default sweeps on the
standard state, and the device-compiled schedule of each point of the sweeps it lists:
every pulse, acquisition and loop, its time and settings. The schedules are built from the
recorded sweeps, so a node's schedule is checked even where its default sweeps changed.

A change that alters a schedule or a default sweep on purpose rewrites the snapshots with
``UPDATE_GOLDENS=1 pytest tergite_tuner/tests/test_schedule_snapshots.py``, and the commit
says why. Run it without ``-n``: both tests of a node write its file.
"""

import os
from pathlib import Path

import pytest

from tergite_tuner.backend import (
    ExtendedTransmon,
    QuantumDevice,
    close_device_resources,
    configure_device,
)
from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib import run
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.lib.spec import NodeSpec
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import TEST_COUPLERS, TEST_QUBITS
from tergite_tuner.tests.utils.snapshots import (
    compile_to_device,
    find_differences,
    find_value_differences,
    get_snapshot,
    read_snapshot_file,
    to_plain,
    to_sweeps,
    write_snapshot_file,
)
from tergite_tuner.tests.utils.state import loaded_state
from tergite_tuner.utils.types.node_enum import NodeEnum

SNAPSHOT_DIR = Path(get_fixture_path("goldens", "schedule_snapshots"))
STATE_FILE = get_fixture_path("states", "standard_state.json")
SNAPSHOT_NODES = sorted(path.stem for path in SNAPSHOT_DIR.glob("*.json"))


@pytest.mark.parametrize("node_name", SNAPSHOT_NODES)
def test_default_sweeps_match_the_snapshot(node_name, session_context):
    path = SNAPSHOT_DIR / f"{node_name}.json"
    record = read_snapshot_file(path)
    spec = DEFAULT_NODE_SPECS[NodeEnum(node_name)]
    session = session_context.model_copy(update={"user_samplespace": {}})

    with loaded_state(session, STATE_FILE):
        default_sweeps = to_plain(
            {
                "sweeps": run.get_sweeps(spec, session),
                "outer_sweeps": run.get_outer_sweeps(spec, session),
                "external_sweeps": run.get_external_sweeps(spec, session),
            }
        )

    if _should_update():
        record["default_sweeps"] = default_sweeps
        write_snapshot_file(path, record)
    assert find_value_differences(record["default_sweeps"], default_sweeps) == []


@pytest.mark.parametrize("node_name", SNAPSHOT_NODES)
def test_schedules_match_the_snapshot(node_name, session_context):
    path = SNAPSHOT_DIR / f"{node_name}.json"
    record = read_snapshot_file(path)
    spec = DEFAULT_NODE_SPECS[NodeEnum(node_name)]

    with loaded_state(session_context, STATE_FILE):
        ExtendedTransmon.close_all()
        device = configure_device(
            node_name, TEST_QUBITS, TEST_COUPLERS, session_context
        )
        try:
            snapshots = [
                _get_point_snapshot(
                    spec,
                    device,
                    record["sweeps"] | expected["outer_point"],
                    session_context,
                )
                for expected in record["schedules"]
            ]
        finally:
            close_device_resources(device)

    if _should_update():
        schedules = [
            {"outer_point": expected["outer_point"], **snapshot}
            for expected, snapshot in zip(record["schedules"], snapshots, strict=True)
        ]
        record["schedules"] = schedules
        write_snapshot_file(path, record)
    differences = [
        f"point {index} {expected['outer_point']}: {difference}"
        for index, (expected, snapshot) in enumerate(
            zip(record["schedules"], snapshots, strict=True)
        )
        for difference in find_differences(expected, snapshot)
    ]
    assert differences == []


def _get_point_snapshot(
    spec: NodeSpec, device: QuantumDevice, sweeps: dict, session: SessionContext
) -> dict:
    schedule = run.get_node_schedule(spec, device, to_sweeps(sweeps), session)
    return get_snapshot(compile_to_device(schedule, device, spec.name.value))


def _should_update() -> bool:
    if not os.environ.get("UPDATE_GOLDENS"):
        return False
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail("UPDATE_GOLDENS rewrites shared files: run it without -n")
    return True
