# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Pontus Vikstahl 2024
# (C) Copyright Stefan Hill 2024
# (C) Copyright Martin Ahindura 2023
# (C) Copyright Michele Faucci Giannelli 2024, 2025
# (C) Copyright Axel Erik Andersson 2025
# (C) Copyright Abdullah Al Amin 2026
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import time
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from qblox_instruments import Cluster
from qblox_instruments.types import ClusterType
from quantify_scheduler.instrument_coordinator import InstrumentCoordinator
from quantify_scheduler.instrument_coordinator.components.qblox import ClusterComponent

from tergite_tuner.backend.spi import SpiDAC
from tergite_tuner.exc import ClusterUnreachableError
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.types.enums import MeasurementMode

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

PORT_SUFFIXES = {"coupler": ":fl", "resonator": ":res", "qubit": ":mw"}


class Hardware:
    """The cluster the nodes measure on, its instrument coordinator and, for couplers, the SPI rack."""

    def __init__(self, session: "SessionContext") -> None:
        self.session = session
        self.cluster = _connect_cluster(session)
        self.coordinator = InstrumentCoordinator("lab_ic")
        connectivity = MappingProxyType(
            {
                str(node): frozenset(neighbours.keys())
                for node, neighbours in session.cluster_config.connectivity.graph.adj.items()
            }
        )
        set_output_attenuations(
            self.cluster,
            connectivity,
            session.device_config.get_output_attenuations(),
        )
        self.coordinator.add_component(ClusterComponent(self.cluster))
        self.coordinator.timeout(session.cluster_timeout)
        self.spi: SpiDAC | None = None

    def connect_spi(self, couplers: list[str]) -> SpiDAC:
        self.spi = SpiDAC(couplers, self.session)
        return self.spi

    def wait(self, seconds: float) -> None:
        """Lets the device settle; a dummy cluster has nothing to wait for."""
        if self.session.cluster_mode == MeasurementMode.real:
            logger.info(f"sleeping for {seconds} seconds")
            time.sleep(seconds)


def set_output_attenuations(
    cluster: Cluster,
    connectivity: Mapping[str, frozenset[str]],
    attenuations: Mapping[str, Mapping[str, int]],
) -> None:
    """Sets each coupler's, resonator's and qubit's output attenuation on its port of ``cluster``.

    Args:
        cluster: the cluster to configure; ports of other clusters are skipped.
        connectivity: each device port (``q01:mw``) mapped to the cluster ports it is wired to.
        attenuations: the attenuation in dB of each device, per ``coupler``, ``resonator`` and ``qubit``.
    """
    module_names = frozenset(
        module.name for module in cluster.get_connected_modules().values()
    )
    for device_type, port_suffix in PORT_SUFFIXES.items():
        for name, attenuation in attenuations[device_type].items():
            device_port = name + port_suffix
            if device_port not in connectivity:
                logger.warning(
                    f"Skipping setting attenuation for '{device_port}', as it is "
                    "not in the connectivity graph of the cluster_config.json."
                )
                continue

            ports = connectivity[device_port]
            assert len(ports) == 1
            port_path = next(iter(ports))
            cluster_name, module_name, port = tuple(port_path.split(sep="."))

            # the connectivity can map inputs too, though transmon setups seldom do
            assert "output" in port, (device_port, port_path)
            if cluster_name != cluster.name:
                continue
            if f"{cluster_name}_{module_name}" not in module_names:
                continue

            module = getattr(cluster, module_name)
            if port == "complex_output_0":
                module.out0_att(attenuation)
            elif port == "complex_output_1":
                module.out1_att(attenuation)
            else:
                raise KeyError(f"Failed to set attenuation for port: {port_path}")
            logger.debug(f"Applied {attenuation}dB attenuation on {port_path}")
    logger.info("Attenuations are set")


def _connect_cluster(session: "SessionContext") -> Cluster:
    """The session's cluster: the real one, reset unless recalibrating, or a dummy with the configured modules."""
    hardware_description = session.cluster_config.hardware_description
    cluster_name = next(iter(hardware_description))
    Cluster.close_all()
    if session.cluster_mode != MeasurementMode.real:
        modules = hardware_description[cluster_name].modules
        dummy_config = {
            str(slot): ClusterType[f"CLUSTER_{module.instrument_type}"]
            for slot, module in modules.items()
        }
        return Cluster(cluster_name, dummy_cfg=dummy_config)

    try:
        cluster = Cluster(cluster_name, str(session.cluster_ip))
    except ConnectionRefusedError as exp:
        raise ClusterUnreachableError(
            f"Cluster at {session.cluster_ip} refused the connection; "
            "it may have crashed, so try power-cycling it"
        ) from exp

    if not session.is_recalibration:
        cluster.reset()
        logger.status(f" \n⚠ Resetting Cluster at IP *{str(session.cluster_ip)[-3:]}\n")
    return cluster
