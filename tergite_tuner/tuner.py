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
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.lib.utils.graph import get_dependencies_in_topological_order
from tergite_tuner.storage.fs.dataset import get_unique_data_path
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
        run_path: Path | None = None,
    ) -> None:
        self.session = session
        self.hardware = hardware
        # the run's own folder in data_dir, the only one keep_data_files=False deletes
        self.run_path = run_path or session.data_dir

        self.nodes = {**DEFAULT_NODE_SPECS, **session.node_specs}
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
        elements = run.get_elements(node_spec, self.session)
        logger.info(f"Inspecting node {node_name}")
        run.mark_not_calibrated(node_name, elements, self.session)

        # Check Redis if node is calibrated
        if ignore_spec:
            is_node_calibrated = False
            logger.info(f"Ignoring calibration status for {node_name}")
        else:
            is_node_calibrated = run.is_in_spec(node_name, elements, self.session)

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
            # re-analysis reads the datasets already in data_dir; a recalibration
            # writes into the run's folder, so repeated ones need no folder per node
            if self.session.cluster_mode == MeasurementMode.re_analyse:
                data_path = self.session.data_dir
            elif self.session.is_recalibration:
                data_path = self.run_path
            else:
                data_path = get_unique_data_path(self.run_path, node_name)

            run.calibrate(node_spec, self.session, self.hardware, data_path, save_plot)

        # if we are in recalibration, we should not revert node parameters
        if not self.session.is_recalibration:
            revert_node_parameters(self.session, node_name=node_name)


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
    **session_options: Unpack[SessionOptions],
) -> Tuple[SessionContext, CalibrationResults]:
    """Re-run the analysis of ``target_node`` against an already-recorded dataset.

    The cluster mode is forced to :attr:`MeasurementMode.re_analyse`
    internally — callers don't (and can't) override it.

    Args:
        env_file: optional path to .env file to load session config from.
        session: optional session context to use
        refresh_session: whether to refresh the session context before running; defaults to True.
        **session_options: optional keyword arguments to override config settings.
            See `<tergite_tuner.config.session.SessionContext>`_ for details.
    """
    if session is None:
        session = SessionContext.from_env(
            env_file,
            **session_options,
        )

    session.cluster_mode = MeasurementMode.re_analyse
    _reanalyse(session, refresh_session=refresh_session)
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
    run_path = get_unique_data_path(session.data_dir, "run")
    node_manager = NodeManager(hardware, session=session, run_path=run_path)
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

    if not keep_data_files and run_path.exists():
        shutil.rmtree(run_path)


def _reanalyse(
    session: SessionContext,
    refresh_session: bool = True,
) -> None:
    """Internal function implementing the re-analysis logic.

    Args:
        session: the session context to use
        refresh_session: whether to refresh the session before tuning.
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
    run.analyse_node(
        node_manager.nodes[target_node],
        session.data_dir,
        session,
        should_save_plot=False,
    )
    logger.status("Analysis completed.")
