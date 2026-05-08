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

"""Schema for the ``spi_config.toml`` file."""

from os import PathLike
from typing import Dict, Optional

import toml
from pydantic import BaseModel, ConfigDict, Field, RootModel


class _SpiCouplerEntry(BaseModel):
    """Configuration of a single coupler on the QBlox SPI rack.

    ``edge_group`` is optional because not every wired coupler is part
    of an edge group.
    """

    model_config = ConfigDict(extra="allow")

    spi_module_number: int
    dac_name: str
    edge_group: Optional[int] = None


class SpiConfig(RootModel[Dict[str, _SpiCouplerEntry]]):
    """The configuration for the SPI.

    It is also the schema for the ``spi_config.toml`` file.

    Each top-level section is a coupler identifier of the form
    ``q<a>_q<b>`` and maps to a :class:`_SpiCouplerEntry`.

    The empty mapping is a valid configuration: ``SpiConfig()`` returns
    a config with no couplers wired, which is useful as a default in
    :class:`SessionContext`.
    """

    root: Dict[str, _SpiCouplerEntry] = Field(default_factory=dict)

    @classmethod
    def from_toml(cls, file: "PathLike[str]") -> "SpiConfig":
        """Loads the SPI configuration from a TOML file.

        Args:
            file: path to the ``spi_config.toml`` file

        Returns:
            the parsed and validated ``SpiConfig`` instance
        """
        with open(file, "r", encoding="utf-8") as f:
            data = toml.load(f)
        return cls(data)

    def __getitem__(self, key: str) -> _SpiCouplerEntry:
        return self.root[key]

    def __contains__(self, key: object) -> bool:
        return key in self.root

    def __iter__(self):
        return iter(self.root)
