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
from qcodes.instrument import Instrument
from quantify_scheduler.device_under_test.quantum_device import QuantumDevice
from quantify_scheduler.instrument_coordinator import InstrumentCoordinator
from quantify_scheduler.instrument_coordinator.components.qblox import ClusterComponent

from tergite_tuner.backend.spi import SpiDAC
from tergite_tuner.exc import ClusterUnreachableError, InstrumentNameTakenError
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.types.enums import MeasurementMode

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext

PORT_SUFFIXES = {"coupler": ":fl", "resonator": ":res", "qubit": ":mw"}
COORDINATOR_NAME = "lab_ic"


class Hardware:
    """The cluster the nodes measure on, its instrument coordinator, for couplers the SPI rack,
    and the caller's quantum device, if any, whose elements the nodes run on.

    A cluster, coordinator or quantum device passed in belongs to the caller: it is used as
    is, never reset and never closed. One the tuner opens itself is closed by :meth:`close`.

    Args:
        session: the session whose cluster config, mode and attenuations to use.
        cluster: an already-connected cluster to measure on, instead of opening one.
        coordinator: an instrument coordinator that already holds ``cluster``'s component.
        quantum_device: the caller's quantum device, whose elements each node sets from the
            session's state while it runs and sets back afterwards.

    Raises:
        InstrumentNameTakenError: the tuner would open a cluster or coordinator whose name
            another instrument in this process holds.
        ClusterUnreachableError: the real cluster refused the connection.
    """

    def __init__(
        self,
        session: "SessionContext",
        cluster: Cluster | None = None,
        coordinator: InstrumentCoordinator | None = None,
        quantum_device: QuantumDevice | None = None,
    ) -> None:
        self.session = session
        self.quantum_device = quantum_device
        self.is_cluster_owned = cluster is None
        self.is_coordinator_owned = coordinator is None
        self.cluster = cluster
        self.coordinator = coordinator
        self.spi: SpiDAC | None = None
        try:
            if self.cluster is None:
                self.cluster = _connect_cluster(session)
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
            if self.coordinator is None:
                _raise_if_name_taken(COORDINATOR_NAME)
                _raise_if_name_taken(f"ic_{self.cluster.name}")
                self.coordinator = InstrumentCoordinator(COORDINATOR_NAME)
                self.coordinator.add_component(ClusterComponent(self.cluster))
                self.coordinator.timeout(session.cluster_timeout)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        """Closes the cluster, coordinator and SPI rack the tuner opened, leaving the caller's open."""
        if self.spi is not None:
            self.spi.close_spi_rack()
            self.spi = None
        if self.is_coordinator_owned and self.coordinator is not None:
            for name in list(self.coordinator.components()):
                component = self.coordinator.get_component(name)
                self.coordinator.remove_component(name)
                # a cluster's component holds one per module, each under its own name
                for module in getattr(component, "_cluster_modules", {}).values():
                    module.close()
                component.close()
            self.coordinator.close()
            self.coordinator = None
        if self.is_cluster_owned and self.cluster is not None:
            self.cluster.close()
            self.cluster = None

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
    _raise_if_name_taken(cluster_name)
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


def _raise_if_name_taken(name: str) -> None:
    """Raises if an instrument named ``name`` is open in this process."""
    if Instrument.exist(name):
        raise InstrumentNameTakenError(
            f"An instrument named '{name}' is already open in this process; "
            "pass it to the tuner, or close it, rather than opening another"
        )
