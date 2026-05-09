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
* :data:`DEFAULT_NODE_CLS_MAP` — the canonical lookup from node enum
  member to its concrete :class:`BaseNode` subclass. ``TOF`` does not
  appear because it has no implementation; it exists only as a
  placeholder predecessor in the dependency graph.
* :data:`DEFAULT_NODE_NAME_CLS_MAP` — derived view keyed by lowercase node
  name.
* :data:`DEFAULT_NODE_DAG_EDGES` — the directed edges of the calibration
  DAG. Reading ``(A, B)`` as "B depends on A".
"""

from typing import Mapping, Tuple, Type

from tergite_tuner.lib.base.node import BaseNode
from tergite_tuner.lib.nodes.characterization.all_xy.node import AllXYNode
from tergite_tuner.lib.nodes.characterization.process_tomography.node import (
    ProcessTomographySSRONode,
)
from tergite_tuner.lib.nodes.characterization.purity_benchmarking.node import (
    PurityBenchmarkingNode,
)
from tergite_tuner.lib.nodes.characterization.randomized_benchmarking.node import (
    RandomizedBenchmarkingNode,
)
from tergite_tuner.lib.nodes.characterization.t1.node import T1Node
from tergite_tuner.lib.nodes.characterization.t2.node import T2EchoNode, T2Node
from tergite_tuner.lib.nodes.coupler.cz_calibration.node import CZCalibrationNode
from tergite_tuner.lib.nodes.coupler.cz_chevron.node import CZChevronNode
from tergite_tuner.lib.nodes.coupler.cz_local_phases.node import CZLocalPhasesNode
from tergite_tuner.lib.nodes.coupler.cz_parametrization.node import (
    CZParametrizationNode,
)
from tergite_tuner.lib.nodes.coupler.spectroscopy.node import (
    QubitSpectroscopyVsCurrentNode,
    ResonatorSpectroscopyVsCurrentNode,
)
from tergite_tuner.lib.nodes.coupler.tqg_randomized_benchmarking.node import CZRBNode
from tergite_tuner.lib.nodes.qubit_control.motzoi_parameter.node import (
    MotzoiParameter12Node,
    MotzoiParameterNode,
)
from tergite_tuner.lib.nodes.qubit_control.rabi_oscillations.node import (
    NRabiOscillations12Node,
    NRabiOscillationsNode,
    RabiOscillations12Node,
    RabiOscillationsNode,
)
from tergite_tuner.lib.nodes.qubit_control.ramsey_fringes.node import (
    RamseyFringes12Node,
    RamseyFringesNode,
)
from tergite_tuner.lib.nodes.qubit_control.spectroscopy.node import (
    Qubit01SpectroscopyAmplitudeNode,
    Qubit01SpectroscopyNode,
    Qubit12SpectroscopyNode,
)
from tergite_tuner.lib.nodes.readout.punchout.node import PunchoutNode
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    ResonatorSpectroscopy1Node,
    ResonatorSpectroscopy2Node,
    ResonatorSpectroscopyNode,
)
from tergite_tuner.lib.nodes.readout.ro_amplitude_optimization.node import (
    ROAmplitudeThreeStateOptimizationNode,
    ROAmplitudeTwoStateOptimizationNode,
    ThreeStateDiscriminationNode,
)
from tergite_tuner.lib.nodes.readout.ro_frequency_optimization.node import (
    ROFrequencyThreeStateOptimizationNode,
    ROFrequencyTwoStateOptimizationNode,
)
from tergite_tuner.utils.types.node_enum import NodeEnum

DEFAULT_NODE_CLS_MAP: Mapping[NodeEnum, Type[BaseNode]] = {
    NodeEnum.PUNCHOUT: PunchoutNode,
    NodeEnum.RESONATOR_SPECTROSCOPY: ResonatorSpectroscopyNode,
    NodeEnum.RESONATOR_SPECTROSCOPY_1: ResonatorSpectroscopy1Node,
    NodeEnum.RESONATOR_SPECTROSCOPY_2: ResonatorSpectroscopy2Node,
    NodeEnum.RESONATOR_SPECTROSCOPY_VS_CURRENT: ResonatorSpectroscopyVsCurrentNode,
    NodeEnum.QUBIT_SPECTROSCOPY_VS_CURRENT: QubitSpectroscopyVsCurrentNode,
    NodeEnum.COUPLER_ANTICROSSING: QubitSpectroscopyVsCurrentNode,
    NodeEnum.QUBIT_BRING_UP_SPECTROSCOPY: Qubit01SpectroscopyAmplitudeNode,
    NodeEnum.QUBIT_01_SPECTROSCOPY: Qubit01SpectroscopyNode,
    NodeEnum.QUBIT_12_SPECTROSCOPY: Qubit12SpectroscopyNode,
    NodeEnum.RABI_OSCILLATIONS: RabiOscillationsNode,
    NodeEnum.RABI_OSCILLATIONS_12: RabiOscillations12Node,
    NodeEnum.N_RABI_OSCILLATIONS: NRabiOscillationsNode,
    NodeEnum.N_RABI_12_OSCILLATIONS: NRabiOscillations12Node,
    NodeEnum.RAMSEY_CORRECTION: RamseyFringesNode,
    NodeEnum.RAMSEY_CORRECTION_12: RamseyFringes12Node,
    NodeEnum.MOTZOI_PARAMETER: MotzoiParameterNode,
    NodeEnum.MOTZOI_12_PARAMETER: MotzoiParameter12Node,
    NodeEnum.RO_FREQUENCY_TWO_STATE_OPTIMIZATION: ROFrequencyTwoStateOptimizationNode,
    NodeEnum.RO_FREQUENCY_THREE_STATE_OPTIMIZATION: ROFrequencyThreeStateOptimizationNode,
    NodeEnum.RO_AMPLITUDE_TWO_STATE_OPTIMIZATION: ROAmplitudeTwoStateOptimizationNode,
    NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION: ROAmplitudeThreeStateOptimizationNode,
    NodeEnum.THREE_STATE_DISCRIMINATION: ThreeStateDiscriminationNode,
    NodeEnum.T1: T1Node,
    NodeEnum.T2: T2Node,
    NodeEnum.T2_ECHO: T2EchoNode,
    NodeEnum.ALL_XY: AllXYNode,
    NodeEnum.RANDOMIZED_BENCHMARKING: RandomizedBenchmarkingNode,
    NodeEnum.PURITY_BENCHMARKING: PurityBenchmarkingNode,
    # NodeEnum.PROCESS_TOMOGRAPHY_SSRO: ProcessTomographySSRONode,
    NodeEnum.CZ_PARAMETRIZATION: CZParametrizationNode,
    NodeEnum.CZ_CHEVRON: CZChevronNode,
    NodeEnum.CZ_CALIBRATION: CZCalibrationNode,
    NodeEnum.CZ_LOCAL_PHASES: CZLocalPhasesNode,
    NodeEnum.CZ_RB: CZRBNode,
}
"""The default mapping from :class:`NodeEnum` to its concrete :class:`BaseNode` subclass.

