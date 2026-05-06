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
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from os import PathLike
from types import MappingProxyType
from typing import FrozenSet, List, Optional, Tuple, Type, Union

import networkx as nx
from qblox_instruments import Cluster
from qblox_instruments.types import ClusterType
from quantify_scheduler.instrument_coordinator import InstrumentCoordinator
from quantify_scheduler.instrument_coordinator.components.qblox import ClusterComponent

from tergite_tuner.config.session import SessionContext
from tergite_tuner.lib.base.node import BaseNode, CouplerNode
from tergite_tuner.lib.nodes import (
    __NODE_DEPENDENCIES__,
    __NODE_ENUM_CLS_MAP__,
)
from tergite_tuner.lib.utils.graph import (
    get_dependencies_in_topological_order,
)
from tergite_tuner.utils.backend.redis_utils import (
    populate_initial_parameters,
    populate_node_parameters,
    populate_quantities_of_interest,
    revert_node_parameters,
)
from tergite_tuner.utils.dto.enums import DataStatus, MeasurementMode, SPIMode
from tergite_tuner.utils.dto.node_enum import NodeEnum
from tergite_tuner.utils.hardware.spi import SpiDAC
from tergite_tuner.utils.io.dataset import create_node_data_path
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.logging.visuals import draw_arrow_chart


class HardwareManager:
    """
    Manages hardware setup, including initializing clusters and instrument coordinators.
    """

    def __init__(self, session: "SessionContext") -> None:
        # Store the configuration settings and initialize the instrument coordinator
        self.session = session
        self.lab_ic: Optional[InstrumentCoordinator] = None
        logger.info("Initializing Hardware")

        # Check if hardware setup is necessary based on measurement mode
        if self.session.cluster_mode == MeasurementMode.re_analyse:
            # In re-analysis mode, measurements are not needed, so no hardware setup is performed
            logger.info(
                "Cluster will not be defined as there is no need to take a measurement in re-analysis mode."
            )
        else:
            # In measurement mode, create the cluster and initialize the instrument coordinator
            self.cluster: "Cluster" = self._create_cluster()
            self.lab_ic = self._create_instrument_coordinator(self.cluster)

    def _create_cluster(self) -> "Cluster":
        """
        Creates and initializes a Cluster object to represent the hardware cluster
        based on the given IP address in the configuration.
        """
        cluster_name = list(self.session.config.cluster.hardware_description.keys())[0]
        cluster: "Cluster"
        if self.session.cluster_mode == MeasurementMode.real:
            # Ensure all previous connections are closed before creating a new cluster instance
            Cluster.close_all()

            try:
                # Create a new cluster instance using the specified cluster name and IP address
                cluster = Cluster(cluster_name, str(self.session.cluster_ip))
            except ConnectionRefusedError:
                msg = "Cluster is disconnected. Maybe it has crushed? Try flick it off and on"
                logger.status("-" * len(msg))
                logger.status(f"{msg}")
                logger.status("-" * len(msg))
                quit()

            # don't reset cluster when doing recalibration
            if not self.session.is_recalibration:
                cluster.reset()  # Reset the cluster to a default state for consistency
                logger.status(
                    f" \n⚠ Resetting Cluster at IP *{str(self.session.cluster_ip)[-3:]}\n"
                )
            return cluster
        else:
            Cluster.close_all()
            dummy_setup = {str(mod): ClusterType.CLUSTER_QCM_RF for mod in range(1, 16)}
            dummy_setup["16"] = ClusterType.CLUSTER_QRM_RF
            dummy_setup["17"] = ClusterType.CLUSTER_QRM_RF
            cluster = Cluster(cluster_name, dummy_cfg=dummy_setup)
            return cluster

    def _create_instrument_coordinator(
        self, clusters: Union["Cluster", List["Cluster"]]
    ) -> "InstrumentCoordinator":
        """
        Sets up an InstrumentCoordinator to manage communication with the cluster
        and configure its modules with specified attenuation settings.
        """
        lab_ic = InstrumentCoordinator("lab_ic")

        # Ensure clusters is a list, even if a single cluster
        clusters = [clusters] if isinstance(clusters, Cluster) else clusters

        # Load attenuation settings for entire system (possibly across multiple clusters)
        output_attenuation_settings = (
            self.session.config.device.get_output_attenuations()
        )
        connectivity = MappingProxyType(
            {
                str(n): frozenset(neigh.keys())
                for n, neigh in self.session.config.cluster.connectivity.graph.adj.items()
            }
        )

        # Configure each cluster in the list and add it to the instrument coordinator
        for cluster in clusters:
            _configure_cluster_settings(
                cluster,
                connectivity=connectivity,
                output_attenuation_settings=output_attenuation_settings,
            )

            # Add the configured cluster to the instrument coordinator and set a timeout
            lab_ic.add_component(ClusterComponent(cluster))
            lab_ic.timeout(self.session.cluster_timeout)

        return lab_ic

    def create_spi(self, couplers) -> SpiDAC:
        return SpiDAC(couplers, self.session)

    def get_instrument_coordinator(self):
        """Access the instrument coordinator for use by other classes."""
        return self.lab_ic


