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

* a :class:`Configuration` loaded from the bundled
  ``default_device_under_test`` template, and
* a :class:`SessionContext` that bundles the two together and points
  the calibration at fixture data.
"""

from pathlib import Path

import numpy as np
import pytest

from tergite_tuner.config.session import SessionContext
from tergite_tuner.tests.utils.fixtures import get_fixture_path, load_fixture
from tergite_tuner.tests.utils.state import get_state
from tergite_tuner.utils.types.enums import MeasurementMode

_FIXTURE_CONFIGS_DIR = Path(get_fixture_path("configs"))
_PROJECT_ROOT = Path(__file__).parent
_SINGLE_RUN_REDIS_JSON = load_fixture("redis/single-run-redis-data.json")


@pytest.fixture
def session_context() -> SessionContext:
    """A :class:`SessionContext` for the bundled fixture device.

    Function-scoped, so each test gets its own device state.

    The ``config_dir`` is pointed at the bundled fixture device so
    ``session.config`` loads the test configuration package.
    """
    return SessionContext.from_env(
        _FIXTURE_CONFIGS_DIR / "default.env",
        cluster_mode=MeasurementMode.dummy,
        user_samplespace={
            "resonator_spectroscopy": {
                "ro_frequencies": {
                    "q00": np.linspace(4499999949.5, 4500000050.5, 101),
                    "q01": np.linspace(4899999949.5, 4900000050.5, 101),
                }
            },
        },
        cluster_config=_FIXTURE_CONFIGS_DIR / "cluster_config.json",
        node_config=_FIXTURE_CONFIGS_DIR / "node_config.toml",
        spi_config=_FIXTURE_CONFIGS_DIR / "spi_config.toml",
        device_config=_FIXTURE_CONFIGS_DIR / "device_config.toml",
        output_dir=_PROJECT_ROOT / "out" / "pytest",
        fixed_duration_couplers=("q11_q12", "q12_q13"),
        reverse_phase_qubits=("q11", "q13"),
        save_plot=False,
    )


@pytest.fixture
def node_data_dir(request, tmp_path):
    """The 'data' folder beside the test file, as links in a folder of the test's own.

    Tests write plots and datasets into it, and tests of one node share their 'data'
    folder, so in parallel runs one test's clean-up deleted another's files.
    """
    data_dir = request.path.parent / "data"
    if not data_dir.is_dir():
        pytest.fail(f"Expected data directory not found at: {data_dir}")

    linked_dir = tmp_path / "data"
    linked_dir.mkdir()
    for item in data_dir.iterdir():
        (linked_dir / item.name).symlink_to(item)
    return linked_dir


@pytest.fixture
def seeded_state(session_context):
    """The session's state as one recorded run left it."""
    session_context.state = get_state(_SINGLE_RUN_REDIS_JSON)
    return session_context.state
