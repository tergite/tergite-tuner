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

"""Device states for tests, from the state JSON the fixtures keep."""

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tergite_tuner.state import DeviceState

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext
    from tergite_tuner.config.types import DeviceConfig


def get_state(records: Mapping[str, Any] | str | Path) -> DeviceState:
    """The state of ``records``, or of the JSON file holding them."""
    if not isinstance(records, Mapping):
        records = json.loads(Path(records).read_text())
    return DeviceState(records)


@contextmanager
def loaded_state(
    session: "SessionContext", records: Mapping[str, Any] | str | Path
) -> Iterator[DeviceState]:
    """Gives ``session`` the state of ``records`` alone, for the block."""
    session.state = get_state(records)
    yield session.state


def set_drive_frequencies_from_device(
    state: DeviceState, device_config: "DeviceConfig"
) -> None:
    """Sets each qubit's f01 and f12 to the device config's.

    standard_state.json holds another chip's frequencies, 0.6-0.8 GHz above the
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