class NodeManager:
    """
    Manages the initialization and inspection of nodes.
    """

    def __init__(
        self,
        lab_ic: "InstrumentCoordinator",
        session: "SessionContext",
        node_enum_cls_map: MappingProxyType[
            NodeEnum, Type[BaseNode]
        ] = __NODE_ENUM_CLS_MAP__,
        ignore_nodes: Tuple[NodeEnum, ...] = (NodeEnum.TOF, NodeEnum.PUNCHOUT),
        node_dependencies: Tuple[
            Tuple[NodeEnum, NodeEnum], ...
        ] = __NODE_DEPENDENCIES__,
    ) -> None:
        self.session = session
        self.lab_ic = lab_ic
        self.spi_manager: Optional[SpiDAC] = None

        self.node_enum_cls_map = node_enum_cls_map
        self.ignore_nodes = ignore_nodes
        self.node_dependencies = node_dependencies

        # Build the calibration DAG from the dependency edges
        # excluding any given nodes of choice
        self.node_graph: "nx.DiGraph" = nx.DiGraph()
        self.node_graph.add_edges_from(self.node_dependencies)
        for member in self.node_enum_cls_map:
            if member not in self.node_graph:
                self.node_graph.add_node(member)

        populate_initial_parameters(
            self.session.qubits,
            self.session.couplers,
            self.session.redis,
            self.session.config,
        )

    def topo_order(self, target_node: NodeEnum) -> List[NodeEnum]:
        """Return ``target_node``'s ancestors in topological order plus itself."""
        order = get_dependencies_in_topological_order(
            self.node_graph,
            target_node,
            exclude_nodes=self.ignore_nodes,
        )
        return order + [target_node]

    def inspect_node(self, node: NodeEnum, *, ignore_spec: bool = False, save_plot: bool = False):
        node_cls = self.node_enum_cls_map[node]
        node_name = node.value
        logger.info(f"Inspecting node {node_name}")

        populate_quantities_of_interest(
            node_cls,
            node_name,
            self.session.qubits,
            self.session.couplers,
            self.session.redis,
        )

        # Check Redis if node is calibrated
        if ignore_spec:
            status = DataStatus.out_of_spec
            logger.info(f"Ignoring calibration status for {node_name}")
        else:
            status = self._check_calibration_status_redis(node)

        populate_node_parameters(
            node_name,
            is_node_calibrated=status == DataStatus.in_spec,
            qubits=self.session.qubits,
            couplers=self.session.couplers,
            redis_connection=self.session.redis,
            config=self.session.config,
        )

        # Log status
        if status == DataStatus.in_spec:
            logger.info(f" ✔ Node {node_name} in spec")
        else:
            logger.warning(f"⚑⚑⚑ Calibration required for Node {node_name}")

            # Initialize node and update samplespace
            calibration_node = self.initialize_node(node)
            logger.info(f"Calibrating node {calibration_node.name}")

            # Determine the data path for calibration
            data_path = (
                self.session.log_dir
                if self.session.cluster_mode == MeasurementMode.re_analyse
                else create_node_data_path(
                    self.session, node_name=calibration_node.name
                )
            )

            # Perform calibration
            calibration_node.calibrate(data_path, self.session.cluster_mode, save_plot)

        # if we are in recalibration, we should not revert node parameters
        if not self.session.is_recalibration:
            revert_node_parameters(
                node_name,
                qubits=self.session.qubits,
                redis_connection=self.session.redis,
                config=self.session.config,
            )

    def initialize_node(self, node: NodeEnum) -> BaseNode:
        """Initializes a node and updates it with user-defined samplespace if available."""
        node_cls = self.node_enum_cls_map[node]
        node_obj = node_cls(
            all_qubits=self.session.qubits,
            couplers=self.session.couplers,
            session=self.session,
        )

        # Update node samplespace
        if node_obj.name in self.session.user_samplespace:
            logger.info(f"Using user_samplespace for {node_obj.name}")
            self.update_to_user_samplespace(node_obj, self.session.user_samplespace)

        # Since the node is responsible for compiling its schedule
        # it needs access to the instrument_coordinator
        node_obj.lab_instr_coordinator = self.lab_ic

        # nodes operating on couplers require access the SPI DACs
        node_obj.spi_manager = self.spi_manager

        # Log initialization details
        logger.info(
            f"Initializing parameters for qubits: {self.session.qubits} "
            f"and couplers: {self.session.couplers}"
        )
        return node_obj

    def _check_calibration_status_redis(self, node: NodeEnum) -> DataStatus:
        """Queries Redis for the calibration status of each qubit or coupler
        associated with ``node``, determining if it is in or out of specification."""
        node_cls = self.node_enum_cls_map[node]
        node_name = node.value
        elements = (
            self.session.couplers
            if issubclass(node_cls, CouplerNode)
            else self.session.qubits
        )
        for element in elements:
            status = self.session.redis.hget(f"cs:{element}", node_name)
            if status == "not_calibrated":
                return DataStatus.out_of_spec
            elif status != "calibrated":
                raise ValueError(f"REDIS error: cannot find cs:{element}", node_name)
        return DataStatus.in_spec

    @staticmethod
    def update_to_user_samplespace(node: BaseNode, user_samplespace: dict) -> None:
        node_user_samplespace = user_samplespace[node.name]
        for settable, element_samplespace in node_user_samplespace.items():
            if settable in node.schedule_samplespace:
                node.schedule_samplespace[settable] = element_samplespace
            elif settable in node.external_samplespace:
                node.external_samplespace[settable] = element_samplespace
            else:
                raise KeyError(f"{settable} not in any samplespace")
        return


