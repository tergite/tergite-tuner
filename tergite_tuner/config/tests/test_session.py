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

"""Tests for :class:`SessionContext` and its :meth:`from_env` factory.

These exercise the merged ``.env`` file + ``os.environ`` resolution, the
defaults baked into the model, and the type coercion that happens for
values read out of an env file.
"""

from pathlib import Path
from typing import Annotated, Optional, get_origin

import pytest
from pydantic import ValidationError

from tergite_tuner.config.session import SessionContext, SessionOptions
from tergite_tuner.config.types import (
    ClusterConfig,
    DeviceConfig,
    DeviceConfigFile,
    NodeConfig,
    SpiConfig,
)
from tergite_tuner.lib.nodes import (
    DEFAULT_IGNORED_NODES,
    DEFAULT_NODE_CLS_MAP,
    DEFAULT_NODE_DAG_EDGES,
    NodeEnum,
    Qubit01SpectroscopyAmplitudeNode,
    ResonatorSpectroscopy1Node,
)
from tergite_tuner.utils.types.enums import MeasurementMode

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_EXAMPLE_ENV_PATH = _PROJECT_ROOT / ".example.env"

_DEVICE_CONFIG_PATH = _PROJECT_ROOT / "device_config.example.toml"
_NODE_CONFIG_PATH = _PROJECT_ROOT / "node_config.example.toml"
_SPI_CONFIG_PATH = _PROJECT_ROOT / "spi_config.example.toml"
_CLUSTER_CONFIG_PATH = _PROJECT_ROOT / "cluster_config.example.json"

_DEVICE_CONFIG = DeviceConfigFile.from_toml(_DEVICE_CONFIG_PATH).device
_NODE_CONFIG = NodeConfig.from_toml(_NODE_CONFIG_PATH)
_CLUSTER_CONFIG = ClusterConfig.from_json(_CLUSTER_CONFIG_PATH)
_SPI_CONFIG = SpiConfig.from_toml(_SPI_CONFIG_PATH)


@pytest.fixture
def clean_environ(monkeypatch):
    """Strip any env vars that would otherwise bleed into ``from_env``.

    The conftest at the test-suite root injects a few values via
    ``os.environ``; we don't want those interfering with these unit
    tests.
    """
    for key in (
        "STDOUT_LOG_LEVEL",
        "FILE_LOG_LEVEL",
        "CLUSTER_IP",
        "SPI_SERIAL_PORT",
        "REDIS_URL",
        "DATA_DIR",
        "CONFIG_DIR",
        "TARGET_NODE",
        "CLUSTER_MODE",
        "QUBITS",
        "COUPLERS",
        "NAME",
        "CLUSTER_TIMEOUT",
        "IS_RECALIBRATION",
    ):
        monkeypatch.delenv(key, raising=False)


def test_session_loads_example_env(clean_environ):
    """``.example.env`` parses cleanly into a :class:`SessionContext`."""
    session = SessionContext.from_env(_EXAMPLE_ENV_PATH)

    # Values explicitly set in the example file
    assert session.stdout_log_level == 25
    assert session.file_log_level == 10
    assert str(session.cluster_ip) == "192.14.2.1"
    assert session.spi_serial_port == "/dev/ttyACM0"
    assert str(session.redis_url) == "redis://127.0.0.1:6379/0"
    assert session.cluster_timeout == 222
    assert session.is_recalibration is True


def test_session_uses_documented_defaults_for_commented_vars(clean_environ):
    """Commented-out variables fall back to the documented defaults."""
    session = SessionContext.from_env(_EXAMPLE_ENV_PATH)

    assert session.cluster_mode == MeasurementMode.real
    assert str(session.redis_url) == "redis://127.0.0.1:6379/0"
    assert session.data_dir == Path("out")


def test_session_constructs_with_no_args(clean_environ):
    """``SessionContext()`` returns a fully-defaulted instance."""
    session = SessionContext()

    assert session.stdout_log_level == 25
    assert str(session.redis_url) == "redis://127.0.0.1:6379/0"
    assert session.is_recalibration is True


def test_session_overrides_optional_vars(tmp_path, clean_environ):
    """Explicit values for the optional commented-out vars take precedence."""
    sample = tmp_path / ".env"
    sample.write_text(
        f"CLUSTER_MODE='dummy'\n" f"REDIS_URL='redis://127.0.0.1:6378/4'\n"
    )

    session = SessionContext.from_env(sample)
    assert str(session.redis_url) == "redis://127.0.0.1:6378/4"
    assert session.cluster_mode == MeasurementMode.dummy


