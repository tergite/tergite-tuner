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
from typing import Dict, List, Optional, Self, Union

from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    PrivateAttr,
    RedisDsn,
    computed_field,
    field_validator,
    model_validator,
)
from redis import Redis

from tergite_autocalibration.config.files import (
    ClusterConfigFile,
    DeviceConfig,
    DeviceConfigFile,
    MetaConfigFile,
    NodeConfigFile,
    SpiConfigFile,
)
from tergite_autocalibration.lib.nodes import NodeEnum
from tergite_autocalibration.utils.dto.enums import ApplicationStatus, MeasurementMode
from tergite_autocalibration.utils.logging import logger


def _default_root_dir() -> Path:
    """The default ``root_dir``: two levels up from the ``config`` package."""
    return Path(__file__).resolve().parent.parent.parent


def _default_prefix() -> str:
    """The default ``default_prefix``: the current OS user, whitespace stripped."""
    return getpass.getuser().replace(" ", "")


class Configuration(BaseModel):
    """A loaded configuration package.

    Attributes:
        meta_path: absolute path to the ``configuration.meta.toml`` file.
        device: the runtime view of the device configuration. The
            ``[layout]`` section of ``device_config.toml`` is parsed by
            :class:`DeviceConfigFile` but not exposed here, since
            calibration code only needs the device parameters.
        node: the parsed ``node_config.toml``.
        spi: the parsed ``spi_config.toml``, or ``None`` if the package
            does not include one (single-qubit calibrations don't need
            SPI wiring).
        misc: extra folders shipped alongside the package, mapping the
            user-chosen key to the absolute path of the folder.
        cluster: the parsed ``cluster_config.json`` (delegated to
            quantify-scheduler), or ``None`` if not declared in the
            meta file.
    """

    meta_path: PathLike[str]
    device: DeviceConfig
    node: NodeConfigFile
    spi: Optional[SpiConfigFile]
    misc: Dict[str, PathLike[str]]
    cluster: Optional[ClusterConfigFile]

    @classmethod
    def from_dir(
        cls, folder: PathLike[str], meta_filename: str = "configuration.meta.toml"
    ) -> Self:
        """Load a configuration package from its ``configuration.meta.toml``.

        Resolves the relative paths declared in the meta file against the
        directory containing the meta file, eagerly parses the device, node
        and (if present) SPI configs, and defers the cluster config until
        :attr:`Configuration.cluster` is accessed.

        Args:
            folder: path to the folder containing the meta file.
            meta_filename: name of the meta file; default = ``configuration.meta.toml``.

        Returns:
            the loaded :class:`Configuration`.

        Raises:
            TypeError: When file is invalid type
            TomlDecodeError: Error while decoding toml
            IOError / FileNotFoundError: When file does not exist
        """
        base_dir = Path(folder)
        meta_path = base_dir / meta_filename
        meta = MetaConfigFile.from_toml(meta_path)
        config_dir = base_dir / meta.path_prefix

        device_path = config_dir / meta.files.device_config
        node_path = config_dir / meta.files.node_config
        spi_path = config_dir / meta.files.spi_config
        cluster_path = config_dir / meta.files.cluster_config

        logger.info(f"Loading device_config: {meta.files.device_config}")
        device_file = DeviceConfigFile.from_toml(device_path)
        device = device_file.device

        logger.info(f"Loading node_config: {meta.files.node_config}")
        node = NodeConfigFile.from_toml(node_path)

        logger.info(f"Loading spi_config: {meta.files.spi_config}")
        spi = SpiConfigFile.from_toml(spi_path)

        logger.info(f"Loading cluster_config: {meta.files.cluster_config}")
        cluster = ClusterConfigFile.from_json(cluster_path)

        misc = {key: (base_dir / rel_path) for key, rel_path in meta.misc.items()}

        logger.info(f"Loaded configuration described by {meta_path}")
        return Configuration(
            meta_path=meta_path,
            device=device,
            node=node,
            spi=spi,
            misc=misc,
            cluster=cluster,
        )