def run_node(
    node: NodeEnum,
    env_file: Optional[Union[str, "PathLike[str]"]] = None,
    **session_options,
):
    """Run only one node in the calibration sequence

    Args:
        node: The calibration node to run
        env_file: Optional environment file to use
        **session_options: Optional session options
    """
    session = SessionContext.from_env(env_file, **session_options)
    _tune(session, node=node)


def tune_device(
    env_file: Optional[Union[str, "PathLike[str]"]] = None,
    **session_options,
) -> None:
    """Run the full calibration pipeline up to ``target_node``.

    Builds a :class:`SessionContext` from ``env_file`` (and any extra
    ``session_options`` overrides), then walks the dependency DAG up to
    the configured target node, calibrating any nodes that aren't
    already in spec.

    Args:
        env_file: optional path to .env file to load session config from.
        **session_options: optional keyword arguments to override config settings.
    """
    session = SessionContext.from_env(env_file, **session_options)
    _tune(session)


def re_analyse(
    env_file: Optional[Union[str, "PathLike[str]"]] = None,
    **session_options,
) -> None:
    """Re-run the analysis of ``target_node`` against an already-recorded dataset.

    The cluster mode is forced to :attr:`MeasurementMode.re_analyse`
    internally — callers don't (and can't) override it.

    Args:
        env_file: optional path to .env file to load session config from.
        **session_options: optional keyword arguments to override config settings.
    """
    session_options.pop("cluster_mode", None)
    session = SessionContext.from_env(
        env_file,
        cluster_mode=MeasurementMode.re_analyse,
        **session_options,
    )
    _re_analyse(session)


