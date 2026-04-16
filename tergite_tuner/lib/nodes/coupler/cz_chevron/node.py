# This code is part of Tergite
#
# (C) Copyright Eleftherios Moschandreou 2023, 2024, 2025, 2026
# (C) Copyright Liangyu Chen 2023, 2024
# (C) Copyright Amr Osman, 2024
# (C) Chalmers Next Labs 2025, 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

from typing import TYPE_CHECKING, Literal

import numpy as np
import xarray as xr

from tergite_tuner.lib.base.node import CouplerNode
from tergite_tuner.lib.nodes.coupler.cz_chevron.analysis import CZChevronAnalysis
from tergite_tuner.lib.nodes.coupler.cz_chevron.measurement import CZChevronMeasurement
from tergite_tuner.lib.nodes.schedule_node import OuterScheduleNode

if TYPE_CHECKING:
    from tergite_tuner.config.session import SessionContext


class CZChevronNode(CouplerNode):
    name: str = "cz_chevron"
    measurement_cls = CZChevronMeasurement
    analysis_cls = CZChevronAnalysis
    measurement_type_cls = OuterScheduleNode
    coupler_qois = ["cz_working_frequencies", "cz_working_durations_in_ns"]

    def __init__(
        self,
        couplers: list[str],
        session: "SessionContext",
        **schedule_keywords,
    ):
        super().__init__(couplers, session, **schedule_keywords)

        self.couplers = couplers

        self.coupled_qubits = self.get_coupled_qubits()
        self.all_qubits = self.coupled_qubits
        self.validate()

        self.schedule_keywords["loop_repetitions"] = 512 // 4
        self.loops = self.schedule_keywords["loop_repetitions"]
        phase_paths = self.all_phase_paths()
        self.analysis_keywords = {
            coupler: {
                "phase_path": phase_paths[coupler],
                "number_of_working_points": 15,
            }
            for coupler in self.couplers
        }

        self.outer_schedule_samplespace = {
            "cz_pulse_frequencies": {
                coupler: np.linspace(-3.0e6, 2.0e6, 25)
                + self.known_cz_frequency(coupler)
                for coupler in self.couplers
            }
        }

        self.schedule_samplespace = {
            "cz_pulse_durations": {
                coupler: np.arange(24e-9, self.max_duration(coupler), 8e-9)
                for coupler in self.couplers
            },
        }

    def known_cz_frequency(self, coupler: str):
        known_cz_frequency = float(
            self.session.redis.hget(f"couplers:{coupler}", "cz_pulse_frequency")
        )
        return known_cz_frequency

    def max_duration(self, coupler: str):
        half_duration = float(
            self.session.redis.hget(f"couplers:{coupler}", "cz_half_duration")
        )
        max_duration = 2 * half_duration
        max_duration_in_ns = round(max_duration / 1e-9)
        # ensure multiple of 4ns, and add some slack:
        max_duration_in_ns = (max_duration_in_ns // 4) * 4 + 40
        return max_duration_in_ns * 1e-9

    def all_phase_paths(self) -> dict[str, Literal["via_02", "via_20"]]:
        phase_paths = {}
        for coupler in self.couplers:
            path = self.session.redis.hget(f"couplers:{coupler}", "cz_phase_path")
            phase_paths[coupler] = path
        return phase_paths

    def initial_operation(self):
        # during recalibration, initial parking currents should not be set
        if not self.session.is_recalibration:
            self.spi_manager.set_initial_parking_currents(self.couplers)

    def generate_dummy_dataset(self):
        dataset = xr.Dataset()
        for index, coupler in enumerate(self.couplers):
            number_of_durations = len(
                self.schedule_samplespace["cz_pulse_durations"][coupler]
            )
            number_of_iq_samples = number_of_durations * self.loops
            real_part = np.random.uniform(-1, 1, number_of_iq_samples)
            imag_part = np.random.uniform(-1, 1, number_of_iq_samples)
            complex_points = real_part + 1j * imag_part
            data_array = xr.DataArray(complex_points)

            dataset[2 * index] = data_array
            dataset[2 * index + 1] = data_array
        return dataset
