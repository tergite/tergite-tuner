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

import getpass
from os import path

import pytest
from pydantic import ValidationError

from tergite_autocalibration.config.session import SessionContext

_CONFIG_PACKAGE_DIR = path.dirname(path.dirname(path.abspath(__file__)))
_REPO_ROOT = path.dirname(path.dirname(_CONFIG_PACKAGE_DIR))
_EXAMPLE_ENV_PATH = path.join(_REPO_ROOT, ".example.env")


@pytest.fixture
def example_env_path() -> str:
    return _EXAMPLE_ENV_PATH


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
        "PLOTTING",
        "DATA_BROWSER_HOST",
        "DATA_BROWSER_PORT",
        "HW_CONFIG_GENERATOR_HOST",
        "HW_CONFIG_GENERATOR_PORT",
        "DEFAULT_PREFIX",
        "ROOT_DIR",
        "DATA_DIR",
        "CONFIG_DIR",
        "TARGET_NODE",
        "CLUSTER_MODE",
        "QUBITS",
        "COUPLERS",
        "NAME",
        "CLUSTER_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_session_loads_example_env(example_env_path, clean_environ):
    """``.example.env`` parses cleanly into a :class:`SessionContext`."""
    session = SessionContext.from_env(example_env_path)

    # Values explicitly set in the example file
    assert session.stdout_log_level == 25
    assert session.file_log_level == 10
    assert str(session.cluster_ip) == "192.14.2.1"
    assert session.spi_serial_port == "/dev/ttyACM0"
    assert str(session.redis_url) == "redis://127.0.0.1:6379/0"
    assert session.plotting is True
    assert str(session.data_browser_host) == "127.0.0.1"
    assert session.data_browser_port == 8179
    assert str(session.hw_config_generator_host) == "127.0.0.1"
    assert session.hw_config_generator_port == 8079


def test_session_uses_documented_defaults_for_commented_vars(
    example_env_path, clean_environ
):
    """Commented-out variables fall back to the documented defaults."""
    session = SessionContext.from_env(example_env_path)

    assert session.default_prefix == getpass.getuser().replace(" ", "")
    assert session.data_dir == session.root_dir / "out"
    assert session.config_dir == session.root_dir


def test_session_constructs_with_no_args(clean_environ):
    """``SessionContext()`` returns a fully-defaulted instance."""
    session = SessionContext()

    assert session.stdout_log_level == 25
    assert session.plotting is True
    assert str(session.redis_url) == "redis://127.0.0.1:6379/0"
    assert session.data_dir == session.root_dir / "out"
    assert session.config_dir == session.root_dir


def test_session_overrides_optional_vars(tmp_path, clean_environ):
    """Explicit values for the optional commented-out vars take precedence."""
    custom_root = tmp_path / "custom-root"
    custom_data = tmp_path / "custom-data"
    custom_config = tmp_path / "custom-config"

    sample = tmp_path / ".env"
    sample.write_text(
        f"DEFAULT_PREFIX='alice'\n"
        f"ROOT_DIR='{custom_root}'\n"
        f"DATA_DIR='{custom_data}'\n"
        f"CONFIG_DIR='{custom_config}'\n"
    )

    session = SessionContext.from_env(sample)
    assert session.default_prefix == "alice"
    assert session.root_dir == custom_root
    assert session.data_dir == custom_data
    assert session.config_dir == custom_config


def test_session_coerces_string_values(tmp_path, clean_environ):
    """Values from the ``.env`` file (always strings) are coerced to the field type."""
    sample = tmp_path / ".env"
    sample.write_text(
        "REDIS_URL='redis://127.0.0.1:6380/0'\n"
        "PLOTTING='False'\n"
        "STDOUT_LOG_LEVEL='30'\n"
    )

    session = SessionContext.from_env(sample)
    assert str(session.redis_url) == "redis://127.0.0.1:6380/0"
    assert session.plotting is False
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
    sample.write_text("PLOTTING='False'\n")  # only PLOTTING in the file

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6500/0")
    monkeypatch.setenv("QUBITS", "q00,q01")

    session = SessionContext.from_env(sample)
    assert session.plotting is False  # from file
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
    assert session.plotting is True  # class default


def test_session_from_env_raises_for_missing_file(tmp_path):
    """A missing ``.env`` path raises ``FileNotFoundError``."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        SessionContext.from_env(missing)