class SessionContext(BaseModel):
    """Context for the current calibration run.

    The model unifies what was previously split between the ``.env``
    file and a bespoke per-run object. Field names are the lower-case
    versions of the corresponding ``.env`` variable names.

    Build directly from kwargs or use :meth:`from_env` to load from a
    ``.env`` file (with ``os.environ`` as a fallback).

    Attributes:
        _redis: an active Redis client (or fakeredis) used by
            the calibration. ``None`` until injected at the start of a
            run. Carried on the session so it can flow alongside the
            rest of the run state.
        _config: the loaded :class:`Configuration` package. ``None``
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
        redis_url: the URL to the redis server that is to be used effectively
            as RAM for this calibration.
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

    cluster_ip: Optional[IPv4Address] = None
    target_node: Optional[NodeEnum] = None
    qubits: List[str] = []
    couplers: Optional[List[str]] = None
    name: Optional[str] = None
    log_dir: Optional[str] = None
    cluster_mode: MeasurementMode = MeasurementMode.real
    cluster_timeout: int = 222
    user_samplespace: dict = {}
    stdout_log_level: int = 25
    file_log_level: int = 10
    spi_serial_port: str = "/dev/ttyACM0"
    redis_url: RedisDsn = "redis://127.0.0.1:6379/0"
    data_browser_host: IPvAnyAddress = "127.0.0.1"
    data_browser_port: int = 8179
    hw_config_generator_host: IPvAnyAddress = "127.0.0.1"
    hw_config_generator_port: int = 8079
    default_prefix: str = Field(default_factory=_default_prefix)
    root_dir: Path = Field(default_factory=_default_root_dir)
    data_dir: Optional[Path] = None
    config_dir: Optional[Path] = None
    config_meta_filename: str = "configuration.meta.toml"

    _timestamp: datetime = PrivateAttr(default_factory=datetime.now)
    _config: Optional[Configuration] = PrivateAttr(default=None)
    _redis: Optional[Redis] = PrivateAttr(default=None)

    @field_validator("qubits", "couplers", mode="before")
    @classmethod
    def cast_comma_separated_to_list(cls, value):
        """Accept comma-separated strings (e.g. from ``os.environ``) for list fields."""
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("target_node", mode="before")
    @classmethod
    def cast_target_node(cls, value):
        """Accept the lower-case node name (e.g. ``'resonator_spectroscopy'``)
        as well as raw int / :class:`NodeEnum` values."""
        if value is None or isinstance(value, NodeEnum):
            return value
        if isinstance(value, str):
            return NodeEnum.from_string(value)
        return value

    @field_validator("cluster_mode", mode="before")
    @classmethod
    def cast_cluster_mode(cls, value):
        """Accept the lower-case mode name (e.g. ``'real'``, ``'dummy'``,
        ``'re_analyse'``) as well as raw int / :class:`MeasurementMode` values."""
        if value is None or isinstance(value, MeasurementMode):
            return value
        if isinstance(value, str):
            return MeasurementMode[value.strip()]
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

    @property
    def redis(self) -> Redis:
        """The redis connection where data is being saved"""
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    @property
    def config(self) -> Configuration:
        """The configuration derived from the config files"""
        if self._config is None:
            self._config = Configuration.from_dir(
                self.config_dir, meta_filename=self.config_meta_filename
            )
        return self._config

    @classmethod
    def from_env(
        cls,
        file: Optional[Union[str, "PathLike[str]"]] = None,
        **kwargs,
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
            kwargs: extra attributes to set on this instance.
                These override any that are set in the environment already or on the env file

        Returns:
            A validated :class:`SessionContext`.

        Raises:
            FileNotFoundError: if ``file`` is provided but doesn't exist.
        """
        data = {k.lower(): v for k, v in os.environ.items() if v not in (None, "")}

        try:
            with open(file, "r", encoding="utf-8") as fh:
                data.update(
                    {
                        k.lower(): v
                        for k, v in dotenv_values(stream=fh).items()
                        if v not in (None, "")
                    }
                )
        except TypeError:
            pass

        # update with kwargs
        data.update(kwargs)
        return cls.model_validate(data)
