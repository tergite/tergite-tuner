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

"""Tests for the pydantic schemas defined in ``tergite_tuner.config.files``.

The tests load the canonical ``fc8a`` templates that ship with the
package and assert that the parsed objects expose the expected
structure, then exercise a few negative cases to make sure validation
errors actually fire when the input is malformed.
"""

import json
from os import path

import pytest
import toml
from pydantic import ValidationError

from tergite_tuner.config.files import (
    ClusterConfigFile,
    DeviceConfigFile,
    MetaConfigFile,
    NodeConfigFile,
    SpiConfigFile,
)

_CONFIG_PACKAGE_DIR = path.dirname(path.dirname(path.abspath(__file__)))
_TEMPLATE_DIR = path.join(_CONFIG_PACKAGE_DIR, "templates", "fc8a")
_CONFIGS_DIR = path.join(_TEMPLATE_DIR, "configs")


@pytest.fixture
def meta_config_path() -> str:
    return path.join(_TEMPLATE_DIR, "configuration.meta.toml")


@pytest.fixture
def device_config_path() -> str:
    return path.join(_CONFIGS_DIR, "device_config.toml")


@pytest.fixture
def node_config_path() -> str:
    return path.join(_CONFIGS_DIR, "node_config.toml")


@pytest.fixture
def spi_config_path() -> str:
    return path.join(_CONFIGS_DIR, "spi_config.toml")


@pytest.fixture
def cluster_config_path() -> str:
    return path.join(_CONFIGS_DIR, "cluster_config.json")


def test_meta_config_loads_fc8a_template(meta_config_path):
    """The meta configuration of the fc8a template loads cleanly."""
    meta = MetaConfigFile.from_toml(meta_config_path)

    assert meta.path_prefix == "configs"
    assert meta.files.cluster_config == "cluster_config.json"
    assert meta.files.device_config == "device_config.toml"
    assert meta.files.spi_config == "spi_config.toml"
    assert meta.files.node_config == "node_config.toml"
    assert {key: str(value) for key, value in meta.misc.items()} == {
        "miscellaneous_files": "misc"
    }


def test_meta_config_defaults_when_files_missing(tmp_path):
    """An almost-empty meta file should still parse, with defaults applied."""
    sample = tmp_path / "configuration.meta.toml"
    sample.write_text("path_prefix = 'configs'\n")

    meta = MetaConfigFile.from_toml(sample)
    assert meta.path_prefix == "configs"
    # missing keys fall back to the documented filenames
    assert meta.files.cluster_config == "cluster_config.json"
    assert meta.files.device_config == "device_config.toml"
    assert meta.files.spi_config == "spi_config.toml"
    assert meta.files.node_config == "node_config.toml"
    assert meta.misc == {}


def test_meta_config_tolerates_unknown_files(tmp_path):
    """Unknown keys under ``[files]`` should be stored on the model rather than rejected."""
    sample = tmp_path / "configuration.meta.toml"
    sample.write_text(
        "path_prefix = 'configs'\n"
        "\n"
        "[files]\n"
        "device_config = 'device_config.toml'\n"
        "future_config = 'future_config.toml'\n"
    )

    meta = MetaConfigFile.from_toml(sample)
    assert meta.files.device_config == "device_config.toml"
    # Unknown keys are kept thanks to ``extra="allow"``
    assert meta.files.model_dump().get("future_config") == "future_config.toml"


def test_device_config_loads_fc8a_template(device_config_path):
    """The device configuration of the fc8a template loads cleanly."""
    dev = DeviceConfigFile.from_toml(device_config_path)

    assert dev.device.name == "V8a #1"
    assert dev.device.owner == "QC2"

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
    assert dev.device.owner == "no_owner_configured"
    assert dev.device.resonators == {}
    assert dev.device.qubits == {}
    assert dev.device.couplers == {}


def test_node_config_loads_fc8a_template(node_config_path):
    """The node configuration of the fc8a template loads cleanly."""
    node = NodeConfigFile.from_toml(node_config_path)

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
        NodeConfigFile({"resonator_spectroscopy": "not-a-dict"})

    assert any(
        "valid dictionary" in err["msg"].lower() for err in excinfo.value.errors()
    )


def test_node_config_membership_iteration(node_config_path):
    """The dunder helpers should expose the parsed content like a dict."""
    node = NodeConfigFile.from_toml(node_config_path)
    assert "punchout" in node
    assert "non_existent_node" not in node
    assert set(iter(node)) == set(node.root.keys())


def test_spi_config_loads_fc8a_template(spi_config_path):
    """The SPI configuration of the fc8a template loads cleanly."""
    spi = SpiConfigFile.from_toml(spi_config_path)

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
        SpiConfigFile({"q01_q02": {"spi_module_number": 1}})

    locs = [err["loc"] for err in excinfo.value.errors()]
    assert ("q01_q02", "dac_name") in locs


def test_spi_config_rejects_non_integer_module_number():
    """``spi_module_number`` must be coercible to an int."""
    with pytest.raises(ValidationError) as excinfo:
        SpiConfigFile({"q01_q02": {"spi_module_number": "not-int", "dac_name": "dac0"}})

    locs = [err["loc"] for err in excinfo.value.errors()]
    assert ("q01_q02", "spi_module_number") in locs


def test_spi_config_membership_iteration(spi_config_path):
    spi = SpiConfigFile.from_toml(spi_config_path)
    assert "q11_q12" in spi
    assert "q99_q99" not in spi
    assert "q08_q09" in list(iter(spi))


def test_cluster_config_loads_fc8a_template(cluster_config_path):
    """The cluster configuration of the fc8a template loads via quantify-scheduler."""
    pytest.importorskip("quantify_scheduler")

    cluster = ClusterConfigFile.from_json(cluster_config_path)

    # ``from_json`` returns the canonical quantify-scheduler model, so a
    # few of its fields should be populated
    assert "clusterA" in cluster.hardware_description
    assert cluster.hardware_options is not None

    # The raw json file matches what quantify-scheduler ingests
    with open(cluster_config_path, "r") as f:
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
        ClusterConfigFile.from_json(sample)


@pytest.mark.parametrize(
    "loader",
    [
        MetaConfigFile.from_toml,
        DeviceConfigFile.from_toml,
        NodeConfigFile.from_toml,
        SpiConfigFile.from_toml,
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
        ClusterConfigFile.from_json(missing)


@pytest.mark.parametrize(
    ("loader", "extension"),
    [
        (MetaConfigFile.from_toml, ".toml"),
        (DeviceConfigFile.from_toml, ".toml"),
        (NodeConfigFile.from_toml, ".toml"),
        (SpiConfigFile.from_toml, ".toml"),
    ],
)
def test_toml_loaders_raise_on_invalid_toml(tmp_path, loader, extension):
    """Invalid TOML content raises a ``TomlDecodeError`` from the loader."""
    bad = tmp_path / f"bad{extension}"
    bad.write_text("invalid: toml: content")

    with pytest.raises(toml.TomlDecodeError):
        loader(bad)
