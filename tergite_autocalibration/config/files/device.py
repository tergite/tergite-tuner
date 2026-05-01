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

"""Schema for the ``device_config.toml`` file."""

from os import PathLike
from typing import Any, Dict

import toml
from pydantic import BaseModel, ConfigDict, Field


class _Position(BaseModel):
    """The (column, row) position of a component on the device layout."""

    column: int
    row: int


class _LayoutEntry(BaseModel):
    """A single entry in the ``[layout.<component>.<id>]`` section."""

    model_config = ConfigDict(extra="allow")

    position: _Position


class _DeviceLayout(BaseModel):
    """The ``[layout]`` section of the device configuration.

    Each component type (``resonator``, ``qubit``, ``coupler``) maps
    component identifiers (``q01``, ``q06_q07``, ...) to a layout
    entry that, for now, just contains the position on the chip.
    """

    model_config = ConfigDict(extra="allow")

    resonator: Dict[str, _LayoutEntry] = Field(default_factory=dict)
    qubit: Dict[str, _LayoutEntry] = Field(default_factory=dict)
    coupler: Dict[str, _LayoutEntry] = Field(default_factory=dict)


class _DeviceSection(BaseModel):
    """The ``[device]`` section of the device configuration.

    The per-component subsections (``[device.qubit.q01]``,
    ``[device.qubit.all]``, ...) carry arbitrary, possibly nested
    parameters (e.g. ``measure.acq_delay``), so they are kept as
    free-form dicts. The special ``all`` key, when present, holds
    defaults applied to every component of that type.

    Attributes:
        name: device name. Part of the general device metadata known
            after fabrication and first manual characterization.
        owner: owner of the device.
        resonator: resonator-specific properties, keyed by resonator
            identifier (e.g. ``q01``) or by the special ``all`` key for
            shared defaults.
        qubit: qubit-specific properties, keyed by qubit identifier or
            by the special ``all`` key for shared defaults.
        coupler: coupler-specific properties, keyed by coupler
            identifier (e.g. ``q06_q07``) or by the special ``all`` key
            for shared defaults.
    """

    model_config = ConfigDict(extra="allow")

    name: str = "no_device_name_configured"
    owner: str = "no_owner_configured"
    resonator: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    qubit: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    coupler: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class DeviceConfigFile(BaseModel):
    """Schema for the ``device_config.toml`` file.

    Only the high-level structure (``[device]`` and ``[layout]``) is
    validated strictly; the parameters within each component's
    sub-section are kept as untyped dicts because they vary widely from
    device to device and are interpreted further down the calibration
    pipeline.

    Attributes:
        device: general device properties known after fabrication and
            first manual characterization steps, plus the
            resonator/qubit/coupler parameter blocks.
        layout: physical layout of the chip. Each component type maps
            component identifiers (``q01``, ``q06_q07``, ...) to a
            position on the chip. This also serves as the declaration of
            which components are supported/present on the device.
    """

    model_config = ConfigDict(extra="allow")

    device: _DeviceSection = Field(default_factory=_DeviceSection)
    layout: _DeviceLayout = Field(default_factory=_DeviceLayout)

    @classmethod
    def from_toml(cls, file: PathLike[str]) -> "DeviceConfigFile":
        """Loads the device configuration from a TOML file.

        Args:
            file: path to the ``device_config.toml`` file

        Returns:
            the parsed and validated ``DeviceConfigFile`` instance
        """
        with open(file, "r", encoding="utf-8") as f:
            data = toml.load(f)
        return cls(**data)
