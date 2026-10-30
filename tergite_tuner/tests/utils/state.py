# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Device states for tests, from the Redis dumps the fixtures keep."""

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tergite_tuner.state import COLLECTIONS, DeviceState

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext
    from tergite_tuner.config.types import DeviceConfig


def get_state(dump: Mapping[str, Any] | str | Path) -> DeviceState:
    """The state in a Redis dump, or its JSON file: each ``<collection>:<element>`` hash."""
    if not isinstance(dump, Mapping):
        dump = json.loads(Path(dump).read_text())
    records = {}
    for key, entry in dump.items():
        collection, _, element = key.partition(":")
        if collection in COLLECTIONS and entry["type"] == "hash":
            records.setdefault(collection, {})[element] = {
                field: _decode(value) for field, value in entry["value"].items()
            }
    return DeviceState(records)


@contextmanager
def loaded_state(
    session: "SessionContext", dump: Mapping[str, Any] | str | Path
) -> Iterator[DeviceState]:
    """Gives ``session`` the state in a Redis dump, alone, for the block."""
    session.state = get_state(dump)
    yield session.state


def set_drive_frequencies_from_device(
    state: DeviceState, device_config: "DeviceConfig"
) -> None:
    """Sets each qubit's f01 and f12 to the device config's.

    standard_redis_mock.json holds another chip's frequencies, 0.6-0.8 GHz above the
    fixture cluster's drive LOs, which the dummy cluster refuses to set as NCO frequencies.
    """
    state.load(
        {
            "transmons": {
                qubit: {
                    "clock_freqs:f01": values["VNA_f01_frequency"],
                    "clock_freqs:f12": values["VNA_f12_frequency"],
                }
                for qubit, values in device_config.qubits.items()
                if state.get_record("transmons", qubit)
            }
        }
    )


def _decode(value: str) -> Any:
    """A dumped value as the Redis store read one saved without its type: JSON, else the string."""
    with suppress(json.JSONDecodeError):
        return json.loads(value)
    return value
