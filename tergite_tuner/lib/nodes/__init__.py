# This code is part of Tergite
#
# (C) Chalmers Next Labs 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Entry point for the nodes module.

This module exposes:

* :class:`NodeEnum` (re-exported from
  :mod:`tergite_tuner.utils.dto.node_enum`) — every calibration
  node referenced anywhere in the pipeline. Names are kept in sync with
  :data:`DEFAULT_NODE_DAG_EDGES` below; if a node never appears in the
  dependency edges, it should not be in the enum.
* :data:`DEFAULT_NODE_SPECS` — each node enum member's :class:`NodeSpec`.
  ``TOF`` does not appear because it has no implementation; it exists only
  as a placeholder predecessor in the dependency graph.
* :data:`DEFAULT_NODE_DAG_EDGES` — the directed edges of the calibration
  DAG. Reading ``(A, B)`` as "B depends on A".
"""

from typing import Mapping, Tuple

from tergite_tuner.lib.nodes.characterization.all_xy.node import (
    ALL_XY_SPECS,
)
from tergite_tuner.lib.nodes.characterization.purity_benchmarking.node import (
    PURITY_BENCHMARKING_SPECS,
)
from tergite_tuner.lib.nodes.characterization.randomized_benchmarking.node import (
    RANDOMIZED_BENCHMARKING_SPECS,
)
from tergite_tuner.lib.nodes.characterization.t1.node import (
    T1_SPECS,
)
from tergite_tuner.lib.nodes.characterization.t2.node import (
    T2_SPECS,
)
from tergite_tuner.lib.nodes.coupler.cz_calibration.node import (
    CZ_CALIBRATION_SPECS,
)
from tergite_tuner.lib.nodes.coupler.cz_chevron.node import (
    CZ_CHEVRON_SPECS,
)
from tergite_tuner.lib.nodes.coupler.cz_local_phases.node import (
    CZ_LOCAL_PHASES_SPECS,
)
from tergite_tuner.lib.nodes.coupler.cz_parametrization.node import (
    CZ_PARAMETRIZATION_SPECS,
)
from tergite_tuner.lib.nodes.coupler.spectroscopy.node import (
    COUPLER_SPECTROSCOPY_SPECS,
)
from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.node import (
    CZ_RB_SPECS,
)
from tergite_tuner.lib.nodes.qubit_control.motzoi_parameter.node import (
    MOTZOI_SPECS,
)
from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.node import (
    N_RABI_SPECS,
    RABI_SPECS,
)
from tergite_tuner.lib.nodes.qubit_control.ramsey_fringes.node import (
    RAMSEY_SPECS,
)
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.node import (
    QUBIT_SPECTROSCOPY_SPECS,
)
from tergite_tuner.lib.nodes.readout.punchout.node import (
    PUNCHOUT_SPECS,
)
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    RESONATOR_SPECTROSCOPY_SPECS,
)
from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.node import (
    RO_AMPLITUDE_SPECS,
)
from tergite_tuner.lib.nodes.readout.ro_frequency_optimization.node import (
    RO_FREQUENCY_SPECS,
)
from tergite_tuner.lib.spec import NodeSpec
from tergite_tuner.utils.types.node_enum import NodeEnum

DEFAULT_NODE_SPECS: Mapping[NodeEnum, NodeSpec] = {
    **RESONATOR_SPECTROSCOPY_SPECS,
    **RABI_SPECS,
    **N_RABI_SPECS,
    **RAMSEY_SPECS,
    **MOTZOI_SPECS,
    **QUBIT_SPECTROSCOPY_SPECS,
    **PUNCHOUT_SPECS,
    **RO_FREQUENCY_SPECS,
    **RO_AMPLITUDE_SPECS,
    **T1_SPECS,
    **T2_SPECS,
    **ALL_XY_SPECS,
    **RANDOMIZED_BENCHMARKING_SPECS,
    **PURITY_BENCHMARKING_SPECS,
    **COUPLER_SPECTROSCOPY_SPECS,
    **CZ_LOCAL_PHASES_SPECS,
    **CZ_RB_SPECS,
    **CZ_CHEVRON_SPECS,
    **CZ_CALIBRATION_SPECS,
    **CZ_PARAMETRIZATION_SPECS,
}

DEFAULT_NODE_DAG_EDGES: Tuple[Tuple[NodeEnum, NodeEnum], ...] = (
    (NodeEnum.TOF, NodeEnum.RESONATOR_SPECTROSCOPY),
    (NodeEnum.RESONATOR_SPECTROSCOPY, NodeEnum.RESONATOR_SPECTROSCOPY_VS_CURRENT),
    (NodeEnum.QUBIT_01_SPECTROSCOPY, NodeEnum.COUPLER_ANTICROSSING),
    (NodeEnum.RESONATOR_SPECTROSCOPY, NodeEnum.QUBIT_BRING_UP_SPECTROSCOPY),
    (NodeEnum.RESONATOR_SPECTROSCOPY, NodeEnum.QUBIT_01_SPECTROSCOPY),
    (
        NodeEnum.RESONATOR_SPECTROSCOPY_VS_CURRENT,
        NodeEnum.QUBIT_SPECTROSCOPY_VS_CURRENT,
    ),
    (NodeEnum.QUBIT_01_SPECTROSCOPY, NodeEnum.RABI_OSCILLATIONS),
    (NodeEnum.RABI_OSCILLATIONS, NodeEnum.RAMSEY_CORRECTION),
    (NodeEnum.RAMSEY_CORRECTION, NodeEnum.T1),
    (NodeEnum.RAMSEY_CORRECTION, NodeEnum.MOTZOI_PARAMETER),
    (NodeEnum.MOTZOI_PARAMETER, NodeEnum.N_RABI_OSCILLATIONS),
    (NodeEnum.N_RABI_OSCILLATIONS, NodeEnum.RESONATOR_SPECTROSCOPY_1),
    (
        NodeEnum.RESONATOR_SPECTROSCOPY_1,
        NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
    ),
    (
        NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION,
    ),
    (NodeEnum.N_RABI_OSCILLATIONS, NodeEnum.ALL_XY),
    (NodeEnum.RESONATOR_SPECTROSCOPY_1, NodeEnum.QUBIT_12_SPECTROSCOPY),
    (NodeEnum.QUBIT_12_SPECTROSCOPY, NodeEnum.RABI_OSCILLATIONS_12),
    (NodeEnum.RABI_OSCILLATIONS_12, NodeEnum.RAMSEY_CORRECTION_12),
    (NodeEnum.RAMSEY_CORRECTION_12, NodeEnum.MOTZOI_12_PARAMETER),
    (NodeEnum.MOTZOI_12_PARAMETER, NodeEnum.N_RABI_12_OSCILLATIONS),
    (NodeEnum.MOTZOI_12_PARAMETER, NodeEnum.RESONATOR_SPECTROSCOPY_2),
    (
        NodeEnum.RESONATOR_SPECTROSCOPY_2,
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
    ),
    (
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
    ),
    (
        NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION,
        NodeEnum.THREE_STATE_DISCRIMINATION,
    ),
    (
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
        NodeEnum.CZ_PARAMETRIZATION,
    ),
    (NodeEnum.T1, NodeEnum.T2),
    (NodeEnum.T2, NodeEnum.T2_ECHO),
    (
        NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
        NodeEnum.RANDOMIZED_BENCHMARKING,
    ),
    (NodeEnum.T2_ECHO, NodeEnum.PURITY_BENCHMARKING),
    (NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION, NodeEnum.CZ_CHEVRON),
    (NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION, NodeEnum.CZ_CALIBRATION),
    (NodeEnum.CZ_CALIBRATION, NodeEnum.CZ_LOCAL_PHASES),
    (NodeEnum.CZ_LOCAL_PHASES, NodeEnum.CZ_RB),
)
"""The default directed edges of the calibration DAG.

Each tuple ``(parent, child)`` reads as "``child`` depends on ``parent``".
"""

DEFAULT_IGNORED_NODES: Tuple[NodeEnum, ...] = (NodeEnum.TOF, NodeEnum.PUNCHOUT)
"""The nodes that are to be ignored by default"""
