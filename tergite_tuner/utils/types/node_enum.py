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

"""The :class:`NodeEnum` lives in its own module to avoid the import cycle
that would otherwise form between :mod:`tergite_tuner.config.session` (which
references :class:`NodeEnum` for field validation) and
:mod:`tergite_tuner.lib.nodes` (which imports every concrete
node class to populate :data:`DEFAULT_NODE_CLS_MAP`).

:mod:`tergite_tuner.lib.nodes` re-exports :class:`NodeEnum`
for backwards compatibility."""

from enum import Enum


class NodeEnum(str, Enum):
    """An enumeration of all calibration nodes.

    Each member's value is the lowercase canonical string name used
    everywhere external — redis hash fields, log lines, env-var
    payloads, exported JSON. Subclassing :class:`str` means that:

    * ``NodeEnum.T1.value == "t1"`` (and ``str(NodeEnum.T1) == "t1"``
      after :meth:`__str__`).
    * ``NodeEnum.T1 == "t1"`` evaluates true, so existing string-based
      comparisons keep working during the migration.
    * Pydantic / ``json.dumps`` serialise members directly to their
      string form without extra coercion.
    """

    TOF = "tof"
    PUNCHOUT = "punchout"
    RESONATOR_SPECTROSCOPY = "resonator_spectroscopy"
    RESONATOR_SPECTROSCOPY_1 = "resonator_spectroscopy_1"
    RESONATOR_SPECTROSCOPY_2 = "resonator_spectroscopy_2"
    RESONATOR_SPECTROSCOPY_VS_CURRENT = "resonator_spectroscopy_vs_current"
    QUBIT_SPECTROSCOPY_VS_CURRENT = "qubit_spectroscopy_vs_current"
    COUPLER_ANTICROSSING = "coupler_anticrossing"
    QUBIT_BRING_UP_SPECTROSCOPY = "qubit_bring_up_spectroscopy"
    QUBIT_01_SPECTROSCOPY = "qubit_01_spectroscopy"
    QUBIT_12_SPECTROSCOPY = "qubit_12_spectroscopy"
    RABI_OSCILLATIONS = "rabi_oscillations"
    RABI_OSCILLATIONS_12 = "rabi_oscillations_12"
    N_RABI_OSCILLATIONS = "n_rabi_oscillations"
    N_RABI_12_OSCILLATIONS = "n_rabi_12_oscillations"
    RAMSEY_CORRECTION = "ramsey_correction"
    RAMSEY_CORRECTION_12 = "ramsey_correction_12"
    MOTZOI_PARAMETER = "motzoi_parameter"
    MOTZOI_12_PARAMETER = "motzoi_12_parameter"
    RO_FREQUENCY_TWO_STATE_OPTIMIZATION = "ro_frequency_two_state_optimization"
    RO_FREQUENCY_THREE_STATE_OPTIMIZATION = "ro_frequency_three_state_optimization"
    RO_AMPLITUDE_TWO_STATE_OPTIMIZATION = "ro_amplitude_two_state_optimization"
    RO_AMPLITUDE_THREE_STATE_OPTIMIZATION = "ro_amplitude_three_state_optimization"
    THREE_STATE_DISCRIMINATION = "three_state_discrimination"
    T1 = "t1"
    T2 = "t2"
    T2_ECHO = "t2_echo"
    ALL_XY = "all_xy"
    RANDOMIZED_BENCHMARKING = "randomized_benchmarking"
    PURITY_BENCHMARKING = "purity_benchmarking"
    PROCESS_TOMOGRAPHY_SSRO = "process_tomography_ssro"
    CZ_PARAMETRIZATION = "cz_parametrization"
    CZ_CHEVRON = "cz_chevron"
    CZ_CALIBRATION = "cz_calibration"
    CZ_LOCAL_PHASES = "cz_local_phases"
    CZ_RB = "cz_rb"

    def __str__(self) -> str:
        # Override the default ``Enum.__str__`` ("NodeEnum.T1") so that
        # logging / f-strings emit the canonical name ("t1") directly.
        return self.value
