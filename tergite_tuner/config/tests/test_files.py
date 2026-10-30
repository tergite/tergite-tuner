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

"""Tests for the pydantic schemas defined in ``tergite_tuner.config.files``."""

import json
from os import path
from pathlib import Path

import pytest
import toml
from pydantic import ValidationError

from tergite_tuner.config.types import (
    ClusterConfig,
    DeviceConfigFile,
    NodeConfig,
    SpiConfig,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_DEVICE_CONFIG_PATH = _PROJECT_ROOT / "device_config.example.toml"
_NODE_CONFIG_PATH = _PROJECT_ROOT / "node_config.example.toml"
_SPI_CONFIG_PATH = _PROJECT_ROOT / "spi_config.example.toml"
_CLUSTER_CONFIG_PATH = _PROJECT_ROOT / "cluster_config.example.json"


def test_device_config_load_example():
    """The device configuration of the example template loads cleanly."""
    dev = DeviceConfigFile.from_toml(_DEVICE_CONFIG_PATH)

    assert dev.device.name == "V8a #1"

    # The ``[device.*.all]`` defaults are merged into each per-entry block
    # by the model validator, so ``all`` itself is consumed.
    assert "all" not in dev.device.qubits
    assert "all" not in dev.device.resonators
    assert "all" not in dev.device.couplers

    # Sanity-check a few specific entries from the template
    assert dev.device.resonators["q01"]["VNA_frequency"] == 6433000000.0
    assert dev.device.qubits["q06"]["VNA_f01_frequency"] == 4635600000.0
    assert dev.device.couplers["q06_q07"]["control_qubit"] == "q07"
    assert dev.device.couplers["q06_q07"]["target_qubit"] == "q06"

    # Layout positions are typed
    assert dev.layout.qubit["q01"].position.column == 0
    assert dev.layout.qubit["q01"].position.row == 1
    assert dev.layout.resonator["q02"].position.column == 2


def test_device_config_rejects_non_integer_layout_position():
    """Layout positions must be integers."""
    with pytest.raises(ValidationError) as excinfo:
        DeviceConfigFile(
            device={},
            layout={"qubit": {"q01": {"position": {"column": "not-an-int", "row": 0}}}},
        )

    locs = [err["loc"] for err in excinfo.value.errors()]
    assert ("layout", "qubit", "q01", "position", "column") in locs


def test_device_config_uses_defaults_when_section_missing(tmp_path):
    """Missing top-level sections fall back to sensible defaults."""
    sample = tmp_path / "device_config.toml"
    sample.write_text("")

    dev = DeviceConfigFile.from_toml(sample)
    assert dev.device.name == "no_device_name_configured"
    assert dev.device.resonators == {}
    assert dev.device.qubits == {}
    assert dev.device.couplers == {}


def test_node_config_load_example():
    """The node configuration of the example loads cleanly."""
    node = NodeConfig.from_toml(_NODE_CONFIG_PATH)

    expected_sections = {
        "resonator_spectroscopy",
        "punchout",
        "resonator_spectroscopy_1",
        "coupler_resonator_spectroscopy",
        "resonator_spectroscopy_2",
        "qubit_01_spectroscopy",
        "qubit_spectroscopy_vs_current",
        "qubit_12_spectroscopy_pulsed",
        "cz_chevron",
    }
    assert expected_sections.issubset(set(node.root.keys()))

    # Dotted TOML keys come back as nested dicts
    assert node["resonator_spectroscopy"]["all"] == {"reset": {"duration": 60e-6}}
    assert node["cz_chevron"]["all"]["coupler_spec_amp"] == 0.3


def test_node_config_rejects_non_dict_section():
    """A section whose body is not a table must fail validation."""
    with pytest.raises(ValidationError) as excinfo:
        NodeConfig({"resonator_spectroscopy": "not-a-dict"})

    assert any(
        "valid dictionary" in err["msg"].lower() for err in excinfo.value.errors()
    )


def test_node_config_membership_iteration():
    """The dunder helpers should expose the parsed content like a dict."""
    node = NodeConfig.from_toml(_NODE_CONFIG_PATH)
    assert "punchout" in node
    assert "non_existent_node" not in node
    assert set(iter(node)) == set(node.root.keys())


def test_node_config_default_is_empty():
    """``NodeConfig()`` constructs with no nodes — it is the default for
    :class:`SessionContext.node_config`, so this contract matters."""
    node = NodeConfig()
    assert node.root == {}
    assert "anything" not in node
    assert list(iter(node)) == []


def test_spi_config_load_example():
    """The SPI configuration from the example spi config file loads cleanly."""
    spi = SpiConfig.from_toml(_SPI_CONFIG_PATH)

    # Coupler with an edge group
    assert spi["q11_q12"].spi_module_number == 1
    assert spi["q11_q12"].dac_name == "dac0"
    assert spi["q11_q12"].edge_group == 1

    # Coupler without an edge group (edge_group is Optional)
    assert spi["q08_q09"].spi_module_number == 2
    assert spi["q08_q09"].dac_name == "dac0"
    assert spi["q08_q09"].edge_group is None


def test_spi_config_rejects_missing_dac_name():
    """``dac_name`` is required."""
    with pytest.raises(ValidationError) as excinfo:
        SpiConfig({"q01_q02": {"spi_module_number": 1}})

    locs = [err["loc"] for err in excinfo.value.errors()]
    assert ("q01_q02", "dac_name") in locs


def test_spi_config_rejects_non_integer_module_number():
    """``spi_module_number`` must be coercible to an int."""
    with pytest.raises(ValidationError) as excinfo:
        SpiConfig({"q01_q02": {"spi_module_number": "not-int", "dac_name": "dac0"}})

    locs = [err["loc"] for err in excinfo.value.errors()]
    assert ("q01_q02", "spi_module_number") in locs


def test_spi_config_membership_iteration():
    spi = SpiConfig.from_toml(_SPI_CONFIG_PATH)
    assert "q11_q12" in spi
    assert "q99_q99" not in spi
    assert "q08_q09" in list(iter(spi))


def test_spi_config_default_is_empty():
    """``SpiConfig()`` constructs with no couplers wired — useful as a
    default when the calibration doesn't drive the SPI rack."""
    spi = SpiConfig()
    assert spi.root == {}
    assert "anything" not in spi
    assert list(iter(spi)) == []


def test_cluster_config_load_example():
    """The cluster configuration of the example file loads via quantify-scheduler."""
    pytest.importorskip("quantify_scheduler")

    cluster = ClusterConfig.from_json(_CLUSTER_CONFIG_PATH)

    # ``from_json`` returns the canonical quantify-scheduler model, so a
    # few of its fields should be populated
    assert "clusterA" in cluster.hardware_description
    assert cluster.hardware_options is not None

    # The raw json file matches what quantify-scheduler ingests
    with open(_CLUSTER_CONFIG_PATH, "r") as f:
        raw = json.load(f)
    assert (
        raw["config_type"]
        == "quantify_scheduler.backends.qblox_backend.QbloxHardwareCompilationConfig"
    )


def test_cluster_config_rejects_invalid_payload(tmp_path):
    """A cluster config with a missing required field must fail validation."""
    pytest.importorskip("quantify_scheduler")

    sample = tmp_path / "cluster_config.json"
    # An empty object is missing the required ``hardware_description`` /
    # ``hardware_options`` keys, so quantify-scheduler will reject it.
    sample.write_text("{}")

    with pytest.raises(ValidationError):
        ClusterConfig.from_json(sample)


@pytest.mark.parametrize(
    "loader",
    [
        DeviceConfigFile.from_toml,
        NodeConfig.from_toml,
        SpiConfig.from_toml,
    ],
)
def test_toml_loaders_raise_for_missing_file(tmp_path, loader):
    """Every file-based loader propagates a ``FileNotFoundError`` for a non-existent file."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        loader(missing)


def test_cluster_loader_raises_for_missing_file(tmp_path):
    """The cluster JSON loader propagates a ``FileNotFoundError`` for a non-existent file."""
    pytest.importorskip("quantify_scheduler")

    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        ClusterConfig.from_json(missing)


@pytest.mark.parametrize(
    ("loader", "extension"),
    [
        (DeviceConfigFile.from_toml, ".toml"),
        (NodeConfig.from_toml, ".toml"),
        (SpiConfig.from_toml, ".toml"),
    ],
)
def test_toml_loaders_raise_on_invalid_toml(tmp_path, loader, extension):
    """Invalid TOML content raises a ``TomlDecodeError`` from the loader."""
    bad = tmp_path / f"bad{extension}"
    bad.write_text("invalid: toml: content")

    with pytest.raises(toml.TomlDecodeError):
        loader(bad)