def test_session_coerces_string_values(tmp_path, clean_environ):
    """Values from the ``.env`` file (always strings) are coerced to the field type."""
    sample = tmp_path / ".env"
    sample.write_text(
        "REDIS_URL='redis://127.0.0.1:6380/0'\n" "STDOUT_LOG_LEVEL='30'\n"
    )

    session = SessionContext.from_env(sample)
    assert str(session.redis_url) == "redis://127.0.0.1:6380/0"
    assert session.stdout_log_level == 30


def test_session_rejects_non_integer_port(tmp_path, clean_environ):
    """Malformed Redis URLs fail validation."""
    sample = tmp_path / ".env"
    sample.write_text("REDIS_URL='not-a-url'\n")

    with pytest.raises(ValidationError) as excinfo:
        SessionContext.from_env(sample)

    locs = [err["loc"] for err in excinfo.value.errors()]
    assert ("redis_url",) in locs


def test_session_falls_back_to_os_environ(tmp_path, monkeypatch, clean_environ):
    """When a field is absent from the ``.env`` file, ``os.environ`` is consulted."""
    sample = tmp_path / ".env"
    sample.write_text("STDOUT_LOG_LEVEL='30'\n")  # some value in the file

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6500/0")
    monkeypatch.setenv("QUBITS", "q00,q01")

    session = SessionContext.from_env(sample)
    assert str(session.redis_url) == "redis://127.0.0.1:6500/0"  # from os.environ
    assert session.qubits == ["q00", "q01"]  # csv-coerced


def test_session_env_file_wins_over_os_environ(tmp_path, monkeypatch, clean_environ):
    """If the ``.env`` file has a value, ``os.environ`` is ignored for that field."""
    sample = tmp_path / ".env"
    sample.write_text("REDIS_URL='redis://127.0.0.1:6380/0'\n")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6500/0")

    session = SessionContext.from_env(sample)
    assert str(session.redis_url) == "redis://127.0.0.1:6380/0"


def test_session_from_env_without_file(monkeypatch, clean_environ):
    """``from_env(None)`` reads ``os.environ`` and uses class defaults."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6500/0")
    session = SessionContext.from_env()
    assert str(session.redis_url) == "redis://127.0.0.1:6500/0"


def test_session_from_env_raises_for_missing_file(tmp_path):
    """A missing ``.env`` path raises ``FileNotFoundError``."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        SessionContext.from_env(missing)


def test_session_loads_configs_from_dicts():
    """One can pass dicts instead of file paths for some of the configs"""
    session = SessionContext(
        device_config=_DEVICE_CONFIG.model_dump(),
        node_config=_NODE_CONFIG.model_dump(),
        cluster_config=_CLUSTER_CONFIG.model_dump(),
        spi_config=_SPI_CONFIG.model_dump(),
    )
    assert session.device_config == _DEVICE_CONFIG
    assert session.node_config == _NODE_CONFIG
    assert session.cluster_config.model_dump() == _CLUSTER_CONFIG.model_dump()
    assert session.spi_config == _SPI_CONFIG


def test_session_loads_configs_from_models():
    """One can pass base model instances instead of file paths for some of the configs"""
    session = SessionContext(
        device_config=_DEVICE_CONFIG,
        node_config=_NODE_CONFIG,
        cluster_config=_CLUSTER_CONFIG,
        spi_config=_SPI_CONFIG,
    )
    assert session.device_config == _DEVICE_CONFIG
    assert session.node_config == _NODE_CONFIG
    assert session.cluster_config.model_dump() == _CLUSTER_CONFIG.model_dump()
    assert session.spi_config == _SPI_CONFIG


def test_session_loads_configs_from_file_paths():
    """One can pass file paths instead of dicts for some of the configs"""
    session = SessionContext(
        device_config=_DEVICE_CONFIG_PATH,
        node_config=_NODE_CONFIG_PATH,
        cluster_config=_CLUSTER_CONFIG_PATH,
        spi_config=_SPI_CONFIG_PATH,
    )
    assert session.device_config == _DEVICE_CONFIG
    assert session.node_config == _NODE_CONFIG
    assert session.cluster_config.model_dump() == _CLUSTER_CONFIG.model_dump()
    assert session.spi_config == _SPI_CONFIG


