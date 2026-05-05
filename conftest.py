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

This file lives at the repository root — outside the
``tergite_tuner`` package — so it is automatically discovered
by pytest for every test in the project but is *not* shipped with the
built wheel.

The fixtures below build everything a calibration run needs:

* a fakeredis-backed ``redis_connection`` that stands in for a live
  Redis server,
* a :class:`Configuration` loaded from the bundled
  ``default_device_under_test`` template, and
* a :class:`SessionContext` that bundles the two together and points
  the calibration at fixture data.
"""

from pathlib import Path

import fakeredis
import numpy as np
import pytest

from tergite_tuner.config.session import SessionContext
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.utils.dto.enums import MeasurementMode

_FIXTURE_ENV_FILE = get_fixture_path("configs", "env", "default.env")
_FIXTURE_CONFIG_DIR = get_fixture_path(
    "templates",
    "default_device_under_test",
)
_FIXTURE_CONFIG_PATH = Path(_FIXTURE_CONFIG_DIR).resolve()
_PROJECT_ROOT = Path(__file__).parent


@pytest.fixture(autouse=True)
def redis_connection(monkeypatch):
    """A fakeredis-backed connection used by every test."""
    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    # mock Redis calls to return this connection. ``from_url`` must be
    # patched first because once ``redis.Redis`` is replaced with a
    # lambda, attribute lookup for ``from_url`` would fail.
    monkeypatch.setattr("redis.Redis.from_url", lambda *args, **kwargs: fake_redis)
    monkeypatch.setattr("redis.Redis", lambda *args, **kwargs: fake_redis)

    yield fake_redis
    fake_redis.flushall()


@pytest.fixture
def session_context(redis_connection) -> SessionContext:
    """A :class:`SessionContext` for the bundled fixture device.

    Function-scoped because it depends on the (function-scoped)
    ``redis_connection`` fixture; this also keeps the lazy
    ``session.redis`` cache from leaking a stale fakeredis client
    across tests.

    The ``config_dir`` is pointed at the bundled fixture device so
    ``session.config`` loads the test configuration package.
    """
    return SessionContext.from_env(
        _FIXTURE_ENV_FILE,
        config_dir=_FIXTURE_CONFIG_DIR,
        cluster_mode=MeasurementMode.dummy,
        user_samplespace={
            "resonator_spectroscopy": {
                "ro_frequencies": {
                    "q00": np.linspace(4499999949.5, 4500000050.5, 101),
                    "q01": np.linspace(4899999949.5, 4900000050.5, 101),
                }
            },
        },
        cluster_config=_FIXTURE_CONFIG_PATH / "cluster_config.json",
        node_config=_FIXTURE_CONFIG_PATH / "node_config.toml",
        spi_config=_FIXTURE_CONFIG_PATH / "spi_config.toml",
        device_config=_FIXTURE_CONFIG_PATH / "device_config.toml",
        output_dir=_PROJECT_ROOT / "out" / "pytest",
    )
