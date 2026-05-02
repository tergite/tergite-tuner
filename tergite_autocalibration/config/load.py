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

"""Loader for a complete configuration package.

A configuration package is a directory containing a
``configuration.meta.toml`` file that points at the individual
configuration files (cluster, device, node, spi). :func:`load_configuration`
reads that meta file and returns a :class:`Configuration` bundling the
already-validated pydantic models for each file.
"""

import os
from os import PathLike
from typing import Dict, Optional, Union

from tergite_autocalibration.config.files import (
    ClusterConfigFile,
    DeviceConfig,
    DeviceConfigFile,
    MetaConfigFile,
    NodeConfigFile,
    SpiConfigFile,
)
from tergite_autocalibration.utils.logging import logger


class Configuration:
    """A loaded configuration package.

    Attributes:
        meta_path: absolute path to the ``configuration.meta.toml`` file.
        device: the runtime view of the device configuration. The
            ``[layout]`` section of ``device_config.toml`` is parsed by
            :class:`DeviceConfigFile` but not exposed here, since
            calibration code only needs the device parameters.
        node: the parsed ``node_config.toml``.
        spi: the parsed ``spi_config.toml``, or ``None`` if the package
            does not include one (single-qubit calibrations don't need
            SPI wiring).
        misc: extra folders shipped alongside the package, mapping the
            user-chosen key to the absolute path of the folder.
        cluster: the parsed ``cluster_config.json`` (delegated to
            quantify-scheduler), or ``None`` if not declared in the
            meta file.
    """

    def __init__(
        self,
        *,
        meta_path: str,
        device: DeviceConfig,
        node: NodeConfigFile,
        spi: Optional[SpiConfigFile],
        misc: Dict[str, str],
        cluster: Optional[ClusterConfigFile],
    ) -> None:
        self.meta_path = meta_path
        self.device = device
        self.node = node
        self.spi = spi
        self.misc = misc
        self.cluster = cluster


def load_configuration(
    meta_config_path: Union[str, PathLike[str]],
) -> Configuration:
    """Load a configuration package from its ``configuration.meta.toml``.

    Resolves the relative paths declared in the meta file against the
    directory containing the meta file, eagerly parses the device, node
    and (if present) SPI configs, and defers the cluster config until
    :attr:`Configuration.cluster` is accessed.

    Args:
        meta_config_path: path to the ``configuration.meta.toml`` file.

    Returns:
        the loaded :class:`Configuration`.

    Raises:
        FileNotFoundError: if ``meta_config_path`` does not point at an
            existing file.
    """
    meta_path = os.fspath(meta_config_path)
    if not os.path.isfile(meta_path):
        raise FileNotFoundError(
            f"Cannot find configuration.meta.toml at {meta_path!r}."
        )

    meta = MetaConfigFile.from_toml(meta_path)

    base_dir = os.path.dirname(os.path.abspath(meta_path))
    config_dir = os.path.join(base_dir, meta.path_prefix)

    def _resolve(rel: Optional[str]) -> Optional[str]:
        return os.path.join(config_dir, rel) if rel else None

    device_path = _resolve(meta.files.device_config)
    node_path = _resolve(meta.files.node_config)
    spi_path = _resolve(meta.files.spi_config)
    cluster_path = _resolve(meta.files.cluster_config)

    if device_path is None:
        raise ValueError(
            "configuration.meta.toml is missing required 'device_config' entry."
        )
    if node_path is None:
        raise ValueError(
            "configuration.meta.toml is missing required 'node_config' entry."
        )

    logger.info(f"Loading device_config: {meta.files.device_config}")
    device_file = DeviceConfigFile.from_toml(device_path)
    # The ``[layout]`` section is validated by ``DeviceConfigFile`` but
    # not consumed by calibration code, so we only carry the runtime
    # ``DeviceConfig`` view forward.
    device = device_file.device

    logger.info(f"Loading node_config: {meta.files.node_config}")
    node = NodeConfigFile.from_toml(node_path)

    spi: Optional[SpiConfigFile] = None
    if spi_path is not None:
        logger.info(f"Loading spi_config: {meta.files.spi_config}")
        spi = SpiConfigFile.from_toml(spi_path)

    cluster: Optional[ClusterConfigFile] = None
    if cluster_path is not None:
        logger.info(f"Loading cluster_config: {meta.files.cluster_config}")
        cluster = ClusterConfigFile.from_json(cluster_path)

    misc = {
        key: os.path.join(base_dir, rel_path) for key, rel_path in meta.misc.items()
    }

    logger.info(f"Loaded configuration package from {meta_path}")
    return Configuration(
        meta_path=meta_path,
        device=device,
        node=node,
        spi=spi,
        misc=misc,
        cluster=cluster,
    )


# CLAUDE-FIX: Maybe move Configuration and SessionContext to the same file i.e this file and remove the session.py file. the lines below look patchy

# Resolve the forward reference to ``Configuration`` declared (under
# ``TYPE_CHECKING``) on :class:`SessionContext`. Importing this module is
# the canonical way to obtain ``Configuration``, so it is also the right
# place to rebuild the pydantic model now that the type is concrete.
from tergite_autocalibration.config.session import (  # noqa: E402  pylint: disable=wrong-import-position
    SessionContext,
)

SessionContext.model_rebuild()
