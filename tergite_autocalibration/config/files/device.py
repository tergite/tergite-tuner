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

import copy
from os import PathLike
from types import MappingProxyType
from typing import Any, Dict, Tuple

import toml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tergite_autocalibration.utils.dto.enums import QubitRole
from tergite_autocalibration.utils.misc.helpers import update_nested


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


class DeviceConfig(BaseModel):
    """Runtime view of the ``[device]`` section of the device configuration.

    This is the object that calibration code consumes via
    ``CONFIG.device``. It mirrors the ``[device]`` table of
    ``device_config.toml`` but exposes the per-component blocks under
    plural Python names (``qubits``, ``resonators``, ``couplers``) via
    :class:`pydantic.Field` aliases — the TOML keys themselves
    (``[device.qubit.*]``, ``[device.resonator.*]``,
    ``[device.coupler.*]``) are unchanged.

    The per-component subsections (``[device.qubit.q01]``,
    ``[device.qubit.all]``, ...) carry arbitrary, possibly nested
    parameters (e.g. ``measure.acq_delay``), so they are kept as
    free-form dicts.

    The special ``all`` block in each component subsection holds
    defaults applied to every other entry of that type. A
    :func:`model_validator` runs *before* field validation and merges
    those defaults in place, then drops the ``all`` key. As a result,
    ``self.qubits["q01"]`` always carries the fully-resolved parameters
    and you never need to re-merge ``all`` at the call site.

    Attributes:
        name: device name. Part of the general device metadata known
            after fabrication and first manual characterization.
        owner: owner of the device.
        resonators: resonator-specific parameters, keyed by resonator
            identifier (e.g. ``q01``). The ``[device.resonator.all]``
            defaults have already been merged into each entry.
        qubits: qubit-specific parameters, keyed by qubit identifier.
            The ``[device.qubit.all]`` defaults have already been
            merged into each entry.
        couplers: coupler-specific parameters, keyed by coupler
            identifier (e.g. ``q06_q07``). The ``[device.coupler.all]``
            defaults have already been merged into each entry.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = "no_device_name_configured"
    owner: str = "no_owner_configured"
    resonators: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, alias="resonator"
    )
    qubits: Dict[str, Dict[str, Any]] = Field(default_factory=dict, alias="qubit")
    couplers: Dict[str, Dict[str, Any]] = Field(default_factory=dict, alias="coupler")

    @model_validator(mode="before")
    @classmethod
    def _merge_all_defaults(cls, data: Any) -> Any:
        """Apply ``[device.<comp>.all]`` defaults into per-entry blocks.

        Runs before field validation so the merge happens once, at
        construction time, instead of on every property access. Both
        the TOML alias (``qubit``) and the field name (``qubits``) are
        accepted because :class:`DeviceConfig` uses
        ``populate_by_name``.
        """
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for key in (
            "qubit",
            "qubits",
            "resonator",
            "resonators",
            "coupler",
            "couplers",
        ):
            if key in out:
                out[key] = _apply_all_defaults(out[key])
        return out

    def get_qubit_role(self, coupler_name: str, qubit_name: str) -> "QubitRole":
        """Get the role of a qubit in the context of a coupler.

        Args:
            coupler_name: e.g. ``"q00_q01"``.
            qubit_name: e.g. ``"q00"``.

        Returns:
            ``QubitRole.TARGET`` if ``qubit_name`` is the coupler's
            ``target_qubit``, ``QubitRole.CONTROL`` if it's the
            ``control_qubit``, and ``QubitRole.NOTSET`` otherwise (or
            when the coupler isn't defined).
        """
        coupler = self.couplers.get(coupler_name, {})
        if coupler.get("target_qubit") == qubit_name:
            return QubitRole.TARGET
        if coupler.get("control_qubit") == qubit_name:
            return QubitRole.CONTROL
        return QubitRole.NOTSET

    def get_control_target_qubit_pair_by_coupler(
        self, coupler_name: str
    ) -> Tuple[str, str]:
        """Get the (control, target) qubit pair for a coupler.

        Args:
            coupler_name: e.g. ``"q00_q01"``.

        Returns:
            ``(control_qubit, target_qubit)``, e.g. ``("q01", "q00")``.

        Raises:
            KeyError: if the coupler isn't defined, or if it lacks a
                ``control_qubit`` / ``target_qubit`` entry.
        """
        coupler = self.couplers.get(coupler_name)
        if coupler is None:
            raise KeyError(
                f"Coupler name {coupler_name} is not found in the device "
                "configuration."
            )
        try:
            return coupler["control_qubit"], coupler["target_qubit"]
        except KeyError:
            raise KeyError(
                f"Coupler with name {coupler_name} does not define "
                "'control_qubit' or 'target_qubit'."
            )

    def get_output_attenuations(
        self,
    ) -> MappingProxyType[str, MappingProxyType[str, int]]:
        """Per-component output attenuations as a read-only mapping.

        This is an intentional bypass of the hardware config method of
        setting attenuation. For higher energy levels you almost always
        want the same attenuation, but Quantify scheduler requires the
        clocks to be different (since the frequency of transition is
        statefully stored in the clock resource). Reading attenuations
        from the device config rather than the cluster config keeps the
        cluster config from getting repetitive.

        Defaults: 30 dB on qubits and couplers, 60 dB on resonators
        (which matches the QCM-RF / QRM-RF maxima documented at
        https://docs.qblox.com).
        """
        xy = MappingProxyType(
            {q: data.get("attenuation", 30) for q, data in self.qubits.items()}
        )
        z = MappingProxyType(
            {c: data.get("attenuation", 30) for c, data in self.couplers.items()}
        )
        ro = MappingProxyType(
            {r: data.get("attenuation", 60) for r, data in self.resonators.items()}
        )
        return MappingProxyType({"resonator": ro, "coupler": z, "qubit": xy})


class DeviceConfigFile(BaseModel):
    """Schema for the ``device_config.toml`` file.

    Only the high-level structure (``[device]`` and ``[layout]``) is
    validated strictly; the parameters within each component's
    sub-section are kept as untyped dicts because they vary widely from
    device to device and are interpreted further down the calibration
    pipeline.

    Note that this is the file-shape mirror of the TOML, intended for
    loading and validation. Calibration code consumes the
    :class:`DeviceConfig` runtime view (assigned to ``CONFIG.device``)
    rather than this object directly.

    Attributes:
        device: general device properties known after fabrication and
            first manual characterization steps, plus the
            resonator/qubit/coupler parameter blocks. See
            :class:`DeviceConfig` for the available attributes and
            helper methods.
        layout: physical layout of the chip. Each component type maps
            component identifiers (``q01``, ``q06_q07``, ...) to a
            position on the chip. This also serves as the declaration of
            which components are supported/present on the device.
    """

    model_config = ConfigDict(extra="allow")

    device: DeviceConfig = Field(default_factory=DeviceConfig)
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


def _apply_all_defaults(
    section: Any,
) -> Any:
    """Apply ``all`` defaults to every other entry in a device subsection.

    ``[device.qubit.all]``-style blocks describe defaults that every
    sibling block inherits unless it sets the value itself. This helper
    returns a deep copy with that inheritance applied and the ``all``
    key removed; per-entry values always win.

    If ``section`` is not a dict (e.g. validation will fail later
    anyway), it is returned unchanged.
    """
    if not isinstance(section, dict):
        return section
    if not section:
        return {}
    defaults = section.get("all", {})
    out: Dict[str, Dict[str, Any]] = {}
    for key, value in section.items():
        if key == "all":
            continue
        merged = copy.deepcopy(value) if isinstance(value, dict) else value
        if defaults and isinstance(merged, dict):
            update_nested(merged, copy.deepcopy(defaults))
        out[key] = merged
    return out
