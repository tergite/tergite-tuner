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
import os
import shutil
from os import PathLike
from pathlib import Path
from typing import List, Optional, Tuple, TypeVar, Union, Unpack

import networkx as nx

from tergite_tuner import read_result
from tergite_tuner.backend import Hardware
from tergite_tuner.config.session import SessionContext, SessionOptions
from tergite_tuner.export import CalibrationResults
from tergite_tuner.lib import run
from tergite_tuner.lib.base.node import BaseNode, CouplerNode
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.lib.spec import NodeSpec
from tergite_tuner.lib.utils.graph import get_dependencies_in_topological_order
from tergite_tuner.storage.fs.dataset import create_node_data_path
from tergite_tuner.storage.redis.utils import (
    populate_initial_parameters,
    populate_node_parameters,
    revert_node_parameters,
)
from tergite_tuner.utils.logging import logger
from tergite_tuner.utils.logging.visuals import draw_arrow_chart
from tergite_tuner.utils.types.enums import MeasurementMode, SPIMode
from tergite_tuner.utils.types.node_enum import NodeEnum

T = TypeVar("T")


class NodeManager:
    """
    Manages the initialization and inspection of nodes.
    """

    def __init__(
        self,
        hardware: Optional[Hardware],
        session: "SessionContext",
    ) -> None:
        self.session = session
        self.hardware = hardware

        # a node class the session maps wins over a default spec
        self.nodes = {**DEFAULT_NODE_SPECS, **session.node_cls_map}
        self.node_cls_map = session.node_cls_map
        self.ignored_nodes = session.ignored_nodes
        self.node_dag_edges = session.node_dag_edges

        # Build the calibration DAG from the dependency edges
        # excluding any given nodes of choice
        self.node_graph: "nx.DiGraph" = nx.DiGraph()
        self.node_graph.add_edges_from(self.node_dag_edges)
        for member in self.nodes:
            if member not in self.node_graph:
                self.node_graph.add_node(member)

        populate_initial_parameters(self.session)

    def topo_order(self, target_node: NodeEnum) -> List[NodeEnum]:
        """Return ``target_node``'s ancestors in topological order plus itself."""
        order = get_dependencies_in_topological_order(
            self.node_graph,
            target_node,
            exclude_nodes=self.ignored_nodes,
        )
        return order + [target_node]

    def inspect_node(
        self, node: NodeEnum, *, ignore_spec: bool = False, save_plot: bool = False
    ):
        node_spec = self.nodes[node]
        node_name = node.value
        logger.info(f"Inspecting node {node_name}")
        if isinstance(node_spec, NodeSpec):
            run.mark_not_calibrated(node_spec, self.session)
        else:
            node_spec.reset_qois(self.session, node_name=node_name)

        # Check Redis if node is calibrated
        if ignore_spec:
            is_node_calibrated = False
            logger.info(f"Ignoring calibration status for {node_name}")
        else:
            is_node_calibrated = run.is_in_spec(
                node_name, self._get_elements(node), self.session
            )

        populate_node_parameters(
            node_name,
            is_node_calibrated=is_node_calibrated,
            session=self.session,
        )

        # Log status
        if is_node_calibrated:
            logger.info(f" ✔ Node {node_name} in spec")
        else:
            logger.warning(f"⚑⚑⚑ Calibration required for Node {node_name}")

            logger.info(f"Calibrating node {node_name}")
            data_path = self.session.data_dir
            # avoid creating new logs folders if we are re_analysing or recalibrating
            if (
                self.session.cluster_mode != MeasurementMode.re_analyse
                and not self.session.is_recalibration
            ):
                data_path = create_node_data_path(self.session, node_name=node_name)

            if isinstance(node_spec, NodeSpec):
                run.calibrate(
                    node_spec, self.session, self.hardware, data_path, save_plot
                )
            else:
                calibration_node = self.initialize_node(node)
                calibration_node.calibrate(
                    data_path, self.session.cluster_mode, save_plot
                )

        # if we are in recalibration, we should not revert node parameters
        if not self.session.is_recalibration:
            revert_node_parameters(self.session, node_name=node_name)

    def initialize_node(self, node: NodeEnum) -> BaseNode:
        """Initializes a node and updates it with user-defined samplespace if available."""
        node_cls = self.node_cls_map[node]
        node_obj = node_cls(
            all_qubits=self.session.qubits,
            couplers=self.session.couplers,
            session=self.session,
        )

        # Update node samplespace
        if node_obj.name in self.session.user_samplespace:
            logger.info(f"Using user_samplespace for {node_obj.name}")
            self.update_to_user_samplespace(node_obj, self.session.user_samplespace)

        node_obj.hardware = self.hardware

        # Log initialization details
        logger.info(
            f"Initializing parameters for qubits: {self.session.qubits} "
            f"and couplers: {self.session.couplers}"
        )
        return node_obj

    def _get_elements(self, node: NodeEnum) -> list[str]:
        node_spec = self.nodes[node]
        if isinstance(node_spec, NodeSpec):
            return run.get_elements(node_spec, self.session)
        if issubclass(node_spec, CouplerNode):
            return list(self.session.couplers)
        return list(self.session.qubits)

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
    session: Optional[SessionContext] = None,
    refresh_session: bool = True,
    keep_data_files: bool = True,
    **session_options: Unpack[SessionOptions],
) -> Tuple[SessionContext, CalibrationResults]:
    """Run only one node in the calibration sequence

    Args:
        node: The calibration node to run
        env_file: Optional environment file to use
        session: Optional session context to use
        refresh_session: whether to refresh the session context before running; defaults to True.
        keep_data_files: whether to keep the data files produced during calibration; defaults to True.
        **session_options: Optional session options
            See `<tergite_tuner.config.session.SessionContext>`_ for details.

    Returns:
        the session context and the results from that session
    """
    if session is None:
        session = SessionContext.from_env(env_file, **session_options)
    _tune(
        session,
        node=node,
        refresh_session=refresh_session,
        keep_data_files=keep_data_files,
    )
    return session, read_result(session)


