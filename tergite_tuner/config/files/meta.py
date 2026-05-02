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

"""Schema for the ``configuration.meta.toml`` file."""

from os import PathLike
from typing import Dict

import toml
from pydantic import BaseModel, ConfigDict, Field


class _MetaFiles(BaseModel):
    """Paths (relative to ``path_prefix``) of the individual configuration files.

    The known files are listed explicitly so that they can be validated
    upfront, but additional, unknown files are also tolerated for
    forward compatibility.

    Attributes:
        cluster_config: file that QBlox needs to compile schedules on the
            hardware. It is a JSON file and has no built-in default.
        device_config: file with the initial values for the device
            configuration.
        spi_config: file that configures the wiring on the QBlox SPI
            rack. Only required when running two-qubit calibrations.
        node_config: file with the runtime values for the calibration
            nodes.
    """

    model_config = ConfigDict(extra="allow")

    cluster_config: str = "cluster_config.json"
    device_config: str = "device_config.toml"
    spi_config: str = "spi_config.toml"
    node_config: str = "node_config.toml"


class MetaConfigFile(BaseModel):
    """Schema for the ``configuration.meta.toml`` file.

    The meta configuration is the entry point of a configuration
    package: it declares the relative ``path_prefix`` from which the
    rest of the configuration files are resolved, the named
    configuration files themselves and an arbitrary number of
    ``misc`` folders that ship along with the package.

    Attributes:
        path_prefix: relative path from this meta file to the directory
            where the configuration files are stored. Default: 'configs'
        files: relative paths (under ``path_prefix``) of the named
            configuration files that make up the package.
        misc: extra folders shipped alongside the package, mapping a
            user-chosen key to the folder's relative path. These are
            intended for unstructured data such as mixer corrections or
            wiring diagrams. The folders must live at or below the level
            of ``configuration.meta.toml``.
    """

    model_config = ConfigDict(extra="allow")

    path_prefix: str = "configs"
    files: _MetaFiles = Field(default_factory=_MetaFiles)
    misc: Dict[str, PathLike[str]] = Field(default_factory=dict)

    @classmethod
    def from_toml(cls, file: "PathLike[str]") -> "MetaConfigFile":
        """Loads the meta configuration from a TOML file.

        Args:
            file: path to the ``configuration.meta.toml`` file

        Returns:
            the parsed and validated ``MetaConfigFile`` instance

        Raises:
            TypeError: When file is invalid type
            TomlDecodeError: Error while decoding toml
            IOError / FileNotFoundError: When file does not exist
        """
        with open(file, "r", encoding="utf-8") as f:
            data = toml.load(f)
        return cls(**data)
