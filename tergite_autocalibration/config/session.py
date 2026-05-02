# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2024
# (C) Copyright Michele Faucci Giannelli 2025
# (C) Copyright Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The single per-process configuration object for a calibration run.

:class:`SessionContext` carries every value that drives a calibration
run: environment-driven settings (formerly the ``.env`` file), and the
per-run state that used to live on a bespoke object (target node, qubit
list, mode, etc.).

Build a :class:`SessionContext` directly with kwargs, or via the
:meth:`SessionContext.from_env` factory which merges values read from a
``.env`` file with the matching ``os.environ`` entries.
"""

import getpass
import os
import os.path
from datetime import datetime
from functools import cached_property
from ipaddress import IPv4Address
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Self, Union

from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    computed_field,
    field_validator,
    model_validator,
)

from tergite_autocalibration.lib.nodes import NodeEnum
from tergite_autocalibration.utils.dto.enums import ApplicationStatus, MeasurementMode

if TYPE_CHECKING:
    from tergite_autocalibration.config.load import Configuration


def _default_root_dir() -> Path:
    """The default ``root_dir``: two levels up from the ``config`` package."""
    return Path(__file__).resolve().parent.parent.parent


def _default_prefix() -> str:
    """The default ``default_prefix``: the current OS user, whitespace stripped."""
    return getpass.getuser().replace(" ", "")


class SessionContext(BaseModel):
    """Context for the current calibration run.

    The model unifies what was previously split between the ``.env``
    file and a bespoke per-run object. Field names are the lower-case
    versions of the corresponding ``.env`` variable names.

    Build directly from kwargs or use :meth:`from_env` to load from a
    ``.env`` file (with ``os.environ`` as a fallback).

    Attributes:
        redis_connection: an active Redis client (or fakeredis) used by
            the calibration. ``None`` until injected at the start of a
            run. Carried on the session so it can flow alongside the
            rest of the run state.
        config: the loaded :class:`Configuration` package. ``None``
            until injected at the start of a run.
        cluster_ip: IP address of the Qblox cluster being used.
        target_node: the calibration node on which to stop. Stored as a
            :class:`NodeEnum`; the lower-case string form is exposed via
            :attr:`target_node_name`.
        qubits: list of qubit names to calibrate. Accepts a
            comma-separated string from env vars (``QUBITS='q00,q01'``).
        couplers: list of coupler names to calibrate. Accepts a
            comma-separated string from env vars.
        name: human-readable name for the run; defaults to the target
            node name in lower case.
        log_dir: relative path (under ``data_dir``) where the log files
            are stored. Auto-derived from the timestamp and the run name.
        cluster_mode: measurement mode (``real``, ``dummy`` or
            ``re_analyse``).
        cluster_timeout: timeout in seconds used when waiting on the
            cluster for acquisitions.
        user_samplespace: the user samplespace for this session.
        stdout_log_level: console logger level (Python ``logging``
            convention). Defaults to ``25`` to suppress noisy
            third-party output.
        file_log_level: file logger level. Defaults to ``10`` so that
            all debug information is captured in log files.
        spi_serial_port: serial port on which the SPI rack is connected.
        redis_port: port to use when connecting to Redis. A custom port
            can be started with ``redis-server --port <REDIS_PORT>``.
        plotting: whether plots should be shown during the run. Accepts
            string values like ``"True"`` / ``"False"`` from env vars.
        data_browser_host: host URL under which the data browser should
            be available.
        data_browser_port: port on which the data browser runs.
        hw_config_generator_host: host URL under which the hardware
            configuration generator should be available.
        hw_config_generator_port: port on which the hardware
            configuration generator runs.
        default_prefix: prefix added to logfiles, redis entries and the
            data directory. The actual value does not matter, but it is
            typically the user's name. Defaults to the current user as
            reported by :func:`getpass.getuser`.
        root_dir: top-level folder of the ``tergite-autocalibration``
            checkout. In most cases the path to the cloned repository.
            Defaults to two levels up from this module.
        data_dir: directory where calibration data and plots are stored.
            Created automatically if it does not exist. Defaults to
            ``<root_dir>/out``.
        config_dir: directory where the configuration package is stored.
            Defaults to ``<root_dir>``.
        id: stable identifier of this session, derived from the
            timestamp.
        target_node_name: lower-case name of :attr:`target_node`.
    """

    model_config = ConfigDict(
        extra="allow", populate_by_name=True, arbitrary_types_allowed=True
    )

    # --- runtime resources injected at the start of a run ---
    redis_connection: Optional[Any] = Field(default=None, exclude=True, repr=False)
    config: Optional["Configuration"] = Field(default=None, exclude=True, repr=False)

    # --- per-run / runtime state ---
    cluster_ip: Optional[IPv4Address] = None
    target_node: Optional[NodeEnum] = None
    qubits: List[str] = []
    couplers: Optional[List[str]] = None
    name: Optional[str] = None
    log_dir: Optional[str] = None
    cluster_mode: MeasurementMode = MeasurementMode.real
    cluster_timeout: int = 222
    user_samplespace: dict = {}

    # --- env-file-driven state ---
    stdout_log_level: int = 25
    file_log_level: int = 10
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

    _timestamp: datetime = PrivateAttr(default_factory=datetime.now)

    @field_validator("qubits", "couplers", mode="before")
    @classmethod
    def _split_csv(cls, value):
        """Accept comma-separated strings (e.g. from ``os.environ``) for list fields."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("plotting", mode="before")
    @classmethod
    def _coerce_bool(cls, value):
        """Accept ``"True"`` / ``"False"`` strings from env files / ``os.environ``."""
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return value

    @model_validator(mode="after")
    def update_attrs(self) -> Self:
        """Derive cross-field defaults: data_dir, config_dir, name, log_dir."""
        if self.data_dir is None:
            self.data_dir = self.root_dir / "out"
        if self.config_dir is None:
            self.config_dir = self.root_dir
        if self.name is None and isinstance(self.target_node, NodeEnum):
            self.name = self.target_node.to_string()
        if self.log_dir is None and self.name is not None:
            self.log_dir = os.path.join(
                self._timestamp.strftime("%Y-%m-%d"),
                f"{self._timestamp.strftime('%H-%M-%S')}_{self.name}-{str(ApplicationStatus.ACTIVE.value)}",
            )
        return self

    @computed_field
    @cached_property
    def id(self) -> str:
        """Identifier of the session"""
        return f"{self._timestamp.strftime('%Y-%m-%d--%H-%M-%S')}--tac-run-id"

    @computed_field
    @cached_property
    def target_node_name(self) -> Optional[str]:
        """Name of the target node (or ``None`` if unset)."""
        if self.target_node is None:
            return None
        return self.target_node.to_string()

    @classmethod
    def from_env(
        cls, file: Optional[Union[str, "PathLike[str]"]] = None
    ) -> "SessionContext":
        """Build a :class:`SessionContext` from a ``.env`` file and ``os.environ``.

        Resolution order, per field:
          1. The matching ``KEY`` in the ``.env`` file at ``file`` (if
             ``file`` is provided and the file exists).
          2. ``os.environ[<FIELD_NAME_UPPER>]`` if present and non-empty.
          3. The :class:`SessionContext` field default.

        Args:
            file: path to a ``.env`` file. When ``None`` (or the path
                does not exist), only ``os.environ`` and the class
                defaults are used.

        Returns:
            A validated :class:`SessionContext`.

        Raises:
            FileNotFoundError: if ``file`` is provided but doesn't exist.
        """
        # ``redis_connection`` and ``config`` are runtime resources and
        # cannot be expressed as strings in a ``.env`` file or environment
        # variable. Skip them when resolving from text-based sources.
        text_fields = {
            name
            for name in cls.model_fields
            if name not in {"redis_connection", "config"}
        }

        data: Dict[str, Any] = {}

        if file is not None:
            path = Path(file)
            if not path.exists():
                raise FileNotFoundError(path)
            with open(path, "r", encoding="utf-8") as fh:
                raw = dotenv_values(stream=fh)
            for key, value in raw.items():
                if value is None:
                    continue
                lowered = key.lower()
                if lowered in text_fields:
                    data[lowered] = value

        for field_name in text_fields:
            if field_name in data:
                continue
            os_val = os.environ.get(field_name.upper())
            if os_val is None or os_val == "":
                continue
            data[field_name] = os_val

        return cls.model_validate(data)
