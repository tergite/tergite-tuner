# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Joel Sandås 2024
# (C) Copyright Michele Faucci Giannelli 2024
# (C) Copyright Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""DAG utilities for the calibration supervisor.

These helpers operate on any node identifier — qubit name, ``NodeEnum``
member, etc. — via a generic ``_T`` type variable. Concrete graphs,
``exclude_nodes`` sets, and ``from_nodes`` ranges are constructed by
the caller (typically the supervisor's :class:`NodeManager`).
"""

from typing import Iterable, List, TypeVar

import networkx as nx

_T = TypeVar("_T")


def get_dependencies_in_topological_order(
    graph: "nx.DiGraph",
    target_node: _T,
    exclude_nodes: Iterable[_T],
) -> List[_T]:
    """The ancestors of ``target_node`` but ``exclude_nodes``, each after its own ancestors.

    Ancestors on the same level come in no set order.

    Args:
        graph: the dependency graph, an edge from each node to the nodes that need it.
        target_node: the node whose dependencies to list.
        exclude_nodes: nodes to leave out; their own dependencies are still listed.

    Returns:
        The dependencies, in an order they can run in; ``target_node`` is not among them.

    Raises:
        RuntimeError: if there is no such order, as for a cycle.
    """
    exclude_set = set(exclude_nodes)

    def filter_ancestors(graph_, target_, exclude_):
        return set(nx.ancestors(graph_, target_)).difference(exclude_)

    # All nodes that will appear in the final result, but not yet ordered
    nodes_to_visit = filter_ancestors(graph, target_node, exclude_set)

    # Pre-compute per-node ancestor sets so the inner loop is cheap
    ancestors = {
        node: filter_ancestors(graph, node, exclude_set) for node in nodes_to_visit
    }

    topological_order: List[_T] = []
    exit_condition = len(nodes_to_visit)
    while nodes_to_visit:
        to_visit_copy = nodes_to_visit.copy()

        for node in nodes_to_visit:
            if ancestors[node].issubset(set(topological_order)):
                topological_order.append(node)
                to_visit_copy.remove(node)

        nodes_to_visit = to_visit_copy

        exit_condition -= 1
        if exit_condition < 0:
            raise RuntimeError(
                f"Dependencies for node {target_node} in the given graph cannot be "
                f"found. Please check the dependency graph."
            )

    return topological_order