``TOF`` is intentionally absent; it has no implementation and is only
used as a virtual predecessor in :data:`DEFAULT_NODE_DAG_EDGES`.
"""

DEFAULT_NODE_NAME_CLS_MAP: Mapping[str, Type[BaseNode]] = {
    member.value: cls for member, cls in DEFAULT_NODE_CLS_MAP.items()
}
"""Same data as :data:`DEFAULT_NODE_CLS_MAP`, keyed by the lowercase
:class:`NodeEnum` value (``member.value``).

This is the form used everywhere the calibration system needs a string
identifier — redis hash keys, log lines, file paths. The Python class
name (``cls.__name__``) and the class's ``name`` attribute are
internal; they may match the lookup key but the maps are the source
of truth for the canonical string.
"""

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
    # (NodeEnum.N_RABI_12_OSCILLATIONS, NodeEnum.RESONATOR_SPECTROSCOPY_2),
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
    # (NodeEnum.CZ_PARAMETRIZATION, NodeEnum.CZ_CHEVRON),
    (NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION, NodeEnum.CZ_CHEVRON),
    # (NodeEnum.CZ_CHEVRON, NodeEnum.CZ_CALIBRATION),
    (NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION, NodeEnum.CZ_CALIBRATION),
    (NodeEnum.CZ_CALIBRATION, NodeEnum.CZ_LOCAL_PHASES),
    (NodeEnum.CZ_LOCAL_PHASES, NodeEnum.CZ_RB),
    # (
    #     NodeEnum.RO_AMPLITUDE_THREE_STATE_OPTIMIZATION,
    #     NodeEnum.PROCESS_TOMOGRAPHY_SSRO,
    # ),
)
"""The default directed edges of the calibration DAG.

Each tuple ``(parent, child)`` reads as "``child`` depends on ``parent``".
"""

DEFAULT_IGNORED_NODES: Tuple[NodeEnum, ...] = (NodeEnum.TOF, NodeEnum.PUNCHOUT)
"""The nodes that are to be ignored by default"""