def _tune(session: SessionContext, node: Optional[NodeEnum] = None) -> None:
    """Internal function implementing the tuning/calibration logic."""
    hardware_manager = HardwareManager(session=session)
    lab_ic = hardware_manager.get_instrument_coordinator()
    node_manager = NodeManager(lab_ic, session=session)
    if node is None:
        topo_order = node_manager.topo_order(session.target_node)
    else:
        topo_order = [node]

    logger.info("Node Manager is initialized")

    logger.info("Starting System Calibration")
    number_of_qubits = len(session.qubits)

    draw_arrow_chart(
        f"Qubits: {number_of_qubits}",
        [str(n.value) for n in topo_order],
    )

    # The node manager provides every node with access to the DACS
    if session.couplers:
        node_manager.spi_manager = hardware_manager.create_spi(session.couplers)
        # no setting initial parking currents during recalibration
        if not session.is_recalibration:
            assert session.spi_mode == SPIMode.real, 'Set spi_mode to "real" in the session.'
            node_manager.spi_manager.set_initial_parking_currents(session.couplers)

    for calibration_node in topo_order:
        node_manager.inspect_node(
            calibration_node, 
            ignore_spec=session.ignore_spec,
            save_plot=session.save_plot
            )
        logger.info(f"{calibration_node.value} node is completed")


def _re_analyse(session: SessionContext) -> None:
    """Internal function implementing the re-analysis logic."""
    if session.cluster_mode != MeasurementMode.re_analyse:
        raise ValueError(
            f"Wrong mode for re-analysis: '{session.cluster_mode}', should be: {MeasurementMode.re_analyse}"
        )

    hardware_manager = HardwareManager(session=session)
    lab_ic = hardware_manager.get_instrument_coordinator()
    node_manager = NodeManager(lab_ic, session=session)

    target_node = session.target_node
    node = node_manager.initialize_node(target_node)
    logger.status(
        f"Analysing '{session.target_node_name}' with {node.analysis_cls.__name__}"
    )
    node.post_process(session.log_dir)
    logger.status("Analysis completed.")


# intermediary function in the call stack in case we want to set other cluster settings
def _configure_cluster_settings(
    cluster: Cluster,
    *,
    connectivity: MappingProxyType[str, FrozenSet[str]],
    output_attenuation_settings: MappingProxyType[str, MappingProxyType[str, int]],
):
    _set_output_attenuations(cluster, connectivity, output_attenuation_settings)


def _set_output_attenuations(cluster, connectivity, settings):
    """
    Sets the output attenuations for modules in the given cluster based on the provided settings.

    This function iterates over couplers, resonators, and qubits, finds the corresponding output
    ports from the connectivity map, and applies attenuation settings to the correct output
    channels (complex_output_0 or complex_output_1) for modules that are part of the cluster.

    Args:
        cluster: Cluster object to configure
        connectivity: A mapping that relates device names (with port suffixes) to their physical port paths.
        settings: A dictionary specifying attenuation values for 'coupler', 'resonator', and 'qubit' devices.
    """
    cluster_modules = cluster.get_connected_modules()
    module_names = frozenset(mod.name for _, mod in cluster_modules.items())

    # read the device configuration (device_config.toml) settings for attenuation
    # entire file, all couplers, all qubits, all resonators
    for device_type, quantify_port_suffix in zip(
        ["coupler", "resonator", "qubit"], [":fl", ":res", ":mw"]
    ):
        for name, att in settings[device_type].items():
            quantify_port = name + quantify_port_suffix

            if quantify_port not in connectivity.keys():
                logger.warning(
                    f"Skipping setting attenuation for '{quantify_port}', as it is "
                    "not in the connectivity graph of the cluster_config.json."
                )
                continue

            ports = connectivity[quantify_port]
            assert len(ports) == 1
            port_str = next(iter(ports))

            # e.g. "cluster.module1.complex_output_0"
            cl, mod, port = tuple(port_str.split(sep="."))

            # inputs can also be specified in the connectivity graph, although such
            # mappings are seldomly used in transmon systems, so just do a simple
            # check here that we are actually configuring an output
            assert "output" in port, (name + quantify_port_suffix, port_str)

            # if the cluster that this qubit is mapped to in the connectivity
            # is not the same as the cluster to be configured, then simply skip
            if cl != cluster.name:
                continue

            # skip if the module is not connected
            if "_".join((cl, mod)) not in module_names:
                continue

            # otherwise, use the dedicated QCoDeS function
            # to set the attenuation
            module_obj = getattr(cluster, mod)

            if port == "complex_output_0":
                module_obj.out0_att(att)
            elif port == "complex_output_1":
                module_obj.out1_att(att)
            else:
                raise KeyError(f"Failed to set attenuation for port: {port_str}")

            logger.debug(f"Applied {att}dB attenuation on {port_str}")
    logger.info("Attenuations are set")
