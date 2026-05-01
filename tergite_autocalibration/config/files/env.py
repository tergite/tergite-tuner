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

"""Schema for the ``.env`` file."""

import getpass
from os import PathLike
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, model_validator


def _default_root_dir() -> Path:
    """The default ``ROOT_DIR``: two levels up from the ``config`` package."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _default_prefix() -> str:
    """The default ``DEFAULT_PREFIX``: the current user, whitespace stripped."""
    return getpass.getuser().replace(" ", "")


class EnvConfigFile(BaseModel):
    """Schema for the ``.env`` file mirroring ``.example.env``.

    Field names are the lower-case versions of the env-var names from
    ``.example.env``. Defaults follow the example file: explicit values
    for variables that are set in the file, and the values described in
    the ``# Default: ...`` comments for variables that are commented out
    by default.

    Attributes:
        stdout_log_level: logging level for the console prints, following
            the log levels of the built-in Python ``logging`` library.
            Default is ``25`` to prevent very low-level information from
            third-party libraries from being logged.
        file_log_level: logging level for the file logs. Default is ``10``
            so that all debug information is captured.
        cluster_ip: IP address of the instrument cluster to connect with.
        spi_serial_port: serial port on which the SPI rack is connected.
        redis_port: port to use when connecting to redis. A custom port
            can be started with ``redis-server --port <REDIS_PORT>``.
        plotting: whether plots should be shown or whether the program
            should run silently in the background.
        data_browser_host: host URL under which the data browser should
            be available.
        data_browser_port: port for the data browser to run on.
        hw_config_generator_host: host URL under which the hardware
            configuration generator should be available.
        hw_config_generator_port: port for the hardware configuration
            generator to run on.
        default_prefix: prefix added to logfiles, redis entries and the
            data directory. The actual value does not matter, but it is
            typically the user's name. Defaults to the current user as
            found by :func:`getpass.getuser`.
        root_dir: top-level folder of the ``tergite-autocalibration``
            checkout. In most cases this is the path to the folder to
            which the repository was cloned. Defaults to two levels up
            from the ``config`` package.
        data_dir: directory where plots are stored. If the path does not
            exist, the program will try to create it automatically.
            Defaults to ``<root_dir>/out``.
        config_dir: directory where the configuration package is stored.
            Defaults to ``<root_dir>``.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    stdout_log_level: int = 25
    file_log_level: int = 10
    cluster_ip: str = "192.14.2.1"
    spi_serial_port: str = "/dev/ttyACM0"
    redis_port: int = 6379
    plotting: bool = True
    data_browser_host: str = "127.0.0.1"
    data_browser_port: int = 8179
    hw_config_generator_host: str = "127.0.0.1"
    hw_config_generator_port: int = 8079

    default_prefix: str = Field(default_factory=_default_prefix)
    root_dir: Path = Field(default_factory=_default_root_dir)
    data_dir: Optional[Path] = None
    config_dir: Optional[Path] = None

    @model_validator(mode="after")
    def _resolve_dependent_paths(self) -> "EnvConfigFile":
        """Fill in the ``data_dir`` / ``config_dir`` defaults from ``root_dir``."""
        if self.data_dir is None:
            self.data_dir = self.root_dir / "out"
        if self.config_dir is None:
            self.config_dir = self.root_dir
        return self

    @classmethod
    def from_dotenv(cls, file: "PathLike[str]") -> "EnvConfigFile":
        """Loads the environment configuration from a ``.env`` file.

        Args:
            file: path to the ``.env`` file

        Returns:
            the parsed and validated ``EnvConfigFile`` instance
        """
        with open(file, "r", encoding="utf-8") as f:
            raw = dotenv_values(stream=f)
        data = {k.lower(): v for k, v in raw.items() if v is not None}
        return cls.model_validate(data)
