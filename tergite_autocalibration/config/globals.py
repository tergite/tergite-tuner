# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Process-wide configuration singletons.

This module is imported once at startup and exposes the loaded
:data:`ENV` (parsed ``.env`` file), :data:`CONFIG` (the calibration
configuration package) and a few derived helpers (redis connection,
matplotlib backend, log directory). Per-run state belongs on the
:class:`SessionContext` passed into the calibration supervisor, not
here.
"""

import atexit
import os
import sys
from pathlib import Path
from typing import Optional

import redis

from tergite_autocalibration.config.files import EnvConfigFile
from tergite_autocalibration.config.load import Configuration, load_configuration
from tergite_autocalibration.utils.handlers.exit import exception_handler, exit_handler
from tergite_autocalibration.utils.logging import logger
from tergite_autocalibration.utils.logging.decorators import is_logging_suppressed
from tergite_autocalibration.utils.misc.tests import is_pytest

### BEGIN Explicit global variables
# Please note: The variables in this section are meant to move to respective configuration files
#              as soon as there is found the best position to put them.
#              E.g. for the case of the downconvert frequency it has to be discussed whether it
#              can be part of the coupler section in the device config.

DOWNCONVERT_FREQUENCY = 4.4e9

### END Explicit global variables


def _default_dotenv_path() -> Path:
    """Find the ``.env`` file shipped alongside the source checkout.

    Looks in the repo root first, then falls back to the current
    working directory.
    """
    repo_root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if repo_root_env.exists():
        return repo_root_env
    return Path(os.getcwd()) / ".env"


def _load_env() -> EnvConfigFile:
    """Load the ``.env`` file if present, else return defaults.

    During pytest runs the bundled fixture ``.env`` is used so that the
    test suite is independent of the developer's local environment.
    """
    if is_pytest():
        fixture_env = (
            Path(__file__).resolve().parent.parent
            / "tests"
            / "fixtures"
            / "configs"
            / "env"
            / "default.env"
        )
        return EnvConfigFile.from_dotenv(fixture_env)
    dotenv_path = _default_dotenv_path()
    if dotenv_path.exists():
        return EnvConfigFile.from_dotenv(dotenv_path)
    return EnvConfigFile()


def _load_config(env: EnvConfigFile) -> Optional[Configuration]:
    """Load the configuration package, returning ``None`` if not yet set up.

    During pytest the bundled ``default_device_under_test`` fixture is
    used. Outside pytest, the meta TOML is expected at
    ``<config_dir>/configuration.meta.toml``. A missing file is
    tolerated so that first-time users can run ``acli config load``
    before the package is in place.
    """
    if is_pytest():
        meta_path = (
            Path(__file__).resolve().parent.parent
            / "tests"
            / "fixtures"
            / "templates"
            / "default_device_under_test"
            / "configuration.meta.toml"
        )
    else:
        meta_path = Path(env.config_dir) / "configuration.meta.toml"

    try:
        return load_configuration(meta_path)
    except FileNotFoundError:
        logger.warning(
            "Default configuration is not yet loaded. "
            "If you are in the process of setting up the configuration, "
            "you can ignore this warning. Please copy configuration files "
            "to the root_directory or run "
            "`acli config load -f <YOUR_CONFIGURATION.zip>`."
        )
        return None


# The parsed .env file
ENV: EnvConfigFile = _load_env()

# The loaded configuration package, or None if not yet set up
CONFIG: Optional[Configuration] = _load_config(ENV)

# Creates a redis instance. Under pytest we use fakeredis so the test
# suite does not require a running Redis server.
if is_pytest():
    import fakeredis

    REDIS_CONNECTION = fakeredis.FakeRedis(decode_responses=True)
else:
    REDIS_CONNECTION = redis.Redis(decode_responses=True, port=ENV.redis_port)

# This will be set in matplotlib
PLOTTING_BACKEND = "tkagg" if ENV.plotting else "agg"


# Adding handlers to the logger
# Everything logged above will be captured by the default handlers.
# Until a calibration run kicks off and provides its own SessionContext-
# derived log_dir, we only need a stable, run-agnostic location.
if is_pytest():
    _log_dir = "pytest"
elif is_logging_suppressed():
    _log_dir = "default"
else:
    _log_dir = "default"

# Here, there is the absolute path to the log directory
_log_file_path = os.path.join(ENV.data_dir, _log_dir)
if not os.path.exists(_log_file_path):
    os.makedirs(_log_file_path, exist_ok=True)

logger.add_console_handler(log_level=ENV.stdout_log_level)
logger.add_file_handler(
    log_file=os.path.join(str(_log_file_path), "autocalibration.log"),
    log_level=ENV.file_log_level,
)


# NOTE: The cluster IP right now is passed only as a single value. For bigger setups with more than
#       one cluster it might make sense to store the cluster ip somewhere else. As of now, there is no
#       field in the hardware options of the QBLOX hardware configuration that would handle the ip.
CLUSTER_IP = ENV.cluster_ip

# The data directory where plots and results are saved
# Default is a folder called 'out' on the root level of the repository
# NOTE: Please only import DATA_DIR when you are implementing something on the very high level
#       that directly modifies paths. For files e.g. logs, data or plots that relate to an
#       active calibration run, please use the active SessionContext.log_dir, which lives inside
#       DATA_DIR.
DATA_DIR = ENV.data_dir

# If the data directory does not exist, it will be created automatically
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    logger.info(f"Initialised DATA_DIR -> {DATA_DIR}")

# Register exception handler
# This is triggered as soon as there is an uncaught exception
sys.excepthook = exception_handler

# Register exit handler
# The exit handler is executed on shutdown of the application
atexit.register(exit_handler)
