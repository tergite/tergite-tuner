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
``tergite_autocalibration/config/templates/<device>``. Each top-level
configuration file lives in its own submodule and exposes a
``from_toml`` / ``from_json`` classmethod that loads and validates the
file in one shot. The pattern loosely follows
``tergite-backend/app/libs/device_parameters/dtos.py``.
"""

from tergite_autocalibration.config.files.cluster import ClusterConfigFile
from tergite_autocalibration.config.files.device import DeviceConfigFile
from tergite_autocalibration.config.files.env import EnvConfigFile
from tergite_autocalibration.config.files.meta import MetaConfigFile
from tergite_autocalibration.config.files.node import NodeConfigFile
from tergite_autocalibration.config.files.spi import SpiConfigFile

__all__ = [
    "ClusterConfigFile",
    "DeviceConfigFile",
    "EnvConfigFile",
    "MetaConfigFile",
    "NodeConfigFile",
    "SpiConfigFile",
]
