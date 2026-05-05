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

"""Schema for the ``node_config.toml`` file."""

from os import PathLike
from typing import Any, Dict

import toml
from pydantic import RootModel, model_validator


class NodeConfig(RootModel[Dict[str, Dict[str, Any]]]):
    """The configuration for each node, including initial parameter values to use

    It is also the schema for the ``node_config.toml`` file.

    Each top-level section is a node name (e.g. ``resonator_spectroscopy``)
    and its body is a mapping of qubit identifiers (or the special
    ``all`` key) to arbitrary, possibly nested parameter dicts such as
    ``reset.duration = 60e-6`` or ``spec.spec_amp = 6e-4``.
    """

    @model_validator(mode="after")
    def _check_section_shape(self) -> "NodeConfig":
        """Each section must itself be a mapping of qubit -> parameters."""
        for node_name, node_section in self.root.items():
            if not isinstance(node_section, dict):
                raise ValueError(
                    f"Section '{node_name}' must be a table mapping qubit "
                    f"names (or 'all') to parameters, got "
                    f"{type(node_section).__name__}"
                )
        return self

    @classmethod
    def from_toml(cls, file: "PathLike[str]") -> "NodeConfig":
        """Loads the node configuration from a TOML file.

        Args:
            file: path to the ``node_config.toml`` file

        Returns:
            the parsed and validated ``NodeConfig`` instance
        """
        with open(file, "r", encoding="utf-8") as f:
            data = toml.load(f)
        return cls(data)

    def __getitem__(self, key: str) -> Dict[str, Any]:
        return self.root[key]

    def __contains__(self, key: object) -> bool:
        return key in self.root

    def __iter__(self):
        return iter(self.root)