@pytest.mark.parametrize(
    "raw_value",
    ["True", "true", "TRUE", " true ", "1", "yes", "Y", "on", ""],
)
def test_session_is_recalibration_truthy_strings(tmp_path, clean_environ, raw_value):
    """Truthy ``IS_RECALIBRATION`` values from the env file coerce to ``True``. Default is True also"""
    sample = tmp_path / ".env"
    sample.write_text(f"IS_RECALIBRATION='{raw_value}'\n")

    session = SessionContext.from_env(sample)
    assert session.is_recalibration is True


@pytest.mark.parametrize(
    "raw_value",
    ["False", "false", "FALSE", " false ", "0", "no", "N", "off"],
)
def test_session_is_recalibration_falsy_strings(tmp_path, clean_environ, raw_value):
    """Falsy ``IS_RECALIBRATION`` values from the env file coerce to ``False``."""
    sample = tmp_path / ".env"
    sample.write_text(f"IS_RECALIBRATION='{raw_value}'\n")

    session = SessionContext.from_env(sample)
    assert session.is_recalibration is False


def test_session_is_recalibration_from_os_environ(monkeypatch, clean_environ):
    """``IS_RECALIBRATION`` can be supplied via ``os.environ``."""
    monkeypatch.setenv("IS_RECALIBRATION", "true")

    session = SessionContext.from_env()
    assert session.is_recalibration is True


def test_session_is_recalibration_kwarg_overrides_env(tmp_path, clean_environ):
    """A ``kwargs`` value for ``is_recalibration`` overrides the env file."""
    sample = tmp_path / ".env"
    sample.write_text("IS_RECALIBRATION='False'\n")

    session = SessionContext.from_env(sample, is_recalibration=True)
    assert session.is_recalibration is True


def test_session_is_recalibration_kwarg_bool_directly(clean_environ):
    """Passing a real ``bool`` directly as a kwarg is preserved."""
    assert SessionContext(is_recalibration=True).is_recalibration is True
    assert SessionContext(is_recalibration=False).is_recalibration is False


def test_session_rejects_invalid_is_recalibration(tmp_path, clean_environ):
    """Unrecognised string values for ``IS_RECALIBRATION`` fail validation."""
    sample = tmp_path / ".env"
    sample.write_text("IS_RECALIBRATION='maybe'\n")

    with pytest.raises(ValidationError) as excinfo:
        SessionContext.from_env(sample)

    locs = [err["loc"] for err in excinfo.value.errors()]
    assert ("is_recalibration",) in locs


def test_session_loads_node_vars_from_py_objects():
    """Can load the node vars like node_dag_edges, ignored_nodes etc. from python objects"""
    node_cls_map = {
        NodeEnum.CZ_RB: ResonatorSpectroscopy1Node,
        NodeEnum.CZ_CHEVRON: Qubit01SpectroscopyAmplitudeNode,
    }
    ignored_nodes = (NodeEnum.CZ_RB,)
    node_dag_edges = (
        (NodeEnum.CZ_CHEVRON, NodeEnum.CZ_RB),
        (NodeEnum.TOF, NodeEnum.RESONATOR_SPECTROSCOPY),
    )

    session = SessionContext(
        node_cls_map=node_cls_map,
        ignored_nodes=ignored_nodes,
        node_dag_edges=node_dag_edges,
    )
    assert session.node_cls_map == node_cls_map
    assert session.node_dag_edges == node_dag_edges
    assert session.ignored_nodes == ignored_nodes


def test_default_session_has_default_node_props():
    """default session has the default node vars."""
    session = SessionContext()
    assert session.node_cls_map == DEFAULT_NODE_CLS_MAP
    assert session.ignored_nodes == DEFAULT_IGNORED_NODES
    assert session.node_dag_edges == DEFAULT_NODE_DAG_EDGES


def test_session_options_match_session_context():
    """The SessionOptions typed dict matches the SessionContext field set"""
    excluded_fields = ()
    session_options_fields = SessionOptions.__annotations__
    assert SessionOptions.__total__ is False
    for name, field in SessionContext.model_fields.items():
        assert not field.is_required()

        if name not in excluded_fields:
            options_type = session_options_fields[name]
            context_type = field.annotation
            if get_origin(options_type) is Annotated:
                assert options_type.__origin__ == context_type
            elif context_type in (
                DeviceConfig,
                NodeConfig,
                Optional[SpiConfig],
                Optional[ClusterConfig],
            ):
                assert options_type == context_type | Path | str
            else:
                assert options_type == context_type
