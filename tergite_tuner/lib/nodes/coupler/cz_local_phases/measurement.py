# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2024
# (C) Copyright Amr Osman 2024
# (C) Copyright Chalmers Next Labs 2024, 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

import numpy as np

from tergite_tuner.backend import (
    X90,
    ExtendedCompositeSquareEdge,
    ExtendedTransmon,
    IdlePulse,
    Reset,
    Rxy,
    Schedule,
    SoftSquarePulse,
)
from tergite_tuner.lib.base.measurement import BaseMeasurement
from tergite_tuner.lib.utils.schedules import (
    add_cz_clock,
    add_pair_measurement,
    get_repeated_schedule,
)


class CZLocalPhasesMeasurement(BaseMeasurement):
    def __init__(
        self,
        transmons: dict[str, ExtendedTransmon],
        couplers: dict[str, ExtendedCompositeSquareEdge],
    ):
        super().__init__(transmons)
        self.transmons = transmons
        self.couplers = couplers

    def ro_shot(
        self,
        local_phases: dict[str, np.ndarray],
        swap: dict[str, np.ndarray],
        cz_gate_modes: dict[str, np.ndarray],
        coupler_dict: dict[str, dict],
    ) -> Schedule:
        shot = Schedule("cz_local_phase_shot", repetitions=1)
        qubits = self.transmons.keys()
        root_relaxation = shot.add(IdlePulse(4e-9))
        for coupler in self.couplers:
            control_qubit = coupler_dict[coupler]["control_qubit"]
            target_qubit = coupler_dict[coupler]["target_qubit"]
            gate_modes = cz_gate_modes[coupler]
            add_cz_clock(shot, coupler, self.couplers[coupler].clock_freqs.cz_freq())
            # To enforce parallelism we refer to the root relaxation
            shot.add(Reset(*qubits), ref_op=root_relaxation)
            for outer_index, swap_mode in enumerate(swap[coupler]):
                if swap_mode:
                    control_qubit, target_qubit = target_qubit, control_qubit
                phases = local_phases[target_qubit]
                for intermediate_index, gate_mode in enumerate(gate_modes):
                    for inner_index, local_phase in enumerate(phases):
                        self._add_point(
                            shot,
                            coupler,
                            (control_qubit, target_qubit),
                            (gate_mode, local_phase),
                            (outer_index * len(gate_modes) + intermediate_index)
                            * len(phases)
                            + inner_index,
                        )
        return shot

    def _add_point(
        self,
        shot: Schedule,
        coupler: str,
        pair: tuple[str, str],
        point: tuple[bool, float],
        acq_index: int,
    ) -> None:
        """A Ramsey on the target around ``coupler``'s CZ pulse, or an idle as long if the gate is off."""
        control_qubit, target_qubit = pair
        is_gate_on, local_phase = point
        edge = self.couplers[coupler]
        cz_duration = edge.cz.square_duration()
        start = shot.add(IdlePulse(4e-9))
        shot.add(X90(target_qubit), ref_op=start)
        shot.add(IdlePulse(4e-9))
        if is_gate_on:
            shot.add(
                SoftSquarePulse(
                    duration=cz_duration,
                    amp=edge.cz.square_amp(),
                    port=f"{coupler}:fl",
                    clock=f"{coupler}.cz",
                ),
            )
        else:
            shot.add(IdlePulse(cz_duration))
        shot.add(IdlePulse(4e-9))
        final = shot.add(Rxy(theta=90, phi=local_phase, qubit=target_qubit))
        add_pair_measurement(shot, pair, acq_index, final)
        shot.add(Reset(control_qubit, target_qubit))

    def schedule_function(
        self,
        local_phases: dict[str, np.ndarray],
        swap: dict[str, np.ndarray],
        gate_modes: dict[str, np.ndarray],
        loop_repetitions: int,
        coupler_dict: dict[str, dict],
        repetitions: int = 1,
    ) -> Schedule:

        local_phase_shot = self.ro_shot(
            local_phases=local_phases,
            swap=swap,
            cz_gate_modes=gate_modes,
            coupler_dict=coupler_dict,
        )

        return get_repeated_schedule(
            "CZ_local_phases", local_phase_shot, loop_repetitions, 16e-9, repetitions
        )
