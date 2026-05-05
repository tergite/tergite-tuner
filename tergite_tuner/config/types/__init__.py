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

"""Schemas of the configuration files expected for this library.

These pydantic models mirror the structure of the templates kept under
``tergite_tuner/config/templates/<device>``. Each top-level
configuration file lives in its own submodule and exposes a
``from_toml`` / ``from_json`` classmethod that loads and validates the
file in one shot. The pattern loosely follows
``tergite-backend/app/libs/device_parameters/dtos.py``.

Note:
    Importing :class:`ClusterConfig` pulls in ``quantify_scheduler``,
    which has a non-trivial import chain. The calibration tool needs it
    anyway, so we pay the cost once at startup rather than working
    around it.
"""

from tergite_tuner.config.types.cluster import ClusterConfig
from tergite_tuner.config.types.device import DeviceConfig, DeviceConfigFile
from tergite_tuner.config.types.node import NodeConfig
from tergite_tuner.config.types.spi import SpiConfig

__all__ = [
    "ClusterConfig",
    "DeviceConfig",
    "DeviceConfigFile",
    "NodeConfig",
    "SpiConfig",
]