def tune_device(
    env_file: Optional[Union[str, "PathLike[str]"]] = None,
    session: Optional[SessionContext] = None,
    refresh_session: bool = True,
    keep_data_files: bool = True,
    **session_options: Unpack[SessionOptions],
) -> Tuple[SessionContext, CalibrationResults]:
    """Run the full calibration pipeline up to ``target_node``.

    Builds a :class:`SessionContext` from ``env_file`` (and any extra
    ``session_options`` overrides), then walks the dependency DAG up to
    the configured target node, calibrating any nodes that aren't
    already in spec.

    Args:
        env_file: optional path to .env file to load session config from.
        session: optional session context to use
        refresh_session: whether to refresh the session context before running; defaults to True.
        keep_data_files: whether to keep the data files produced during calibration; defaults to True.
        **session_options: optional keyword arguments to override config settings.
            See `<tergite_tuner.config.session.SessionContext>`_ for details.

    Returns:
        the session context and the results from that session
    """
    if session is None:
        session = SessionContext.from_env(env_file, **session_options)
    _tune(session, refresh_session=refresh_session, keep_data_files=keep_data_files)
    results = read_result(session)
    return session, results


def reanalyse(
    env_file: Optional[Union[str, "PathLike[str]"]] = None,
    session: Optional[SessionContext] = None,
    refresh_session: bool = True,
    keep_data_files: bool = True,
    **session_options: Unpack[SessionOptions],
) -> Tuple[SessionContext, CalibrationResults]:
    """Re-run the analysis of ``target_node`` against an already-recorded dataset.

    The cluster mode is forced to :attr:`MeasurementMode.re_analyse`
    internally — callers don't (and can't) override it.

    Args:
        env_file: optional path to .env file to load session config from.
        session: optional session context to use
        refresh_session: whether to refresh the session context before running; defaults to True.
        keep_data_files: whether to keep the data files produced during calibration; defaults to True.
        **session_options: optional keyword arguments to override config settings.
            See `<tergite_tuner.config.session.SessionContext>`_ for details.
    """
    if session is None:
        session = SessionContext.from_env(
            env_file,
            **session_options,
        )

    session.cluster_mode = MeasurementMode.re_analyse
    _reanalyse(
        session, refresh_session=refresh_session, keep_data_files=keep_data_files
    )
    results = read_result(session)
    return session, results


