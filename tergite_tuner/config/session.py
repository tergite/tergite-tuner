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

Build a :class:`SessionContext` with kwargs, which it fills from the
environment, or with :meth:`SessionContext.from_env`, which also reads a
``.env`` file.
"""

from collections.abc import Iterable
from datetime import datetime
from functools import cached_property
from ipaddress import IPv4Address
from os import PathLike
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Self,
    Tuple,
    TypedDict,
    Union,
)

from pydantic import (
    Field,
    PrivateAttr,
    RedisDsn,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from redis import Redis

from tergite_tuner.backend import QbloxHardwareCompilationConfig
from tergite_tuner.config.types import (
    ClusterConfig,
    DeviceConfig,
    DeviceConfigFile,
    NodeConfig,
    SpiConfig,
    load_config,
)
from tergite_tuner.lib.nodes import (
    DEFAULT_IGNORED_NODES,
    DEFAULT_NODE_DAG_EDGES,
    NodeSpec,
)
from tergite_tuner.storage.redis import RedisStore
from tergite_tuner.utils.types.enums import MeasurementMode, SPIMode
from tergite_tuner.utils.types.node_enum import NodeEnum

_CONFIG_FILE_MODELS = {
    "device_config": DeviceConfigFile,
    "node_config": NodeConfig,
    "spi_config": SpiConfig,
    "cluster_config": ClusterConfig,
}


def _default_data_dir() -> Path:
    """The default ``data_dir``: 'out' in the current working directory."""
    return Path.cwd() / "./out"


class SessionOptions(TypedDict, total=False):
    """Options for initializing the SessionContext as copied from SessionContext.

    This is useful in functions that create a session context object.
    You just need to use ``**kwargs: Unpack[SessionOptions]``
    """

    cluster_ip: Optional[IPv4Address]
    target_node: Optional[NodeEnum]
    qubits: List[str]
    couplers: List[str]
    name: Optional[str]
    cluster_mode: MeasurementMode
    cluster_timeout: int
    spi_mode: SPIMode
    user_samplespace: dict
    stdout_log_level: int
    file_log_level: int
    spi_serial_port: str
    redis_url: RedisDsn
    is_recalibration: bool
    ignore_spec: bool
    save_plot: bool
    data_dir: Path
    device_config: DeviceConfig | Path | str
    node_config: NodeConfig | Path | str
    spi_config: Optional[SpiConfig] | Path | str
    cluster_config: Optional[QbloxHardwareCompilationConfig] | Path | str
    node_specs: Mapping[NodeEnum, NodeSpec]
    ignored_nodes: Tuple[NodeEnum, ...]
    node_dag_edges: Tuple[Tuple[NodeEnum, NodeEnum], ...]
    fixed_duration_couplers: Tuple[str, ...]
    reverse_phase_qubits: Tuple[str, ...]


class SessionContext(BaseSettings):
    """Context for the current calibration run.

    Each field is read, in this order, from the keyword arguments, the environment
    variable of its upper-case name, the ``.env`` file given to :meth:`from_env`, and
    its default. Enums are read by name from the environment and the ``.env`` file,
    and lists as comma-separated values.

    Attributes:
        _redis: an active Redis client used by
            the calibration. ``None`` until injected at the start of a
            run. Carried on the session so it can flow alongside the
            rest of the run state.
        cluster_ip: IP address of the Qblox cluster being used.
        target_node: the calibration node on which to stop. Stored as a
            :class:`NodeEnum`; the lower-case string form is exposed via
            :attr:`target_node_name`.
        qubits: list of qubit names to calibrate, e.g. ``QUBITS='q00,q01'``.
        couplers: list of coupler names to calibrate.
        name: human-readable name for the run; defaults to the target
            node name in lower case.
        data_dir: path where the data files are stored. default: 'out' in the working directory.
        cluster_mode: measurement mode (``real``, ``dummy`` or
            ``re_analyse``).
        cluster_timeout: timeout in seconds used when waiting on the
            cluster for acquisitions.
        spi_mode: spi mode (``real`` or ``dummy``).
        user_samplespace: the user samplespace for this session.
        stdout_log_level: console logger level (Python ``logging``
            convention). Defaults to ``25`` to suppress noisy
            third-party output.
        file_log_level: file logger level. Defaults to ``10`` so that
            all debug information is captured in log files.
        spi_serial_port: serial port on which the SPI rack is connected.
        redis_url: the URL to the redis server that is to be used effectively
            as RAM for this calibration.
        id: stable identifier of this session, derived from the
            timestamp.
        cluster_config: config that QBlox needs to compile schedules on the
            hardware. It can also be a path to the quantify-scheduler-based cluster_config JSON file.
            See cluster_config.example.json
        device_config: config with the initial values for the device
            configuration. It can also be a path to the device_config TOML file.
            See device_config.example.toml
        spi_config: config that configures the wiring on the QBlox SPI
            rack. Only required when running two-qubit calibrations.
            It can also be a path to the spi_config TOML file.
            See spi_config.example.toml
        node_config: file with the runtime values for the calibration
            nodes. It can also be a path to the node_config TOML file.
            See node_config.example.toml
        target_node_name: lower-case name of :attr:`target_node`.
        is_recalibration: recalibrate specific nodes (True) or tune up
            the device from the scratch (False).
        ignore_spec: recalibrate the nodes by ignoring the previous
            calibration status (True) or skip the calibration if it is
            already calibrated (False).
        save_plot: save the analysis plot (True) or not (False).
        node_dag_edges: the directed edges of the calibration Directed Acyclic Graph (DAG)
            with edges of format ``(parent, child)`` where ``child`` depends on ``parent``.
            Defaults to :data:`tergite_tuner.lib.nodes.DEFAULT_NODE_DAG_EDGES`
        ignored_nodes: the nodes that should not be included in the final DAG
            even if there are nodes that depend on them. Defaults to
            :data:`tergite_tuner.lib.nodes.DEFAULT_IGNORED_NODES`
        node_specs: nodes to run in place of the defaults in
            :data:`tergite_tuner.lib.nodes.DEFAULT_NODE_SPECS`, or in addition to them.
            A node replaced here must keep its node's name.
        fixed_duration_couplers: the couplers with a fixed duration working points for cz calibration.
        reverse_phase_qubits: the qubits which have the reverse of the expected phase when attached
            to a coupler
    """

    model_config = SettingsConfigDict(
        extra="ignore",
        arbitrary_types_allowed=True,
        env_ignore_empty=True,
        env_parse_enums=True,
    )

    cluster_ip: Optional[IPv4Address] = None
    target_node: Optional[NodeEnum] = None
    qubits: Annotated[List[str], NoDecode] = []
    couplers: Annotated[List[str], NoDecode] = []
    name: Optional[str] = None
    cluster_mode: MeasurementMode = MeasurementMode.real
    cluster_timeout: int = 222
    spi_mode: SPIMode = SPIMode.dummy
    user_samplespace: dict = {}
    stdout_log_level: int = 25
    file_log_level: int = 10
    spi_serial_port: str = "/dev/ttyACM0"
    redis_url: RedisDsn = "redis://127.0.0.1:6379/0"
    is_recalibration: bool = True
    ignore_spec: bool = True
    save_plot: bool = False
    data_dir: Path = Field(default_factory=_default_data_dir)
    # NoDecode: a file path, not JSON
    device_config: Annotated[DeviceConfig, NoDecode] = Field(
        default_factory=DeviceConfig
    )
    node_config: Annotated[NodeConfig, NoDecode] = Field(default_factory=NodeConfig)
    spi_config: Annotated[Optional[SpiConfig], NoDecode] = None
    cluster_config: Annotated[Optional[QbloxHardwareCompilationConfig], NoDecode] = None
    node_specs: Mapping[NodeEnum, NodeSpec] = {}
    ignored_nodes: Tuple[NodeEnum, ...] = DEFAULT_IGNORED_NODES
    node_dag_edges: Tuple[Tuple[NodeEnum, NodeEnum], ...] = DEFAULT_NODE_DAG_EDGES
    fixed_duration_couplers: Annotated[Tuple[str, ...], NoDecode] = ()
    reverse_phase_qubits: Annotated[Tuple[str, ...], NoDecode] = ()
    _redis_fields_touched: Dict[str, int] = {}

    _timestamp: datetime = PrivateAttr(default_factory=datetime.now)
    _redis: Optional[Redis] = PrivateAttr(default=None)
    _redis_store: RedisStore = PrivateAttr(default=None)

    @field_validator(
        "device_config", "node_config", "spi_config", "cluster_config", mode="before"
    )
    @classmethod
    def load_config_files(cls, value: Any, info: ValidationInfo) -> Any:
        """Loads a config given as a file path."""
        if not isinstance(value, (str, Path)):
            return value
        config = load_config(_CONFIG_FILE_MODELS[info.field_name], value)
        return config.device if isinstance(config, DeviceConfigFile) else config

    @field_validator(
        "qubits",
        "couplers",
        "fixed_duration_couplers",
        "reverse_phase_qubits",
        mode="before",
    )
    @classmethod
    def split_comma_separated(cls, value: Any) -> Any:
        """Splits a comma-separated string, as the environment gives lists."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("target_node", mode="before")
    @classmethod
    def cast_target_node(cls, value):
        """Accept the canonical lower-case node name
        (e.g. ``'resonator_spectroscopy'``) as well as raw
        :class:`NodeEnum` members. The string form is normalised to
        lower case so users can write either ``T1`` or ``t1``."""
        if value is None or isinstance(value, NodeEnum):
            return value
        if isinstance(value, str):
            return NodeEnum(value.lower())
        return value

    @model_validator(mode="after")
    def update_attrs(self) -> Self:
        """Derive cross-field defaults: name"""
        if self.name is None and isinstance(self.target_node, NodeEnum):
            self.name = self.target_node.value
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
        return self.target_node.value

    @property
    def redis(self) -> Redis:
        """The redis connection where data is being saved"""
        if self._redis is None:
            self._redis = Redis.from_url(str(self.redis_url), decode_responses=True)
        return self._redis

    @property
    def redis_store(self) -> RedisStore:
        """The redis store instance that handles data persistence"""
        if self._redis_store is None:
            self._redis_store = RedisStore(self.redis)
        return self._redis_store

    @computed_field
    @property
    def redis_fields_touched(self) -> Dict[str, int]:
        """The redis fields that might have been touched by the calibration"""
        return self._redis_fields_touched

    def update_redis_fields_log(self, fields: Iterable[str]):
        """Counts ``fields`` as touched in this session."""
        for field in fields:
            old_count = self._redis_fields_touched.setdefault(field, 0)
            self._redis_fields_touched[field] = old_count + 1

    def refresh_redis_fields_log(self):
        """Refreshes the log that tracks the fields that have been touched in the session"""
        self._redis_fields_touched.clear()

    @classmethod
    def from_env(
        cls,
        file: Optional[Union[str, "PathLike[str]"]] = None,
        **kwargs: Any,
    ) -> "SessionContext":
        """A session from ``kwargs``, the environment and the ``.env`` file at ``file``, in that order.

        Raises:
            FileNotFoundError: if ``file`` is given but does not exist.
        """
        if file is not None and not Path(file).exists():
            raise FileNotFoundError(f"No .env file at {file}")
        return cls(_env_file=file, **kwargs)
