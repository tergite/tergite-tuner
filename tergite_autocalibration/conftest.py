# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Test-suite-wide pytest configuration.

The fixtures below build everything a calibration run needs:

* a fakeredis-backed ``redis_connection`` that stands in for a live
  Redis server,
* a :class:`Configuration` loaded from the bundled
  ``default_device_under_test`` template, and
* a :class:`SessionContext` that bundles the two together and points
  the calibration at fixture data.

The session is a ``yield`` so the fakeredis client can be flushed
between sessions if needed in the future.
"""

from pathlib import Path

import fakeredis
import numpy as np
import pytest

from tergite_autocalibration.config.load import Configuration, load_configuration
from tergite_autocalibration.config.session import SessionContext
from tergite_autocalibration.lib.nodes import NodeEnum
from tergite_autocalibration.utils.dto.enums import MeasurementMode

_FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures"
_FIXTURE_ENV_PATH = _FIXTURES / "configs" / "env" / "default.env"
_FIXTURE_META_PATH = (
    _FIXTURES / "templates" / "default_device_under_test" / "configuration.meta.toml"
)


@pytest.fixture(scope="session")
def redis_connection():
    """A fakeredis-backed connection used by every test."""
    conn = fakeredis.FakeRedis(decode_responses=True)
    yield conn
    conn.flushall()


@pytest.fixture(scope="session")
def configuration() -> Configuration:
    """The :class:`Configuration` loaded from the bundled fixture meta."""
    return load_configuration(_FIXTURE_META_PATH)


@pytest.fixture(scope="session")
def session_context(redis_connection, configuration) -> SessionContext:
    """A :class:`SessionContext` for the bundled fixture device."""
    return SessionContext(
        cluster_mode=MeasurementMode.dummy,
        cluster_ip=None,
        target_node=NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
        qubits=["q00", "q01"],
        couplers=["q00_q01"],
        name="no_name_for_this_run_set",
        plotting=False,
        user_samplespace={
            "resonator_spectroscopy": {
                "ro_frequencies": {
                    "q00": np.linspace(4499999949.5, 4500000050.5, 101),
                    "q01": np.linspace(4899999949.5, 4900000050.5, 101),
                }
            },
        },
        redis_connection=redis_connection,
        config=configuration,
    )