def _tune(
    session: SessionContext,
    node: Optional[NodeEnum] = None,
    refresh_session: bool = True,
    keep_data_files: bool = True,
) -> None:
    """Tunes the device running all nodes till target node if node is None else only that node.

    Args:
        session: the session context to use
        node: the only node to run.
            If not provided, all nodes are run till target node.
        refresh_session: whether to refresh the session before tuning.
        keep_data_files: whether to keep the data files produced during calibration; defaults to True.

    Returns:
        the current affected state of the device after the tuning
    """
    if refresh_session:
        session.refresh_redis_fields_log()
    hardware = Hardware(session)
    node_manager = NodeManager(hardware, session=session)
    qubits = session.qubits
    couplers = session.couplers

    if node:
        topo_order = [node]
    else:
        topo_order = node_manager.topo_order(session.target_node)

    logger.info("Node Manager is initialized")
    logger.info("Starting System Calibration")

    draw_arrow_chart(
        f"Qubits: {len(qubits)}",
        [str(n.value) for n in topo_order],
    )

    if couplers:
        hardware.connect_spi(couplers)
        # no setting initial parking currents during recalibration
        if not session.is_recalibration:
            assert (
                session.spi_mode == SPIMode.real
            ), 'Set spi_mode to "real" in the session.'
            hardware.spi.set_initial_parking_currents(couplers)

    for calibration_node in topo_order:
        node_manager.inspect_node(
            calibration_node,
            ignore_spec=session.ignore_spec,
            save_plot=session.save_plot,
        )
        logger.info(f"{calibration_node.value} node is completed")

    if not keep_data_files and is_safe_path(session.data_dir):
        shutil.rmtree(session.data_dir)
        os.makedirs(session.data_dir)


def _reanalyse(
    session: SessionContext,
    refresh_session: bool = True,
    keep_data_files: bool = True,
) -> None:
    """Internal function implementing the re-analysis logic.

    Args:
        session: the session context to use
        refresh_session: whether to refresh the session before tuning.
        keep_data_files: whether to keep the data files produced during calibration; defaults to True.
    """
    if refresh_session:
        session.refresh_redis_fields_log()

    if session.cluster_mode != MeasurementMode.re_analyse:
        raise ValueError(
            f"Wrong mode for re-analysis: '{session.cluster_mode}', should be: {MeasurementMode.re_analyse}"
        )

    node_manager = NodeManager(None, session=session)

    target_node = session.target_node
    logger.status(f"Analysing '{session.target_node_name}'")
    node_spec = node_manager.nodes[target_node]
    if isinstance(node_spec, NodeSpec):
        run.analyse_node(node_spec, session.data_dir, session, should_save_plot=False)
    else:
        node_manager.initialize_node(target_node).post_process(session.data_dir)
    logger.status("Analysis completed.")

    if not keep_data_files and is_safe_path(session.data_dir):
        shutil.rmtree(session.data_dir)
        os.makedirs(session.data_dir)


def is_safe_path(path_str: PathLike[str]) -> bool:
    """Checks that a path is safe to delete

    Unsafe paths include '/', '/etc', '/var', '/bin', '/usr/'

    Args:
        path_str: the path to check

    Returns:
        True if the path is safe to delete, False otherwise
    """
    path = Path(path_str).resolve()

    # Check against root
    if path == path.parents[-1] if path.parents else path == Path("/"):
        return False

    # Extra safety: Ensure it's not a critical system directory
    forbidden = {Path("/"), Path("/etc"), Path("/usr"), Path("/bin"), Path("/var")}
    if path in forbidden:
        return False

    return True
